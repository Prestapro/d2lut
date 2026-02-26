"""Tests for PriceLookupEngine."""

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from d2lut.models import PriceEstimate
from d2lut.overlay.price_lookup import FGListing, PriceLookupEngine


@pytest.fixture
def test_db():
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
    
    # Insert sample price estimates
    now = datetime.now(timezone.utc)
    conn.execute("""
        INSERT INTO price_estimates 
        (market_key, variant_key, estimate_fg, range_low_fg, range_high_fg, confidence, sample_count, updated_at)
        VALUES 
        ('d2jsp', 'rune:jah', 5000.0, 4500.0, 5500.0, 'high', 25, ?),
        ('d2jsp', 'rune:ber', 3500.0, 3200.0, 3800.0, 'high', 30, ?),
        ('d2jsp', 'charm:gheed', 150.0, 100.0, 200.0, 'medium', 8, ?),
        ('d2jsp', 'unique:shako', 800.0, 700.0, 900.0, 'high', 50, ?)
    """, (now.isoformat(), now.isoformat(), now.isoformat(), now.isoformat()))
    
    # Insert sample threads
    conn.execute("""
        INSERT INTO threads (source, forum_id, thread_id, url, title)
        VALUES 
        ('d2jsp', 53, 1001, 'https://example.com/1001', 'FT: Jah Rune'),
        ('d2jsp', 53, 1002, 'https://example.com/1002', 'ISO: Ber Rune'),
        ('d2jsp', 53, 1003, 'https://example.com/1003', 'FT: Gheeds Fortune Charm')
    """)
    
    # Insert sample observed prices
    recent_time = (now - timedelta(days=5)).isoformat()
    old_time = (now - timedelta(days=45)).isoformat()
    
    conn.executemany("""
        INSERT INTO observed_prices 
        (source, market_key, forum_id, thread_id, post_id, source_kind, signal_kind, 
         canonical_item_id, variant_key, price_fg, confidence, observed_at, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ('d2jsp', 'd2jsp', 53, 1001, 10001, 'title', 'bin', 'rune:jah', 'rune:jah', 5000.0, 0.9, recent_time, 'https://example.com/1001'),
        ('d2jsp', 'd2jsp', 53, 1001, 10002, 'post', 'bin', 'rune:jah', 'rune:jah', 4800.0, 0.85, recent_time, 'https://example.com/1001'),
        ('d2jsp', 'd2jsp', 53, 1001, 10003, 'post', 'sold', 'rune:jah', 'rune:jah', 4900.0, 0.95, old_time, 'https://example.com/1001'),
        ('d2jsp', 'd2jsp', 53, 1002, 10004, 'title', 'ask', 'rune:ber', 'rune:ber', 3600.0, 0.8, recent_time, 'https://example.com/1002'),
        ('d2jsp', 'd2jsp', 53, 1003, 10005, 'title', 'bin', 'charm:gheed', 'charm:gheed', 150.0, 0.7, recent_time, 'https://example.com/1003'),
    ])
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    db_path.unlink()


def test_price_lookup_engine_init(test_db):
    """Test PriceLookupEngine initialization."""
    engine = PriceLookupEngine(test_db)
    assert engine.db_path == test_db
    engine.close()


def test_price_lookup_engine_init_missing_db():
    """Test PriceLookupEngine initialization with missing database."""
    with pytest.raises(FileNotFoundError):
        PriceLookupEngine("/nonexistent/path/to/db.db")


def test_get_price_basic(test_db):
    """Test basic price lookup."""
    with PriceLookupEngine(test_db) as engine:
        price = engine.get_price("rune:jah")
        
        assert price is not None
        assert isinstance(price, PriceEstimate)
        assert price.variant_key == "rune:jah"
        assert price.estimate_fg == 5000.0
        assert price.range_low_fg == 4500.0
        assert price.range_high_fg == 5500.0
        assert price.confidence == "high"
        assert price.sample_count == 25


def test_get_price_with_variant(test_db):
    """Test price lookup with explicit variant."""
    with PriceLookupEngine(test_db) as engine:
        price = engine.get_price("rune", variant="rune:ber")
        
        assert price is not None
        assert price.variant_key == "rune:ber"
        assert price.estimate_fg == 3500.0


def test_get_price_not_found(test_db):
    """Test price lookup for non-existent item."""
    with PriceLookupEngine(test_db) as engine:
        price = engine.get_price("nonexistent:item")
        
        assert price is None


def test_get_prices_for_variants(test_db):
    """Test getting prices for all variants of an item."""
    with PriceLookupEngine(test_db) as engine:
        prices = engine.get_prices_for_variants("rune")
        
        assert len(prices) == 2
        assert "rune:jah" in prices
        assert "rune:ber" in prices
        
        # Should be sorted by price descending
        keys = list(prices.keys())
        assert prices[keys[0]].estimate_fg >= prices[keys[1]].estimate_fg


def test_get_prices_for_variants_single(test_db):
    """Test getting prices for item with single variant."""
    with PriceLookupEngine(test_db) as engine:
        prices = engine.get_prices_for_variants("charm:gheed")
        
        assert len(prices) == 1
        assert "charm:gheed" in prices


def test_get_prices_for_variants_none(test_db):
    """Test getting prices for non-existent item."""
    with PriceLookupEngine(test_db) as engine:
        prices = engine.get_prices_for_variants("nonexistent")
        
        assert len(prices) == 0


def test_get_fg_listings_basic(test_db):
    """Test getting FG listings."""
    with PriceLookupEngine(test_db) as engine:
        listings = engine.get_fg_listings("rune:jah")
        
        assert len(listings) == 3
        assert all(isinstance(l, FGListing) for l in listings)
        
        # Should be sorted by most recent first
        assert listings[0].posted_at >= listings[1].posted_at


def test_get_fg_listings_with_limit(test_db):
    """Test getting FG listings with limit."""
    with PriceLookupEngine(test_db) as engine:
        listings = engine.get_fg_listings("rune:jah", limit=2)
        
        assert len(listings) == 2


def test_get_fg_listings_recent_flag(test_db):
    """Test that is_recent flag is set correctly."""
    with PriceLookupEngine(test_db) as engine:
        listings = engine.get_fg_listings("rune:jah", recent_days=30)
        
        # Should have 2 recent and 1 old listing
        recent_count = sum(1 for l in listings if l.is_recent)
        old_count = sum(1 for l in listings if not l.is_recent)
        
        assert recent_count == 2
        assert old_count == 1


def test_get_fg_listings_types(test_db):
    """Test that listing types are correctly identified."""
    with PriceLookupEngine(test_db) as engine:
        listings = engine.get_fg_listings("rune:jah")
        
        listing_types = {l.listing_type for l in listings}
        assert "bin" in listing_types
        assert "sold" in listing_types


def test_get_fg_listings_thread_info(test_db):
    """Test that thread information is included in listings."""
    with PriceLookupEngine(test_db) as engine:
        listings = engine.get_fg_listings("rune:jah")
        
        # At least one listing should have thread title
        assert any(l.thread_title is not None for l in listings)
        assert any(l.source_url is not None for l in listings)


def test_get_fg_listings_empty(test_db):
    """Test getting FG listings for item with no observations."""
    with PriceLookupEngine(test_db) as engine:
        listings = engine.get_fg_listings("nonexistent:item")
        
        assert len(listings) == 0


def test_get_market_summary_with_data(test_db):
    """Test getting comprehensive market summary."""
    with PriceLookupEngine(test_db) as engine:
        summary = engine.get_market_summary("rune:jah")
        
        assert summary["item_id"] == "rune:jah"
        assert summary["variant_key"] == "rune:jah"
        assert summary["has_data"] is True
        
        # Check price estimate
        assert summary["price_estimate"] is not None
        assert summary["price_estimate"].estimate_fg == 5000.0
        
        # Check listings
        assert len(summary["listings"]) == 3
        
        # Check market activity
        activity = summary["market_activity"]
        assert activity["total_listings"] == 3
        assert activity["recent_listings"] == 2
        assert activity["bin_count"] == 2
        assert activity["sold_count"] == 1
        assert activity["has_active_market"] is True


def test_get_market_summary_no_data(test_db):
    """Test getting market summary for item with no data."""
    with PriceLookupEngine(test_db) as engine:
        summary = engine.get_market_summary("nonexistent:item")
        
        assert summary["has_data"] is False
        assert summary["price_estimate"] is None
        assert len(summary["listings"]) == 0
        
        activity = summary["market_activity"]
        assert activity["total_listings"] == 0
        assert activity["has_active_market"] is False


def test_context_manager(test_db):
    """Test using PriceLookupEngine as context manager."""
    with PriceLookupEngine(test_db) as engine:
        price = engine.get_price("rune:jah")
        assert price is not None
    
    # Connection should be closed after context exit
    # Attempting to query an uncached item should fail
    with pytest.raises(sqlite3.ProgrammingError):
        engine.get_price("rune:ber")


def test_insufficient_data_handling(test_db):
    """Test graceful handling of insufficient data cases."""
    with PriceLookupEngine(test_db) as engine:
        # Non-existent item
        price = engine.get_price("nonexistent:item")
        assert price is None
        
        # Empty listings
        listings = engine.get_fg_listings("nonexistent:item")
        assert listings == []
        
        # Market summary with no data
        summary = engine.get_market_summary("nonexistent:item")
        assert summary["has_data"] is False
        assert summary["price_estimate"] is None


def test_variant_specific_pricing(test_db):
    """Test that variant-specific pricing works correctly."""
    with PriceLookupEngine(test_db) as engine:
        # Get specific variant
        jah_price = engine.get_price("rune", variant="rune:jah")
        ber_price = engine.get_price("rune", variant="rune:ber")
        
        assert jah_price is not None
        assert ber_price is not None
        assert jah_price.estimate_fg != ber_price.estimate_fg
        assert jah_price.estimate_fg > ber_price.estimate_fg  # Jah is more expensive


def test_price_estimate_fields(test_db):
    """Test that all PriceEstimate fields are populated correctly."""
    with PriceLookupEngine(test_db) as engine:
        price = engine.get_price("unique:shako")
        
        assert price is not None
        assert price.variant_key == "unique:shako"
        assert isinstance(price.estimate_fg, float)
        assert isinstance(price.range_low_fg, float)
        assert isinstance(price.range_high_fg, float)
        assert isinstance(price.confidence, str)
        assert isinstance(price.sample_count, int)
        assert isinstance(price.last_updated, datetime)
        
        # Validate ranges
        assert price.range_low_fg <= price.estimate_fg <= price.range_high_fg


def test_fg_listing_fields(test_db):
    """Test that all FGListing fields are populated correctly."""
    with PriceLookupEngine(test_db) as engine:
        listings = engine.get_fg_listings("rune:jah")
        
        assert len(listings) > 0
        
        for listing in listings:
            assert isinstance(listing.price_fg, float)
            assert isinstance(listing.listing_type, str)
            assert isinstance(listing.thread_id, int)
            assert isinstance(listing.is_recent, bool)
            
            # Optional fields
            if listing.posted_at is not None:
                assert isinstance(listing.posted_at, datetime)
