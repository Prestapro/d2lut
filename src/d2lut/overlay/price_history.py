"""Price history tracking for trend analysis.

Populates the price_history table on snapshot refresh, tracks median/low/high
prices over time, and calculates market stability and direction.

Requirements: 3.4, 11.4
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class PriceSnapshot:
    """A single recorded price observation at a point in time."""

    variant_key: str
    market_key: str
    recorded_at: datetime
    median_fg: float
    low_fg: float
    high_fg: float
    sample_count: int
    demand_score: float | None


@dataclass(slots=True)
class PriceTrend:
    """Trend analysis for a variant over a time window."""

    variant_key: str
    snapshots: list[PriceSnapshot]
    stability: str  # stable / moderate / volatile
    price_change_pct: float | None  # % change oldest -> newest
    direction: str  # rising / falling / flat


_CREATE_TABLE_SQL = """
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
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_price_history_time
  ON price_history(recorded_at DESC, market_key, variant_key);
"""


class PriceHistoryTracker:
    """Records and queries price history snapshots.

    Reads current price_estimates rows and records them into price_history
    for trend analysis over time.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self.conn.executescript(_CREATE_TABLE_SQL + _CREATE_INDEX_SQL)

    # -- recording -----------------------------------------------------------

    def record_snapshot(
        self,
        variant_key: str,
        market_key: str,
        median_fg: float,
        low_fg: float,
        high_fg: float,
        sample_count: int,
        demand_score: float | None = None,
    ) -> None:
        """Insert a single price history row."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT INTO price_history
                (market_key, variant_key, recorded_at, median_fg, low_fg, high_fg,
                 sample_count, demand_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (market_key, variant_key, now, median_fg, low_fg, high_fg,
             sample_count, demand_score),
        )
        self.conn.commit()

    def record_all_current(self) -> int:
        """Snapshot all rows from price_estimates into price_history.

        Returns the number of rows recorded.
        """
        now = datetime.now(timezone.utc).isoformat()
        rows = self.conn.execute(
            """
            SELECT market_key, variant_key, estimate_fg, range_low_fg,
                   range_high_fg, sample_count
            FROM price_estimates
            """
        ).fetchall()

        for r in rows:
            self.conn.execute(
                """
                INSERT INTO price_history
                    (market_key, variant_key, recorded_at, median_fg, low_fg,
                     high_fg, sample_count, demand_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (r["market_key"], r["variant_key"], now,
                 r["estimate_fg"], r["range_low_fg"], r["range_high_fg"],
                 r["sample_count"]),
            )

        self.conn.commit()
        return len(rows)

    # -- querying ------------------------------------------------------------

    def get_history(
        self,
        variant_key: str,
        days: int = 30,
    ) -> list[PriceSnapshot]:
        """Return snapshots for *variant_key* within the last *days* days."""
        rows = self.conn.execute(
            """
            SELECT market_key, variant_key, recorded_at, median_fg,
                   low_fg, high_fg, sample_count, demand_score
            FROM price_history
            WHERE variant_key = ?
              AND recorded_at >= datetime('now', ?)
            ORDER BY recorded_at DESC
            """,
            (variant_key, f"-{days} days"),
        ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def get_trend(
        self,
        variant_key: str,
        days: int = 30,
    ) -> PriceTrend:
        """Return trend analysis for *variant_key* over *days*."""
        snapshots = self.get_history(variant_key, days)
        stability = self.calculate_stability(snapshots)
        direction, change_pct = self.calculate_direction(snapshots)
        return PriceTrend(
            variant_key=variant_key,
            snapshots=snapshots,
            stability=stability,
            price_change_pct=change_pct,
            direction=direction,
        )

    # -- analysis helpers ----------------------------------------------------

    @staticmethod
    def calculate_stability(snapshots: list[PriceSnapshot]) -> str:
        """Classify price stability from coefficient of variation.

        stable   : CV < 0.10
        moderate : CV < 0.25
        volatile : CV >= 0.25
        """
        if len(snapshots) < 2:
            return "stable"

        medians = [s.median_fg for s in snapshots]
        mean = sum(medians) / len(medians)
        if mean == 0:
            return "stable"

        variance = sum((m - mean) ** 2 for m in medians) / len(medians)
        std = variance ** 0.5
        cv = std / abs(mean)

        if cv < 0.10:
            return "stable"
        if cv < 0.25:
            return "moderate"
        return "volatile"

    @staticmethod
    def calculate_direction(
        snapshots: list[PriceSnapshot],
    ) -> tuple[str, float | None]:
        """Compare oldest vs newest median to determine direction.

        rising  : change > +5%
        falling : change < -5%
        flat    : otherwise

        Returns (direction, change_pct).
        """
        if len(snapshots) < 2:
            return ("flat", None)

        # snapshots are ordered DESC, so newest first
        newest = snapshots[0].median_fg
        oldest = snapshots[-1].median_fg

        if oldest == 0:
            return ("flat", None)

        change_pct = ((newest - oldest) / abs(oldest)) * 100.0
        change_pct = round(change_pct, 2)

        if change_pct > 5.0:
            return ("rising", change_pct)
        if change_pct < -5.0:
            return ("falling", change_pct)
        return ("flat", change_pct)

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self.conn.close()
    def estimate_memory_bytes(self) -> int:
        """Approximate in-process memory (connection + Python objects).

        The bulk of price_history data lives in SQLite on disk; this
        returns a small fixed estimate for the connection overhead.
        """
        return 4096  # connection + row_factory overhead

    def __enter__(self) -> PriceHistoryTracker:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    # -- internal ------------------------------------------------------------

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> PriceSnapshot:
        return PriceSnapshot(
            variant_key=row["variant_key"],
            market_key=row["market_key"],
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
            median_fg=row["median_fg"],
            low_fg=row["low_fg"],
            high_fg=row["high_fg"],
            sample_count=row["sample_count"],
            demand_score=row["demand_score"],
        )
