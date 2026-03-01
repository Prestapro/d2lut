#!/usr/bin/env python3
"""Export KPI + regression dashboard for market coverage and OCR quality.

Usage:
    PYTHONPATH=src python scripts/export_kpi_dashboard.py [--db data/cache/d2lut.db] [--output kpi_dashboard.html]
    PYTHONPATH=src python scripts/export_kpi_dashboard.py --persist --check-thresholds

Exit code 1 if --check-thresholds and regression detected (CI integration).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from d2lut.overlay.kpi_dashboard import (
    build_kpi_dashboard_html,
    check_regression_thresholds,
    collect_kpi_snapshot,
    compare_snapshots,
    ensure_kpi_table,
    load_kpi_history,
    persist_kpi_snapshot,
)


def main() -> int:
    p = argparse.ArgumentParser(description="KPI + regression dashboard")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--output", default="kpi_dashboard.html", help="Output HTML path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--min-fg", type=float, default=300.0, help="Min FG for high-value threshold")
    p.add_argument("--persist", action="store_true", help="Save current snapshot to DB")
    p.add_argument(
        "--check-thresholds",
        action="store_true",
        help="Check regression thresholds and exit non-zero on regression",
    )
    p.add_argument("--history-limit", type=int, default=50, help="Max history snapshots to show")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    try:
        ensure_kpi_table(conn)

        # Collect current KPIs
        current = collect_kpi_snapshot(conn, args.market_key, min_fg=args.min_fg)
        print(f"Current KPIs: observed_prices={current.observed_prices} "
              f"variants={current.variants} canonical_items={current.canonical_items} "
              f"hv_obs={current.high_value_observations} hv_var={current.high_value_variants} "
              f"img_obs={current.resolved_by_image_obs} img_var={current.resolved_by_image_variants} "
              f"ocr_precision={current.ocr_precision:.4f}")

        # Optionally persist
        if args.persist:
            row_id = persist_kpi_snapshot(conn, current)
            print(f"Persisted snapshot id={row_id}")

        # Load history (includes just-persisted snapshot if --persist)
        history = load_kpi_history(conn, limit=args.history_limit)

        # Compare with previous baseline
        alerts: list[str] = []
        if len(history) >= 2:
            baseline = history[1] if args.persist else history[0]
            target = current if args.persist else history[0]
            # If we just persisted, current is history[0], baseline is history[1]
            if args.persist:
                baseline = history[1]
                target = history[0]
            comparison = compare_snapshots(target, baseline)
            alerts = check_regression_thresholds(target, baseline)
            print(f"\nComparison vs baseline ({baseline.timestamp}):")
            print(json.dumps(comparison, indent=2))
        else:
            print("\nNo previous baseline for comparison (first snapshot).")

        if alerts:
            print("\n⚠ REGRESSION ALERTS:")
            for a in alerts:
                print(f"  {a}")

        # Build and write HTML
        out_html = build_kpi_dashboard_html(history, alerts)
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_html, encoding="utf-8")
        print(f"\nDashboard written to {out_path}")

        # Exit non-zero on regression if requested
        if args.check_thresholds and alerts:
            print("\nFailing build due to regression thresholds.", file=sys.stderr)
            return 1

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
