#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path


def _norm_text(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("'", "")
    s = s.replace("`", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _ocr_fold_text(s: str) -> str:
    # One-way fold for OCR-noise tolerant matching (not reversible).
    s = (s or "").lower()
    fold_map = str.maketrans(
        {
            "0": "o",
            "1": "l",
            "i": "l",
            "|": "l",
            "5": "s",
            "$": "s",
            "8": "b",
        }
    )
    s = s.translate(fold_map)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _alias_candidates(affix_name: str) -> list[tuple[str, str]]:
    """Return (alias_kind, alias_text) variants for affix matching."""
    name = (affix_name or "").strip()
    if not name:
        return []
    out: list[tuple[str, str]] = [("canonical", name)]

    # Common punctuation/spacing variants seen in OCR/jsp text.
    dehyphen = name.replace("-", " ")
    if dehyphen != name:
        out.append(("dehyphen", dehyphen))
    deapost = name.replace("'", "")
    if deapost != name:
        out.append(("deapostrophe", deapost))
    compact = re.sub(r"[\s'\-]+", "", name)
    if compact and compact.lower() != name.lower():
        out.append(("compact", compact))

    # Token-level shortened variant for two-word+ affixes: keep meaningful tokens.
    toks = [t for t in re.split(r"[^A-Za-z0-9]+", name) if t]
    if len(toks) >= 2:
        out.append(("spaced", " ".join(toks)))

    # de-duplicate while preserving order (case-insensitive)
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for kind, alias in out:
        key = alias.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append((kind, alias.strip()))
    return deduped


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog_affix_lexicon (
          id INTEGER PRIMARY KEY,
          affix_id TEXT NOT NULL,
          affix_kind TEXT NOT NULL,
          affix_name TEXT NOT NULL,
          alias_kind TEXT NOT NULL,          -- canonical|compact|dehyphen|...
          alias_text TEXT NOT NULL,
          norm_key TEXT NOT NULL,            -- lowercase normalized (spacing/punct folded)
          ocr_norm_key TEXT NOT NULL,        -- OCR-tolerant folded form
          token_count INTEGER NOT NULL DEFAULT 0,
          mods_json TEXT,
          mod_codes_json TEXT,               -- ["ac%","dmg%"]
          itypes_json TEXT,
          etypes_json TEXT,
          enabled INTEGER NOT NULL DEFAULT 1,
          UNIQUE(affix_id, alias_kind, alias_text)
        );
        CREATE INDEX IF NOT EXISTS idx_affix_lex_norm ON catalog_affix_lexicon(norm_key);
        CREATE INDEX IF NOT EXISTS idx_affix_lex_ocr_norm ON catalog_affix_lexicon(ocr_norm_key);
        CREATE INDEX IF NOT EXISTS idx_affix_lex_affix ON catalog_affix_lexicon(affix_id);
        """
    )

    # Lightweight migrations if table existed from an older revision.
    for col_sql in (
        "ALTER TABLE catalog_affix_lexicon ADD COLUMN mod_codes_json TEXT",
        "ALTER TABLE catalog_affix_lexicon ADD COLUMN itypes_json TEXT",
        "ALTER TABLE catalog_affix_lexicon ADD COLUMN etypes_json TEXT",
        "ALTER TABLE catalog_affix_lexicon ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1",
    ):
        try:
            conn.execute(col_sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _extract_mod_codes(mods_json_text: str | None) -> list[str]:
    if not mods_json_text:
        return []
    try:
        mods = json.loads(mods_json_text)
    except json.JSONDecodeError:
        return []
    if not isinstance(mods, list):
        return []
    out: list[str] = []
    for m in mods:
        if not isinstance(m, dict):
            continue
        code = str(m.get("code") or "").strip()
        if code and code not in out:
            out.append(code)
    return out


def build_lexicon(conn: sqlite3.Connection, *, replace: bool = True) -> dict[str, int]:
    ensure_schema(conn)
    if replace:
        conn.execute("DELETE FROM catalog_affix_lexicon")
        conn.commit()

    src_rows = conn.execute(
        """
        SELECT affix_id, affix_kind, affix_name, mods_json, itypes_json, etypes_json, enabled
        FROM catalog_affixes
        WHERE COALESCE(enabled, 1) = 1
        ORDER BY affix_kind, affix_name
        """
    ).fetchall()

    inserted = 0
    by_kind: defaultdict[str, int] = defaultdict(int)
    for r in src_rows:
        affix_id = str(r["affix_id"])
        affix_kind = str(r["affix_kind"])
        affix_name = str(r["affix_name"])
        mods_json = r["mods_json"]
        mod_codes = _extract_mod_codes(mods_json)
        itypes_json = r["itypes_json"]
        etypes_json = r["etypes_json"]
        enabled = int(r["enabled"] or 1)
        for alias_kind, alias_text in _alias_candidates(affix_name):
            norm_key = _norm_text(alias_text)
            ocr_norm_key = _ocr_fold_text(alias_text)
            token_count = len(norm_key.split()) if norm_key else 0
            conn.execute(
                """
                INSERT OR REPLACE INTO catalog_affix_lexicon(
                  affix_id, affix_kind, affix_name, alias_kind, alias_text,
                  norm_key, ocr_norm_key, token_count, mods_json, mod_codes_json,
                  itypes_json, etypes_json, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    affix_id,
                    affix_kind,
                    affix_name,
                    alias_kind,
                    alias_text,
                    norm_key,
                    ocr_norm_key,
                    token_count,
                    mods_json,
                    json.dumps(mod_codes, ensure_ascii=True),
                    itypes_json,
                    etypes_json,
                    enabled,
                ),
            )
            inserted += 1
            by_kind[affix_kind] += 1
    conn.commit()
    return {
        "source_affixes": len(src_rows),
        "lexicon_rows": inserted,
        **{f"rows_{k}": v for k, v in sorted(by_kind.items())},
    }


def cmd_stats(conn: sqlite3.Connection, limit: int) -> int:
    total = conn.execute("SELECT COUNT(*) FROM catalog_affix_lexicon").fetchone()[0]
    uniq_aff = conn.execute("SELECT COUNT(DISTINCT affix_id) FROM catalog_affix_lexicon").fetchone()[0]
    print(f"catalog_affix_lexicon rows={total} unique_affixes={uniq_aff}")
    print("# by alias_kind")
    for r in conn.execute(
        "SELECT alias_kind, COUNT(*) AS n FROM catalog_affix_lexicon GROUP BY alias_kind ORDER BY n DESC, alias_kind ASC"
    ):
        print(f"{r['alias_kind']}: {r['n']}")
    print("# sample")
    for r in conn.execute(
        """
        SELECT affix_id, affix_name, alias_kind, alias_text, norm_key, ocr_norm_key, mod_codes_json
        FROM catalog_affix_lexicon
        ORDER BY affix_kind, affix_name, alias_kind
        LIMIT ?
        """,
        (limit,),
    ):
        print(
            f"{r['affix_id']:<36} {r['alias_kind']:<12} alias={r['alias_text']!r} "
            f"norm={r['norm_key']!r} ocr={r['ocr_norm_key']!r} mods={r['mod_codes_json']}"
        )
    return 0


def cmd_search(conn: sqlite3.Connection, query: str, ocr: bool, limit: int) -> int:
    key = _ocr_fold_text(query) if ocr else _norm_text(query)
    col = "ocr_norm_key" if ocr else "norm_key"
    print(f"query={query!r} {'ocr' if ocr else 'norm'}_key={key!r}")
    rows = conn.execute(
        f"""
        SELECT affix_id, affix_kind, affix_name, alias_kind, alias_text, {col} AS match_key, mod_codes_json
        FROM catalog_affix_lexicon
        WHERE {col} = ? OR {col} LIKE ?
        ORDER BY CASE WHEN {col} = ? THEN 0 ELSE 1 END, token_count DESC, affix_kind, affix_name
        LIMIT ?
        """,
        (key, f"%{key}%", key, limit),
    ).fetchall()
    for r in rows:
        print(
            f"{r['affix_id']:<36} {r['alias_kind']:<12} alias={r['alias_text']!r} mods={r['mod_codes_json']}"
        )
    if not rows:
        print("no matches")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Build affix lexicon (catalog_affixes -> OCR/classifier matching layer)")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    sp = p.add_subparsers(dest="cmd", required=False)

    p_build = sp.add_parser("build", help="Build/rebuild catalog_affix_lexicon")
    p_build.add_argument("--no-replace", action="store_true", help="Append/update instead of clearing first")

    p_stats = sp.add_parser("stats", help="Show lexicon stats/sample")
    p_stats.add_argument("--limit", type=int, default=20)

    p_search = sp.add_parser("search", help="Search affix lexicon by normalized or OCR-folded key")
    p_search.add_argument("query")
    p_search.add_argument("--ocr", action="store_true", help="Use OCR-folded matching")
    p_search.add_argument("--limit", type=int, default=25)

    args = p.parse_args()
    if args.cmd is None:
        args.cmd = "build"
        args.no_replace = False

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if args.cmd == "build":
            stats = build_lexicon(conn, replace=not args.no_replace)
            print("built catalog_affix_lexicon")
            for k in sorted(stats):
                print(f"{k}={stats[k]}")
            return 0
        if args.cmd == "stats":
            return cmd_stats(conn, args.limit)
        if args.cmd == "search":
            return cmd_search(conn, args.query, args.ocr, args.limit)
        p.error(f"unknown cmd: {args.cmd}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
