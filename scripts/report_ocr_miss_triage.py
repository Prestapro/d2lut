#!/usr/bin/env python3
"""OCR miss triage queue.

Reads the same SQLite DB as export_property_price_table_html.py and classifies
rows that failed to produce a valid property signature into failure pattern
groups, ranked by total FG value lost.

Failure patterns:
  no_variant_hint        – variant_key is None or empty
  wrong_class            – inferred item category doesn't match observed type
  ocr_corruption         – raw_excerpt contains OCR noise indicators
  base_only_vs_finished_rw – base item confused with runeword (or vice versa)
  no_property_signature  – has variant_hint but extract_props+props_signature → None

Usage:
    python scripts/report_ocr_miss_triage.py --db data/cache/d2lut.db
    python scripts/report_ocr_miss_triage.py --min-fg 200 --json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

# Allow standalone execution
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_property_price_table_html import extract_props, props_signature
from d2lut.normalize.modifier_lexicon import infer_item_category_from_variant

# ---------------------------------------------------------------------------
# OCR noise detection
# ---------------------------------------------------------------------------

# Common OCR confusions: O↔0, l↔1, I↔1 adjacent to digits
_RE_OCR_NOISE = re.compile(
    r"(?:\d[OIl]|[OIl]\d)",
)


# Runeword names used for base-vs-finished confusion detection
_RUNEWORD_NAMES = {
    "enigma", "infinity", "grief", "fortitude", "spirit", "insight",
    "hoto", "heart of the oak", "cta", "call to arms", "botd",
    "breath of the dying", "chains of honor", "coh", "last wish",
    "faith", "phoenix", "exile", "beast", "doom", "pride",
    "bramble", "dragon", "dream",
}

# Base item names that appear in kit listings
_BASE_ITEM_KEYWORDS = {
    "archon plate", "mage plate", "monarch", "thresher", "giant thresher",
    "cryptic axe", "colossus voulge", "great poleaxe", "phase blade",
    "berserker axe", "dusk shroud", "wire fleece", "sacred targe",
    "sacred rondache", "sacred armor", "vortex shield",
}

# Individual rune names
_RUNE_NAMES = {
    "el", "eld", "tir", "nef", "eth", "ith", "tal", "ral", "ort", "thul",
    "amn", "sol", "shael", "dol", "hel", "io", "lum", "ko", "fal", "lem",
    "pul", "um", "mal", "ist", "gul", "vex", "ohm", "lo", "sur", "ber",
    "jah", "cham", "zod",
}


# ---------------------------------------------------------------------------
# Failure pattern classification
# ---------------------------------------------------------------------------

def classify_failure(
    row: dict,
    *,
    props=None,
    sig: str | None = None,
) -> str | None:
    """Classify a row into a failure pattern. Returns None if row is not a miss."""
    variant_key = (row.get("variant_key") or "").strip()
    excerpt = (row.get("raw_excerpt") or "").strip()

    # If we have a valid signature, this is not a miss
    if sig is not None:
        return None

    # Pattern 1: no_variant_hint
    if not variant_key:
        return "no_variant_hint"

    # Pattern 4: base_only_vs_finished_rw
    # Check if excerpt looks like a kit/base listing but variant says runeword
    # or vice versa.
    text_lower = excerpt.lower()
    inferred_cat = infer_item_category_from_variant(variant_key)
    has_rw_name = any(rw in text_lower for rw in _RUNEWORD_NAMES)
    has_base_name = any(b in text_lower for b in _BASE_ITEM_KEYWORDS)
    has_rune_names = sum(1 for r in _RUNE_NAMES if re.search(rf"\b{re.escape(r)}\b", text_lower)) >= 2

    if inferred_cat == "runeword_item" and has_base_name and has_rune_names and not has_rw_name:
        return "base_only_vs_finished_rw"
    if inferred_cat in ("base_armor", "base_weapon") and has_rw_name:
        return "base_only_vs_finished_rw"

    # Pattern 2: wrong_class
    # Variant hint exists but inferred category doesn't match excerpt content
    _CATEGORY_EXCERPT_HINTS = {
        "torch": [r"\btorch\b"],
        "anni": [r"\banni(?:hilus)?\b"],
        "jewel": [r"\bjewel\b"],
        "charm": [r"\bcharm\b", r"\b[sgl]c\b"],
        "runeword_item": [rf"\b{re.escape(rw)}\b" for rw in _RUNEWORD_NAMES],
    }
    excerpt_cats: set[str] = set()
    for cat, patterns in _CATEGORY_EXCERPT_HINTS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                excerpt_cats.add(cat)
                break

    if excerpt_cats and inferred_cat not in excerpt_cats and inferred_cat != "generic":
        return "wrong_class"

    # Pattern 3: ocr_corruption
    if _RE_OCR_NOISE.search(excerpt):
        return "ocr_corruption"

    # Pattern 5: no_property_signature (catch-all for rows with variant but no sig)
    return "no_property_signature"


# ---------------------------------------------------------------------------
# Triage grouping
# ---------------------------------------------------------------------------

def triage_rows(
    rows: list[dict],
) -> dict[str, list[dict]]:
    """Group miss rows by failure pattern."""
    groups: dict[str, list[dict]] = defaultdict(list)

    for row in rows:
        excerpt = (row.get("raw_excerpt") or "").strip()
        vk = row.get("variant_key")
        props = extract_props(excerpt, vk) if excerpt else None
        sig = props_signature(props) if props else None

        pattern = classify_failure(row, props=props, sig=sig)
        if pattern is not None:
            groups[pattern].append(row)

    return dict(groups)


def rank_groups(
    groups: dict[str, list[dict]],
) -> list[dict]:
    """Rank miss groups by total FG value lost, include up to 5 samples each."""
    ranked: list[dict] = []

    for pattern, rows in groups.items():
        prices = [float(r.get("price_fg", 0)) for r in rows]
        total_fg = sum(prices)
        median_fg = median(prices) if prices else 0.0

        # Pick up to 5 sample excerpts, preferring higher FG rows
        sorted_rows = sorted(rows, key=lambda r: -float(r.get("price_fg", 0)))
        samples = []
        for r in sorted_rows[:5]:
            samples.append({
                "variant_key": r.get("variant_key") or "",
                "price_fg": float(r.get("price_fg", 0)),
                "excerpt": (r.get("raw_excerpt") or "")[:200],
            })

        ranked.append({
            "pattern": pattern,
            "count": len(rows),
            "total_fg_lost": round(total_fg, 1),
            "median_fg": round(median_fg, 1),
            "samples": samples,
        })

    ranked.sort(key=lambda g: -g["total_fg_lost"])
    return ranked


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _print_human(
    ranked: list[dict],
    *,
    market_key: str,
    min_fg: float,
    scanned: int,
    total_misses: int,
) -> None:
    print("=== OCR Miss Triage Report ===")
    print(f"Market: {market_key} | Min FG: {min_fg} | Scanned: {scanned} | Total misses: {total_misses}")
    print()

    if not ranked:
        print("No misses found.")
        return

    for g in ranked:
        print(f"--- {g['pattern']} ({g['count']} rows, {g['total_fg_lost']:.0f} FG lost) ---")
        print(f"  Median FG: {g['median_fg']:.0f}")
        for i, s in enumerate(g["samples"], 1):
            print(f"  {i}. [{s['price_fg']:.0f}fg] {s['variant_key']}")
            if s["excerpt"]:
                print(f"     excerpt: {s['excerpt'][:120]}")
        print()


def _print_json(
    ranked: list[dict],
    *,
    market_key: str,
    min_fg: float,
    scanned: int,
    total_misses: int,
) -> None:
    payload = {
        "market_key": market_key,
        "min_fg": min_fg,
        "observations_scanned": scanned,
        "total_misses": total_misses,
        "groups": ranked,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="OCR miss triage queue")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--min-fg", type=float, default=100.0, help="Minimum FG threshold (default: 100)")
    p.add_argument("--limit", type=int, default=5000, help="Max rows to scan (default: 5000)")
    p.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT source, forum_id, thread_id, source_url, signal_kind,
                   variant_key, price_fg, confidence,
                   COALESCE(raw_excerpt, '') AS raw_excerpt, observed_at
            FROM observed_prices
            WHERE market_key = ? AND price_fg >= ?
            ORDER BY price_fg DESC, id DESC
            LIMIT ?
            """,
            (args.market_key, args.min_fg, args.limit),
        ).fetchall()
    finally:
        conn.close()

    # Convert sqlite3.Row to dicts for processing
    row_dicts = [dict(r) for r in rows]

    groups = triage_rows(row_dicts)
    ranked = rank_groups(groups)
    total_misses = sum(g["count"] for g in ranked)

    if args.json_output:
        _print_json(ranked, market_key=args.market_key, min_fg=args.min_fg,
                     scanned=len(rows), total_misses=total_misses)
    else:
        _print_human(ranked, market_key=args.market_key, min_fg=args.min_fg,
                      scanned=len(rows), total_misses=total_misses)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
