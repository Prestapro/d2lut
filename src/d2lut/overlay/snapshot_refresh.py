"""Snapshot refresh manager for market data and price history.

Coordinates refreshing market data snapshots and recording price history.
The actual market data pipeline (parsing forum snapshots, recalculating
price_estimates) is handled by external scripts. This module only records
the current price_estimates state into price_history and provides
scheduling infrastructure.

Requirements: 6.5
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from d2lut.overlay.price_history import PriceHistoryTracker

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RefreshResult:
    """Result of a snapshot refresh operation."""

    success: bool
    refreshed_at: datetime
    price_estimates_count: int
    history_snapshots_recorded: int
    error: str | None


class SnapshotRefreshManager:
    """Coordinates refreshing market data and recording price history.

    Provides manual refresh, periodic scheduling, and last-refresh queries.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._tracker = PriceHistoryTracker(self.db_path)
        self._periodic_timer: threading.Timer | None = None
        self._periodic_running = False
        self._periodic_lock = threading.Lock()
        self._interval_hours: int = 24

    # -- manual refresh ------------------------------------------------------

    def refresh(self) -> RefreshResult:
        """Record current price_estimates into price_history.

        This is the manual refresh trigger. It snapshots all current
        price_estimates rows into the price_history table.
        """
        now = datetime.now(timezone.utc)
        try:
            recorded = self._tracker.record_all_current()
            estimates_count = self._count_price_estimates()
            return RefreshResult(
                success=True,
                refreshed_at=now,
                price_estimates_count=estimates_count,
                history_snapshots_recorded=recorded,
                error=None,
            )
        except Exception as exc:
            logger.exception("Refresh failed")
            return RefreshResult(
                success=False,
                refreshed_at=now,
                price_estimates_count=0,
                history_snapshots_recorded=0,
                error=str(exc),
            )

    # -- last refresh time ---------------------------------------------------

    def get_last_refresh_time(self) -> datetime | None:
        """Return the most recent recorded_at from price_history, or None."""
        row = self._tracker.conn.execute(
            "SELECT MAX(recorded_at) AS latest FROM price_history"
        ).fetchone()
        if row is None or row["latest"] is None:
            return None
        return datetime.fromisoformat(row["latest"])

    # -- periodic scheduling -------------------------------------------------

    def schedule_periodic(self, interval_hours: int = 24) -> None:
        """Start a background thread that calls refresh() periodically."""
        with self._periodic_lock:
            if self._periodic_running:
                return
            self._interval_hours = interval_hours
            self._periodic_running = True
            self._schedule_next()

    def stop_periodic(self) -> None:
        """Stop the background refresh thread."""
        with self._periodic_lock:
            self._periodic_running = False
            if self._periodic_timer is not None:
                self._periodic_timer.cancel()
                self._periodic_timer = None

    def is_periodic_running(self) -> bool:
        """Return whether periodic refresh is active."""
        return self._periodic_running

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Stop periodic scheduling and close the tracker."""
        self.stop_periodic()
        self._tracker.close()

    def __enter__(self) -> SnapshotRefreshManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    # -- internal ------------------------------------------------------------

    def _schedule_next(self) -> None:
        """Schedule the next periodic refresh."""
        interval_seconds = self._interval_hours * 3600
        self._periodic_timer = threading.Timer(
            interval_seconds, self._periodic_tick
        )
        self._periodic_timer.daemon = True
        self._periodic_timer.start()

    def _periodic_tick(self) -> None:
        """Execute one periodic refresh and reschedule."""
        with self._periodic_lock:
            if not self._periodic_running:
                return
        try:
            result = self.refresh()
            logger.info(
                "Periodic refresh: recorded=%d estimates=%d",
                result.history_snapshots_recorded,
                result.price_estimates_count,
            )
        except Exception:
            logger.exception("Periodic refresh tick failed")
        with self._periodic_lock:
            if self._periodic_running:
                self._schedule_next()

    def _count_price_estimates(self) -> int:
        """Count current rows in price_estimates."""
        row = self._tracker.conn.execute(
            "SELECT COUNT(*) AS cnt FROM price_estimates"
        ).fetchone()
        return row["cnt"] if row else 0
