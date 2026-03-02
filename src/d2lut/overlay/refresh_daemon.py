"""Live/near-real-time market refresh daemon.

Runs incremental market refresh on a configurable schedule:
  snapshot fetch -> parse -> estimate rebuild

Persists refresh metadata to SQLite and supports soft-reload of prices
in the overlay without a full restart.

Requirements: 6.5, 12.1, 12.4, 12.5
"""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_REFRESH_METADATA_SQL = """
CREATE TABLE IF NOT EXISTS refresh_metadata (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    success INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    observations_before INTEGER,
    observations_after INTEGER,
    estimates_before INTEGER,
    estimates_after INTEGER,
    observations_delta INTEGER,
    estimates_delta INTEGER,
    trigger TEXT NOT NULL DEFAULT 'scheduled'
);
"""

_CREATE_REFRESH_METADATA_INDEX = """
CREATE INDEX IF NOT EXISTS idx_refresh_metadata_finished
    ON refresh_metadata(finished_at DESC);
"""

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RefreshMetadata:
    """Persisted metadata for a single refresh run."""

    id: int | None
    started_at: datetime
    finished_at: datetime | None
    success: bool
    last_error: str | None
    observations_before: int | None
    observations_after: int | None
    estimates_before: int | None
    estimates_after: int | None
    observations_delta: int | None
    estimates_delta: int | None
    trigger: str  # "scheduled" | "manual"


@dataclass(slots=True)
class RefreshStatus:
    """Current daemon status exposed to overlay/browser UX."""

    last_success_at: datetime | None
    last_refresh_at: datetime | None
    last_error: str | None
    is_running: bool
    next_scheduled_at: datetime | None
    observations_delta: int | None
    estimates_delta: int | None


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------


class RefreshDaemon:
    """Background daemon that runs incremental market refresh.

    Lifecycle::

        daemon = RefreshDaemon(db_path, pipeline_script=...)
        daemon.start(interval_hours=4)   # background thread
        daemon.trigger_manual()           # force immediate refresh
        daemon.get_status()               # query for overlay UX
        daemon.stop()                     # clean shutdown

    After each successful refresh the daemon:
    - Persists metadata (deltas, timestamps, errors) to ``refresh_metadata``
    - Calls *on_refresh_complete* callbacks so the overlay can soft-reload
      (e.g. clear PriceLookupEngine cache).
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        pipeline_script: str | Path | None = None,
        pipeline_callable: Callable[[], int] | None = None,
        interval_hours: float = 4.0,
        enable_image_recovery: bool = False,
        image_recovery_callable: Callable[[], Any] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self._pipeline_script = (
            Path(pipeline_script) if pipeline_script is not None else None
        )
        self._pipeline_callable = pipeline_callable
        self._interval_hours = interval_hours
        self._enable_image_recovery = enable_image_recovery
        self._image_recovery_callable = image_recovery_callable

        # SQLite connection (owned by daemon, used from daemon thread only
        # except for get_status which reads from a separate connection).
        self._conn: sqlite3.Connection | None = None

        # Threading
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._manual_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False
        self._refreshing = False

        # Callbacks invoked after successful refresh (e.g. cache clear)
        self._on_complete_callbacks: list[Callable[[], None]] = []

        # Timestamp tracking (in-memory, also persisted)
        self._last_success_at: datetime | None = None
        self._last_refresh_at: datetime | None = None
        self._last_error: str | None = None
        self._last_obs_delta: int | None = None
        self._last_est_delta: int | None = None

    # -- public API ----------------------------------------------------------

    def on_refresh_complete(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked after each successful refresh."""
        self._on_complete_callbacks.append(callback)

    def register_dashboard_export(
        self,
        out_path: str | Path = "data/cache/market_dashboard.html",
        market_key: str = "d2r_sc_ladder",
    ) -> None:
        """Register a post-refresh callback that re-exports the market dashboard.

        The dashboard HTML is rebuilt from the DB after each successful
        refresh so browser artifacts stay current.
        """
        db = str(self.db_path)
        out = str(out_path)
        mk = market_key

        def _export_cb() -> None:
            try:
                from d2lut.overlay.market_dashboard import export_dashboard
                p = export_dashboard(db, out, mk)
                logger.info("Dashboard exported to %s", p)
            except Exception:
                logger.warning("Dashboard export callback failed", exc_info=True)

        self.on_refresh_complete(_export_cb)

    def start(self, interval_hours: float | None = None) -> None:
        """Start the background refresh loop."""
        with self._lock:
            if self._running:
                return
            if interval_hours is not None:
                self._interval_hours = interval_hours
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop, name="refresh-daemon", daemon=True
            )
            self._thread.start()
            logger.info(
                "Refresh daemon started (interval=%.1fh)", self._interval_hours
            )

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the daemon and wait for the thread to finish."""
        with self._lock:
            if not self._running:
                return
            self._running = False
        self._stop_event.set()
        self._manual_event.set()  # unblock wait
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        self._close_conn()
        logger.info("Refresh daemon stopped")

    def trigger_manual(self) -> None:
        """Request an immediate refresh (non-blocking)."""
        self._manual_event.set()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_refreshing(self) -> bool:
        return self._refreshing

    def get_status(self) -> RefreshStatus:
        """Return current daemon status (thread-safe, read-only query)."""
        with self._lock:
            next_at: datetime | None = None
            if self._running and self._last_refresh_at is not None:
                from datetime import timedelta

                next_at = self._last_refresh_at + timedelta(
                    hours=self._interval_hours
                )
            return RefreshStatus(
                last_success_at=self._last_success_at,
                last_refresh_at=self._last_refresh_at,
                last_error=self._last_error,
                is_running=self._running,
                next_scheduled_at=next_at,
                observations_delta=self._last_obs_delta,
                estimates_delta=self._last_est_delta,
            )

    def get_history(self, limit: int = 20) -> list[RefreshMetadata]:
        """Return recent refresh metadata rows (thread-safe)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            self._ensure_table(conn)
            rows = conn.execute(
                "SELECT * FROM refresh_metadata ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_metadata(r) for r in rows]
        finally:
            conn.close()

    # -- background loop -----------------------------------------------------

    def _loop(self) -> None:
        """Main daemon loop: wait -> refresh -> repeat."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_table(self._conn)

        # Load last state from DB
        self._load_last_state()

        interval_secs = self._interval_hours * 3600.0

        while not self._stop_event.is_set():
            # Wait for interval or manual trigger
            triggered = self._manual_event.wait(timeout=interval_secs)
            if self._stop_event.is_set():
                break
            self._manual_event.clear()

            trigger = "manual" if triggered else "scheduled"
            self._run_refresh(trigger)

        self._close_conn()

    def _run_refresh(self, trigger: str) -> None:
        """Execute one refresh cycle."""
        self._refreshing = True
        now = datetime.now(timezone.utc)
        meta_id: int | None = None

        try:
            obs_before = self._count_table(self._conn, "observed_prices")
            est_before = self._count_table(self._conn, "price_estimates")

            # Persist "started" row
            meta_id = self._insert_started(now, trigger)

            # Run the pipeline
            rc = self._execute_pipeline()

            obs_after = self._count_table(self._conn, "observed_prices")
            est_after = self._count_table(self._conn, "price_estimates")

            finished = datetime.now(timezone.utc)
            success = rc == 0
            error_msg = None if success else f"Pipeline exited with code {rc}"

            obs_delta = obs_after - obs_before
            est_delta = est_after - est_before

            self._update_finished(
                meta_id, finished, success, error_msg,
                obs_before, obs_after, est_before, est_after,
                obs_delta, est_delta,
            )

            with self._lock:
                self._last_refresh_at = finished
                self._last_obs_delta = obs_delta
                self._last_est_delta = est_delta
                if success:
                    self._last_success_at = finished
                    self._last_error = None
                else:
                    self._last_error = error_msg

            # Optional image recovery after successful market refresh
            image_recovery_result = None
            if success and self._enable_image_recovery:
                image_recovery_result = self._run_image_recovery()

            if success:
                self._fire_callbacks()

            logger.info(
                "Refresh %s (%s): obs_delta=%+d est_delta=%+d%s",
                "OK" if success else "FAIL",
                trigger,
                obs_delta,
                est_delta,
                (
                    f" image_recovery_errors={len(image_recovery_result.errors)}"
                    if image_recovery_result is not None
                    else ""
                ),
            )

        except Exception as exc:
            logger.exception("Refresh cycle failed")
            finished = datetime.now(timezone.utc)
            error_msg = str(exc)
            if meta_id is not None:
                try:
                    self._update_finished(
                        meta_id, finished, False, error_msg,
                        None, None, None, None, None, None,
                    )
                except Exception:
                    logger.warning("Failed to persist error metadata")
            with self._lock:
                self._last_refresh_at = finished
                self._last_error = error_msg
        finally:
            self._refreshing = False

    # -- image recovery ------------------------------------------------------

    def _run_image_recovery(self) -> Any:
        """Run image recovery pipeline after successful market refresh."""
        if self._image_recovery_callable is not None:
            try:
                return self._image_recovery_callable()
            except Exception as exc:
                logger.warning("Image recovery callable failed: %s", exc)
                # Return a minimal result-like object
                from dataclasses import dataclass, field as _f

                @dataclass
                class _Err:
                    errors: list[str] = _f(default_factory=list)

                return _Err(errors=[str(exc)])

        try:
            from d2lut.overlay.image_recovery_pipeline import run_image_recovery

            return run_image_recovery(self.db_path, quiet=True)
        except Exception as exc:
            logger.warning("Image recovery pipeline failed: %s", exc)
            from dataclasses import dataclass, field as _f

            @dataclass
            class _Err:
                errors: list[str] = _f(default_factory=list)

            return _Err(errors=[str(exc)])

    # -- pipeline execution --------------------------------------------------

    def _execute_pipeline(self) -> int:
        """Run the market pipeline. Returns 0 on success."""
        if self._pipeline_callable is not None:
            return self._pipeline_callable()

        if self._pipeline_script is not None:
            return self._run_script(self._pipeline_script)

        # Default: try to find the pipeline script relative to repo root
        default_script = Path("scripts/run_d2jsp_snapshot_pipeline.py")
        if default_script.exists():
            return self._run_script(default_script)

        logger.warning("No pipeline script or callable configured; skipping")
        return 0

    def _run_script(self, script: Path) -> int:
        """Shell out to a pipeline script."""
        env = dict(os.environ)
        env.setdefault("PYTHONPATH", "src")
        cmd = [sys.executable, str(script), "--db", str(self.db_path), "--quiet"]
        logger.info("Running pipeline: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour max
            )
            if result.returncode != 0:
                logger.warning(
                    "Pipeline stderr:\n%s", result.stderr[-2000:] if result.stderr else "(empty)"
                )
            return result.returncode
        except subprocess.TimeoutExpired:
            logger.error("Pipeline timed out after 1 hour")
            return 1
        except Exception as exc:
            logger.error("Pipeline execution error: %s", exc)
            return 1

    # -- callbacks -----------------------------------------------------------

    def _fire_callbacks(self) -> None:
        """Invoke all on-refresh-complete callbacks."""
        for cb in self._on_complete_callbacks:
            try:
                cb()
            except Exception:
                logger.warning("Refresh callback failed", exc_info=True)

    # -- SQLite helpers ------------------------------------------------------

    @staticmethod
    def _ensure_table(conn: sqlite3.Connection) -> None:
        conn.executescript(
            _CREATE_REFRESH_METADATA_SQL + _CREATE_REFRESH_METADATA_INDEX
        )

    def _insert_started(self, started_at: datetime, trigger: str) -> int:
        assert self._conn is not None
        cur = self._conn.execute(
            """INSERT INTO refresh_metadata (started_at, trigger)
               VALUES (?, ?)""",
            (started_at.isoformat(), trigger),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def _update_finished(
        self,
        meta_id: int | None,
        finished_at: datetime,
        success: bool,
        error: str | None,
        obs_before: int | None,
        obs_after: int | None,
        est_before: int | None,
        est_after: int | None,
        obs_delta: int | None,
        est_delta: int | None,
    ) -> None:
        if meta_id is None or self._conn is None:
            return
        self._conn.execute(
            """UPDATE refresh_metadata SET
                   finished_at = ?,
                   success = ?,
                   last_error = ?,
                   observations_before = ?,
                   observations_after = ?,
                   estimates_before = ?,
                   estimates_after = ?,
                   observations_delta = ?,
                   estimates_delta = ?
               WHERE id = ?""",
            (
                finished_at.isoformat(),
                1 if success else 0,
                error,
                obs_before,
                obs_after,
                est_before,
                est_after,
                obs_delta,
                est_delta,
                meta_id,
            ),
        )
        self._conn.commit()

    @staticmethod
    def _count_table(conn: sqlite3.Connection | None, table: str) -> int:
        if conn is None:
            return 0
        try:
            row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
            return row["cnt"] if row else 0
        except sqlite3.OperationalError:
            return 0

    def _load_last_state(self) -> None:
        """Populate in-memory state from the most recent metadata row."""
        if self._conn is None:
            return
        row = self._conn.execute(
            """SELECT * FROM refresh_metadata
               WHERE finished_at IS NOT NULL
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            return
        with self._lock:
            self._last_refresh_at = (
                datetime.fromisoformat(row["finished_at"])
                if row["finished_at"]
                else None
            )
            if row["success"]:
                self._last_success_at = self._last_refresh_at
            self._last_error = row["last_error"]
            self._last_obs_delta = row["observations_delta"]
            self._last_est_delta = row["estimates_delta"]

    def _close_conn(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Alias for stop()."""
        self.stop()

    def __enter__(self) -> RefreshDaemon:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _row_to_metadata(row: sqlite3.Row) -> RefreshMetadata:
        return RefreshMetadata(
            id=row["id"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=(
                datetime.fromisoformat(row["finished_at"])
                if row["finished_at"]
                else None
            ),
            success=bool(row["success"]),
            last_error=row["last_error"],
            observations_before=row["observations_before"],
            observations_after=row["observations_after"],
            estimates_before=row["estimates_before"],
            estimates_after=row["estimates_after"],
            observations_delta=row["observations_delta"],
            estimates_delta=row["estimates_delta"],
            trigger=row["trigger"],
        )
