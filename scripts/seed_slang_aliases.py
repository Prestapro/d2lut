#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def norm_alias(text: str) -> str:
    import re
    s = text.lower().replace("&amp;", "and").replace("'", "")
    s = re.sub(r"[^a-z0-9+]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def ensure_slang_schema(conn: sqlite3.Connection) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "src" / "d2lut" / "catalog" / "slang_schema.sql"
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def resolve_canonical(conn: sqlite3.Connection, alias_query: str) -> str:
    q = norm_alias(alias_query)
    row = conn.execute(
        """
        SELECT canonical_item_id
        FROM catalog_aliases
        WHERE alias_norm = ?
        ORDER BY priority ASC, canonical_item_id ASC
        LIMIT 1
        """,
        (q,),
    ).fetchone()
    return str(row[0]) if row else ""


def upsert_alias(
    conn: sqlite3.Connection,
    *,
    term_raw: str,
    term_type: str,
    canonical_item_id: str = "",
    replacement_text: str = "",
    confidence: float = 0.95,
    source: str = "seed_d2jsp",
    notes: str | None = None,
) -> None:
    term_norm = norm_alias(term_raw)
    if not term_norm:
        return
    conn.execute(
        """
        INSERT INTO slang_aliases(term_norm, term_raw, term_type, canonical_item_id, replacement_text, confidence, source, notes, enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(term_norm, canonical_item_id, replacement_text) DO UPDATE SET
          term_raw=excluded.term_raw,
          term_type=excluded.term_type,
          confidence=excluded.confidence,
          source=excluded.source,
          notes=excluded.notes,
          enabled=1
        """,
        (term_norm, term_raw, term_type, canonical_item_id, replacement_text, confidence, source, notes),
    )


def cmd_seed(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    ensure_slang_schema(conn)

    # Noise / trade chatter to suppress in candidate discovery.
    for term in [
        "fg", "forum gold", "please", "fast trade", "trade", "come", "get", "ur", "stat stick",
        "come get", "come get ur", "get ur", "get ur stat", "ur stat", "ur stat stick",
        "###", "paying", "total", "each", "ea", "here", "now",
    ]:
        upsert_alias(conn, term_raw=term, term_type="noise", replacement_text="", confidence=0.99)

    # Common trade terms / markers / lobby shorthand.
    for term in [
        "ft", "iso", "lf", "wug", "wun", "obo", "nn", "nty", "no ty", "gn", "desc", "bt", "/w", "pm",
        "bin", "c/o", "co", "res", "pc", "unid", "perf", "eth", "sup", "t4t",
    ]:
        upsert_alias(conn, term_raw=term, term_type="trade_term", replacement_text=term.replace("/", ""), confidence=0.99)

    # Base / socket shorthand (replacement_text for parser use later).
    base_expansions = {
        "gt": "giant thresher",
        "thresh": "thresher",
        "thresher": "thresher",
        "ca": "cryptic axe",
        "cv": "colossus voulge",
        "gpa": "great poleaxe",
        "pb": "phase blade",
        "ba": "berserker axe",
        "ap": "archon plate",
        "mp": "mage plate",
        "mon": "monarch",
        "zerker": "berserker axe",
        "sac targ": "sacred targe",
        "sac rond": "sacred rondache",
        "4os": "4 sockets",
        "5os": "5 sockets",
        "6os": "6 sockets",
    }
    for term, replacement in base_expansions.items():
        upsert_alias(conn, term_raw=term, term_type="base_alias", replacement_text=replacement, confidence=0.95)

    # Item slang mapped to canonical catalog ids when resolvable.
    item_aliases = {
        "amy": "tal ammy",
        "ammy": "tal ammy",
        "tal amy": "tal ammy",
        "tals amy": "tal ammy",
        "shako": "shako",
        "arach": "arach",
        "arachs": "arach",
        "torch": "torch",
        "anni": "anni",
        "token": "token",
        "hoz": "herald of zakarum",
        "zaka": "herald of zakarum",
        "nw": "nightwing",
        "cta": "call to arms",
        "hoto": "heart of the oak",
        "botd": "breath of the dying",
        "ebotdz": "eth botd zerker",
        "3x3": "3x3",
        "key set": "3x3",
        "organ set": "organ set",
        "spirit set": "spirit set",
        "insight set": "insight set",
        "pgems": "pgems",
        "p skulls": "pskulls",
    }
    for term, catalog_lookup in item_aliases.items():
        cid = resolve_canonical(conn, catalog_lookup)
        upsert_alias(
            conn,
            term_raw=term,
            term_type="item_alias",
            canonical_item_id=cid,
            replacement_text="",
            confidence=0.99 if cid else 0.6,
            notes=f"catalog_lookup={catalog_lookup}",
        )

    # Stat shorthand (used for later rule engine / parser normalization).
    stat_aliases = {
        "fcr": "faster cast rate",
        "frw": "faster run walk",
        "ias": "increased attack speed",
        "ed": "enhanced damage",
        "def": "defense",
        "res": "resistances",
        "allres": "all resistances",
        "@": "all resistances",
        "ll": "life leech",
        "ml": "mana leech",
        "ar": "attack rating",
        "mf": "magic find",
        "gf": "gold find",
    }
    for term, replacement in stat_aliases.items():
        upsert_alias(conn, term_raw=term, term_type="stat_alias", replacement_text=replacement, confidence=0.95)

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM slang_aliases").fetchone()[0]
    by_type = conn.execute("SELECT term_type, COUNT(*) FROM slang_aliases GROUP BY term_type ORDER BY term_type").fetchall()
    print(f"seeded slang_aliases total={total}")
    for t, c in by_type:
        print(f"{t}={c}")
    conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Seed common d2jsp slang aliases/noise into d2lut DB")
    p.add_argument("--db", default="data/cache/d2lut.db")
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("seed")
    s.set_defaults(func=cmd_seed)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
