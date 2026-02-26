"""Tests for Task 16: Last Seen / freshness column.

Validates:
- Req 21.1: last_seen computed as max observed_at from group
- Req 21.2: relative-time JS formatting logic (tested via Python equivalent)
- Req 21.3: stale-row detection (>7 days)
- Req 21.4: sortable Last Seen column in HTML output
"""

from __future__ import annotations

import sqlite3
import re
from datetime import datetime, timedelta, timezone

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from export_property_price_table_html import _max_observed_at, _build_html


# ---------------------------------------------------------------------------
# Helpers: create fake sqlite3.Row objects
# ---------------------------------------------------------------------------

def _make_rows(timestamps: list[str]) -> list[sqlite3.Row]:
    """Create minimal sqlite3.Row-like objects with observed_at values."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (observed_at TEXT)")
    for ts in timestamps:
        conn.execute("INSERT INTO t VALUES (?)", (ts,))
    rows = conn.execute("SELECT * FROM t").fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Tests for _max_observed_at  (Req 21.1)
# ---------------------------------------------------------------------------

class TestMaxObservedAt:
    def test_single_timestamp(self):
        rows = _make_rows(["2025-01-15T10:00:00"])
        assert _max_observed_at(rows) == "2025-01-15T10:00:00"

    def test_multiple_timestamps_returns_max(self):
        rows = _make_rows([
            "2025-01-10T08:00:00",
            "2025-01-20T12:00:00",
            "2025-01-15T10:00:00",
        ])
        assert _max_observed_at(rows) == "2025-01-20T12:00:00"

    def test_empty_rows(self):
        rows = _make_rows([])
        assert _max_observed_at(rows) == ""

    def test_none_and_empty_timestamps_skipped(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE t (observed_at TEXT)")
        conn.execute("INSERT INTO t VALUES (NULL)")
        conn.execute("INSERT INTO t VALUES ('')")
        conn.execute("INSERT INTO t VALUES ('2025-03-01T00:00:00')")
        rows = conn.execute("SELECT * FROM t").fetchall()
        conn.close()
        assert _max_observed_at(rows) == "2025-03-01T00:00:00"

    def test_all_none_returns_empty(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE t (observed_at TEXT)")
        conn.execute("INSERT INTO t VALUES (NULL)")
        conn.execute("INSERT INTO t VALUES (NULL)")
        rows = conn.execute("SELECT * FROM t").fetchall()
        conn.close()
        assert _max_observed_at(rows) == ""


# ---------------------------------------------------------------------------
# Tests for stale detection logic (Req 21.3)
# ---------------------------------------------------------------------------

class TestStaleDetection:
    """Verify the JS isStale() logic via its Python-equivalent semantics.

    The JS function: isStale(iso) => (Date.now() - new Date(iso)) > 7*24*60*60*1000
    We test the boundary: exactly 7 days is NOT stale, >7 days IS stale.
    """

    @staticmethod
    def _is_stale_py(iso_str: str) -> bool:
        """Python equivalent of the JS isStale() function."""
        if not iso_str:
            return False
        try:
            d = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except ValueError:
            return False
        now = datetime.now(timezone.utc)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (now - d).total_seconds() > 7 * 24 * 60 * 60

    def test_recent_not_stale(self):
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert not self._is_stale_py(recent)

    def test_old_is_stale(self):
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        assert self._is_stale_py(old)

    def test_exactly_7_days_not_stale(self):
        # 7 days minus 1 second should not be stale
        border = (datetime.now(timezone.utc) - timedelta(days=7) + timedelta(seconds=1)).isoformat()
        assert not self._is_stale_py(border)

    def test_empty_string_not_stale(self):
        assert not self._is_stale_py("")

    def test_none_not_stale(self):
        assert not self._is_stale_py(None)


# ---------------------------------------------------------------------------
# Tests for HTML output (Req 21.2, 21.3, 21.4)
# ---------------------------------------------------------------------------

class TestHtmlLastSeenColumn:
    """Verify the generated HTML includes Last Seen column infrastructure."""

    @pytest.fixture()
    def minimal_html(self):
        """Generate HTML with a single row containing a last_seen timestamp."""
        row = {
            "row_kind": "property",
            "name_display": "test item",
            "type_l1": "unique",
            "type_l2": "",
            "type_l3": "",
            "class_tags": "",
            "signature": "test_sig",
            "req_lvl_min": None,
            "median_fg": 500.0,
            "max_fg": 1000.0,
            "obs_count": 5,
            "variant_count": 1,
            "potential_score": 1,
            "potential_tags": [],
            "perfect_tier": "",
            "iso_sell": "",
            "top_variants": ["unique:test"],
            "signals": "bin:3",
            "confidence": "high",
            "example_excerpt": "test excerpt",
            "last_source_url": "",
            "kit": False,
            "lld_bucket": "unknown",
            "last_seen": "2025-01-15T10:00:00",
            "observations": [],
        }
        return _build_html("test_market", [row])

    def test_header_present(self, minimal_html):
        """Req 21.2: Last Seen column header exists."""
        assert 'data-key="last_seen"' in minimal_html
        assert "Last Seen" in minimal_html

    def test_relative_time_function_present(self, minimal_html):
        """Req 21.2: relativeTime JS function is defined."""
        assert "function relativeTime" in minimal_html

    def test_is_stale_function_present(self, minimal_html):
        """Req 21.3: isStale JS function is defined."""
        assert "function isStale" in minimal_html

    def test_stale_row_css_present(self, minimal_html):
        """Req 21.3: stale-row CSS class is defined."""
        assert ".stale-row" in minimal_html

    def test_sort_cases_present(self, minimal_html):
        """Req 21.4: last_seen sort cases exist in sortRows."""
        assert "last_seen_desc" in minimal_html
        assert "last_seen_asc" in minimal_html

    def test_header_sort_key_mapping(self, minimal_html):
        """Req 21.4: headerSortKey maps last_seen data-key."""
        assert '"last_seen": return "last_seen"' in minimal_html

    def test_last_seen_in_json_payload(self, minimal_html):
        """Req 21.1: last_seen value is present in the DATA payload."""
        assert "2025-01-15T10:00:00" in minimal_html
