#!/usr/bin/env python3
"""Export sell recommendations as self-contained HTML.

Reads a JSON scan-results file (same format as export_valuation.py),
classifies each item, detects duplicates, and produces a browser-viewable
HTML page with recommendation tags and quick-sell totals.

Usage::

    PYTHONPATH=src python scripts/export_sell_recommendations.py \
        --input data/cache/my_scan.json --output sell_recs.html

    # With minimum FG filter
    PYTHONPATH=src python scripts/export_sell_recommendations.py \
        --input data/cache/my_scan.json --min-fg 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(
        description="Export sell recommendations HTML from scan results JSON",
    )
    p.add_argument(
        "--input", "-i",
        required=True,
        help="Path to JSON file with scan results (list of item dicts)",
    )
    p.add_argument(
        "--output", "-o",
        default="sell_recommendations.html",
        help="Output HTML path (default: sell_recommendations.html)",
    )
    p.add_argument(
        "--min-fg",
        type=float,
        default=0.0,
        help="Minimum FG threshold – items below this are still shown but not tagged sell_now",
    )
    p.add_argument(
        "--title", "-t",
        default="Sell Recommendations",
        help="Page title",
    )
    p.add_argument(
        "--db",
        default=None,
        help="Path to market SQLite DB (reserved for future premium lookup)",
    )

    args = p.parse_args()

    # Lazy imports so PYTHONPATH=src works at script level
    from d2lut.overlay.sell_recommendations import (
        build_recommendations,
        build_sell_recommendations_html,
        estimate_quick_sell_total,
    )
    from d2lut.overlay.valuation_export import items_from_scan_result

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    with open(input_path) as f:
        raw = json.load(f)

    items = items_from_scan_result(raw)
    recs = build_recommendations(items)

    html_str = build_sell_recommendations_html(recs, title=args.title)

    out_path = Path(args.output)
    out_path.write_text(html_str, encoding="utf-8")

    quick_total = estimate_quick_sell_total(recs)
    print(f"Wrote {len(recs)} items to {out_path} ({out_path.stat().st_size:,} bytes)")
    print(f"Quick-sell total: {quick_total:,.0f} fg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
