"""Integration tests for price trend display in overlay.

Task 18.2 — validates that:
- HoverState has price_trend field (default None)
- get_hover_details enriches with trend data when available
- Backward compatibility (no trend data when no history exists)
- on_hover_end resets price_trend

Requirements: 3.4
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from d2lut.overlay.overlay_app import HoverState, OverlayApp
from d2lut.overlay.config import OverlayConfig, OCRConfig
from d2lut.overlay.inventory_overlay import OverlayDetails
from d2lut.overlay.price_history import PriceTrend, PriceSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_market_db(tmp_path: Path) -> Path:
    """Create a minimal market DB with all tables needed by OverlayApp."""
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
        CREATE TABLE IF NOT EXISTS slang_aliases (
            id INTEGER PRIMARY KEY,
            term_norm TEXT NOT NULL,
            term_raw TEXT,
            canonical_item_id TEXT,
            replacement_text TEXT,
            confidence REAL DEFAULT 1.0,
            term_type TEXT DEFAULT 'alias',
            enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS catalog_items (
            canonical_item_id TEXT PRIMARY KEY,
            display_name TEXT,
            category TEXT,
            quality_class TEXT,
            base_code TEXT,
            tradeable INTEGER DEFAULT 1,
            metadata_json TEXT,
            enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS catalog_aliases (
            id INTEGER PRIMARY KEY,
            alias_norm TEXT NOT NULL,
            canonical_item_id TEXT,
            priority INTEGER DEFAULT 0
        );
    """)
    conn.close()
    return db_path


def _make_config() -> OverlayConfig:
    """Config using pytesseract (available in test env)."""
    cfg = OverlayConfig()
    cfg.ocr = OCRConfig(engine="pytesseract")
    return cfg


def _make_snapshot(median: float = 350.0) -> PriceSnapshot:
    return PriceSnapshot(
        variant_key="unique:shako",
        market_key="sc_ladder",
        recorded_at=datetime.now(timezone.utc),
        median_fg=median,
        low_fg=median * 0.8,
        high_fg=median * 1.2,
        sample_count=25,
        demand_score=None,
    )


# ---------------------------------------------------------------------------
# HoverState.price_trend field
# ---------------------------------------------------------------------------

class TestHoverStatePriceTrend:
    """HoverState has a price_trend field."""

    def test_default_none(self):
        hs = HoverState()
        assert hs.price_trend is None

    def test_assign_trend(self):
        trend = PriceTrend(
            variant_key="unique:shako",
            snapshots=[],
            stability="stable",
            price_change_pct=None,
            direction="flat",
        )
        hs = HoverState(price_trend=trend)
        assert hs.price_trend is trend
        assert hs.price_trend.stability == "stable"

    def test_assign_trend_with_snapshots(self):
        trend = PriceTrend(
            variant_key="unique:shako",
            snapshots=[_make_snapshot()],
            stability="stable",
            price_change_pct=2.0,
            direction="flat",
        )
        hs = HoverState(price_trend=trend)
        assert len(hs.price_trend.snapshots) == 1
        assert hs.price_trend.direction == "flat"


# ---------------------------------------------------------------------------
# get_hover_details enrichment with trend data
# ---------------------------------------------------------------------------

class TestGetHoverDetailsTrendEnrichment:
    """get_hover_details enriches market_activity with trend data."""

    @pytest.fixture(autouse=True)
    def setup_app(self, tmp_path):
        self.db_path = _create_market_db(tmp_path)
        self.app = OverlayApp(db_path=self.db_path, config=_make_config())
        yield
        self.app.close()

    def test_trend_data_enriched_in_hover_details(self):
        """When price_trend has snapshots, hover details include trend keys."""
        trend = PriceTrend(
            variant_key="unique:shako",
            snapshots=[_make_snapshot(350.0), _make_snapshot(320.0)],
            stability="moderate",
            price_change_pct=8.5,
            direction="rising",
        )
        self.app.state.hover_state.price_trend = trend
        self.app.state.hover_state.overlay_details = OverlayDetails(
            slot_id=0,
            item_name="Harlequin Crest",
            median_price=350.0,
            price_range=(280.0, 420.0),
            confidence="high",
            sample_count=25,
            last_updated=None,
            market_activity=None,
        )

        details = self.app.get_hover_details()
        assert details is not None
        assert details.market_activity is not None
        assert details.market_activity["price_stability"] == "moderate"
        assert details.market_activity["price_direction"] == "rising"
        assert details.market_activity["price_change_pct"] == 8.5
        assert details.market_activity["price_history_count"] == 2

    def test_no_trend_data_when_no_history(self):
        """When price_trend is None, hover details have no trend keys."""
        self.app.state.hover_state.overlay_details = OverlayDetails(
            slot_id=0,
            item_name="Harlequin Crest",
            median_price=350.0,
            price_range=(280.0, 420.0),
            confidence="high",
            sample_count=25,
            last_updated=None,
            market_activity=None,
        )
        # price_trend is None by default

        details = self.app.get_hover_details()
        assert details is not None
        if details.market_activity:
            assert "price_stability" not in details.market_activity

    def test_empty_snapshots_no_trend_keys(self):
        """When price_trend has empty snapshots, trend keys are not added."""
        trend = PriceTrend(
            variant_key="unique:shako",
            snapshots=[],
            stability="stable",
            price_change_pct=None,
            direction="flat",
        )
        self.app.state.hover_state.price_trend = trend
        self.app.state.hover_state.overlay_details = OverlayDetails(
            slot_id=0,
            item_name="Harlequin Crest",
            median_price=350.0,
            price_range=(280.0, 420.0),
            confidence="high",
            sample_count=25,
            last_updated=None,
            market_activity=None,
        )

        details = self.app.get_hover_details()
        assert details is not None
        if details.market_activity:
            assert "price_stability" not in details.market_activity


# ---------------------------------------------------------------------------
# on_hover_end resets price_trend
# ---------------------------------------------------------------------------

class TestOnHoverEndResetsTrend:
    """on_hover_end clears price_trend."""

    @pytest.fixture(autouse=True)
    def setup_app(self, tmp_path):
        self.db_path = _create_market_db(tmp_path)
        self.app = OverlayApp(db_path=self.db_path, config=_make_config())
        yield
        self.app.close()

    def test_hover_end_resets_price_trend(self):
        trend = PriceTrend(
            variant_key="unique:shako",
            snapshots=[],
            stability="stable",
            price_change_pct=None,
            direction="flat",
        )
        self.app.state.hover_state.price_trend = trend
        assert self.app.state.hover_state.price_trend is not None

        self.app.on_hover_end()
        assert self.app.state.hover_state.price_trend is None
