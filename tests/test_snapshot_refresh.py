"""Tests for snapshot refresh manager.

Validates: Requirements 6.5
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from d2lut.overlay.snapshot_refresh import RefreshResult, SnapshotRefreshManager


# -- fixtures ----------------------------------------------------------------


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


@pytest.fixture()
def empty_db_path(tmp_path: Path) -> Path:
    """Create a temp DB with price_estimates but no rows."""
    path = tmp_path / "empty_market.db"
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
    return path


# -- manual refresh ----------------------------------------------------------


def test_refresh_records_price_history(db_path: Path) -> None:
    """Manual refresh should record price_estimates into price_history."""
    with SnapshotRefreshManager(db_path) as mgr:
        result = mgr.refresh()

    assert result.success is True
    assert result.history_snapshots_recorded == 2
    assert result.error is None

    # Verify rows actually in price_history
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    conn.close()
    assert count == 2


def test_refresh_returns_correct_counts(db_path: Path) -> None:
    """Refresh result should report correct estimate and history counts."""
    with SnapshotRefreshManager(db_path) as mgr:
        result = mgr.refresh()

    assert result.price_estimates_count == 2
    assert result.history_snapshots_recorded == 2
    assert isinstance(result.refreshed_at, datetime)


def test_refresh_empty_estimates_returns_zero(empty_db_path: Path) -> None:
    """Refresh with no price_estimates should return 0 counts."""
    with SnapshotRefreshManager(empty_db_path) as mgr:
        result = mgr.refresh()

    assert result.success is True
    assert result.price_estimates_count == 0
    assert result.history_snapshots_recorded == 0


# -- get_last_refresh_time ---------------------------------------------------


def test_last_refresh_time_none_when_no_history(empty_db_path: Path) -> None:
    """get_last_refresh_time returns None when price_history is empty."""
    with SnapshotRefreshManager(empty_db_path) as mgr:
        assert mgr.get_last_refresh_time() is None


def test_last_refresh_time_after_refresh(db_path: Path) -> None:
    """get_last_refresh_time returns a datetime after a refresh."""
    with SnapshotRefreshManager(db_path) as mgr:
        before = datetime.now(timezone.utc)
        mgr.refresh()
        last = mgr.get_last_refresh_time()

    assert last is not None
    assert last >= before.replace(microsecond=0)


# -- periodic scheduling ----------------------------------------------------


def test_schedule_periodic_starts_and_stops(db_path: Path) -> None:
    """Periodic scheduling should start and stop cleanly."""
    with SnapshotRefreshManager(db_path) as mgr:
        mgr.schedule_periodic(interval_hours=24)
        assert mgr.is_periodic_running() is True

        mgr.stop_periodic()
        assert mgr.is_periodic_running() is False


def test_is_periodic_running_reflects_state(db_path: Path) -> None:
    """is_periodic_running should reflect the actual scheduling state."""
    with SnapshotRefreshManager(db_path) as mgr:
        assert mgr.is_periodic_running() is False

        mgr.schedule_periodic(interval_hours=1)
        assert mgr.is_periodic_running() is True

        mgr.stop_periodic()
        assert mgr.is_periodic_running() is False


def test_schedule_periodic_idempotent(db_path: Path) -> None:
    """Calling schedule_periodic twice should not create duplicate timers."""
    with SnapshotRefreshManager(db_path) as mgr:
        mgr.schedule_periodic(interval_hours=24)
        mgr.schedule_periodic(interval_hours=24)
        assert mgr.is_periodic_running() is True
        mgr.stop_periodic()
        assert mgr.is_periodic_running() is False


# -- context manager ---------------------------------------------------------


def test_context_manager_closes_cleanly(db_path: Path) -> None:
    """Context manager should stop periodic and close tracker."""
    mgr = SnapshotRefreshManager(db_path)
    mgr.schedule_periodic(interval_hours=24)
    assert mgr.is_periodic_running() is True

    mgr.__exit__(None, None, None)
    assert mgr.is_periodic_running() is False


# -- error handling ----------------------------------------------------------


def test_refresh_with_missing_table(tmp_path: Path) -> None:
    """Refresh should handle DB errors gracefully."""
    path = tmp_path / "broken.db"
    conn = sqlite3.connect(str(path))
    # Create price_history but NOT price_estimates
    conn.executescript("""
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
        );
    """)
    conn.close()

    with SnapshotRefreshManager(path) as mgr:
        result = mgr.refresh()

    assert result.success is False
    assert result.error is not None
    assert "price_estimates" in result.error.lower() or "no such table" in result.error.lower()
