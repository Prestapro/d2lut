"""Demand scoring model for the overlay pricing system.

Calculates demand vs supply signal ratios, adaptive time windows,
and market heat classification from observed_prices data.

Requirements: 11.1, 11.2, 11.3, 11.4
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class DemandMetrics:
    """Demand analysis results for a variant."""

    demand_score: float  # 0.0-1.0, ratio of demand (ISO) vs supply (FT) signals
    observed_velocity: float  # observations per day
    iso_count: int  # buyer demand signals
    ft_count: int  # seller supply signals
    sold_count: int  # completed sales
    total_observations: int
    time_window_days: int  # adaptive window actually used
    market_heat: str  # hot, warm, cold, dead


class DemandModel:
    """Demand scoring engine backed by the market database.

    Queries observed_prices joined with threads to classify demand
    vs supply signals and compute velocity / market heat.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    # -- public API ----------------------------------------------------------

    def calculate_demand(
        self,
        variant_key: str,
        base_window_days: int = 30,
    ) -> DemandMetrics:
        """Calculate demand metrics for *variant_key*.

        1. Query observed_prices within the adaptive time window.
        2. Join threads to get context_kind (ft/iso/pc/service).
        3. Count ISO (demand) vs FT (supply) vs SOLD signals.
        4. Derive demand_score, velocity, and market_heat.
        """
        window = self.get_adaptive_window(variant_key, base_window_days)
        counts = self._query_signal_counts(variant_key, window)

        iso_count = counts.get("iso", 0)
        ft_count = counts.get("ft", 0)
        sold_count = counts.get("sold", 0)
        total = counts.get("total", 0)

        demand_score = self._compute_demand_score(iso_count, ft_count)
        velocity = total / window if window > 0 else 0.0
        heat = self.classify_market_heat(velocity, demand_score)

        return DemandMetrics(
            demand_score=demand_score,
            observed_velocity=round(velocity, 4),
            iso_count=iso_count,
            ft_count=ft_count,
            sold_count=sold_count,
            total_observations=total,
            time_window_days=window,
            market_heat=heat,
        )

    def get_adaptive_window(
        self,
        variant_key: str,
        base_window_days: int = 30,
    ) -> int:
        """Return an adaptive time window based on recent activity.

        High-velocity items (>1.0 obs/day) → 14 days (focus on recent).
        Medium-velocity (>0.3 obs/day)     → base_window_days (default 30).
        Low-velocity                       → 60 days (broaden for sparse data).
        """
        # Probe with the base window first to estimate velocity.
        total = self._count_observations(variant_key, base_window_days)
        velocity = total / base_window_days if base_window_days > 0 else 0.0

        if velocity > 1.0:
            return 14
        if velocity > 0.3:
            return base_window_days
        return 60

    def classify_market_heat(
        self,
        velocity: float,
        demand_score: float,
    ) -> str:
        """Classify market activity into hot / warm / cold / dead."""
        if velocity > 1.0 and demand_score > 0.6:
            return "hot"
        if velocity > 0.3:
            return "warm"
        if velocity > 0.05:
            return "cold"
        return "dead"

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _compute_demand_score(iso_count: int, ft_count: int) -> float:
        """Demand score = iso / (iso + ft).  Neutral 0.5 when no signals."""
        total_signals = iso_count + ft_count
        if total_signals == 0:
            return 0.5
        return round(iso_count / total_signals, 4)

    def _count_observations(self, variant_key: str, window_days: int) -> int:
        """Count total observations within *window_days*."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM observed_prices
            WHERE variant_key = ?
              AND observed_at >= date('now', ?)
            """,
            (variant_key, f"-{window_days} days"),
        ).fetchone()
        return row["cnt"] if row else 0

    def _query_signal_counts(
        self,
        variant_key: str,
        window_days: int,
    ) -> dict[str, int]:
        """Query ISO / FT / SOLD / total counts within *window_days*.

        ISO signals come from threads with thread_trade_type = 'iso'.
        FT signals come from threads with thread_trade_type = 'ft'.
        SOLD signals come from signal_kind = 'sold' regardless of thread type.
        """
        rows = self.conn.execute(
            """
            SELECT
                COALESCE(op.thread_trade_type, 'unknown') AS trade_type,
                op.signal_kind,
                COUNT(*) AS cnt
            FROM observed_prices op
            WHERE op.variant_key = ?
              AND op.observed_at >= date('now', ?)
            GROUP BY trade_type, op.signal_kind
            """,
            (variant_key, f"-{window_days} days"),
        ).fetchall()

        iso = 0
        ft = 0
        sold = 0
        total = 0
        for r in rows:
            count = r["cnt"]
            total += count
            if r["signal_kind"] == "sold":
                sold += count
            if r["trade_type"] == "iso":
                iso += count
            elif r["trade_type"] == "ft":
                ft += count

        return {"iso": iso, "ft": ft, "sold": sold, "total": total}

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> DemandModel:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()
