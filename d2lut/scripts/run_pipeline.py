#!/usr/bin/env python3
"""D2LUT Pipeline Orchestrator.

Runs the complete pipeline: collect → normalize → build filter.

Usage:
    python run_pipeline.py --forum 271 --pages 5 --output filter.filter
    python run_pipeline.py --help
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sqlite3
from statistics import median
from datetime import datetime
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def init_database(db_path: Path, schema_path: Optional[Path] = None) -> None:
    """Initialize database with schema.
    
    Args:
        db_path: Path to SQLite database file
        schema_path: Path to schema SQL file (defaults to data/schema.sql)
    """
    if schema_path is None:
        schema_path = Path(__file__).parent.parent / "data" / "schema.sql"
    
    if not schema_path.exists():
        logger.warning(f"Schema file not found: {schema_path}")
        # Create minimal schema
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS observed_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_key TEXT NOT NULL,
                price_fg REAL NOT NULL CHECK (price_fg > 0),
                signal_kind TEXT DEFAULT 'bin',
                confidence REAL DEFAULT 0.5,
                topic_id INTEGER,
                author TEXT,
                observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_estimates (
                variant_key TEXT PRIMARY KEY,
                price_fg REAL NOT NULL,
                observation_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        logger.info(f"Created minimal database: {db_path}")
        return
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    logger.info(f"Initialized database from schema: {db_path}")


async def collect_prices(
    db_path: Path,
    forum_id: int = 271,
    max_pages: int = 5,
    timeout: int = 30,
) -> int:
    """Collect prices from D2JSP forum.
    
    Args:
        db_path: Path to SQLite database
        forum_id: D2JSP forum ID
        max_pages: Maximum pages to scan
        timeout: Timeout in seconds
        
    Returns:
        Number of observations collected
    """
    try:
        from d2lut.collect.live_collector import LiveCollector, CollectorConfig
        from d2lut.patterns import find_items_in_text, find_best_price_in_text
    except ImportError:
        logger.error("d2lut package not installed. Run: pip install -e .")
        return 0
    
    config = CollectorConfig(
        forum_id=forum_id,
        max_pages=max_pages,
        timeout=timeout,
    )
    
    observations = []
    
    async with LiveCollector(config) as collector:
        result = await collector.scan_forum()
        observations = result.observations
        logger.info(
            f"Scan complete: {len(observations)} observations, "
            f"{result.pages_scanned} pages, {len(result.errors)} errors"
        )
    
    if not observations:
        logger.warning("No observations collected")
        return 0
    
    # Store in database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    inserted = 0
    for obs in observations:
        try:
            cursor.execute("""
                INSERT INTO observed_prices 
                (variant_key, price_fg, signal_kind, confidence, topic_id, author, observed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f"unique:{obs.item_name}",  # Simplified key
                obs.price_fg,
                "bin",  # Default
                obs.confidence,
                obs.topic_id,
                obs.author,
                obs.timestamp.isoformat() if obs.timestamp else None,
            ))
            inserted += 1
        except sqlite3.Error as e:
            logger.debug(f"Failed to insert observation: {e}")
    
    conn.commit()
    conn.close()
    logger.info(f"Stored {inserted} observations in database")
    
    return inserted


def update_estimates(db_path: Path) -> int:
    """Update price estimates from observations.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        Number of estimates updated
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT variant_key, price_fg, confidence, observed_at
        FROM observed_prices
        WHERE price_fg > 0
        ORDER BY variant_key, observed_at
        """
    )

    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in cursor.fetchall():
        grouped.setdefault(row["variant_key"], []).append(row)

    if not grouped:
        conn.close()
        logger.info("Updated 0 price estimates")
        return 0

    now = datetime.utcnow()
    updated = 0
    for variant_key, rows in grouped.items():
        prices = sorted(float(row["price_fg"]) for row in rows if row["price_fg"])
        if not prices:
            continue

        count = len(prices)
        trim = int(count * 0.1)
        if count < 5 or trim == 0:
            trimmed_prices = prices
        else:
            trimmed_prices = prices[trim:-trim] or prices

        median_price = float(median(prices))
        trimmed_mean = float(sum(trimmed_prices) / len(trimmed_prices))
        robust_price = (median_price * 0.6) + (trimmed_mean * 0.4)

        mean_price = float(sum(prices) / count)
        variance = sum((price - mean_price) ** 2 for price in prices) / count
        std_dev = math.sqrt(variance)

        min_price = prices[0]
        max_price = prices[-1]

        first_observed = rows[0]["observed_at"]
        last_observed = rows[-1]["observed_at"]

        last_dt = datetime.fromisoformat(last_observed) if last_observed else now
        age_hours = max((now - last_dt).total_seconds() / 3600, 0.0)
        staleness_penalty = min(age_hours / (24 * 7), 1.0)

        avg_input_conf = sum(float(row["confidence"] or 0.5) for row in rows) / count
        sample_boost = min(math.log10(count + 1) / 2, 1.0)
        confidence = max(
            0.1,
            min(1.0, (avg_input_conf * 0.5) + (sample_boost * 0.5) - (0.4 * staleness_penalty)),
        )

        if robust_price >= 500:
            tier = "GG"
        elif robust_price >= 100:
            tier = "HIGH"
        elif robust_price >= 20:
            tier = "MID"
        elif robust_price >= 5:
            tier = "LOW"
        else:
            tier = "TRASH"

        cursor.execute(
            """
            INSERT OR REPLACE INTO price_estimates (
                variant_key,
                price_fg,
                confidence,
                observation_count,
                min_price,
                max_price,
                std_dev,
                price_tier,
                first_observed,
                last_observed,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                variant_key,
                robust_price,
                confidence,
                count,
                min_price,
                max_price,
                std_dev,
                tier,
                first_observed,
                last_observed,
            ),
        )
        updated += 1

    conn.commit()
    conn.close()

    logger.info(f"Updated {updated} price estimates")
    return updated


def build_filter(
    db_path: Path,
    output_path: Path,
    preset: str = "default",
) -> bool:
    """Build loot filter from database.
    
    Args:
        db_path: Path to SQLite database
        output_path: Output filter file path
        preset: Filter preset name
        
    Returns:
        True if successful
    """
    try:
        from scripts.build_d2r_filter import FilterBuilder
    except ImportError:
        # Try direct import
        import sys
        scripts_path = Path(__file__).parent
        if str(scripts_path) not in sys.path:
            sys.path.insert(0, str(scripts_path))
        from build_d2r_filter import FilterBuilder
    
    builder = FilterBuilder(db_path=db_path, preset=preset)
    builder.load_prices()
    builder.build_filter(output_path)
    
    logger.info(f"Built filter with {builder.filtered_count} items: {output_path}")
    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="D2LUT Pipeline - collect, normalize, build filter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full pipeline with defaults
    %(prog)s --db d2lut.db --output filter.filter
    
    # Collect more pages
    %(prog)s --db d2lut.db --pages 10 --output filter.filter
    
    # Just build filter (skip collection)
    %(prog)s --db d2lut.db --output filter.filter --no-collect
        """,
    )
    
    parser.add_argument(
        "--db", "-d",
        type=Path,
        default=Path("data/d2lut.db"),
        help="Database path (default: data/d2lut.db)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("dist/d2r_filter.filter"),
        help="Output filter file (default: dist/d2r_filter.filter)",
    )
    parser.add_argument(
        "--forum", "-f",
        type=int,
        default=271,
        help="D2JSP forum ID (default: 271 for D2R Ladder)",
    )
    parser.add_argument(
        "--pages", "-p",
        type=int,
        default=5,
        help="Max pages to scan (default: 5)",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="Timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--preset",
        default="default",
        choices=["default", "roguecore", "minimal", "verbose"],
        help="Filter preset (default: default)",
    )
    parser.add_argument(
        "--no-collect",
        action="store_true",
        help="Skip collection, just build filter",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database before running",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    start_time = datetime.now()
    
    # Initialize database if needed
    if args.init_db or not args.db.exists():
        args.db.parent.mkdir(parents=True, exist_ok=True)
        init_database(args.db)
    
    # Run collection
    if not args.no_collect:
        logger.info("Starting price collection...")
        try:
            count = asyncio.run(collect_prices(
                db_path=args.db,
                forum_id=args.forum,
                max_pages=args.pages,
                timeout=args.timeout,
            ))
            if count > 0:
                update_estimates(args.db)
        except Exception as e:
            logger.error(f"Collection failed: {e}")
            return 1
    
    # Build filter
    logger.info("Building loot filter...")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not build_filter(args.db, args.output, args.preset):
        return 1
    
    elapsed = datetime.now() - start_time
    print(f"\n✅ Pipeline complete in {elapsed}")
    print(f"   Database: {args.db}")
    print(f"   Filter:   {args.output}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
