"""Tests for display mode switching (Task 15).

Validates: Requirements 4.1, 4.2, 4.3, 4.4
"""

import json
import sqlite3

from scripts.export_property_price_table_html import (
    _build_html,
    _collect_observations,
)


# ---------------------------------------------------------------------------
# Helpers — lightweight sqlite3.Row stand-in
# ---------------------------------------------------------------------------

def _make_row(data: dict) -> sqlite3.Row:
    """Create a real sqlite3.Row from a dict for testing."""
    cols = list(data.keys())
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    placeholders = ", ".join("?" for _ in cols)
    col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
    conn.execute(f"CREATE TABLE _tmp ({col_defs})")
    conn.execute(f"INSERT INTO _tmp VALUES ({placeholders})", [data[c] for c in cols])
    row = conn.execute("SELECT * FROM _tmp").fetchone()
    conn.close()
    return row


def _sample_obs_rows():
    """Return a list of sqlite3.Row objects simulating observed_prices rows."""
    return [
        _make_row({
            "source_url": "https://forums.d2jsp.org/topic.php?t=100&f=271",
            "raw_excerpt": "eth 4os GT 500fg bin",
            "signal_kind": "bin",
            "price_fg": 500.0,
            "observed_at": "2025-01-15T10:00:00",
            "variant_key": "base:giant_thresher:eth:4os",
            "thread_id": 100,
            "forum_id": 271,
        }),
        _make_row({
            "source_url": "",
            "raw_excerpt": "eth GT 4os 400fg",
            "signal_kind": "sold",
            "price_fg": 400.0,
            "observed_at": "2025-01-14T08:00:00",
            "variant_key": "base:giant_thresher:eth:4os",
            "thread_id": 101,
            "forum_id": 271,
        }),
        _make_row({
            "source_url": "https://forums.d2jsp.org/topic.php?t=102&f=271",
            "raw_excerpt": "eth thresher 4os 350fg",
            "signal_kind": "bin",
            "price_fg": 350.0,
            "observed_at": "2025-01-13T12:00:00",
            "variant_key": "base:thresher:eth:4os",
            "thread_id": 102,
            "forum_id": 271,
        }),
    ]


# ---------------------------------------------------------------------------
# 15.1 — _collect_observations embeds per-observation data
# ---------------------------------------------------------------------------

class TestCollectObservations:
    def test_returns_all_observations(self):
        rows = _sample_obs_rows()
        obs = _collect_observations(rows)
        assert len(obs) == 3

    def test_observation_fields_present(self):
        rows = _sample_obs_rows()
        obs = _collect_observations(rows)
        required_keys = {"source_url", "raw_excerpt", "signal_kind", "price_fg", "observed_at", "variant_key"}
        for o in obs:
            assert required_keys.issubset(o.keys()), f"Missing keys: {required_keys - o.keys()}"

    def test_source_url_fallback_from_thread_id(self):
        """When source_url is empty, should construct URL from thread_id."""
        rows = _sample_obs_rows()
        obs = _collect_observations(rows)
        # Second row has empty source_url but has thread_id=101
        assert "t=101" in obs[1]["source_url"]
        assert obs[1]["source_url"].startswith("https://forums.d2jsp.org/")

    def test_price_fg_is_float(self):
        rows = _sample_obs_rows()
        obs = _collect_observations(rows)
        for o in obs:
            assert isinstance(o["price_fg"], float)

    def test_raw_excerpt_truncated_to_300(self):
        long_excerpt = "x" * 500
        row = _make_row({
            "source_url": "", "raw_excerpt": long_excerpt, "signal_kind": "bin",
            "price_fg": 100.0, "observed_at": "2025-01-01", "variant_key": "test",
            "thread_id": None, "forum_id": None,
        })
        obs = _collect_observations([row])
        assert len(obs[0]["raw_excerpt"]) == 300

    def test_empty_rows_returns_empty_list(self):
        assert _collect_observations([]) == []


# ---------------------------------------------------------------------------
# 15.1 + 15.2 — _build_html embeds observations and display mode controls
# ---------------------------------------------------------------------------

def _minimal_row(**overrides):
    """Build a minimal out_rows dict for _build_html."""
    base = {
        "row_kind": "property",
        "name_display": "Test Item",
        "type_l1": "runeword",
        "type_l2": "",
        "type_l3": "",
        "class_tags": "",
        "signature": "test_sig",
        "req_lvl_min": None,
        "median_fg": 500.0,
        "max_fg": 600.0,
        "obs_count": 3,
        "variant_count": 2,
        "potential_score": 0,
        "potential_tags": [],
        "perfect_tier": "",
        "iso_sell": "",
        "top_variants": ["runeword:test"],
        "signals": "bin:2 sold:1",
        "confidence": "medium",
        "example_excerpt": "test excerpt",
        "last_source_url": "https://example.com",
        "kit": False,
        "lld_bucket": "unknown",
        "observations": [
            {
                "source_url": "https://example.com/1",
                "raw_excerpt": "obs 1 excerpt",
                "signal_kind": "bin",
                "price_fg": 600.0,
                "observed_at": "2025-01-15",
                "variant_key": "runeword:test",
            },
            {
                "source_url": "https://example.com/2",
                "raw_excerpt": "obs 2 excerpt",
                "signal_kind": "sold",
                "price_fg": 400.0,
                "observed_at": "2025-01-14",
                "variant_key": "runeword:test_v2",
            },
        ],
    }
    base.update(overrides)
    return base


class TestBuildHtmlDisplayMode:
    def test_html_contains_display_mode_selector(self):
        html = _build_html("test_market", [_minimal_row()])
        assert 'id="displayMode"' in html

    def test_html_contains_three_display_mode_options(self):
        html = _build_html("test_market", [_minimal_row()])
        assert 'value="grouped"' in html
        assert 'value="expanded_by_variant"' in html
        assert 'value="expanded_by_listing"' in html

    def test_html_contains_observations_in_json_payload(self):
        row = _minimal_row()
        html = _build_html("test_market", [row])
        # Extract the JSON payload from the HTML
        marker = "const DATA = "
        start = html.index(marker) + len(marker)
        end = html.index(";\n", start)
        payload = json.loads(html[start:end])
        assert len(payload) == 1
        assert "observations" in payload[0]
        assert len(payload[0]["observations"]) == 2

    def test_display_mode_state_initialized_to_grouped(self):
        html = _build_html("test_market", [_minimal_row()])
        assert 'displayMode:"grouped"' in html

    def test_expand_rows_function_present(self):
        html = _build_html("test_market", [_minimal_row()])
        assert "function expandRows" in html

    def test_display_mode_event_listener_present(self):
        html = _build_html("test_market", [_minimal_row()])
        assert '"displayMode"' in html
        assert "state.displayMode" in html


# ---------------------------------------------------------------------------
# 15.2 — Filter/sort state preservation across mode switches
# ---------------------------------------------------------------------------

class TestFilterSortPreservation:
    """Verify that the JS state object retains filter/sort when displayMode changes.

    Since the JS render pipeline is: filterRows(DATA) -> expandRows -> sortRows,
    changing displayMode only affects expandRows — filter and sort state are
    independent fields in the state object and are never reset by mode switching.
    """

    def test_state_object_has_all_filter_fields_and_display_mode(self):
        html = _build_html("test_market", [_minimal_row()])
        # The state object should contain displayMode alongside all filter fields
        assert "displayMode:" in html
        assert "sort:" in html
        assert "q:" in html
        assert "minFg:" in html
        assert "charClass:" in html
        assert "rowKind:" in html

    def test_render_uses_expand_rows_in_pipeline(self):
        """The render function should call expandRows in its pipeline."""
        html = _build_html("test_market", [_minimal_row()])
        assert "expandRows(filterRows(DATA))" in html

    def test_display_mode_change_only_sets_display_mode(self):
        """The displayMode event listener should only set state.displayMode, not reset other state."""
        html = _build_html("test_market", [_minimal_row()])
        # Find the displayMode event listener line
        lines = html.split("\n")
        dm_lines = [l for l in lines if "displayMode" in l and "addEventListener" in l]
        assert len(dm_lines) == 1
        listener_line = dm_lines[0]
        # Should set displayMode and call render, nothing else
        assert "state.displayMode = e.target.value" in listener_line
        assert "render()" in listener_line
        # Should NOT reset other state fields
        assert "state.q" not in listener_line
        assert "state.sort" not in listener_line
        assert "state.minFg" not in listener_line
