"""Tests for the refresh daemon.

Validates: Requirements 6.5, 12.1, 12.4, 12.5
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from d2lut.overlay.refresh_daemon import (
    RefreshDaemon,
    RefreshMetadata,
    RefreshStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_db(path: Path) -> None:
    """Create a minimal market DB with the tables the daemon reads."""
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS observed_prices (
            id INTEGER PRIMARY KEY,
            market_key TEXT,
            variant_key TEXT,
            price_fg REAL,
            signal_kind TEXT,
            thread_id INTEGER,
            post_id INTEGER,
            observed_at TEXT,
            source TEXT,
            source_url TEXT
        );
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
    # Seed some data
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO price_estimates
           (market_key, variant_key, estimate_fg, range_low_fg, range_high_fg,
            confidence, sample_count, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("sc_ladder", "unique:shako", 350.0, 280.0, 420.0, "high", 25, now),
    )
    conn.execute(
        """INSERT INTO observed_prices
           (market_key, variant_key, price_fg, signal_kind, thread_id,
            post_id, observed_at, source, source_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("sc_ladder", "unique:shako", 350.0, "bin", 1, 1, now, "d2jsp", None),
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test_market.db"
    _seed_db(path)
    return path


# ---------------------------------------------------------------------------
# Pipeline callable helpers
# ---------------------------------------------------------------------------


def _ok_pipeline() -> int:
    """Simulates a successful pipeline run."""
    return 0


def _fail_pipeline() -> int:
    """Simulates a failed pipeline run."""
    return 1


def _adding_pipeline(db_path: Path) -> callable:
    """Returns a callable that adds rows to the DB (simulates real pipeline)."""
    def _run() -> int:
        conn = sqlite3.connect(str(db_path))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT OR IGNORE INTO price_estimates
               (market_key, variant_key, estimate_fg, range_low_fg, range_high_fg,
                confidence, sample_count, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("sc_ladder", "rune:ber", 2800.0, 2600.0, 3000.0, "high", 40, now),
        )
        conn.execute(
            """INSERT INTO observed_prices
               (market_key, variant_key, price_fg, signal_kind, thread_id,
                post_id, observed_at, source, source_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("sc_ladder", "rune:ber", 2800.0, "bin", 2, 2, now, "d2jsp", None),
        )
        conn.commit()
        conn.close()
        return 0
    return _run


# ---------------------------------------------------------------------------
# Metadata persistence
# ---------------------------------------------------------------------------


class TestMetadataPersistence:
    """Refresh metadata is persisted to SQLite."""

    def test_successful_refresh_persists_metadata(self, db_path: Path) -> None:
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        daemon.stop()

        history = daemon.get_history(limit=5)
        assert len(history) >= 1
        latest = history[0]
        assert latest.success is True
        assert latest.finished_at is not None
        assert latest.last_error is None
        assert latest.trigger == "manual"

    def test_failed_refresh_persists_error(self, db_path: Path) -> None:
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_fail_pipeline, interval_hours=999
        )
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        daemon.stop()

        history = daemon.get_history(limit=5)
        assert len(history) >= 1
        latest = history[0]
        assert latest.success is False
        assert latest.last_error is not None
        assert "code 1" in latest.last_error.lower()

    def test_deltas_recorded_on_success(self, db_path: Path) -> None:
        pipeline = _adding_pipeline(db_path)
        daemon = RefreshDaemon(
            db_path, pipeline_callable=pipeline, interval_hours=999
        )
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        daemon.stop()

        history = daemon.get_history(limit=5)
        latest = history[0]
        assert latest.success is True
        # Pipeline added 1 obs + 1 estimate
        assert latest.observations_delta is not None
        assert latest.observations_delta >= 1
        assert latest.estimates_delta is not None
        assert latest.estimates_delta >= 1


# ---------------------------------------------------------------------------
# Status API
# ---------------------------------------------------------------------------


class TestStatusAPI:
    """get_status() exposes metadata to overlay/browser UX."""

    def test_initial_status(self, db_path: Path) -> None:
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=4
        )
        status = daemon.get_status()
        assert status.is_running is False
        assert status.last_success_at is None
        assert status.last_refresh_at is None

    def test_status_after_successful_refresh(self, db_path: Path) -> None:
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        daemon.stop()

        status = daemon.get_status()
        assert status.last_success_at is not None
        assert status.last_refresh_at is not None
        assert status.last_error is None

    def test_status_after_failed_refresh(self, db_path: Path) -> None:
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_fail_pipeline, interval_hours=999
        )
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        daemon.stop()

        status = daemon.get_status()
        assert status.last_error is not None
        assert status.last_success_at is None


# ---------------------------------------------------------------------------
# Soft-reload (cache clear callbacks)
# ---------------------------------------------------------------------------


class TestSoftReload:
    """After successful refresh, registered callbacks are fired."""

    def test_callback_fired_on_success(self, db_path: Path) -> None:
        called = []
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        daemon.on_refresh_complete(lambda: called.append(True))
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        daemon.stop()

        assert len(called) >= 1

    def test_callback_not_fired_on_failure(self, db_path: Path) -> None:
        called = []
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_fail_pipeline, interval_hours=999
        )
        daemon.on_refresh_complete(lambda: called.append(True))
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        daemon.stop()

        assert len(called) == 0

    def test_callback_exception_does_not_crash_daemon(self, db_path: Path) -> None:
        def bad_callback():
            raise RuntimeError("boom")

        daemon = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        daemon.on_refresh_complete(bad_callback)
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        # Daemon should still be alive
        assert daemon.is_running
        daemon.stop()


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


class TestScheduling:
    """Daemon runs on a configurable schedule."""

    def test_start_stop_lifecycle(self, db_path: Path) -> None:
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        assert daemon.is_running is False
        daemon.start()
        assert daemon.is_running is True
        daemon.stop()
        assert daemon.is_running is False

    def test_start_idempotent(self, db_path: Path) -> None:
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        daemon.start()
        daemon.start()  # second call should be no-op
        assert daemon.is_running is True
        daemon.stop()

    def test_context_manager(self, db_path: Path) -> None:
        with RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        ) as daemon:
            daemon.start()
            assert daemon.is_running is True
        assert daemon.is_running is False

    def test_manual_trigger(self, db_path: Path) -> None:
        daemon = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        daemon.stop()

        status = daemon.get_status()
        assert status.last_success_at is not None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Daemon is resilient to pipeline failures."""

    def test_exception_in_pipeline_callable(self, db_path: Path) -> None:
        def exploding():
            raise RuntimeError("kaboom")

        daemon = RefreshDaemon(
            db_path, pipeline_callable=exploding, interval_hours=999
        )
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        # Daemon should survive the exception
        assert daemon.is_running
        daemon.stop()

        status = daemon.get_status()
        assert status.last_error is not None
        assert "kaboom" in status.last_error

    def test_missing_tables_handled(self, tmp_path: Path) -> None:
        """Daemon handles a DB without observed_prices/price_estimates."""
        bare_db = tmp_path / "bare.db"
        conn = sqlite3.connect(str(bare_db))
        conn.close()

        daemon = RefreshDaemon(
            bare_db, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        daemon.start()
        daemon.trigger_manual()
        time.sleep(0.5)
        daemon.stop()

        # Should not crash; counts default to 0
        history = daemon.get_history(limit=5)
        assert len(history) >= 1


# ---------------------------------------------------------------------------
# History persistence across restarts
# ---------------------------------------------------------------------------


class TestHistoryPersistence:
    """Metadata survives daemon restart (persisted in SQLite)."""

    def test_history_survives_restart(self, db_path: Path) -> None:
        # First daemon run
        d1 = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        d1.start()
        d1.trigger_manual()
        time.sleep(0.5)
        d1.stop()

        # Second daemon reads persisted history
        d2 = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        history = d2.get_history(limit=5)
        assert len(history) >= 1
        assert history[0].success is True

    def test_last_state_loaded_on_start(self, db_path: Path) -> None:
        # First run
        d1 = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        d1.start()
        d1.trigger_manual()
        time.sleep(0.5)
        d1.stop()

        # Second daemon should load last state
        d2 = RefreshDaemon(
            db_path, pipeline_callable=_ok_pipeline, interval_hours=999
        )
        d2.start()
        time.sleep(0.2)  # let _load_last_state run
        status = d2.get_status()
        d2.stop()

        assert status.last_success_at is not None
