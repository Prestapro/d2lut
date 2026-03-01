"""Tests for Task 17 — Signal split columns (BIN / c/o / ASK / SOLD).

Validates:
- Req 22.1: per-signal-type median FG fields (bin_fg, co_fg, ask_fg, sold_fg)
- Req 22.2: medians computed from observations within the group
- Req 22.3: missing signal types show as None (not 0)
- Req 22.4: HTML contains new columns and sort infrastructure
"""

import sqlite3
from statistics import median
from unittest.mock import MagicMock

import pytest

from scripts.export_property_price_table_html import (
    _signal_medians,
    _build_html,
)


# ---------------------------------------------------------------------------
# Helpers — fake sqlite3.Row-like objects
# ---------------------------------------------------------------------------

def _make_row(**kwargs) -> sqlite3.Row:
    """Create a sqlite3.Row-like object with dict-style access."""
    row = MagicMock(spec=sqlite3.Row)
    row.__getitem__ = lambda self, key: kwargs.get(key)
    row.keys = lambda: list(kwargs.keys())
    return row


def _rows_from_signals(signal_prices: list[tuple[str, float]]) -> list:
    """Build a list of fake rows from (signal_kind, price_fg) pairs."""
    return [_make_row(signal_kind=sk, price_fg=pf) for sk, pf in signal_prices]


# ===========================================================================
# 22.1 / 22.2 — per-signal-type median FG computation
# ===========================================================================

class TestSignalMedians:
    """Validates: Requirements 22.1, 22.2"""

    def test_single_signal_type(self):
        rows = _rows_from_signals([("bin", 100.0), ("bin", 200.0), ("bin", 300.0)])
        result = _signal_medians(rows)
        assert result["bin_fg"] == 200.0
        assert result["co_fg"] is None
        assert result["ask_fg"] is None
        assert result["sold_fg"] is None

    def test_multiple_signal_types(self):
        rows = _rows_from_signals([
            ("bin", 100.0), ("bin", 300.0),
            ("sold", 50.0), ("sold", 150.0), ("sold", 250.0),
            ("co", 80.0),
            ("ask", 400.0), ("ask", 600.0),
        ])
        result = _signal_medians(rows)
        assert result["bin_fg"] == median([100.0, 300.0])
        assert result["sold_fg"] == median([50.0, 150.0, 250.0])
        assert result["co_fg"] == 80.0
        assert result["ask_fg"] == median([400.0, 600.0])

    def test_single_observation_per_type(self):
        rows = _rows_from_signals([("bin", 500.0)])
        result = _signal_medians(rows)
        assert result["bin_fg"] == 500.0

    def test_even_count_median(self):
        """Median of even-count list uses middle values."""
        rows = _rows_from_signals([("sold", 100.0), ("sold", 200.0)])
        result = _signal_medians(rows)
        assert result["sold_fg"] == median([100.0, 200.0])


# ===========================================================================
# 22.3 — missing signal types produce None
# ===========================================================================

class TestMissingSignalTypes:
    """Validates: Requirement 22.3"""

    def test_empty_rows(self):
        result = _signal_medians([])
        assert result["bin_fg"] is None
        assert result["co_fg"] is None
        assert result["ask_fg"] is None
        assert result["sold_fg"] is None

    def test_partial_signals(self):
        rows = _rows_from_signals([("bin", 100.0), ("sold", 200.0)])
        result = _signal_medians(rows)
        assert result["bin_fg"] == 100.0
        assert result["sold_fg"] == 200.0
        assert result["co_fg"] is None
        assert result["ask_fg"] is None

    def test_unknown_signal_kind_ignored(self):
        rows = _rows_from_signals([("unknown", 999.0)])
        result = _signal_medians(rows)
        assert result["bin_fg"] is None
        assert result["co_fg"] is None
        assert result["ask_fg"] is None
        assert result["sold_fg"] is None


# ===========================================================================
# 22.4 — HTML contains new columns and sort infrastructure
# ===========================================================================

class TestSignalColumnsInHTML:
    """Validates: Requirement 22.4"""

    @pytest.fixture()
    def html(self):
        """Generate HTML with a minimal row containing signal fields."""
        row = {
            "row_kind": "property",
            "name_display": "test item",
            "type_l1": "unique", "type_l2": "", "type_l3": "",
            "class_tags": "", "signature": "test_sig",
            "req_lvl_min": None,
            "median_fg": 500.0, "max_fg": 800.0,
            "obs_count": 5, "variant_count": 2,
            "potential_score": 1, "potential_tags": [],
            "perfect_tier": "", "iso_sell": "",
            "top_variants": ["unique:test"],
            "signals": "bin:3 sold:2",
            "bin_fg": 450.0, "co_fg": None, "ask_fg": 300.0, "sold_fg": 200.0,
            "confidence": "medium",
            "example_excerpt": "test excerpt",
            "last_source_url": "",
            "kit": False, "lld_bucket": "unknown",
            "last_seen": "2025-01-01T00:00:00",
            "observations": [],
        }
        return _build_html("test_market", [row])

    def test_header_columns_present(self, html):
        assert 'data-key="bin_fg"' in html
        assert 'data-key="co_fg"' in html
        assert 'data-key="ask_fg"' in html
        assert 'data-key="sold_fg"' in html

    def test_header_labels(self, html):
        assert ">BIN</th>" in html
        assert ">c/o</th>" in html
        assert ">ASK</th>" in html
        assert ">SOLD</th>" in html

    def test_sort_cases_present(self, html):
        for key in ("bin_fg_desc", "bin_fg_asc", "co_fg_desc", "co_fg_asc",
                     "ask_fg_desc", "ask_fg_asc", "sold_fg_desc", "sold_fg_asc"):
            assert f'case "{key}"' in html, f"Missing sort case: {key}"

    def test_header_sort_key_mappings(self, html):
        for key in ("bin_fg", "co_fg", "ask_fg", "sold_fg"):
            assert f'case "{key}": return "{key}"' in html

    def test_signal_data_in_payload(self, html):
        # The JSON payload should contain the signal fields
        assert '"bin_fg": 450.0' in html or '"bin_fg":450.0' in html or '"bin_fg": 450' in html
        assert '"sold_fg": 200.0' in html or '"sold_fg":200.0' in html or '"sold_fg": 200' in html
        # co_fg is None → should be null in JSON
        assert '"co_fg": null' in html or '"co_fg":null' in html
