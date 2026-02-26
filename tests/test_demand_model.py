"""Tests for d2lut.overlay.demand_model.

Covers demand score calculation, velocity, adaptive window selection,
market heat classification, and edge cases.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from d2lut.overlay.demand_model import DemandMetrics, DemandModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_market_db(tmp_path):
    """Create a minimal in-memory-style SQLite DB with the required schema."""
    db_path = tmp_path / "market.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS observed_prices (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL DEFAULT 'd2jsp',
            market_key TEXT NOT NULL DEFAULT 'sc_ladder',
            forum_id INTEGER NOT NULL DEFAULT 271,
            thread_id INTEGER,
            post_id INTEGER,
            source_kind TEXT NOT NULL DEFAULT 'title',
            signal_kind TEXT NOT NULL,
            thread_category_id INTEGER,
            thread_trade_type TEXT,
            canonical_item_id TEXT NOT NULL,
            variant_key TEXT NOT NULL,
            price_fg REAL NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            observed_at TEXT,
            source_url TEXT,
            raw_excerpt TEXT
        );
        """
    )
    conn.close()
    return db_path


def _insert_observation(
    conn: sqlite3.Connection,
    variant_key: str,
    signal_kind: str = "bin",
    thread_trade_type: str = "ft",
    days_ago: int = 5,
    price_fg: float = 100.0,
    thread_id: int = 1,
):
    """Insert a single observed_price row *days_ago* days in the past."""
    ts = (datetime.now() - timedelta(days=days_ago)).isoformat()
    conn.execute(
        """
        INSERT INTO observed_prices
            (source, market_key, forum_id, thread_id, signal_kind,
             thread_trade_type, canonical_item_id, variant_key,
             price_fg, confidence, observed_at)
        VALUES ('d2jsp','sc_ladder',271,?,?,?,?,?,?,1.0,?)
        """,
        (thread_id, signal_kind, thread_trade_type, variant_key, variant_key,
         price_fg, ts),
    )


# ---------------------------------------------------------------------------
# classify_market_heat (pure logic, no DB)
# ---------------------------------------------------------------------------

class TestClassifyMarketHeat:
    """Unit tests for DemandModel.classify_market_heat (static-like)."""

    def _cls(self, velocity: float, demand_score: float) -> str:
        # classify_market_heat is a regular method but doesn't use self.conn
        # We can call it on any instance; use a class-level trick instead.
        return DemandModel.classify_market_heat(None, velocity, demand_score)  # type: ignore[arg-type]

    def test_hot(self):
        assert self._cls(1.5, 0.7) == "hot"

    def test_hot_requires_both(self):
        # High velocity but low demand → warm, not hot
        assert self._cls(1.5, 0.4) == "warm"

    def test_warm(self):
        assert self._cls(0.5, 0.3) == "warm"

    def test_cold(self):
        assert self._cls(0.1, 0.5) == "cold"

    def test_dead(self):
        assert self._cls(0.01, 0.5) == "dead"

    def test_zero_velocity(self):
        assert self._cls(0.0, 0.5) == "dead"

    def test_boundary_hot(self):
        # velocity exactly 1.0 is NOT > 1.0
        assert self._cls(1.0, 0.7) == "warm"

    def test_boundary_warm(self):
        # velocity exactly 0.3 is NOT > 0.3
        assert self._cls(0.3, 0.5) == "cold"

    def test_boundary_cold(self):
        # velocity exactly 0.05 is NOT > 0.05
        assert self._cls(0.05, 0.5) == "dead"


# ---------------------------------------------------------------------------
# _compute_demand_score (pure logic)
# ---------------------------------------------------------------------------

class TestComputeDemandScore:

    def test_neutral_no_signals(self):
        assert DemandModel._compute_demand_score(0, 0) == 0.5

    def test_all_iso(self):
        assert DemandModel._compute_demand_score(10, 0) == 1.0

    def test_all_ft(self):
        assert DemandModel._compute_demand_score(0, 10) == 0.0

    def test_equal_split(self):
        assert DemandModel._compute_demand_score(5, 5) == 0.5

    def test_ratio(self):
        # 3 iso, 7 ft → 0.3
        assert DemandModel._compute_demand_score(3, 7) == 0.3

    def test_single_iso(self):
        assert DemandModel._compute_demand_score(1, 0) == 1.0

    def test_single_ft(self):
        assert DemandModel._compute_demand_score(0, 1) == 0.0


# ---------------------------------------------------------------------------
# DB-backed tests
# ---------------------------------------------------------------------------

class TestDemandModelDB:
    """Tests that exercise the full calculate_demand path with a real SQLite DB."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        self.db_path = _create_market_db(tmp_path)
        self.model = DemandModel(self.db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        yield
        self.conn.close()
        self.model.close()

    # -- edge: no observations -----------------------------------------------

    def test_no_observations(self):
        m = self.model.calculate_demand("nonexistent:item")
        assert m.total_observations == 0
        assert m.demand_score == 0.5  # neutral
        assert m.observed_velocity == 0.0
        assert m.market_heat == "dead"
        assert m.iso_count == 0
        assert m.ft_count == 0
        assert m.sold_count == 0

    # -- single observation --------------------------------------------------

    def test_single_iso_observation(self):
        _insert_observation(self.conn, "unique:shako", signal_kind="bin",
                            thread_trade_type="iso", days_ago=3)
        self.conn.commit()

        m = self.model.calculate_demand("unique:shako")
        assert m.total_observations == 1
        assert m.iso_count == 1
        assert m.ft_count == 0
        assert m.demand_score == 1.0
        # 1 obs in 60-day window → velocity ~0.0167
        assert m.time_window_days == 60  # low activity → broad window
        assert m.market_heat == "dead"

    def test_single_ft_observation(self):
        _insert_observation(self.conn, "unique:shako", signal_kind="bin",
                            thread_trade_type="ft", days_ago=3)
        self.conn.commit()

        m = self.model.calculate_demand("unique:shako")
        assert m.ft_count == 1
        assert m.iso_count == 0
        assert m.demand_score == 0.0

    # -- mixed signals -------------------------------------------------------

    def test_mixed_iso_ft(self):
        """3 ISO + 7 FT → demand_score ~0.3."""
        for i in range(3):
            _insert_observation(self.conn, "rune:jah", signal_kind="bin",
                                thread_trade_type="iso", days_ago=i + 1,
                                thread_id=100 + i)
        for i in range(7):
            _insert_observation(self.conn, "rune:jah", signal_kind="bin",
                                thread_trade_type="ft", days_ago=i + 1,
                                thread_id=200 + i)
        self.conn.commit()

        m = self.model.calculate_demand("rune:jah")
        assert m.iso_count == 3
        assert m.ft_count == 7
        assert m.demand_score == 0.3
        assert m.total_observations == 10

    # -- sold signals --------------------------------------------------------

    def test_sold_counted_separately(self):
        _insert_observation(self.conn, "unique:shako", signal_kind="sold",
                            thread_trade_type="ft", days_ago=2)
        _insert_observation(self.conn, "unique:shako", signal_kind="bin",
                            thread_trade_type="iso", days_ago=2, thread_id=2)
        self.conn.commit()

        m = self.model.calculate_demand("unique:shako")
        assert m.sold_count == 1
        assert m.iso_count == 1
        # sold from ft thread counts toward ft as well
        assert m.ft_count == 1
        assert m.total_observations == 2

    # -- adaptive window -----------------------------------------------------

    def test_high_velocity_narrow_window(self):
        """Many recent observations → 14-day window."""
        for i in range(40):
            _insert_observation(self.conn, "rune:ber", signal_kind="bin",
                                thread_trade_type="ft", days_ago=i % 28,
                                thread_id=300 + i)
        self.conn.commit()

        window = self.model.get_adaptive_window("rune:ber")
        assert window == 14

    def test_medium_velocity_base_window(self):
        """Moderate observations → base window (30)."""
        for i in range(12):
            _insert_observation(self.conn, "unique:oculus", signal_kind="bin",
                                thread_trade_type="ft", days_ago=i * 2,
                                thread_id=400 + i)
        self.conn.commit()

        window = self.model.get_adaptive_window("unique:oculus")
        assert window == 30

    def test_low_velocity_broad_window(self):
        """Few observations → 60-day window."""
        _insert_observation(self.conn, "unique:rare_thing", signal_kind="bin",
                            thread_trade_type="ft", days_ago=10)
        self.conn.commit()

        window = self.model.get_adaptive_window("unique:rare_thing")
        assert window == 60

    # -- all same signal type ------------------------------------------------

    def test_all_iso_signals(self):
        for i in range(5):
            _insert_observation(self.conn, "charm:torch", signal_kind="bin",
                                thread_trade_type="iso", days_ago=i + 1,
                                thread_id=500 + i)
        self.conn.commit()

        m = self.model.calculate_demand("charm:torch")
        assert m.demand_score == 1.0
        assert m.iso_count == 5
        assert m.ft_count == 0

    def test_all_ft_signals(self):
        for i in range(5):
            _insert_observation(self.conn, "charm:torch", signal_kind="bin",
                                thread_trade_type="ft", days_ago=i + 1,
                                thread_id=600 + i)
        self.conn.commit()

        m = self.model.calculate_demand("charm:torch")
        assert m.demand_score == 0.0
        assert m.ft_count == 5
        assert m.iso_count == 0

    # -- velocity calculation ------------------------------------------------

    def test_velocity_calculation(self):
        """10 observations in a 60-day window → velocity ~0.1667."""
        for i in range(10):
            _insert_observation(self.conn, "set:tals_armor", signal_kind="bin",
                                thread_trade_type="ft", days_ago=i * 5,
                                thread_id=700 + i)
        self.conn.commit()

        m = self.model.calculate_demand("set:tals_armor")
        assert m.total_observations == 10
        expected_vel = 10 / m.time_window_days
        assert abs(m.observed_velocity - round(expected_vel, 4)) < 0.001

    # -- context manager -----------------------------------------------------

    def test_context_manager(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        db_path = _create_market_db(sub)
        with DemandModel(db_path) as dm:
            m = dm.calculate_demand("nonexistent")
            assert m.market_heat == "dead"

    # -- missing DB ----------------------------------------------------------

    def test_missing_db_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            DemandModel(tmp_path / "nope.db")

    # -- old observations outside window -------------------------------------

    def test_old_observations_excluded(self):
        """Observations older than the window should not be counted."""
        # Insert one recent and one old observation
        _insert_observation(self.conn, "unique:windforce", signal_kind="bin",
                            thread_trade_type="ft", days_ago=5, thread_id=800)
        _insert_observation(self.conn, "unique:windforce", signal_kind="bin",
                            thread_trade_type="iso", days_ago=90, thread_id=801)
        self.conn.commit()

        m = self.model.calculate_demand("unique:windforce")
        # The 90-day-old observation should be outside the 60-day max window
        assert m.total_observations == 1
        assert m.ft_count == 1
        assert m.iso_count == 0
