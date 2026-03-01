#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from pathlib import Path


def _node_extract(data_js: Path) -> dict:
    script = rf"""
const path = require('node:path');
const {{ pathToFileURL }} = require('node:url');
(async () => {{
  const mod = await import(pathToFileURL(path.resolve({json.dumps(str(data_js))})).href);
  const d = mod.default;
  function rowCount(v) {{
    return Array.isArray(v) ? v.length : (v && typeof v === 'object' ? Object.keys(v).length : 0);
  }}
  function collectModCodes(obj, prefixes) {{
    const out = [];
    for (const p of prefixes) {{
      for (let i = 1; i <= 12; i++) {{
        const code = obj[`${{p}}${{i}}code`] ?? obj[`${{p}}${{i}}`];
        if (typeof code === 'string' && code && !out.includes(code)) out.push(code);
      }}
    }}
    return out;
  }}
  function collectItemTypes(obj) {{
    const out = [];
    for (const [k, v] of Object.entries(obj)) {{
      if (/^(i|e)type\\d+$/.test(k) && typeof v === 'string' && v) out.push(v);
    }}
    return out;
  }}
  const families = ['magicPrefix','magicSuffix','autoMagic','crafted','qualityItems','propertyGroups','itemStatCost'];
  const familyCounts = Object.fromEntries(families.map(f => [f, rowCount(d[f])]));
  const entries = [];
  for (const fam of families) {{
    const src = d[fam] || {{}};
    if (Array.isArray(src)) {{
      for (let idx = 0; idx < src.length; idx++) {{
        const row = src[idx];
        if (!Array.isArray(row)) continue;
        entries.push({{
          family: fam,
          source_key: String(idx),
          display_name: String(row[2] ?? row[1] ?? ''),
          token_key: String(row[1] ?? row[0] ?? ''),
          mod_codes: [],
          item_types: [],
          meta: row,
        }});
      }}
      continue;
    }}
    for (const [k, v] of Object.entries(src)) {{
      if (!v || typeof v !== 'object') {{
        entries.push({{ family: fam, source_key: k, display_name: '', token_key: k, mod_codes: [], item_types: [], meta: v }});
        continue;
      }}
      let display = '';
      if (typeof v.name === 'string') display = v.name;
      else if (typeof v.description === 'string') display = v.description;
      else if (typeof v.descstrpos === 'string') display = v.descstrpos;
      else display = k;
      let modCodes = [];
      if (fam === 'itemStatCost') {{
        modCodes = [k];
      }} else if (fam === 'propertyGroups') {{
        for (let i=1;i<=8;i++) {{
          const code=v[`prop${{i}}`];
          if (typeof code === 'string' && code && !modCodes.includes(code)) modCodes.push(code);
        }}
      }} else {{
        modCodes = collectModCodes(v, ['mod','prop','pcode','fcode','aprop']);
      }}
      entries.push({{
        family: fam,
        source_key: k,
        display_name: display,
        token_key: k,
        mod_codes: modCodes,
        item_types: collectItemTypes(v),
        meta: v,
      }});
    }}
  }}
  console.log(JSON.stringify({{ familyCounts, entries }}));
}})().catch((e)=>{{ console.error(e); process.exit(1); }});
"""
    proc = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def _norm(s: str) -> str:
    import re

    s = (s or "").lower().replace("'", "").replace("`", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _ocr_norm(s: str) -> str:
    import re

    s = (s or "").lower()
    trans = str.maketrans({"@": "o", "®": "o", "0": "o", "1": "l", "i": "l", "|": "l", "5": "s", "$": "s", "8": "b"})
    s = s.translate(trans)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


MANUAL_MODIFIER_ALIASES: list[tuple[str, str, str, str, float]] = [
    # source_domain, token_kind, canonical_key, alias_text, confidence
    ("manual", "stat_shorthand", "itemStatCost:allres", "all res", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:fcr", "fcr", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:ias", "ias", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:frw", "frw", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:fhr", "fhr", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:mf", "mf", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:ed", "ed", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:def", "def", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:str", "str", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:dex", "dex", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:life", "life", 0.99),
    ("manual", "stat_shorthand", "itemStatCost:mana", "mana", 0.99),
    ("manual", "item_alias", "runeword:heart_of_the_oak", "hoto", 0.99),
    ("manual", "item_alias", "runeword:call_to_arms", "cta", 0.99),
    ("manual", "item_alias", "runeword:infinity", "infanity", 0.95),
    ("manual", "item_alias", "runeword:breath_of_the_dying", "botd", 0.99),
]


DEFAULT_CONSTRAINT_ROWS: list[tuple[str, str, str, str]] = [
    ("runes", "deny_code_prefix", "sock", "manual"),
    ("runes", "deny_code_prefix", "ac", "manual"),
    ("runes", "deny_code_prefix", "dmg", "manual"),
    ("torch", "deny_code_prefix", "sock", "manual"),
    ("anni", "deny_code_prefix", "sock", "manual"),
    ("base_armor", "allow_code_prefix", "sock", "manual"),
    ("base_armor", "allow_code_prefix", "ac", "manual"),
    ("base_weapon", "allow_code_prefix", "sock", "manual"),
    ("base_weapon", "allow_code_prefix", "dmg", "manual"),
    ("jewel", "deny_code_prefix", "sock", "manual"),
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS maxroll_modifier_lexicon (
          id INTEGER PRIMARY KEY,
          family TEXT NOT NULL,
          source_key TEXT NOT NULL,
          display_name TEXT,
          token_key TEXT,
          alias_kind TEXT NOT NULL DEFAULT 'canonical',
          alias_text TEXT NOT NULL,
          norm_key TEXT NOT NULL,
          ocr_norm_key TEXT NOT NULL,
          mod_codes_json TEXT,
          item_types_json TEXT,
          meta_json TEXT,
          UNIQUE(family, source_key, alias_kind, alias_text)
        );
        CREATE INDEX IF NOT EXISTS idx_maxroll_mod_lex_family ON maxroll_modifier_lexicon(family);
        CREATE INDEX IF NOT EXISTS idx_maxroll_mod_lex_norm ON maxroll_modifier_lexicon(norm_key);
        CREATE INDEX IF NOT EXISTS idx_maxroll_mod_lex_ocr ON maxroll_modifier_lexicon(ocr_norm_key);

        CREATE TABLE IF NOT EXISTS maxroll_data_family_stats (
          family TEXT PRIMARY KEY,
          row_count INTEGER NOT NULL,
          source TEXT NOT NULL DEFAULT 'maxroll_d2planner'
        );

        CREATE TABLE IF NOT EXISTS modifier_alias_lexicon (
          id INTEGER PRIMARY KEY,
          source_domain TEXT NOT NULL,      -- catalog_affix|maxroll|manual
          token_kind TEXT NOT NULL,         -- modifier_name|mod_code|stat_shorthand|item_alias
          canonical_key TEXT NOT NULL,
          alias_text TEXT NOT NULL,
          norm_key TEXT NOT NULL,
          ocr_norm_key TEXT NOT NULL,
          category_scope TEXT,
          confidence REAL NOT NULL DEFAULT 1.0,
          metadata_json TEXT,
          UNIQUE(source_domain, token_kind, canonical_key, alias_text)
        );
        CREATE INDEX IF NOT EXISTS idx_modifier_alias_norm ON modifier_alias_lexicon(norm_key);
        CREATE INDEX IF NOT EXISTS idx_modifier_alias_ocr ON modifier_alias_lexicon(ocr_norm_key);
        CREATE INDEX IF NOT EXISTS idx_modifier_alias_key ON modifier_alias_lexicon(canonical_key);

        CREATE TABLE IF NOT EXISTS modifier_category_constraints (
          id INTEGER PRIMARY KEY,
          category_key TEXT NOT NULL,
          rule_type TEXT NOT NULL,          -- allow_code_prefix|deny_code_prefix|allow_family|deny_family
          rule_value TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'manual',
          UNIQUE(category_key, rule_type, rule_value)
        );
        """
    )
    conn.commit()


def main() -> int:
    p = argparse.ArgumentParser(description="Import Maxroll D2 Planner modifier-related data into SQLite lexicon tables")
    p.add_argument("--db", default="data/cache/d2lut.db")
    p.add_argument("--maxroll-dir", default="data/raw/maxroll/d2planner")
    p.add_argument("--replace", action="store_true", help="Clear and rebuild maxroll/alias/constraint tables")
    args = p.parse_args()

    db_path = Path(args.db)
    maxroll_dir = Path(args.maxroll_dir)
    data_candidates = sorted(maxroll_dir.glob("data.min-*.js"))
    data_js = max(data_candidates, key=lambda p: p.stat().st_mtime) if data_candidates else None
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2
    if data_js is None:
        print(f"ERROR: missing data.min-*.js in {maxroll_dir}")
        return 2

    extracted = _node_extract(data_js)
    family_counts = extracted["familyCounts"]
    entries = extracted["entries"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        if args.replace:
            conn.execute("DELETE FROM maxroll_modifier_lexicon")
            conn.execute("DELETE FROM maxroll_data_family_stats")
            conn.execute("DELETE FROM modifier_alias_lexicon")
            conn.execute("DELETE FROM modifier_category_constraints")
            conn.commit()

        for fam, n in family_counts.items():
            conn.execute(
                "INSERT OR REPLACE INTO maxroll_data_family_stats(family, row_count, source) VALUES (?, ?, 'maxroll_d2planner')",
                (fam, int(n)),
            )

        inserted_maxroll = 0
        inserted_alias = 0
        for e in entries:
            fam = str(e.get("family") or "")
            skey = str(e.get("source_key") or "")
            display = str(e.get("display_name") or "")
            token_key = str(e.get("token_key") or "")
            mod_codes = e.get("mod_codes") or []
            item_types = e.get("item_types") or []
            meta = e.get("meta")

            aliases = []
            if display:
                aliases.append(("canonical", display))
            if token_key and token_key != display:
                aliases.append(("token_key", token_key))
            for code in mod_codes:
                if code and code not in {a[1] for a in aliases}:
                    aliases.append(("mod_code", str(code)))

            seen = set()
            for alias_kind, alias_text in aliases:
                alias_text = str(alias_text).strip()
                if not alias_text:
                    continue
                dedupe = (alias_kind, alias_text.lower())
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO maxroll_modifier_lexicon(
                      family, source_key, display_name, token_key, alias_kind, alias_text,
                      norm_key, ocr_norm_key, mod_codes_json, item_types_json, meta_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fam,
                        skey,
                        display,
                        token_key,
                        alias_kind,
                        alias_text,
                        _norm(alias_text),
                        _ocr_norm(alias_text),
                        json.dumps(mod_codes, ensure_ascii=True),
                        json.dumps(item_types, ensure_ascii=True),
                        json.dumps(meta, ensure_ascii=True)[:20000] if meta is not None else None,
                    ),
                )
                inserted_maxroll += 1

            # Add alias lexicon rows for modifier names/codes.
            canonical_key = f"{fam}:{skey}"
            if display:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO modifier_alias_lexicon(
                      source_domain, token_kind, canonical_key, alias_text, norm_key, ocr_norm_key, confidence, metadata_json
                    ) VALUES ('maxroll', 'modifier_name', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_key,
                        display,
                        _norm(display),
                        _ocr_norm(display),
                        0.95,
                        json.dumps({"family": fam}, ensure_ascii=True),
                    ),
                )
                inserted_alias += 1
            for code in mod_codes:
                code = str(code).strip()
                if not code:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO modifier_alias_lexicon(
                      source_domain, token_kind, canonical_key, alias_text, norm_key, ocr_norm_key, confidence, metadata_json
                    ) VALUES ('maxroll', 'mod_code', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_key,
                        code,
                        _norm(code),
                        _ocr_norm(code),
                        0.9,
                        json.dumps({"family": fam}, ensure_ascii=True),
                    ),
                )
                inserted_alias += 1

        # Seed aliases from catalog affix lexicon (all-item parser/classifier foundation).
        try:
            rows = conn.execute(
                """
                SELECT affix_id, affix_name, alias_text, alias_kind
                FROM catalog_affix_lexicon
                WHERE COALESCE(enabled,1)=1
                """
            ).fetchall()
            for r in rows:
                canonical_key = f"catalog_affix:{r['affix_id']}"
                alias_text = str(r["alias_text"] or "").strip()
                if not alias_text:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO modifier_alias_lexicon(
                      source_domain, token_kind, canonical_key, alias_text, norm_key, ocr_norm_key, confidence, metadata_json
                    ) VALUES ('catalog_affix', 'modifier_name', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_key,
                        alias_text,
                        _norm(alias_text),
                        _ocr_norm(alias_text),
                        1.0 if str(r["alias_kind"]) == "canonical" else 0.85,
                        json.dumps({"affix_name": r["affix_name"], "alias_kind": r["alias_kind"]}, ensure_ascii=True),
                    ),
                )
                inserted_alias += 1
        except sqlite3.OperationalError:
            pass

        # Manual shorthand/OCR-noise aliases (items + stat shorthand)
        for src_domain, token_kind, canonical_key, alias_text, conf in MANUAL_MODIFIER_ALIASES:
            conn.execute(
                """
                INSERT OR REPLACE INTO modifier_alias_lexicon(
                  source_domain, token_kind, canonical_key, alias_text, norm_key, ocr_norm_key, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (src_domain, token_kind, canonical_key, alias_text, _norm(alias_text), _ocr_norm(alias_text), conf),
            )
            inserted_alias += 1

        for row in DEFAULT_CONSTRAINT_ROWS:
            conn.execute(
                """
                INSERT OR REPLACE INTO modifier_category_constraints(category_key, rule_type, rule_value, source)
                VALUES (?, ?, ?, ?)
                """,
                row,
            )

        conn.commit()

        print(f"maxroll_entries_input={len(entries)}")
        print(f"maxroll_lexicon_rows_written={inserted_maxroll}")
        print(f"modifier_alias_rows_written={inserted_alias}")
        for fam, n in sorted(family_counts.items()):
            print(f"family_{fam}={n}")
        # Summary from DB
        r = conn.execute("SELECT COUNT(*) FROM maxroll_modifier_lexicon").fetchone()[0]
        print(f"maxroll_modifier_lexicon_total={r}")
        r = conn.execute("SELECT COUNT(*) FROM modifier_alias_lexicon").fetchone()[0]
        print(f"modifier_alias_lexicon_total={r}")
        r = conn.execute("SELECT COUNT(*) FROM modifier_category_constraints").fetchone()[0]
        print(f"modifier_category_constraints_total={r}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
