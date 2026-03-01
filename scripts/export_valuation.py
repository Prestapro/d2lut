#!/usr/bin/env python3
"""Export inventory/stash valuation as self-contained HTML.

Reads scan results from a JSON file and produces a browser-viewable
HTML valuation table with filtering, sorting, and value highlighting.

Usage examples::

    # From a JSON scan-results file
    python scripts/export_valuation.py --input data/cache/my_scan.json

    # With filters
    python scripts/export_valuation.py --input data/cache/my_scan.json \
        --min-fg 50 --title "Stash Tab 1" --output my_stash_value.html

    # Inventory mode (default)
    python scripts/export_valuation.py --input scan.json --type inventory

    # Stash mode
    python scripts/export_valuation.py --input scan.json --type stash
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(
        description="Export inventory/stash valuation HTML from scan results JSON",
    )
    p.add_argument(
        "--input", "-i",
        required=True,
        help="Path to JSON file with scan results (list of item dicts)",
    )
    p.add_argument(
        "--output", "-o",
        default=None,
        help="Output HTML path (default: my_inventory_value.html or my_stash_value.html)",
    )
    p.add_argument(
        "--title", "-t",
        default=None,
        help="Page title (default: based on --type)",
    )
    p.add_argument(
        "--min-fg",
        type=float,
        default=0.0,
        help="Minimum FG threshold for priced items (default: 0)",
    )
    p.add_argument(
        "--high-value",
        type=float,
        default=300.0,
        help="FG threshold for high-value highlighting (default: 300)",
    )
    p.add_argument(
        "--type",
        choices=["inventory", "stash"],
        default="inventory",
        help="Export type: inventory or stash (default: inventory)",
    )
    p.add_argument(
        "--hide-no-data",
        action="store_true",
        help="Hide items without price data",
    )
    p.add_argument(
        "--min-confidence",
        choices=["low", "medium", "high"],
        default=None,
        help="Minimum price confidence to include",
    )

    args = p.parse_args()

    # Lazy import so PYTHONPATH=src works at script level
    from d2lut.overlay.valuation_export import (
        ValuationExportConfig,
        build_valuation_html,
        filter_items,
        items_from_scan_result,
    )

    # Load JSON
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    with open(input_path) as f:
        raw = json.load(f)

    items = items_from_scan_result(raw)

    # Defaults
    title = args.title or ("My Inventory Valuation" if args.type == "inventory" else "My Stash Valuation")
    output = args.output or (
        "my_inventory_value.html" if args.type == "inventory" else "my_stash_value.html"
    )

    cfg = ValuationExportConfig(
        title=title,
        min_fg=args.min_fg,
        high_value_threshold=args.high_value,
        show_no_data=not args.hide_no_data,
        min_confidence=args.min_confidence,
        export_type=args.type,
    )

    filtered = filter_items(items, cfg)
    html_str = build_valuation_html(filtered, cfg)

    out_path = Path(output)
    out_path.write_text(html_str, encoding="utf-8")
    print(f"Wrote {len(filtered)} items to {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
