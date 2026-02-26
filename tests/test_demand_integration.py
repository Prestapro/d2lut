"""Integration tests for demand metrics in PriceEstimate and overlay wiring.

Task 17.2 — validates that:
- PriceEstimate accepts demand_score and observed_velocity
- Backward compatibility (PriceEstimate without demand fields still works)
- overlay_app enriches hover details with demand metrics
- PriceLookupEngine optionally enriches via demand_model
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from d2lut.models import PriceEstimate
from d2lut.overlay.demand_model import DemandModel, DemandMetrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_market_db(tmp_path: Path) -> Path:
    """Create a minimal market DB with schema for demand + price lookups."""
    db_path = tmp_path / "market.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS observed_prices (
            id INTEGER PRIMARY KEY,
            source TEXT DEFAULT 'd2jsp',
            thread_id INTEGER DEFAULT 1,
            post_id INTEGER,
            market_key TEXT,
            variant_key TEXT,
            canonical_item_id TEXT,
            price_fg REAL,
            signal_kind TEXT,
            thread_trade_type TEXT,
            observed_at TEXT,
            source_url TEXT
        );
        CREATE TABLE IF NOT EXISTS price_estimates (
            market_key TEXT,
            variant_key TEXT PRIMARY KEY,
            estimate_fg REAL,
            range_low_fg REAL,
            range_high_fg REAL,
            confidence TEXT,
            sample_count INTEGER,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS threads (
            source TEXT DEFAULT 'd2jsp',
            thread_id INTEGER PRIMARY KEY,
            title TEXT,
            context_kind TEXT
        );
    """)
    conn.close()
    return db_path


def _seed_price_estimate(db_path: Path, variant_key: str, estimate_fg: float) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO price_estimates
           (market_key, variant_key, estimate_fg, range_low_fg, range_high_fg,
            confidence, sample_count, updated_at)
           VALUES (?, ?, ?, ?, ?, 'medium', 5, ?)""",
        (variant_key, variant_key, estimate_fg, estimate_fg * 0.8,
         estimate_fg * 1.2, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def _insert_observation(
    db_path: Path,
    variant_key: str,
    signal_kind: str = "bin",
    trade_type: str = "ft",
    days_ago: int = 0,
) -> None:
    conn = sqlite3.connect(str(db_path))
    obs_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    conn.execute(
        """INSERT INTO observed_prices
           (variant_key, market_key, canonical_item_id, price_fg,
            signal_kind, thread_trade_type, observed_at)
           VALUES (?, ?, ?, 100.0, ?, ?, ?)""",
        (variant_key, variant_key, variant_key, signal_kind, trade_type, obs_date),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# PriceEstimate field tests
# ---------------------------------------------------------------------------

class TestPriceEstimateDemandFields:
    """Verify PriceEstimate accepts demand_score and observed_velocity."""

    def test_defaults_are_none(self):
        pe = PriceEstimate(
            variant_key="rune:jah",
            estimate_fg=3000.0,
            range_low_fg=2500.0,
            range_high_fg=3500.0,
            confidence="high",
            sample_count=20,
            last_updated=datetime.now(),
        )
        assert pe.demand_score is None
        assert pe.observed_velocity is None

    def test_explicit_values(self):
        pe = PriceEstimate(
            variant_key="rune:ber",
            estimate_fg=2800.0,
            range_low_fg=2400.0,
            range_high_fg=3200.0,
            confidence="medium",
            sample_count=10,
            last_updated=datetime.now(),
            demand_score=0.75,
            observed_velocity=1.5,
        )
        assert pe.demand_score == 0.75
        assert pe.observed_velocity == 1.5

    def test_backward_compat_positional(self):
        """Existing code that creates PriceEstimate with 7 positional args still works."""
        pe = PriceEstimate(
            "rune:vex", 500.0, 400.0, 600.0, "low", 3, datetime.now()
        )
        assert pe.variant_key == "rune:vex"
        assert pe.demand_score is None
        assert pe.observed_velocity is None

    def test_mutation(self):
        """demand_score and observed_velocity can be set after construction."""
        pe = PriceEstimate(
            variant_key="unique:shako",
            estimate_fg=1200.0,
            range_low_fg=1000.0,
            range_high_fg=1400.0,
            confidence="high",
            sample_count=15,
            last_updated=datetime.now(),
        )
        pe.demand_score = 0.6
        pe.observed_velocity = 0.8
        assert pe.demand_score == 0.6
        assert pe.observed_velocity == 0.8


# ---------------------------------------------------------------------------
# PriceLookupEngine demand_model integration
# ---------------------------------------------------------------------------

class TestPriceLookupDemandIntegration:
    """PriceLookupEngine.get_price() optionally enriches via demand_model."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        self.db_path = _create_market_db(tmp_path)
        _seed_price_estimate(self.db_path, "rune:jah", 3000.0)
        # Add some observations so demand model has data
        for i in range(5):
            _insert_observation(self.db_path, "rune:jah", "bin", "ft", days_ago=i)
        for i in range(3):
            _insert_observation(self.db_path, "rune:jah", "bin", "iso", days_ago=i)

    def test_get_price_without_demand_model(self):
        from d2lut.overlay.price_lookup import PriceLookupEngine

        engine = PriceLookupEngine(self.db_path)
        pe = engine.get_price("rune:jah")
        assert pe is not None
        assert pe.demand_score is None
        assert pe.observed_velocity is None
        engine.close()

    def test_get_price_with_demand_model(self):
        from d2lut.overlay.price_lookup import PriceLookupEngine

        engine = PriceLookupEngine(self.db_path)
        dm = DemandModel(self.db_path)
        pe = engine.get_price("rune:jah", demand_model=dm)
        assert pe is not None
        assert pe.demand_score is not None
        assert pe.observed_velocity is not None
        assert 0.0 <= pe.demand_score <= 1.0
        assert pe.observed_velocity >= 0.0
        dm.close()
        engine.close()

    def test_get_market_summary_with_demand_model(self):
        from d2lut.overlay.price_lookup import PriceLookupEngine

        engine = PriceLookupEngine(self.db_path)
        dm = DemandModel(self.db_path)
        summary = engine.get_market_summary("rune:jah", demand_model=dm)
        pe = summary["price_estimate"]
        assert pe is not None
        assert pe.demand_score is not None
        dm.close()
        engine.close()


# ---------------------------------------------------------------------------
# HoverState demand_metrics field
# ---------------------------------------------------------------------------

class TestHoverStateDemandMetrics:
    """HoverState has a demand_metrics field."""

    def test_default_none(self):
        from d2lut.overlay.overlay_app import HoverState

        hs = HoverState()
        assert hs.demand_metrics is None

    def test_assign_metrics(self):
        from d2lut.overlay.overlay_app import HoverState

        dm = DemandMetrics(
            demand_score=0.7,
            observed_velocity=1.2,
            iso_count=7,
            ft_count=3,
            sold_count=2,
            total_observations=12,
            time_window_days=14,
            market_heat="hot",
        )
        hs = HoverState(demand_metrics=dm)
        assert hs.demand_metrics is dm
        assert hs.demand_metrics.market_heat == "hot"
