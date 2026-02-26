"""Tests for scripts/backfill_source_urls.py using in-memory SQLite."""
from __future__ import annotations

import json
import sqlite3

import pytest

from scripts.backfill_source_urls import (
    backfill,
    build_thread_url_map,
    count_source_url_stats,
    find_backfillable_rows,
)

MARKET = "d2r_sc_ladder"


def _make_db() -> sqlite3.Connection:
    """Create an in-memory DB with the relevant schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE observed_prices (
            id INTEGER PRIMARY KEY,
            market_key TEXT,
            source TEXT,
            forum_id TEXT,
            thread_id TEXT,
            source_url TEXT,
            signal_kind TEXT,
            variant_key TEXT,
            price_fg REAL,
            confidence REAL,
            raw_excerpt TEXT,
            observed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE threads (
            id INTEGER PRIMARY KEY,
            thread_id TEXT,
            url TEXT,
            title TEXT,
            forum_id TEXT
        )
        """
    )
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    """Insert test data: 5 observed_prices rows, 2 threads."""
    conn.executemany(
        """
        INSERT INTO observed_prices
            (id, market_key, thread_id, source_url, price_fg, signal_kind, variant_key)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            # Row 1: already has source_url — should be untouched
            (1, MARKET, "t100", "https://d2jsp.org/topic.php?t=100", 500, "bin", "runeword:enigma"),
            # Row 2: missing source_url, thread_id resolvable
            (2, MARKET, "t200", None, 300, "bin", "unique:shako"),
            # Row 3: missing source_url, thread_id resolvable
            (3, MARKET, "t200", "", 250, "co", "unique:shako"),
            # Row 4: missing source_url, thread_id NOT resolvable (no thread entry)
            (4, MARKET, "t999", None, 100, "ask", "rune:ber"),
            # Row 5: missing source_url AND thread_id is NULL — not a candidate
            (5, MARKET, None, None, 50, "bin", "rune:jah"),
        ],
    )
    conn.executemany(
        "INSERT INTO threads (id, thread_id, url, title) VALUES (?, ?, ?, ?)",
        [
            (1, "t100", "https://d2jsp.org/topic.php?t=100", "Enigma FT"),
            (2, "t200", "https://d2jsp.org/topic.php?t=200", "Shako FT"),
        ],
    )
    conn.commit()


# ------------------------------------------------------------------
# Unit tests
# ------------------------------------------------------------------


class TestCountSourceUrlStats:
    def test_counts(self):
        conn = _make_db()
        _seed(conn)
        stats = count_source_url_stats(conn, MARKET)
        assert stats["total"] == 5
        assert stats["with_url"] == 1
        assert stats["without_url"] == 4

    def test_empty_db(self):
        conn = _make_db()
        stats = count_source_url_stats(conn, MARKET)
        assert stats == {"total": 0, "with_url": 0, "without_url": 0}


class TestFindBackfillableRows:
    def test_finds_candidates(self):
        conn = _make_db()
        _seed(conn)
        rows = find_backfillable_rows(conn, MARKET)
        ids = {r["id"] for r in rows}
        # Rows 2, 3, 4 have missing source_url + non-null thread_id
        assert ids == {2, 3, 4}

    def test_excludes_null_thread_id(self):
        conn = _make_db()
        _seed(conn)
        rows = find_backfillable_rows(conn, MARKET)
        tids = {r["thread_id"] for r in rows}
        assert None not in tids


class TestBuildThreadUrlMap:
    def test_maps_known_threads(self):
        conn = _make_db()
        _seed(conn)
        url_map = build_thread_url_map(conn, ["t100", "t200", "t999"])
        assert url_map["t100"] == "https://d2jsp.org/topic.php?t=100"
        assert url_map["t200"] == "https://d2jsp.org/topic.php?t=200"
        assert "t999" not in url_map

    def test_empty_list(self):
        conn = _make_db()
        assert build_thread_url_map(conn, []) == {}


class TestBackfill:
    def test_updates_resolvable_rows(self):
        conn = _make_db()
        _seed(conn)
        result = backfill(conn, MARKET)
        assert result["updated"] == 2  # rows 2 and 3
        assert len(result["unresolvable"]) == 1
        assert result["unresolvable"][0]["thread_id"] == "t999"

        # Verify DB was actually updated
        row2 = conn.execute(
            "SELECT source_url FROM observed_prices WHERE id = 2"
        ).fetchone()
        assert row2[0] == "https://d2jsp.org/topic.php?t=200"

        row3 = conn.execute(
            "SELECT source_url FROM observed_prices WHERE id = 3"
        ).fetchone()
        assert row3[0] == "https://d2jsp.org/topic.php?t=200"

    def test_before_after_stats(self):
        conn = _make_db()
        _seed(conn)
        result = backfill(conn, MARKET)
        assert result["before"]["with_url"] == 1
        assert result["after"]["with_url"] == 3  # 1 original + 2 backfilled

    def test_idempotent(self):
        """Running backfill twice produces the same result (Req 11.4)."""
        conn = _make_db()
        _seed(conn)
        r1 = backfill(conn, MARKET)
        assert r1["updated"] == 2

        r2 = backfill(conn, MARKET)
        assert r2["updated"] == 0  # nothing left to update
        assert r2["before"] == r1["after"]
        assert r2["after"] == r1["after"]

    def test_dry_run_no_modification(self):
        conn = _make_db()
        _seed(conn)
        result = backfill(conn, MARKET, dry_run=True)
        assert result["updated"] == 2  # reports what would happen

        # But DB is unchanged
        row2 = conn.execute(
            "SELECT source_url FROM observed_prices WHERE id = 2"
        ).fetchone()
        assert row2[0] is None

    def test_unresolvable_logged(self):
        conn = _make_db()
        _seed(conn)
        result = backfill(conn, MARKET)
        unresolvable_ids = {e["id"] for e in result["unresolvable"]}
        assert 4 in unresolvable_ids

    def test_empty_db(self):
        conn = _make_db()
        result = backfill(conn, MARKET)
        assert result["updated"] == 0
        assert result["unresolvable"] == []

    def test_row_with_existing_url_untouched(self):
        """Row 1 already has source_url — must not be modified."""
        conn = _make_db()
        _seed(conn)
        backfill(conn, MARKET)
        row1 = conn.execute(
            "SELECT source_url FROM observed_prices WHERE id = 1"
        ).fetchone()
        assert row1[0] == "https://d2jsp.org/topic.php?t=100"

    def test_different_market_key_isolated(self):
        """Backfill for one market_key must not touch another."""
        conn = _make_db()
        _seed(conn)
        # Add a row for a different market
        conn.execute(
            """
            INSERT INTO observed_prices
                (id, market_key, thread_id, source_url, price_fg, signal_kind, variant_key)
            VALUES (10, 'other_market', 't200', NULL, 100, 'bin', 'rune:jah')
            """
        )
        conn.commit()
        result = backfill(conn, MARKET)
        # Only MARKET rows updated
        assert result["updated"] == 2

        other_row = conn.execute(
            "SELECT source_url FROM observed_prices WHERE id = 10"
        ).fetchone()
        assert other_row[0] is None  # untouched
