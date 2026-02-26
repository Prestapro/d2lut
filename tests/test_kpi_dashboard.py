"""Tests for KPI + regression dashboard (Task 32).

Covers: KPISnapshot creation, comparison, regression thresholds,
persistence/loading, HTML generation, edge cases.
"""
from __future__ import annotations

import sqlite3

import pytest

from d2lut.overlay.kpi_dashboard import (
    DEFAULT_THRESHOLDS,
    KPISnapshot,
    build_kpi_dashboard_html,
    check_regression_thresholds,
    collect_kpi_snapshot,
    compare_snapshots,
    ensure_kpi_table,
    load_kpi_history,
    persist_kpi_snapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_snapshot(**overrides) -> KPISnapshot:
    defaults = dict(
        timestamp="2025-01-15T12:00:00Z",
        observed_prices=1100,
        variants=85,
        canonical_items=59,
        high_value_observations=556,
        high_value_variants=39,
        resolved_by_image_obs=14,
        resolved_by_image_variants=10,
        ocr_precision=0.9286,
        ocr_comparable_rows=14,
        ocr_exact_match=13,
        ocr_mismatch_count=1,
    )
    defaults.update(overrides)
    return KPISnapshot(**defaults)


def _in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    ensure_kpi_table(conn)
    return conn


def _seed_market_db(conn: sqlite3.Connection) -> None:
    """Create minimal observed_prices and price_estimates tables for testing."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS observed_prices (
            id INTEGER PRIMARY KEY,
            market_key TEXT,
            variant_key TEXT,
            canonical_item_id TEXT,
            price_fg REAL,
            source TEXT,
            signal_kind TEXT,
            source_kind TEXT,
            raw_excerpt TEXT,
            source_url TEXT,
            thread_id INTEGER,
            observed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS price_estimates (
            market_key TEXT,
            variant_key TEXT,
            estimate_fg REAL,
            range_low_fg REAL,
            range_high_fg REAL,
            confidence TEXT,
            sample_count INTEGER,
            canonical_item_id TEXT
        );
    """)
    # Insert sample observations
    conn.executemany(
        "INSERT INTO observed_prices (market_key, variant_key, canonical_item_id, price_fg, source) VALUES (?,?,?,?,?)",
        [
            ("d2r_sc_ladder", "unique:shako", "shako", 350.0, "title"),
            ("d2r_sc_ladder", "unique:shako", "shako", 400.0, "title"),
            ("d2r_sc_ladder", "rune:ber", "ber", 5000.0, "title"),
            ("d2r_sc_ladder", "rune:jah", "jah", 4500.0, "image_ocr_candidate:42"),
            ("d2r_sc_ladder", "base:monarch:4os", "monarch", 50.0, "title"),
        ],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# KPISnapshot creation
# ---------------------------------------------------------------------------

class TestKPISnapshotCreation:
    def test_default_values(self):
        s = KPISnapshot(timestamp="2025-01-01T00:00:00Z")
        assert s.observed_prices == 0
        assert s.ocr_precision == 0.0

    def test_custom_values(self):
        s = _make_snapshot()
        assert s.observed_prices == 1100
        assert s.variants == 85
        assert s.ocr_precision == 0.9286

    def test_all_fields_present(self):
        s = _make_snapshot()
        expected_fields = {
            "timestamp", "observed_prices", "variants", "canonical_items",
            "high_value_observations", "high_value_variants",
            "resolved_by_image_obs", "resolved_by_image_variants",
            "ocr_precision", "ocr_comparable_rows", "ocr_exact_match",
            "ocr_mismatch_count",
        }
        assert set(s.__dataclass_fields__.keys()) == expected_fields


# ---------------------------------------------------------------------------
# Snapshot comparison
# ---------------------------------------------------------------------------

class TestCompareSnapshots:
    def test_identical_snapshots(self):
        s = _make_snapshot()
        result = compare_snapshots(s, s)
        for key, info in result.items():
            assert info["delta"] == 0
            assert info["pct_change"] == 0.0

    def test_increase(self):
        baseline = _make_snapshot(observed_prices=1000)
        current = _make_snapshot(observed_prices=1100)
        result = compare_snapshots(current, baseline)
        assert result["observed_prices"]["delta"] == 100
        assert result["observed_prices"]["pct_change"] == 0.1

    def test_decrease(self):
        baseline = _make_snapshot(variants=100)
        current = _make_snapshot(variants=90)
        result = compare_snapshots(current, baseline)
        assert result["variants"]["delta"] == -10
        assert result["variants"]["pct_change"] == -0.1

    def test_zero_baseline(self):
        baseline = _make_snapshot(resolved_by_image_obs=0)
        current = _make_snapshot(resolved_by_image_obs=5)
        result = compare_snapshots(current, baseline)
        assert result["resolved_by_image_obs"]["delta"] == 5
        # inf when dividing by zero baseline
        assert result["resolved_by_image_obs"]["pct_change"] == float("inf")

    def test_precision_delta(self):
        baseline = _make_snapshot(ocr_precision=0.9286)
        current = _make_snapshot(ocr_precision=0.8500)
        result = compare_snapshots(current, baseline)
        assert result["ocr_precision"]["delta"] == pytest.approx(-0.0786, abs=0.001)


# ---------------------------------------------------------------------------
# Regression threshold checking
# ---------------------------------------------------------------------------

class TestRegressionThresholds:
    def test_no_alerts_when_healthy(self):
        baseline = _make_snapshot()
        current = _make_snapshot()
        alerts = check_regression_thresholds(current, baseline)
        assert alerts == []

    def test_observed_prices_drop_triggers_alert(self):
        baseline = _make_snapshot(observed_prices=1000)
        current = _make_snapshot(observed_prices=850)  # 15% drop > 10% threshold
        alerts = check_regression_thresholds(current, baseline)
        assert any("Observed prices" in a for a in alerts)

    def test_observed_prices_small_drop_no_alert(self):
        baseline = _make_snapshot(observed_prices=1000)
        current = _make_snapshot(observed_prices=950)  # 5% drop < 10% threshold
        alerts = check_regression_thresholds(current, baseline)
        assert not any("Observed prices" in a for a in alerts)

    def test_variants_drop_triggers_alert(self):
        baseline = _make_snapshot(variants=100)
        current = _make_snapshot(variants=90)  # 10% drop > 5% threshold
        alerts = check_regression_thresholds(current, baseline)
        assert any("Variants" in a for a in alerts)

    def test_ocr_precision_drop_triggers_alert(self):
        baseline = _make_snapshot(ocr_precision=0.93)
        current = _make_snapshot(ocr_precision=0.85)  # 0.08 drop > 0.05 threshold
        alerts = check_regression_thresholds(current, baseline)
        assert any("OCR precision" in a for a in alerts)

    def test_ocr_precision_small_drop_no_alert(self):
        baseline = _make_snapshot(ocr_precision=0.93)
        current = _make_snapshot(ocr_precision=0.90)  # 0.03 drop < 0.05 threshold
        alerts = check_regression_thresholds(current, baseline)
        assert not any("OCR precision" in a for a in alerts)

    def test_high_value_drop_triggers_alert(self):
        baseline = _make_snapshot(high_value_observations=1000)
        current = _make_snapshot(high_value_observations=800)  # 20% drop > 15%
        alerts = check_regression_thresholds(current, baseline)
        assert any("High-value" in a for a in alerts)

    def test_custom_thresholds(self):
        baseline = _make_snapshot(observed_prices=100)
        current = _make_snapshot(observed_prices=80)  # 20% drop
        custom = {"observed_prices": {"max_drop_pct": 0.25, "label": "Obs"}}
        alerts = check_regression_thresholds(current, baseline, thresholds=custom)
        assert alerts == []  # 20% < 25% custom threshold

    def test_multiple_alerts(self):
        baseline = _make_snapshot(observed_prices=1000, variants=100, ocr_precision=0.95)
        current = _make_snapshot(observed_prices=800, variants=90, ocr_precision=0.85)
        alerts = check_regression_thresholds(current, baseline)
        assert len(alerts) >= 2


# ---------------------------------------------------------------------------
# Persistence and loading
# ---------------------------------------------------------------------------

class TestPersistAndLoad:
    def test_persist_and_load_roundtrip(self):
        conn = _in_memory_db()
        s = _make_snapshot()
        row_id = persist_kpi_snapshot(conn, s)
        assert row_id > 0

        history = load_kpi_history(conn, limit=10)
        assert len(history) == 1
        loaded = history[0]
        assert loaded.timestamp == s.timestamp
        assert loaded.observed_prices == s.observed_prices
        assert loaded.ocr_precision == s.ocr_precision
        conn.close()

    def test_load_ordering_newest_first(self):
        conn = _in_memory_db()
        persist_kpi_snapshot(conn, _make_snapshot(timestamp="2025-01-01T00:00:00Z"))
        persist_kpi_snapshot(conn, _make_snapshot(timestamp="2025-01-02T00:00:00Z"))
        persist_kpi_snapshot(conn, _make_snapshot(timestamp="2025-01-03T00:00:00Z"))

        history = load_kpi_history(conn, limit=10)
        assert len(history) == 3
        assert history[0].timestamp == "2025-01-03T00:00:00Z"
        assert history[2].timestamp == "2025-01-01T00:00:00Z"
        conn.close()

    def test_load_respects_limit(self):
        conn = _in_memory_db()
        for i in range(10):
            persist_kpi_snapshot(conn, _make_snapshot(timestamp=f"2025-01-{i+1:02d}T00:00:00Z"))

        history = load_kpi_history(conn, limit=3)
        assert len(history) == 3
        conn.close()

    def test_load_empty_db(self):
        conn = _in_memory_db()
        history = load_kpi_history(conn, limit=10)
        assert history == []
        conn.close()

    def test_ensure_table_idempotent(self):
        conn = sqlite3.connect(":memory:")
        ensure_kpi_table(conn)
        ensure_kpi_table(conn)  # should not raise
        conn.close()


# ---------------------------------------------------------------------------
# Collect from DB
# ---------------------------------------------------------------------------

class TestCollectKPISnapshot:
    def test_collect_from_seeded_db(self):
        conn = sqlite3.connect(":memory:")
        _seed_market_db(conn)
        ensure_kpi_table(conn)

        snap = collect_kpi_snapshot(conn, "d2r_sc_ladder", min_fg=300.0)
        assert snap.observed_prices == 5
        assert snap.variants == 4
        assert snap.canonical_items == 4
        # >=300fg: shako(350), shako(400), ber(5000), jah(4500) = 4 obs
        assert snap.high_value_observations == 4
        # image_ocr_candidate source: jah only
        assert snap.resolved_by_image_obs == 1
        assert snap.resolved_by_image_variants == 1
        conn.close()

    def test_collect_empty_db(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript("""
            CREATE TABLE observed_prices (
                id INTEGER PRIMARY KEY, market_key TEXT, variant_key TEXT,
                canonical_item_id TEXT, price_fg REAL, source TEXT,
                signal_kind TEXT, source_kind TEXT, raw_excerpt TEXT,
                source_url TEXT, thread_id INTEGER, observed_at TEXT
            );
        """)
        ensure_kpi_table(conn)
        snap = collect_kpi_snapshot(conn, "d2r_sc_ladder")
        assert snap.observed_prices == 0
        assert snap.variants == 0
        assert snap.ocr_precision == 0.0
        conn.close()


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

class TestBuildKPIDashboardHTML:
    def test_produces_valid_html(self):
        history = [_make_snapshot()]
        html_str = build_kpi_dashboard_html(history)
        assert html_str.startswith("<!DOCTYPE html>")
        assert "</html>" in html_str

    def test_contains_kpi_values(self):
        s = _make_snapshot(observed_prices=1234)
        html_str = build_kpi_dashboard_html([s])
        assert "1234" in html_str

    def test_contains_alert_banner(self):
        history = [_make_snapshot()]
        alerts = ["REGRESSION: Test alert"]
        html_str = build_kpi_dashboard_html(history, alerts=alerts)
        assert "Regression Alerts" in html_str
        assert "Test alert" in html_str

    def test_no_alert_banner_when_clean(self):
        history = [_make_snapshot()]
        html_str = build_kpi_dashboard_html(history, alerts=[])
        # CSS class definition exists, but no actual alert div should be rendered
        assert '<div class="alert-banner">' not in html_str

    def test_comparison_deltas_shown(self):
        s1 = _make_snapshot(timestamp="2025-01-02T00:00:00Z", observed_prices=1200)
        s2 = _make_snapshot(timestamp="2025-01-01T00:00:00Z", observed_prices=1100)
        html_str = build_kpi_dashboard_html([s1, s2])
        # Should contain delta indicators
        assert "+" in html_str or "−" in html_str or "—" in html_str

    def test_history_table_rows(self):
        snapshots = [
            _make_snapshot(timestamp=f"2025-01-{i+1:02d}T00:00:00Z")
            for i in range(3)
        ]
        snapshots.reverse()  # newest first
        html_str = build_kpi_dashboard_html(snapshots)
        assert "2025-01-03" in html_str
        assert "2025-01-01" in html_str

    def test_empty_history(self):
        html_str = build_kpi_dashboard_html([])
        assert "<!DOCTYPE html>" in html_str
        # Should not crash with empty history

    def test_dark_theme_css(self):
        html_str = build_kpi_dashboard_html([_make_snapshot()])
        assert "--bg: #1e1e2e" in html_str

    def test_self_contained(self):
        html_str = build_kpi_dashboard_html([_make_snapshot()])
        # No external CSS/JS references
        assert "href=" not in html_str or 'href="http' not in html_str
        assert "KPI_HISTORY" in html_str

    def test_json_payload_embedded(self):
        html_str = build_kpi_dashboard_html([_make_snapshot(observed_prices=9999)])
        assert "9999" in html_str
        assert "KPI_HISTORY" in html_str


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_first_snapshot_no_baseline(self):
        """First snapshot should not produce alerts (no baseline to compare)."""
        baseline_snap = _make_snapshot()
        # With only one snapshot, check_regression_thresholds needs two snapshots
        # so the CLI handles this by checking len(history) >= 2
        # Here we verify the function itself works with identical snapshots
        alerts = check_regression_thresholds(baseline_snap, baseline_snap)
        assert alerts == []

    def test_zero_baseline_no_crash(self):
        baseline = _make_snapshot(
            observed_prices=0, variants=0, ocr_precision=0.0,
            high_value_observations=0,
        )
        current = _make_snapshot(observed_prices=100, variants=10)
        # Should not crash on zero division
        alerts = check_regression_thresholds(current, baseline)
        assert isinstance(alerts, list)

    def test_compare_zero_baseline(self):
        baseline = _make_snapshot(observed_prices=0)
        current = _make_snapshot(observed_prices=100)
        result = compare_snapshots(current, baseline)
        assert result["observed_prices"]["delta"] == 100
