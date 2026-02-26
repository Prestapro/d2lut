"""Tests for price history tracking module.

Validates: Requirements 3.4, 11.4
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from d2lut.overlay.price_history import (
    PriceHistoryTracker,
    PriceSnapshot,
    PriceTrend,
)


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Create a temp DB with price_estimates seeded."""
    path = tmp_path / "test_market.db"
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS price_estimates (
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
    """)
    conn.execute(
        """INSERT INTO price_estimates
           (market_key, variant_key, estimate_fg, range_low_fg, range_high_fg,
            confidence, sample_count, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("sc_ladder", "unique:shako", 350.0, 280.0, 420.0, "high", 25,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.execute(
        """INSERT INTO price_estimates
           (market_key, variant_key, estimate_fg, range_low_fg, range_high_fg,
            confidence, sample_count, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("sc_ladder", "rune:ber", 2800.0, 2600.0, 3000.0, "high", 40,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
    return path


# -- record_snapshot --------------------------------------------------------

def test_record_snapshot_inserts_row(db_path: Path) -> None:
    with PriceHistoryTracker(db_path) as tracker:
        tracker.record_snapshot(
            variant_key="unique:shako",
            market_key="sc_ladder",
            median_fg=350.0,
            low_fg=280.0,
            high_fg=420.0,
            sample_count=25,
            demand_score=0.7,
        )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM price_history").fetchall()
    conn.close()

    assert len(rows) == 1
    r = rows[0]
    assert r["variant_key"] == "unique:shako"
    assert r["market_key"] == "sc_ladder"
    assert r["median_fg"] == 350.0
    assert r["low_fg"] == 280.0
    assert r["high_fg"] == 420.0
    assert r["sample_count"] == 25
    assert r["demand_score"] == 0.7
    assert r["recorded_at"] is not None


def test_record_snapshot_demand_score_none(db_path: Path) -> None:
    with PriceHistoryTracker(db_path) as tracker:
        tracker.record_snapshot(
            variant_key="rune:ber",
            market_key="sc_ladder",
            median_fg=2800.0,
            low_fg=2600.0,
            high_fg=3000.0,
            sample_count=40,
        )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM price_history").fetchone()
    conn.close()

    assert row["demand_score"] is None


# -- record_all_current -----------------------------------------------------

def test_record_all_current_snapshots_price_estimates(db_path: Path) -> None:
    with PriceHistoryTracker(db_path) as tracker:
        count = tracker.record_all_current()

    assert count == 2

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT * FROM price_history").fetchall()
    conn.close()
    assert len(rows) == 2


def test_record_all_current_empty_estimates(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS price_estimates (
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
    """)
    conn.commit()
    conn.close()

    with PriceHistoryTracker(path) as tracker:
        count = tracker.record_all_current()

    assert count == 0


# -- get_history ------------------------------------------------------------

def test_get_history_returns_recent_snapshots(db_path: Path) -> None:
    with PriceHistoryTracker(db_path) as tracker:
        tracker.record_snapshot("unique:shako", "sc_ladder", 350.0, 280.0, 420.0, 25)
        tracker.record_snapshot("unique:shako", "sc_ladder", 360.0, 290.0, 430.0, 26)

        history = tracker.get_history("unique:shako", days=30)

    assert len(history) == 2
    assert all(isinstance(s, PriceSnapshot) for s in history)
    # Newest first
    assert history[0].median_fg == 360.0
    assert history[1].median_fg == 350.0


def test_get_history_excludes_old_snapshots(db_path: Path) -> None:
    """Manually insert an old row and verify it's excluded."""
    conn = sqlite3.connect(str(db_path))
    old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY,
            market_key TEXT NOT NULL,
            variant_key TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            median_fg REAL NOT NULL,
            low_fg REAL NOT NULL,
            high_fg REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            demand_score REAL
        )
    """)
    conn.execute(
        """INSERT INTO price_history
           (market_key, variant_key, recorded_at, median_fg, low_fg, high_fg,
            sample_count, demand_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, NULL)""",
        ("sc_ladder", "unique:shako", old_date, 300.0, 250.0, 350.0, 20),
    )
    conn.commit()
    conn.close()

    with PriceHistoryTracker(db_path) as tracker:
        tracker.record_snapshot("unique:shako", "sc_ladder", 360.0, 290.0, 430.0, 26)
        history = tracker.get_history("unique:shako", days=30)

    assert len(history) == 1
    assert history[0].median_fg == 360.0


def test_get_history_empty(db_path: Path) -> None:
    with PriceHistoryTracker(db_path) as tracker:
        history = tracker.get_history("nonexistent:item", days=30)

    assert history == []


# -- calculate_stability ----------------------------------------------------

def test_stability_stable() -> None:
    """Low variance → stable."""
    snapshots = [
        _snap(100.0), _snap(101.0), _snap(99.0), _snap(100.5), _snap(100.2),
    ]
    assert PriceHistoryTracker.calculate_stability(snapshots) == "stable"


def test_stability_moderate() -> None:
    """Moderate variance → moderate (CV between 0.10 and 0.25)."""
    snapshots = [
        _snap(100.0), _snap(125.0), _snap(80.0), _snap(110.0), _snap(85.0),
    ]
    assert PriceHistoryTracker.calculate_stability(snapshots) == "moderate"


def test_stability_volatile() -> None:
    """High variance → volatile."""
    snapshots = [
        _snap(100.0), _snap(200.0), _snap(50.0), _snap(180.0), _snap(60.0),
    ]
    assert PriceHistoryTracker.calculate_stability(snapshots) == "volatile"


def test_stability_single_snapshot() -> None:
    """Single snapshot defaults to stable."""
    assert PriceHistoryTracker.calculate_stability([_snap(100.0)]) == "stable"


def test_stability_empty() -> None:
    assert PriceHistoryTracker.calculate_stability([]) == "stable"


# -- calculate_direction ----------------------------------------------------

def test_direction_rising() -> None:
    # Newest first in list (DESC order)
    snapshots = [_snap(120.0), _snap(100.0)]
    direction, pct = PriceHistoryTracker.calculate_direction(snapshots)
    assert direction == "rising"
    assert pct == 20.0


def test_direction_falling() -> None:
    snapshots = [_snap(80.0), _snap(100.0)]
    direction, pct = PriceHistoryTracker.calculate_direction(snapshots)
    assert direction == "falling"
    assert pct == -20.0


def test_direction_flat() -> None:
    snapshots = [_snap(102.0), _snap(100.0)]
    direction, pct = PriceHistoryTracker.calculate_direction(snapshots)
    assert direction == "flat"
    assert pct == 2.0


def test_direction_single_snapshot() -> None:
    direction, pct = PriceHistoryTracker.calculate_direction([_snap(100.0)])
    assert direction == "flat"
    assert pct is None


def test_direction_empty() -> None:
    direction, pct = PriceHistoryTracker.calculate_direction([])
    assert direction == "flat"
    assert pct is None


# -- get_trend --------------------------------------------------------------

def test_get_trend_combines_stability_and_direction(db_path: Path) -> None:
    with PriceHistoryTracker(db_path) as tracker:
        tracker.record_snapshot("unique:shako", "sc_ladder", 350.0, 280.0, 420.0, 25)
        tracker.record_snapshot("unique:shako", "sc_ladder", 352.0, 282.0, 422.0, 26)

        trend = tracker.get_trend("unique:shako", days=30)

    assert isinstance(trend, PriceTrend)
    assert trend.variant_key == "unique:shako"
    assert len(trend.snapshots) == 2
    assert trend.stability == "stable"
    assert trend.direction == "flat"


def test_get_trend_empty_history(db_path: Path) -> None:
    with PriceHistoryTracker(db_path) as tracker:
        trend = tracker.get_trend("nonexistent:item", days=30)

    assert trend.snapshots == []
    assert trend.stability == "stable"
    assert trend.direction == "flat"
    assert trend.price_change_pct is None


# -- context manager --------------------------------------------------------

def test_context_manager(db_path: Path) -> None:
    with PriceHistoryTracker(db_path) as tracker:
        tracker.record_snapshot("unique:shako", "sc_ladder", 350.0, 280.0, 420.0, 25)

    # Connection should be closed; verify data persisted
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT * FROM price_history").fetchall()
    conn.close()
    assert len(rows) == 1


# -- helpers ----------------------------------------------------------------

def _snap(median: float) -> PriceSnapshot:
    """Create a minimal PriceSnapshot for unit tests."""
    return PriceSnapshot(
        variant_key="test",
        market_key="sc_ladder",
        recorded_at=datetime.now(timezone.utc),
        median_fg=median,
        low_fg=median * 0.8,
        high_fg=median * 1.2,
        sample_count=10,
        demand_score=None,
    )
