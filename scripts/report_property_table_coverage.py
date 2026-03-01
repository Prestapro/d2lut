#!/usr/bin/env python3
"""Property table coverage KPI reporter.

Reads the same SQLite DB as export_property_price_table_html.py and computes
quality metrics: row counts by kind, signature coverage ratios, and the top
missing variants (high-FG items with no property signature).

Usage:
    python scripts/report_property_table_coverage.py --db data/cache/d2lut.db
    python scripts/report_property_table_coverage.py --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# Allow standalone execution: python scripts/report_property_table_coverage.py
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_property_price_table_html import extract_props, props_signature


def _has_source_link(row: sqlite3.Row) -> bool:
    url = str(row["source_url"] or "").strip()
    if url:
        return True
    return row["thread_id"] is not None


def _compute_kpis(
    rows: list[sqlite3.Row],
    *,
    min_fg: float,
) -> dict:
    property_rows = 0
    fallback_rows = 0
    total_with_excerpt = 0
    with_source_link = 0
    with_req_lvl = 0
    with_class_tags = 0

    variant_all: dict[str, list[sqlite3.Row]] = defaultdict(list)
    variant_has_sig: set[str] = set()

    for r in rows:
        vk = str(r["variant_key"] or "").strip()
        if vk:
            variant_all[vk].append(r)

        excerpt = (r["raw_excerpt"] or "").strip()
        if not excerpt:
            continue

        total_with_excerpt += 1

        if _has_source_link(r):
            with_source_link += 1

        props = extract_props(excerpt, r["variant_key"])
        sig = props_signature(props)

        if props.req_lvl is not None:
            with_req_lvl += 1

        # Class tags: check if any class can be inferred from excerpt + variant
        hay = f"{vk} {excerpt}".lower()
        _class_keywords = [
            "sorc", "pala", "barb", "ama", "zon", "assa", "sin",
            "necro", "druid", "sorceress", "paladin", "barbarian",
            "amazon", "assassin", "necromancer",
        ]
        if any(kw in hay for kw in _class_keywords):
            with_class_tags += 1

        if sig:
            property_rows += 1
            if vk:
                variant_has_sig.add(vk)
        else:
            fallback_rows += 1

    # Market-gap rows: variants WITH a sig but where some observations lack one.
    # (mirrors the exporter's market-gap logic)
    market_gap_rows = 0
    for vk, vrows in variant_all.items():
        if vk not in variant_has_sig:
            continue
        prices = [float(r["price_fg"]) for r in vrows]
        obs_max = max(prices) if prices else 0.0
        if obs_max < min_fg:
            continue
        # Count observations in this variant that have no sig.
        no_sig_count = 0
        for r in vrows:
            excerpt = (r["raw_excerpt"] or "").strip()
            if not excerpt:
                continue
            props = extract_props(excerpt, r["variant_key"])
            sig = props_signature(props)
            if not sig:
                no_sig_count += 1
        if no_sig_count > 0:
            market_gap_rows += 1

    sig_coverage = (property_rows / total_with_excerpt * 100) if total_with_excerpt else 0.0
    pct_source = (with_source_link / total_with_excerpt * 100) if total_with_excerpt else 0.0
    pct_req_lvl = (with_req_lvl / total_with_excerpt * 100) if total_with_excerpt else 0.0
    pct_class_tags = (with_class_tags / total_with_excerpt * 100) if total_with_excerpt else 0.0

    return {
        "property_rows": property_rows,
        "fallback_rows": fallback_rows,
        "market_gap_rows": market_gap_rows,
        "total_with_excerpts": total_with_excerpt,
        "sig_coverage": round(sig_coverage, 1),
        "pct_source_link": round(pct_source, 1),
        "pct_req_lvl": round(pct_req_lvl, 1),
        "pct_class_tags": round(pct_class_tags, 1),
    }


def _top_missing_variants(
    rows: list[sqlite3.Row],
    *,
    min_fg: float,
    top_n: int = 20,
) -> list[dict]:
    """Variants with observations but NO property signature, sorted by max FG."""
    variant_obs: dict[str, list[sqlite3.Row]] = defaultdict(list)
    variant_has_sig: set[str] = set()

    for r in rows:
        vk = str(r["variant_key"] or "").strip()
        if not vk:
            continue
        variant_obs[vk].append(r)
        excerpt = (r["raw_excerpt"] or "").strip()
        if not excerpt:
            continue
        props = extract_props(excerpt, r["variant_key"])
        sig = props_signature(props)
        if sig:
            variant_has_sig.add(vk)

    missing: list[dict] = []
    for vk, vrows in variant_obs.items():
        if vk in variant_has_sig:
            continue
        prices = [float(r["price_fg"]) for r in vrows]
        max_fg = max(prices) if prices else 0.0
        if max_fg < min_fg:
            continue
        missing.append({
            "variant_key": vk,
            "obs_count": len(vrows),
            "max_fg": max_fg,
        })

    missing.sort(key=lambda m: -m["max_fg"])
    return missing[:top_n]


def _print_human(
    kpis: dict,
    missing: list[dict],
    *,
    market_key: str,
    min_fg: float,
    scanned: int,
) -> None:
    print("=== Property Table Coverage Report ===")
    print(f"Market: {market_key} | Min FG: {min_fg} | Observations scanned: {scanned}")
    print()
    print("Row counts:")
    print(f"  property_rows:     {kpis['property_rows']}")
    print(f"  fallback_rows:      {kpis['fallback_rows']}")
    print(f"  market_gap_rows:    {kpis['market_gap_rows']}")
    print()
    print("Coverage:")
    print(f"  sig_coverage:      {kpis['sig_coverage']:.1f}%  ({kpis['property_rows']} / {kpis['total_with_excerpts']} with excerpts)")
    print(f"  with_source_link:  {kpis['pct_source_link']:.1f}%")
    print(f"  with_req_lvl:      {kpis['pct_req_lvl']:.1f}%")
    print(f"  with_class_tags:   {kpis['pct_class_tags']:.1f}%")
    print()
    if missing:
        print(f"Top {len(missing)} missing variants (no property signature, >={min_fg}fg):")
        for i, m in enumerate(missing, 1):
            print(f"  {i:>2}. {m['variant_key']:<35s} obs={m['obs_count']:<4d} max_fg={m['max_fg']:.0f}")
    else:
        print("No missing variants above threshold.")


def _print_json(
    kpis: dict,
    missing: list[dict],
    *,
    market_key: str,
    min_fg: float,
    scanned: int,
) -> None:
    payload = {
        "market_key": market_key,
        "min_fg": min_fg,
        "observations_scanned": scanned,
        **kpis,
        "top_missing_variants": missing,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> int:
    p = argparse.ArgumentParser(description="Property table coverage KPI reporter")
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

    kpis = _compute_kpis(rows, min_fg=args.min_fg)
    missing = _top_missing_variants(rows, min_fg=args.min_fg)

    if args.json_output:
        _print_json(kpis, missing, market_key=args.market_key, min_fg=args.min_fg, scanned=len(rows))
    else:
        _print_human(kpis, missing, market_key=args.market_key, min_fg=args.min_fg, scanned=len(rows))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
