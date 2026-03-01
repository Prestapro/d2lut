"""Tests for the image recovery pipeline orchestrator.

Validates:
- Orchestrator calls each step in order
- Failures in one step don't block subsequent steps
- ImageRecoveryResult tracks errors correctly
- RefreshDaemon integration with enable_image_recovery flag

Requirements: 1.1, 2.1, 3.1, 12.1, 12.4, 12.5
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from d2lut.overlay.image_recovery_pipeline import (
    ImageRecoveryResult,
    run_image_recovery,
)
from d2lut.overlay.refresh_daemon import RefreshDaemon


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_db(path: Path) -> None:
    """Create minimal tables so RefreshDaemon and count queries work."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS observed_prices (
            id INTEGER PRIMARY KEY,
            source TEXT, market_key TEXT, forum_id INTEGER,
            thread_id INTEGER, post_id INTEGER, source_kind TEXT,
            signal_kind TEXT, thread_category_id TEXT,
            thread_trade_type TEXT, canonical_item_id TEXT,
            variant_key TEXT, price_fg REAL, confidence REAL,
            observed_at TEXT, source_url TEXT, raw_excerpt TEXT
        );
        CREATE TABLE IF NOT EXISTS price_estimates (
            id INTEGER PRIMARY KEY,
            market_key TEXT, variant_key TEXT, estimate_fg REAL,
            range_low_fg REAL, range_high_fg REAL, confidence TEXT,
            sample_count INTEGER
        );
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    _seed_db(p)
    return p


# ---------------------------------------------------------------------------
# ImageRecoveryResult
# ---------------------------------------------------------------------------

class TestImageRecoveryResult:
    def test_ok_when_no_errors(self) -> None:
        r = ImageRecoveryResult()
        assert r.ok is True

    def test_not_ok_when_errors(self) -> None:
        r = ImageRecoveryResult(errors=["boom"])
        assert r.ok is False

    def test_defaults(self) -> None:
        r = ImageRecoveryResult()
        assert r.enqueued == 0
        assert r.fetched == 0
        assert r.ocr_parsed == 0
        assert r.staged == 0
        assert r.promoted == 0
        assert r.errors == []


# ---------------------------------------------------------------------------
# Orchestrator with mocked steps
# ---------------------------------------------------------------------------

class TestRunImageRecoveryWithCallables:
    """Test the orchestrator using step_callables to mock each step."""

    def test_all_steps_succeed(self, db_path: Path) -> None:
        call_order: list[str] = []

        def make_step(name: str):
            def step():
                call_order.append(name)
                return 0
            return step

        result = run_image_recovery(
            db_path,
            quiet=True,
            step_callables={
                "enqueue": make_step("enqueue"),
                "fetch": make_step("fetch"),
                "ocr": make_step("ocr"),
                "stage": make_step("stage"),
                "promote": make_step("promote"),
            },
        )

        assert result.ok
        assert call_order == ["enqueue", "fetch", "ocr", "stage", "promote"]

    def test_step_failure_does_not_block_others(self, db_path: Path) -> None:
        call_order: list[str] = []

        def ok_step(name: str):
            def step():
                call_order.append(name)
                return 0
            return step

        def fail_step():
            call_order.append("fetch_fail")
            return 1

        result = run_image_recovery(
            db_path,
            quiet=True,
            step_callables={
                "enqueue": ok_step("enqueue"),
                "fetch": fail_step,
                "ocr": ok_step("ocr"),
                "stage": ok_step("stage"),
                "promote": ok_step("promote"),
            },
        )

        assert not result.ok
        assert len(result.errors) == 1
        assert "fetch" in result.errors[0]
        # All steps still ran
        assert call_order == ["enqueue", "fetch_fail", "ocr", "stage", "promote"]

    def test_step_exception_recorded(self, db_path: Path) -> None:
        def exploding_step():
            raise RuntimeError("OCR engine not available")

        result = run_image_recovery(
            db_path,
            quiet=True,
            step_callables={
                "enqueue": lambda: 0,
                "fetch": lambda: 0,
                "ocr": exploding_step,
                "stage": lambda: 0,
                "promote": lambda: 0,
            },
        )

        assert not result.ok
        assert len(result.errors) == 1
        assert "OCR engine not available" in result.errors[0]

    def test_multiple_failures(self, db_path: Path) -> None:
        result = run_image_recovery(
            db_path,
            quiet=True,
            step_callables={
                "enqueue": lambda: 1,
                "fetch": lambda: 1,
                "ocr": lambda: 0,
                "stage": lambda: 0,
                "promote": lambda: 1,
            },
        )

        assert not result.ok
        assert len(result.errors) == 3

    def test_missing_script_when_no_callable(self, db_path: Path, tmp_path: Path) -> None:
        """When scripts_dir points to empty dir and no callable, step fails gracefully."""
        empty_scripts = tmp_path / "empty_scripts"
        empty_scripts.mkdir()

        result = run_image_recovery(
            db_path,
            quiet=True,
            scripts_dir=empty_scripts,
        )

        # All 5 steps should fail (scripts not found)
        assert not result.ok
        assert len(result.errors) == 5
        for err in result.errors:
            assert "script not found" in err


# ---------------------------------------------------------------------------
# RefreshDaemon integration
# ---------------------------------------------------------------------------

class TestRefreshDaemonImageRecovery:
    def test_image_recovery_disabled_by_default(self, db_path: Path) -> None:
        daemon = RefreshDaemon(db_path, pipeline_callable=lambda: 0)
        assert daemon._enable_image_recovery is False

    def test_image_recovery_enabled_flag(self, db_path: Path) -> None:
        daemon = RefreshDaemon(
            db_path,
            pipeline_callable=lambda: 0,
            enable_image_recovery=True,
        )
        assert daemon._enable_image_recovery is True

    def test_image_recovery_runs_after_successful_refresh(self, db_path: Path) -> None:
        recovery_called = []

        def mock_recovery():
            recovery_called.append(True)
            return ImageRecoveryResult()

        daemon = RefreshDaemon(
            db_path,
            pipeline_callable=lambda: 0,
            enable_image_recovery=True,
            image_recovery_callable=mock_recovery,
        )
        daemon._conn = sqlite3.connect(str(db_path))
        daemon._conn.row_factory = sqlite3.Row
        RefreshDaemon._ensure_table(daemon._conn)
        _seed_db(db_path)

        daemon._run_refresh("manual")

        assert len(recovery_called) == 1

    def test_image_recovery_skipped_on_failed_refresh(self, db_path: Path) -> None:
        recovery_called = []

        def mock_recovery():
            recovery_called.append(True)
            return ImageRecoveryResult()

        daemon = RefreshDaemon(
            db_path,
            pipeline_callable=lambda: 1,  # pipeline fails
            enable_image_recovery=True,
            image_recovery_callable=mock_recovery,
        )
        daemon._conn = sqlite3.connect(str(db_path))
        daemon._conn.row_factory = sqlite3.Row
        RefreshDaemon._ensure_table(daemon._conn)
        _seed_db(db_path)

        daemon._run_refresh("manual")

        assert len(recovery_called) == 0

    def test_image_recovery_not_called_when_disabled(self, db_path: Path) -> None:
        recovery_called = []

        def mock_recovery():
            recovery_called.append(True)
            return ImageRecoveryResult()

        daemon = RefreshDaemon(
            db_path,
            pipeline_callable=lambda: 0,
            enable_image_recovery=False,
            image_recovery_callable=mock_recovery,
        )
        daemon._conn = sqlite3.connect(str(db_path))
        daemon._conn.row_factory = sqlite3.Row
        RefreshDaemon._ensure_table(daemon._conn)
        _seed_db(db_path)

        daemon._run_refresh("manual")

        assert len(recovery_called) == 0

    def test_image_recovery_failure_does_not_crash_refresh(self, db_path: Path) -> None:
        def exploding_recovery():
            raise RuntimeError("OCR libs missing")

        daemon = RefreshDaemon(
            db_path,
            pipeline_callable=lambda: 0,
            enable_image_recovery=True,
            image_recovery_callable=exploding_recovery,
        )
        daemon._conn = sqlite3.connect(str(db_path))
        daemon._conn.row_factory = sqlite3.Row
        RefreshDaemon._ensure_table(daemon._conn)
        _seed_db(db_path)

        # Should not raise
        daemon._run_refresh("manual")

        # Refresh itself was successful
        assert daemon._last_success_at is not None
