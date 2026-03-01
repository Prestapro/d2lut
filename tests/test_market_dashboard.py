"""Tests for d2lut.overlay.market_dashboard."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from d2lut.overlay.market_dashboard import (
    CATEGORIES,
    DashboardData,
    DashboardRow,
    RefreshInfo,
    build_dashboard_html,
    classify_category,
    export_dashboard,
    load_dashboard_data,
)


# ---------------------------------------------------------------------------
# classify_category
# ---------------------------------------------------------------------------


class TestClassifyCategory:
    def test_rune_prefix(self):
        assert classify_category("rune:ber") == "runes"

    def test_unique_prefix(self):
        assert classify_category("unique:shako") == "uniques"

    def test_runeword_prefix(self):
        assert classify_category("runeword:enigma") == "runewords"

    def test_set_prefix(self):
        assert classify_category("set:tal_rasha_amulet") == "sets"

    def test_base_prefix(self):
        assert classify_category("base:monarch") == "bases"

    def test_charm_prefix(self):
        assert classify_category("charm:gheed") == "charms"

    def test_jewel_prefix(self):
        assert classify_category("jewel:rainbow_facet") == "jewels"

    def test_weapon_keyword(self):
        assert classify_category("phase_blade_sword") == "weapons"

    def test_armor_keyword(self):
        assert classify_category("dusk_shroud_armor") == "armor"

    def test_unknown_falls_to_other(self):
        assert classify_category("mystery_item_xyz") == "other"

    def test_case_insensitive(self):
        assert classify_category("RUNE:Jah") == "runes"
        assert classify_category("Unique:Shako") == "uniques"

    def test_all_categories_covered(self):
        """Ensure CATEGORIES list includes expected entries."""
        assert "all" in CATEGORIES
        assert "runes" in CATEGORIES
        assert "other" in CATEGORIES
        assert len(CATEGORIES) == 11


# ---------------------------------------------------------------------------
# Premium detection
# ---------------------------------------------------------------------------


class TestPremiumDetection:
    def test_torch_detected(self):
        row = DashboardRow(
            variant_key="unique:hellfire_torch:sorceress",
            category="uniques",
            estimate_fg=1000.0,
            range_low_fg=800.0,
            range_high_fg=1200.0,
            confidence="high",
            sample_count=15,
            updated_at="2024-01-01",
        )
        # Manually check via the module-level helper
        from d2lut.overlay.market_dashboard import _detect_premium
        pcls, pmult, pprice = _detect_premium(row.variant_key, row.estimate_fg)
        assert pcls == "torch"
        assert pmult is not None and pmult > 1.0
        assert pprice is not None and pprice > 1000.0

    def test_no_premium_for_plain_item(self):
        from d2lut.overlay.market_dashboard import _detect_premium
        pcls, pmult, pprice = _detect_premium("rune:ber", 5000.0)
        assert pcls is None
        assert pmult is None

    def test_no_premium_when_no_estimate(self):
        from d2lut.overlay.market_dashboard import _detect_premium
        pcls, pmult, pprice = _detect_premium("unique:hellfire_torch", None)
        assert pcls is None


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------


class TestBuildDashboardHtml:
    def _sample_data(self) -> DashboardData:
        return DashboardData(
            rows=[
                DashboardRow(
                    variant_key="rune:ber",
                    category="runes",
                    estimate_fg=5000.0,
                    range_low_fg=4500.0,
                    range_high_fg=5500.0,
                    confidence="high",
                    sample_count=25,
                    updated_at="2024-01-15",
                ),
                DashboardRow(
                    variant_key="unique:shako",
                    category="uniques",
                    estimate_fg=300.0,
                    range_low_fg=250.0,
                    range_high_fg=400.0,
                    confidence="medium",
                    sample_count=10,
                    updated_at="2024-01-14",
                ),
                DashboardRow(
                    variant_key="unique:hellfire_torch:sorceress",
                    category="uniques",
                    estimate_fg=1000.0,
                    range_low_fg=800.0,
                    range_high_fg=1500.0,
                    confidence="high",
                    sample_count=8,
                    updated_at="2024-01-13",
                    premium_class="torch",
                    premium_multiplier=2.5,
                    premium_price_fg=2500.0,
                ),
            ],
            refresh=RefreshInfo(
                last_success_at="2024-01-15 12:00:00",
                last_refresh_at="2024-01-15 12:00:00",
                observations_delta=15,
                estimates_delta=3,
            ),
            market_key="d2r_sc_ladder",
            generated_at="2024-01-15 13:00:00",
        )

    def test_produces_valid_html(self):
        html = build_dashboard_html(self._sample_data())
        assert html.startswith("<!doctype html>")
        assert "</html>" in html

    def test_contains_variant_keys(self):
        html = build_dashboard_html(self._sample_data())
        assert "rune:ber" in html
        assert "unique:shako" in html

    def test_contains_refresh_info(self):
        html = build_dashboard_html(self._sample_data())
        assert "last_success" in html
        assert "2024-01-15 12:00:00" in html

    def test_contains_category_filters(self):
        html = build_dashboard_html(self._sample_data())
        assert "All categories" in html
        assert "Runes" in html
        assert "Uniques" in html

    def test_contains_confidence_filters(self):
        html = build_dashboard_html(self._sample_data())
        assert "All confidence" in html
        assert "High" in html
        assert "Medium" in html

    def test_self_contained(self):
        html = build_dashboard_html(self._sample_data())
        assert "<style>" in html
        assert "<script>" in html
        # No external CSS/JS references
        assert 'href="http' not in html
        assert 'src="http' not in html

    def test_json_payload_embedded(self):
        html = build_dashboard_html(self._sample_data())
        assert "const DATA=" in html
        assert "const REFRESH=" in html

    def test_premium_column_present(self):
        html = build_dashboard_html(self._sample_data())
        assert "Premium" in html
        assert "torch" in html

    def test_empty_rows(self):
        data = DashboardData(rows=[], generated_at="2024-01-01 00:00:00")
        html = build_dashboard_html(data)
        assert "Items:</span> <span" in html
        assert "<!doctype html>" in html

    def test_dark_theme_css_vars(self):
        html = build_dashboard_html(self._sample_data())
        assert "--bg: #0b1118" in html
        assert "--panel: #101923" in html


# ---------------------------------------------------------------------------
# DB integration (in-memory SQLite)
# ---------------------------------------------------------------------------


def _create_test_db(path: str) -> None:
    """Create a minimal test DB with price_estimates and refresh_metadata."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS price_estimates (
            market_key TEXT NOT NULL,
            variant_key TEXT NOT NULL,
            estimate_fg REAL,
            range_low_fg REAL,
            range_high_fg REAL,
            confidence TEXT,
            sample_count INTEGER,
            updated_at TEXT,
            PRIMARY KEY (market_key, variant_key)
        );
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
    """)
    conn.executemany(
        "INSERT INTO price_estimates VALUES (?,?,?,?,?,?,?,?)",
        [
            ("d2r_sc_ladder", "rune:ber", 5000, 4500, 5500, "high", 25, "2024-01-15"),
            ("d2r_sc_ladder", "unique:shako", 300, 250, 400, "medium", 10, "2024-01-14"),
            ("d2r_sc_ladder", "set:tal_rasha_amulet", 150, 100, 200, "low", 5, "2024-01-13"),
        ],
    )
    conn.execute(
        "INSERT INTO refresh_metadata (started_at, finished_at, success, "
        "observations_delta, estimates_delta, trigger) VALUES (?,?,?,?,?,?)",
        ("2024-01-15 11:00:00", "2024-01-15 11:05:00", 1, 20, 5, "manual"),
    )
    conn.commit()
    conn.close()


class TestLoadDashboardData:
    def test_loads_rows(self, tmp_path):
        db = str(tmp_path / "test.db")
        _create_test_db(db)
        data = load_dashboard_data(db)
        assert len(data.rows) == 3
        assert data.rows[0].variant_key == "rune:ber"  # highest FG first
        assert data.rows[0].category == "runes"

    def test_loads_refresh_info(self, tmp_path):
        db = str(tmp_path / "test.db")
        _create_test_db(db)
        data = load_dashboard_data(db)
        assert data.refresh.last_success_at == "2024-01-15 11:05:00"
        assert data.refresh.observations_delta == 20

    def test_handles_missing_refresh_table(self, tmp_path):
        db = str(tmp_path / "test.db")
        conn = sqlite3.connect(db)
        conn.executescript("""
            CREATE TABLE price_estimates (
                market_key TEXT, variant_key TEXT, estimate_fg REAL,
                range_low_fg REAL, range_high_fg REAL, confidence TEXT,
                sample_count INTEGER, updated_at TEXT,
                PRIMARY KEY (market_key, variant_key)
            );
        """)
        conn.execute(
            "INSERT INTO price_estimates VALUES (?,?,?,?,?,?,?,?)",
            ("d2r_sc_ladder", "rune:jah", 4000, 3500, 4500, "high", 20, "2024-01-15"),
        )
        conn.commit()
        conn.close()
        data = load_dashboard_data(db)
        assert len(data.rows) == 1
        assert data.refresh.last_success_at is None

    def test_category_classification_in_loaded_rows(self, tmp_path):
        db = str(tmp_path / "test.db")
        _create_test_db(db)
        data = load_dashboard_data(db)
        cats = {r.variant_key: r.category for r in data.rows}
        assert cats["rune:ber"] == "runes"
        assert cats["unique:shako"] == "uniques"
        assert cats["set:tal_rasha_amulet"] == "sets"


class TestExportDashboard:
    def test_writes_file(self, tmp_path):
        db = str(tmp_path / "test.db")
        _create_test_db(db)
        out = tmp_path / "out" / "dashboard.html"
        result = export_dashboard(db, out)
        assert result.exists()
        content = result.read_text()
        assert "<!doctype html>" in content
        assert "rune:ber" in content

    def test_creates_parent_dirs(self, tmp_path):
        db = str(tmp_path / "test.db")
        _create_test_db(db)
        out = tmp_path / "deep" / "nested" / "dashboard.html"
        result = export_dashboard(db, out)
        assert result.exists()


# ---------------------------------------------------------------------------
# RefreshDaemon integration
# ---------------------------------------------------------------------------


class TestRefreshDaemonDashboardCallback:
    def test_register_dashboard_export(self, tmp_path):
        """Verify register_dashboard_export adds a callback."""
        from d2lut.overlay.refresh_daemon import RefreshDaemon

        db = str(tmp_path / "test.db")
        _create_test_db(db)
        daemon = RefreshDaemon(db)
        assert len(daemon._on_complete_callbacks) == 0
        daemon.register_dashboard_export(
            out_path=tmp_path / "dash.html",
            market_key="d2r_sc_ladder",
        )
        assert len(daemon._on_complete_callbacks) == 1

    def test_callback_produces_html(self, tmp_path):
        """Verify the registered callback actually writes HTML."""
        from d2lut.overlay.refresh_daemon import RefreshDaemon

        db = str(tmp_path / "test.db")
        _create_test_db(db)
        out = tmp_path / "dash.html"
        daemon = RefreshDaemon(db)
        daemon.register_dashboard_export(out_path=out, market_key="d2r_sc_ladder")
        # Manually fire the callback
        daemon._fire_callbacks()
        assert out.exists()
        content = out.read_text()
        assert "rune:ber" in content
