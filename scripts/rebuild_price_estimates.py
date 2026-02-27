#!/usr/bin/env python3
"""Rebuild price_estimates from existing observed_prices.

This is useful after adding new observations (e.g., from diablo2.io scraper)
to regenerate the price estimates without re-importing all snapshots.

Usage:
    PYTHONPATH=src python3 scripts/rebuild_price_estimates.py --db data/cache/d2lut.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Import the build_estimates function from build_market_db
sys.path.insert(0, str(Path(__file__).parent))
from build_market_db import build_estimates
from d2lut.storage.sqlite import D2LutDB


def main() -> int:
    p = argparse.ArgumentParser(description="Rebuild price_estimates from observed_prices")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    # Count before
    conn = sqlite3.connect(db_path)
    obs_count = conn.execute(
        "SELECT COUNT(*) FROM observed_prices WHERE market_key = ?",
        (args.market_key,)
    ).fetchone()[0]
    est_before = conn.execute(
        "SELECT COUNT(*) FROM price_estimates WHERE market_key = ?",
        (args.market_key,)
    ).fetchone()[0]
    conn.close()

    print(f"Rebuilding price_estimates for market '{args.market_key}'")
    print(f"  observed_prices: {obs_count}")
    print(f"  price_estimates (before): {est_before}")

    # Rebuild
    db = D2LutDB(str(db_path))
    n_est = build_estimates(db, args.market_key)
    db.close()

    print(f"  price_estimates (after): {n_est}")
    print(f"Done. Added {n_est - est_before} new estimates.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
