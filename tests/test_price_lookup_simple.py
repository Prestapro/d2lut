"""Simple integration test for PriceLookupEngine without pytest."""

import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from d2lut.overlay.price_lookup import PriceLookupEngine, FGListing
from d2lut.models import PriceEstimate


def create_test_db():
    """Create a temporary test database with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    conn = sqlite3.connect(str(db_path))
    
    # Create schema
    conn.executescript("""
        CREATE TABLE price_estimates (
            id INTEGER PRIMARY KEY,
            market_key TEXT NOT NULL,
            variant_key TEXT NOT NULL,
            estimate_fg REAL NOT NULL,
            range_low_fg REAL NOT NULL,
            range_high_fg REAL NOT NULL,
            confidence TEXT NOT NULL,
            sample_count INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(market_key, variant_key)
        );
        
        CREATE TABLE observed_prices (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            market_key TEXT NOT NULL,
            forum_id INTEGER NOT NULL,
            thread_id INTEGER,
            post_id INTEGER,
            source_kind TEXT NOT NULL,
            signal_kind TEXT NOT NULL,
            thread_category_id INTEGER,
            thread_trade_type TEXT,
            canonical_item_id TEXT NOT NULL,
            variant_key TEXT NOT NULL,
            price_fg REAL NOT NULL,
            confidence REAL NOT NULL,
            observed_at TEXT,
            source_url TEXT,
            raw_excerpt TEXT
        );
        
        CREATE TABLE threads (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            forum_id INTEGER NOT NULL,
            thread_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            thread_category_id INTEGER,
            thread_trade_type TEXT,
            reply_count INTEGER,
            author TEXT,
            created_at TEXT,
            snapshot_id INTEGER,
            UNIQUE(source, thread_id)
        );
    """)
    
    # Insert sample data
    now = datetime.now(timezone.utc)
    conn.execute("""
        INSERT INTO price_estimates 
        (market_key, variant_key, estimate_fg, range_low_fg, range_high_fg, confidence, sample_count, updated_at)
        VALUES 
        ('d2jsp', 'rune:jah', 5000.0, 4500.0, 5500.0, 'high', 25, ?),
        ('d2jsp', 'rune:ber', 3500.0, 3200.0, 3800.0, 'high', 30, ?)
    """, (now.isoformat(), now.isoformat()))
    
    conn.execute("""
        INSERT INTO threads (source, forum_id, thread_id, url, title)
        VALUES ('d2jsp', 53, 1001, 'https://example.com/1001', 'FT: Jah Rune')
    """)
    
    recent_time = (now - timedelta(days=5)).isoformat()
    conn.execute("""
        INSERT INTO observed_prices 
        (source, market_key, forum_id, thread_id, post_id, source_kind, signal_kind, 
         canonical_item_id, variant_key, price_fg, confidence, observed_at, source_url)
        VALUES ('d2jsp', 'd2jsp', 53, 1001, 10001, 'title', 'bin', 'rune:jah', 'rune:jah', 5000.0, 0.9, ?, 'https://example.com/1001')
    """, (recent_time,))
    
    conn.commit()
    conn.close()
    
    return db_path


def test_basic_functionality():
    """Test basic PriceLookupEngine functionality."""
    print("Creating test database...")
    db_path = create_test_db()
    
    try:
        print("Testing PriceLookupEngine...")
        
        # Test initialization
        engine = PriceLookupEngine(db_path)
        print("✓ Engine initialized successfully")
        
        # Test get_price
        price = engine.get_price("rune:jah")
        assert price is not None, "Price should not be None"
        assert isinstance(price, PriceEstimate), "Should return PriceEstimate"
        assert price.variant_key == "rune:jah", "Variant key should match"
        assert price.estimate_fg == 5000.0, "Estimate should match"
        print(f"✓ get_price() works: {price.variant_key} = {price.estimate_fg} FG")
        
        # Test get_prices_for_variants
        prices = engine.get_prices_for_variants("rune")
        assert len(prices) == 2, "Should find 2 rune variants"
        assert "rune:jah" in prices, "Should include Jah"
        assert "rune:ber" in prices, "Should include Ber"
        print(f"✓ get_prices_for_variants() works: found {len(prices)} variants")
        
        # Test get_fg_listings
        listings = engine.get_fg_listings("rune:jah")
        assert len(listings) == 1, "Should find 1 listing"
        assert isinstance(listings[0], FGListing), "Should return FGListing"
        assert listings[0].price_fg == 5000.0, "Listing price should match"
        print(f"✓ get_fg_listings() works: found {len(listings)} listings")
        
        # Test get_market_summary
        summary = engine.get_market_summary("rune:jah")
        assert summary["has_data"] is True, "Should have data"
        assert summary["price_estimate"] is not None, "Should have price estimate"
        assert len(summary["listings"]) == 1, "Should have listings"
        print(f"✓ get_market_summary() works: has_data={summary['has_data']}")
        
        # Test insufficient data handling
        no_data_price = engine.get_price("nonexistent:item")
        assert no_data_price is None, "Should return None for non-existent item"
        print("✓ Insufficient data handling works")
        
        # Test context manager
        engine.close()
        print("✓ Engine closed successfully")
        
        # Test with context manager
        with PriceLookupEngine(db_path) as engine2:
            price2 = engine2.get_price("rune:jah")
            assert price2 is not None, "Should work with context manager"
        print("✓ Context manager works")
        
        print("\n✅ All tests passed!")
        
    finally:
        # Cleanup
        db_path.unlink()
        print("Test database cleaned up")


if __name__ == "__main__":
    test_basic_functionality()
