#!/usr/bin/env python3
"""Report full catalog price coverage with KPI gates.

KPI gates:
  - 100% catalog rows present in catalog_price_map
  - unknown share <= 10% overall
  - unknown share <= 3% on high-value segment (>=300fg where estimable)
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(
        description="Report full catalog price coverage with KPI gates"
    )
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--unknown-max-pct", type=float, default=10.0,
                    help="Max allowed unknown %% overall (default: 10)")
    p.add_argument("--unknown-hv-max-pct", type=float, default=3.0,
                    help="Max allowed unknown %% on high-value segment (default: 3)")
    p.add_argument("--hv-min-fg", type=float, default=300.0,
                    help="High-value threshold in FG (default: 300)")
    p.add_argument("--strict-market-only", action="store_true",
                    help="Count heuristic_range as unknown for KPI pass/fail")
    p.add_argument("--strict", action="store_true",
                    help="Exit with code 1 if any KPI gate fails")
    p.add_argument("--tradeable-only", action="store_true",
                    help="Exclude non-tradeable items (tradeable=0) from KPI denominators")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Check tables exist
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    if "catalog_price_map" not in tables:
        print("ERROR: catalog_price_map table not found. Run build_catalog_price_map.py first.")
        return 2
    if "catalog_items" not in tables:
        print("ERROR: catalog_items table not found. Run build_catalog_db.py first.")
        return 2

    # Tradeable filter: when --tradeable-only, restrict KPI denominators to tradeable items
    trade_filter = ""
    if args.tradeable_only:
        trade_filter = " AND ci.tradeable = 1"
    trade_join = (
        " JOIN catalog_items ci ON ci.canonical_item_id = cpm.canonical_item_id"
        if args.tradeable_only else ""
    )
    trade_where = " WHERE ci.tradeable = 1" if args.tradeable_only else ""

    # KPI 1: 100% catalog rows present (always counts ALL enabled items)
    catalog_count = conn.execute(
        "SELECT COUNT(*) FROM catalog_items WHERE enabled = 1"
    ).fetchone()[0]
    map_count = conn.execute(
        "SELECT COUNT(*) FROM catalog_price_map"
    ).fetchone()[0]
    coverage_pct = round(100 * map_count / max(catalog_count, 1), 1)
    kpi1_pass = map_count >= catalog_count

    # Tradeable denominator for KPI 2/3
    if args.tradeable_only:
        tradeable_count = conn.execute(
            "SELECT COUNT(*) FROM catalog_items WHERE enabled = 1 AND tradeable = 1"
        ).fetchone()[0]
        non_tradeable_count = catalog_count - tradeable_count
        kpi_denom = tradeable_count
    else:
        tradeable_count = catalog_count
        non_tradeable_count = 0
        kpi_denom = map_count

    # Missing items (in catalog but not in price_map)
    missing = conn.execute("""
        SELECT ci.canonical_item_id, ci.display_name, ci.category
        FROM catalog_items ci
        LEFT JOIN catalog_price_map cpm ON ci.canonical_item_id = cpm.canonical_item_id
        WHERE ci.enabled = 1 AND cpm.canonical_item_id IS NULL
        ORDER BY ci.category, ci.canonical_item_id
        LIMIT 20
    """).fetchall()

    # KPI 2: unknown share <= threshold overall
    if args.tradeable_only:
        status_rows = conn.execute("""
            SELECT cpm.price_status, COUNT(*) as cnt
            FROM catalog_price_map cpm
            JOIN catalog_items ci ON ci.canonical_item_id = cpm.canonical_item_id
            WHERE ci.tradeable = 1
            GROUP BY cpm.price_status
        """).fetchall()
    else:
        status_rows = conn.execute("""
            SELECT price_status, COUNT(*) as cnt
            FROM catalog_price_map
            GROUP BY price_status
        """).fetchall()
    by_status = {r["price_status"]: r["cnt"] for r in status_rows}
    kpi2_total = sum(by_status.values())
    heuristic_count = by_status.get("heuristic_range", 0)
    unknown_count = by_status.get("unknown", 0)
    effective_unknown_count = unknown_count + heuristic_count if args.strict_market_only else unknown_count
    unknown_pct = round(100 * unknown_count / max(kpi2_total, 1), 1)
    effective_unknown_pct = round(100 * effective_unknown_count / max(kpi2_total, 1), 1)
    kpi2_pass = effective_unknown_pct <= args.unknown_max_pct

    # KPI 3: unknown share on high-value segment
    if args.tradeable_only:
        hv_rows = conn.execute("""
            SELECT cpm.price_status, COUNT(*) as cnt
            FROM catalog_price_map cpm
            JOIN catalog_items ci ON ci.canonical_item_id = cpm.canonical_item_id
            WHERE ci.tradeable = 1 AND cpm.fg_median IS NOT NULL AND cpm.fg_median >= ?
            GROUP BY cpm.price_status
        """, (args.hv_min_fg,)).fetchall()
    else:
        hv_rows = conn.execute("""
            SELECT price_status, COUNT(*) as cnt
            FROM catalog_price_map
            WHERE fg_median IS NOT NULL AND fg_median >= ?
            GROUP BY price_status
        """, (args.hv_min_fg,)).fetchall()
    hv_by_status = {r["price_status"]: r["cnt"] for r in hv_rows}
    hv_total = sum(r["cnt"] for r in hv_rows)
    hv_heuristic = hv_by_status.get("heuristic_range", 0)
    hv_unknown = hv_by_status.get("unknown", 0)
    hv_effective_unknown = hv_unknown + hv_heuristic if args.strict_market_only else hv_unknown
    hv_unknown_pct = round(100 * hv_unknown / max(hv_total, 1), 1) if hv_total > 0 else 0.0
    hv_effective_unknown_pct = round(100 * hv_effective_unknown / max(hv_total, 1), 1) if hv_total > 0 else 0.0
    kpi3_pass = hv_effective_unknown_pct <= args.unknown_hv_max_pct

    # Category breakdown (tradeable only when flag set)
    if args.tradeable_only:
        cat_rows = conn.execute("""
            SELECT cpm.category, cpm.price_status, COUNT(*) as cnt
            FROM catalog_price_map cpm
            JOIN catalog_items ci ON ci.canonical_item_id = cpm.canonical_item_id
            WHERE ci.tradeable = 1
            GROUP BY cpm.category, cpm.price_status
            ORDER BY cpm.category, cpm.price_status
        """).fetchall()
    else:
        cat_rows = conn.execute("""
            SELECT category, price_status, COUNT(*) as cnt
            FROM catalog_price_map
            GROUP BY category, price_status
            ORDER BY category, price_status
        """).fetchall()
    cat_summary: dict[str, dict[str, int]] = {}
    for r in cat_rows:
        cat_summary.setdefault(r["category"], {})[r["price_status"]] = r["cnt"]

    # Print report
    print("=" * 70)
    print("FULL CATALOG PRICE COVERAGE REPORT")
    print("=" * 70)

    print(f"\nKPI 1: Catalog coverage")
    print(f"  catalog_items (enabled): {catalog_count}")
    print(f"  catalog_price_map rows:  {map_count}")
    print(f"  coverage: {coverage_pct}%")
    print(f"  PASS: {'YES' if kpi1_pass else 'NO'}")
    if args.tradeable_only:
        print(f"  tradeable items: {tradeable_count}  (non-tradeable excluded: {non_tradeable_count})")
    if missing:
        print(f"  Missing items (first {len(missing)}):")
        for r in missing:
            print(f"    {r['canonical_item_id']:<45} {r['category']}")

    mode_label = "STRICT (heuristic_range counted as unknown)" if args.strict_market_only else "DEFAULT (heuristic_range separate)"
    if args.tradeable_only:
        mode_label += " + TRADEABLE-ONLY"
    print(f"\nMode: {mode_label}")

    print(f"\nKPI 2: Unknown share overall (<= {args.unknown_max_pct}%)")
    print(f"  denominator: {kpi2_total} items")
    for st in ["market", "variant_fallback", "heuristic_range", "unknown"]:
        n = by_status.get(st, 0)
        pct = round(100 * n / max(kpi2_total, 1), 1)
        print(f"  {st:<20} {n:>5} ({pct}%)")
    print(f"  unknown_share(raw): {unknown_pct}%")
    print(f"  unknown_share(effective): {effective_unknown_pct}%")
    print(f"  PASS: {'YES' if kpi2_pass else 'NO'}")

    print(f"\nKPI 3: Unknown share on high-value segment (>={args.hv_min_fg}fg, <= {args.unknown_hv_max_pct}%)")
    print(f"  high-value items: {hv_total}")
    for st in ["market", "variant_fallback", "heuristic_range", "unknown"]:
        n = hv_by_status.get(st, 0)
        pct = round(100 * n / max(hv_total, 1), 1) if hv_total > 0 else 0.0
        print(f"  {st:<20} {n:>5} ({pct}%)")
    print(f"  hv_unknown_share(raw): {hv_unknown_pct}%")
    print(f"  hv_unknown_share(effective): {hv_effective_unknown_pct}%")
    print(f"  PASS: {'YES' if kpi3_pass else 'NO'}")

    print(f"\nCategory breakdown:")
    print(f"  {'Category':<15} {'market':>7} {'fallback':>9} {'heuristic':>10} {'unknown':>8} {'total':>6}")
    print(f"  {'-'*15} {'-'*7} {'-'*9} {'-'*10} {'-'*8} {'-'*6}")
    for cat in sorted(cat_summary.keys()):
        st = cat_summary[cat]
        total = sum(st.values())
        print(
            f"  {cat:<15} {st.get('market', 0):>7} {st.get('variant_fallback', 0):>9} "
            f"{st.get('heuristic_range', 0):>10} {st.get('unknown', 0):>8} {total:>6}"
        )

    # Overall result
    all_pass = kpi1_pass and kpi2_pass and kpi3_pass
    print(f"\n{'=' * 70}")
    print(f"OVERALL: {'ALL KPIs PASS' if all_pass else 'SOME KPIs FAILED'}")
    print(f"{'=' * 70}")

    conn.close()

    if args.strict and not all_pass:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
