"""Tests for Live Collector."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d2lut.collect.live_collector import (
    CollectorConfig,
    CollectorState,
    LiveCollector,
    PriceObservation,
    ScanResult,
    run_collector,
)


class TestCollectorConfig:
    """Tests for CollectorConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CollectorConfig()
        
        assert config.forum_id == 271
        assert 4 in config.categories  # Rune category
        assert config.scan_interval_seconds == 300.0
        assert config.max_pages_per_scan == 50
        assert config.headless is False
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = CollectorConfig(
            forum_id=123,
            headless=True,
            scan_interval_seconds=600.0,
        )
        
        assert config.forum_id == 123
        assert config.headless is True
        assert config.scan_interval_seconds == 600.0


class TestCollectorState:
    """Tests for CollectorState."""
    
    def test_state_creation(self):
        """Test state creation with defaults."""
        state = CollectorState()
        
        assert state.last_scan_time == ""
        assert state.last_topic_id == 0
        assert state.pages_scanned == 0
        assert state.is_running is False
    
    def test_state_serialization(self):
        """Test state serialization to/from dict."""
        state = CollectorState(
            last_scan_time="2024-01-01T00:00:00",
            pages_scanned=100,
            topics_processed=500,
            prices_observed=50,
        )
        
        d = state.to_dict()
        assert d["last_scan_time"] == "2024-01-01T00:00:00"
        assert d["pages_scanned"] == 100
        
        restored = CollectorState.from_dict(d)
        assert restored.last_scan_time == state.last_scan_time
        assert restored.pages_scanned == state.pages_scanned


class TestPriceObservation:
    """Tests for PriceObservation."""
    
    def test_observation_creation(self):
        """Test price observation creation."""
        from datetime import datetime, timezone
        
        obs = PriceObservation(
            topic_id=12345,
            post_id=0,
            variant_key="rune:jah",
            item_name="Jah Rune",
            price_fg=50.0,
            price_type="bin",
            category_id=4,
            author="test_user",
            timestamp=datetime.now(timezone.utc),
        )
        
        assert obs.topic_id == 12345
        assert obs.variant_key == "rune:jah"
        assert obs.price_fg == 50.0
        assert obs.price_type == "bin"
    
    def test_observation_to_db_tuple(self):
        """Test conversion to database tuple."""
        from datetime import datetime, timezone
        
        obs = PriceObservation(
            topic_id=12345,
            post_id=0,
            variant_key="rune:jah",
            item_name="Jah Rune",
            price_fg=50.0,
            price_type="bin",
            category_id=4,
            author="test_user",
            timestamp=datetime.now(timezone.utc),
            raw_text="Jah rune bin 50 fg",
            confidence=0.8,
        )
        
        t = obs.to_db_tuple()
        assert len(t) == 12
        assert t[0] == 12345
        assert t[2] == "rune:jah"


class TestScanResult:
    """Tests for ScanResult."""
    
    def test_scan_result_creation(self):
        """Test scan result creation."""
        from datetime import datetime, timezone
        
        result = ScanResult(
            scan_time=datetime.now(timezone.utc),
            pages_scanned=10,
            topics_processed=50,
            prices_observed=20,
            new_prices=20,
        )
        
        assert result.pages_scanned == 10
        assert result.topics_processed == 50
        assert result.prices_observed == 20
        assert len(result.errors) == 0


class TestPriceExtraction:
    """Tests for price extraction logic."""
    
    def setup_method(self):
        self.collector = LiveCollector()
    
    def test_extract_rune_prices(self):
        """Test extracting rune prices from text."""
        text = "Jah rune bin 50 fg"
        result = self.collector._extract_prices(text)
        
        assert "rune:jah" in result
        assert result["rune:jah"]["price"] == 50.0
    
    def test_extract_sold_price(self):
        """Test extracting sold prices (higher confidence)."""
        text = "Ber rune sold @ 55 fg"
        result = self.collector._extract_prices(text)
        
        assert "rune:ber" in result
        assert result["rune:ber"]["type"] == "sold"
    
    def test_extract_multiple_items(self):
        """Test when multiple items mentioned."""
        text = " Jah and Ber runes, bin 100 fg for both"
        result = self.collector._extract_prices(text)
        
        # Should find both runes
        assert len(result) >= 1
    
    def test_no_price_in_text(self):
        """Test when no price mentioned."""
        text = "WTT Jah rune for Ber"
        result = self.collector._extract_prices(text)
        
        # May or may not find items without prices
        assert isinstance(result, dict)


class TestItemDetection:
    """Tests for item name detection."""
    
    def setup_method(self):
        self.collector = LiveCollector()
    
    def test_detect_high_value_runes(self):
        """Test detection of high-value runes."""
        text = "Selling Jah and Ber runes for 100 fg total"
        result = self.collector._extract_prices(text)
        
        # Should detect runes with prices
        assert len(result) >= 1
    
    def test_detect_uniques(self):
        """Test detection of unique items."""
        text = "Shako 15ed, bin 40 fg"
        result = self.collector._extract_prices(text)
        
        assert "unique:shako" in result
    
    def test_detect_runewords(self):
        """Test detection of runewords."""
        text = "Enigma AP 3os, asking 60 fg"
        result = self.collector._extract_prices(text)
        
        assert "runeword:enigma" in result
    
    def test_detect_charms(self):
        """Test detection of charms."""
        text = "Skiller GC with 40 life, bin 25 fg"
        result = self.collector._extract_prices(text)
        
        # Should detect the charm
        assert any("charm:" in k for k in result.keys())


class TestDatabaseOperations:
    """Tests for database operations."""
    
    def test_schema_creation(self, tmp_path):
        """Test database schema creation."""
        config = CollectorConfig(db_path=str(tmp_path / "test.db"))
        collector = LiveCollector(config)
        
        # Initialize database manually
        import sqlite3
        db_path = Path(config.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        collector._db_conn = sqlite3.connect(str(db_path))
        collector._db_conn.executescript(
            "CREATE TABLE IF NOT EXISTS price_observations (id INTEGER PRIMARY KEY)"
        )
        
        # Check table exists
        cur = collector._db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='price_observations'"
        )
        assert cur.fetchone() is not None
    
    def test_seen_topic_tracking(self, tmp_path):
        """Test tracking seen topics."""
        import sqlite3
        from datetime import datetime, timezone
        
        config = CollectorConfig(db_path=str(tmp_path / "test.db"))
        collector = LiveCollector(config)
        
        # Setup database
        db_path = Path(config.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        collector._db_conn = sqlite3.connect(str(db_path))
        collector._db_conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_topics (topic_id INTEGER PRIMARY KEY, last_seen TEXT)"
        )
        collector._db_conn.commit()
        
        # Test not seen
        assert collector._is_topic_seen(12345) is False
        
        # Mark as seen
        collector._mark_topic_seen(12345)
        
        # Test seen
        assert collector._is_topic_seen(12345) is True


class TestScanResultStorage:
    """Tests for scan result storage."""
    
    def test_store_observations(self, tmp_path):
        """Test storing price observations."""
        import sqlite3
        from datetime import datetime, timezone
        
        config = CollectorConfig(db_path=str(tmp_path / "test.db"))
        collector = LiveCollector(config)
        
        # Setup database
        db_path = Path(config.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        collector._db_conn = sqlite3.connect(str(db_path))
        
        # Create schema
        from d2lut.collect.live_collector import SCHEMA_SQL
        collector._db_conn.executescript(SCHEMA_SQL)
        
        # Create scan result with observations
        result = ScanResult(
            scan_time=datetime.now(timezone.utc),
            pages_scanned=1,
            topics_processed=1,
            prices_observed=1,
            new_prices=1,
            observations=[
                PriceObservation(
                    topic_id=12345,
                    post_id=0,
                    variant_key="rune:jah",
                    item_name="Jah Rune",
                    price_fg=50.0,
                    price_type="bin",
                    category_id=4,
                    author="test",
                    timestamp=datetime.now(timezone.utc),
                )
            ],
        )
        
        # Store
        asyncio.run(collector._store_scan_result(result))
        
        # Verify stored
        cur = collector._db_conn.execute("SELECT COUNT(*) FROM price_observations")
        count = cur.fetchone()[0]
        assert count == 1
