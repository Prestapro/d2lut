#!/usr/bin/env python3
"""Suspicious row detector for the property price table.

Reads the same SQLite DB as export_property_price_table_html.py and flags rows
with likely-wrong data: impossible property combos, extreme price anomalies,
and contradictory type assignments.

Usage:
    python scripts/detect_suspicious_rows.py --db data/cache/d2lut.db
    python scripts/detect_suspicious_rows.py --min-fg 200 --json
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

# Allow standalone execution: python scripts/detect_suspicious_rows.py
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_property_price_table_html import extract_props, props_signature

# ---------------------------------------------------------------------------
# Type-prefix helpers
# ---------------------------------------------------------------------------


def _type_l1(variant_key: str | None) -> str:
    """Extract the first colon-delimited segment of a variant_key."""
    vk = (variant_key or "").strip()
    if not vk:
        return ""
    return vk.split(":")[0].lower()


# ---------------------------------------------------------------------------
# Detection rule 1: impossible property combos  (Req 23.1)
# ---------------------------------------------------------------------------

# Properties that should NOT appear on certain item categories.
_IMPOSSIBLE_COMBOS: dict[str, set[str]] = {
    # Runes are currency items — they have no mods.
    "rune": {"fcr", "ias", "ed", "fhr", "frw", "all_res", "life", "mf", "skills",
             "ar", "max_dmg", "min_dmg", "strength", "dexterity", "os"},
    # Charms cannot have IAS or sockets.
    "charm": {"ias", "os"},
    # Jewels cannot be socketed.
    "jewel": {"os"},
    # Rings/amulets don't have ED or sockets in D2R.
    "ring": {"ed", "os"},
    "amulet": {"ed", "os"},
}


def _check_impossible_combos(
    props, variant_key: str | None,
) -> list[str]:
    """Return reason codes for impossible property combos."""
    cat = _type_l1(variant_key)
    forbidden = _IMPOSSIBLE_COMBOS.get(cat)
    if not forbidden:
        return []
    # Check which forbidden properties are actually set.
    hits: list[str] = []
    for field in forbidden:
        val = getattr(props, field, None)
        if isinstance(val, bool):
            if val:
                hits.append(field)
        elif val is not None:
            hits.append(field)
    if hits:
        return ["impossible_combo"]
    return []


# ---------------------------------------------------------------------------
# Detection rule 2: extreme price anomaly  (Req 23.2)
# ---------------------------------------------------------------------------

def _compute_category_medians(
    rows: list[sqlite3.Row],
) -> dict[str, float]:
    """Compute median FG per type_l1 category."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        cat = _type_l1(r["variant_key"])
        if not cat:
            continue
        buckets[cat].append(float(r["price_fg"]))
    return {cat: median(prices) for cat, prices in buckets.items() if prices}


def _check_price_anomaly(
    price_fg: float,
    variant_key: str | None,
    category_medians: dict[str, float],
    *,
    factor: float = 5.0,
) -> list[str]:
    """Return reason codes for extreme price anomaly."""
    cat = _type_l1(variant_key)
    cat_median = category_medians.get(cat)
    if cat_median is None or cat_median <= 0:
        return []
    ratio = price_fg / cat_median
    if ratio > factor:
        return ["price_anomaly_high"]
    inv_ratio = cat_median / price_fg if price_fg > 0 else 0
    if inv_ratio > factor:
        return ["price_anomaly_low"]
    return []


# ---------------------------------------------------------------------------
# Detection rule 3: contradictory type assignment  (Req 23.3)
# ---------------------------------------------------------------------------

_RE_TORCH = re.compile(r"\btorch\b", re.IGNORECASE)
_RE_ANNI = re.compile(r"\banni(?:hilus)?\b", re.IGNORECASE)
_RE_JEWEL = re.compile(r"\bjewel\b", re.IGNORECASE)

# Common runeword names that might appear in excerpts.
_RUNEWORD_NAMES = [
    "enigma", "infinity", "grief", "fortitude", "spirit", "insight",
    "hoto", "heart of the oak", "cta", "call to arms", "botd",
    "breath of the dying", "chains of honor", "coh", "last wish",
    "faith", "phoenix", "exile", "beast", "doom", "pride",
    "bramble", "dragon", "dream",
]


def _check_contradictory_type(
    excerpt: str, variant_key: str | None,
) -> list[str]:
    """Return reason codes for contradictory type assignment."""
    vk_lower = (variant_key or "").lower()
    cat = _type_l1(variant_key)
    text = excerpt.lower()
    reasons: list[str] = []

    # Torch mentioned but variant_key is not unique:hellfire_torch
    if _RE_TORCH.search(text):
        if "hellfire_torch" not in vk_lower and cat != "":
            # Only flag if variant_key is set but doesn't match torch.
            if vk_lower:
                reasons.append("contradictory_type")

    # Anni mentioned but variant_key is not unique:annihilus
    if _RE_ANNI.search(text) and not reasons:
        if "annihilus" not in vk_lower and vk_lower:
            reasons.append("contradictory_type")

    # Jewel mentioned but variant_key not in jewel category
    if _RE_JEWEL.search(text) and not reasons:
        if cat not in ("jewel", ""):
            reasons.append("contradictory_type")

    # Runeword name in excerpt but variant_key not runeword category
    if not reasons:
        for rw in _RUNEWORD_NAMES:
            if rw in text and cat not in ("runeword", "bundle", ""):
                reasons.append("contradictory_type")
                break

    return reasons


# ---------------------------------------------------------------------------
# Main detection pipeline
# ---------------------------------------------------------------------------

def detect_suspicious(
    rows: list[sqlite3.Row],
    *,
    price_factor: float = 5.0,
) -> list[dict]:
    """Run all detection rules and return flagged rows."""
    category_medians = _compute_category_medians(rows)
    flagged: list[dict] = []

    for r in rows:
        excerpt = (r["raw_excerpt"] or "").strip()
        vk = r["variant_key"]
        price_fg = float(r["price_fg"])

        # Extract props for impossible-combo check.
        props = extract_props(excerpt, vk) if excerpt else None
        sig = props_signature(props) if props else None

        reasons: list[str] = []

        # Rule 1: impossible combos
        if props:
            reasons.extend(_check_impossible_combos(props, vk))

        # Rule 2: price anomaly
        reasons.extend(
            _check_price_anomaly(price_fg, vk, category_medians, factor=price_factor)
        )

        # Rule 3: contradictory type
        if excerpt:
            reasons.extend(_check_contradictory_type(excerpt, vk))

        if reasons:
            flagged.append({
                "variant_key": vk or "",
                "signature": sig or "",
                "reason_code": reasons[0],
                "all_reasons": reasons,
                "excerpt": excerpt[:120] if excerpt else "",
                "median_fg": category_medians.get(_type_l1(vk), 0.0),
                "price_fg": price_fg,
            })

    return flagged


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _print_human(flagged: list[dict], *, market_key: str, scanned: int) -> None:
    print("=== Suspicious Row Report ===")
    print(f"Market: {market_key} | Scanned: {scanned} | Flagged: {len(flagged)}")
    print()
    if not flagged:
        print("No suspicious rows detected.")
        return
    # Group by reason code for readability.
    by_reason: dict[str, list[dict]] = defaultdict(list)
    for f in flagged:
        by_reason[f["reason_code"]].append(f)
    for reason, items in sorted(by_reason.items()):
        print(f"--- {reason} ({len(items)} rows) ---")
        for item in items[:25]:
            print(
                f"  {item['variant_key']:<40s} "
                f"sig={item['signature'][:50]:<50s} "
                f"fg={item['price_fg']:.0f} "
                f"cat_med={item['median_fg']:.0f}"
            )
            if item["excerpt"]:
                print(f"    excerpt: {item['excerpt']}")
        if len(items) > 25:
            print(f"  ... and {len(items) - 25} more")
        print()


def _print_json(flagged: list[dict], *, market_key: str, scanned: int) -> None:
    payload = {
        "market_key": market_key,
        "observations_scanned": scanned,
        "flagged_count": len(flagged),
        "flagged": flagged,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Detect suspicious property table rows")
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

    flagged = detect_suspicious(rows)

    if args.json_output:
        _print_json(flagged, market_key=args.market_key, scanned=len(rows))
    else:
        _print_human(flagged, market_key=args.market_key, scanned=len(rows))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
