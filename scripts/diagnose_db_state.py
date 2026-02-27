#!/usr/bin/env python3
"""Quick DB state diagnostic for d2lut.

Usage:
    PYTHONPATH=src python scripts/diagnose_db_state.py
"""
import sqlite3
from pathlib import Path


def main():
    db_path = Path("data/cache/d2lut.db")
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    
    print("=" * 60)
    print("D2LUT DATABASE STATE DIAGNOSTIC")
    print("=" * 60)
    
    # observed_prices
    print("\n[observed_prices]")
    total_obs = conn.execute("SELECT COUNT(*) FROM observed_prices").fetchone()[0]
    print(f"  Total: {total_obs}")
    
    by_source = conn.execute(
        "SELECT source, COUNT(*) FROM observed_prices GROUP BY source"
    ).fetchall()
    for source, count in by_source:
        print(f"    {source}: {count}")
    
    by_market = conn.execute(
        "SELECT market_key, COUNT(*) FROM observed_prices GROUP BY market_key"
    ).fetchall()
    print(f"  By market:")
    for market, count in by_market:
        print(f"    {market}: {count}")
    
    # price_estimates
    print("\n[price_estimates]")
    total_est = conn.execute("SELECT COUNT(*) FROM price_estimates").fetchone()[0]
    print(f"  Total: {total_est}")
    
    by_market_est = conn.execute(
        "SELECT market_key, COUNT(*) FROM price_estimates GROUP BY market_key"
    ).fetchall()
    for market, count in by_market_est:
        print(f"    {market}: {count}")
    
    # catalog_price_map
    print("\n[catalog_price_map]")
    total_cat = conn.execute("SELECT COUNT(*) FROM catalog_price_map").fetchone()[0]
    print(f"  Total: {total_cat}")
    
    tradeable = conn.execute(
        "SELECT COUNT(*) FROM catalog_price_map WHERE tradeable=1"
    ).fetchone()[0]
    print(f"  Tradeable: {tradeable}")
    
    by_status = conn.execute(
        "SELECT price_status, COUNT(*) FROM catalog_price_map WHERE tradeable=1 GROUP BY price_status"
    ).fetchall()
    print(f"  By status (tradeable only):")
    for status, count in by_status:
        print(f"    {status}: {count}")
    
    # Coverage calculation
    covered = sum(c for s, c in by_status if s in ("market", "variant_fallback"))
    unknown = sum(c for s, c in by_status if s in ("heuristic_range", "unknown"))
    
    print(f"\n[Coverage (strict market-only)]")
    print(f"  Covered (market+variant): {covered} ({100*covered/tradeable:.1f}%)")
    print(f"  Unknown (heuristic+unknown): {unknown} ({100*unknown/tradeable:.1f}%)")
    
    print("\n" + "=" * 60)
    
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
