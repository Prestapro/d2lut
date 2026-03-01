#!/usr/bin/env python3
"""Export self-contained HTML market dashboard from d2lut SQLite DB.

Usage::

    PYTHONPATH=src python scripts/export_market_dashboard.py
    PYTHONPATH=src python scripts/export_market_dashboard.py --db data/cache/d2lut.db --out market_dashboard.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(
        description="Export searchable HTML market dashboard from d2lut DB",
    )
    p.add_argument(
        "--db",
        default="data/cache/d2lut.db",
        help="SQLite database path (default: data/cache/d2lut.db)",
    )
    p.add_argument(
        "--market-key",
        default="d2r_sc_ladder",
        help="Market key to export (default: d2r_sc_ladder)",
    )
    p.add_argument(
        "--out", "-o",
        default="data/cache/market_dashboard.html",
        help="Output HTML file (default: data/cache/market_dashboard.html)",
    )
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    from d2lut.overlay.market_dashboard import export_dashboard

    out = export_dashboard(db_path, args.out, args.market_key)
    print(f"Dashboard exported to {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
