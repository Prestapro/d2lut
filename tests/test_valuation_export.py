"""Tests for d2lut.overlay.valuation_export module.

Covers: HTML generation, filtering, highlighting, summary computation,
and conversion from scan results / dicts.
"""

from __future__ import annotations

import json

import pytest

from d2lut.overlay.valuation_export import (
    ValuationExportConfig,
    ValuationItem,
    ValuationSummary,
    build_valuation_html,
    compute_summary,
    filter_items,
    items_from_scan_result,
    _passes_confidence,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_item(
    slot: int = 0,
    name: str = "Test Item",
    price_fg: float | None = None,
    price_low: float | None = None,
    price_high: float | None = None,
    confidence: str | None = None,
    sample_count: int | None = None,
    canonical_id: str | None = None,
    match_confidence: float = 0.9,
    match_type: str = "exact",
) -> ValuationItem:
    has_price = price_fg is not None
    return ValuationItem(
        slot_index=slot,
        item_name=name,
        canonical_item_id=canonical_id,
        match_confidence=match_confidence,
        match_type=match_type,
        price_fg=price_fg,
        price_low_fg=price_low,
        price_high_fg=price_high,
        price_confidence=confidence,
        sample_count=sample_count,
        has_price=has_price,
    )


@pytest.fixture
def sample_items() -> list[ValuationItem]:
    return [
        _make_item(0, "Shako", 350, 300, 400, "high", 20, "unique:harlequin_crest"),
        _make_item(1, "Ber Rune", 2500, 2400, 2600, "high", 50, "rune:ber"),
        _make_item(2, "Tal Ammy", 80, 60, 100, "medium", 8, "set:tal_rasha_amulet"),
        _make_item(3, "Unknown Rare", None, None, None, None, None, None, 0.3, "fuzzy"),
        _make_item(4, "Vex Rune", 150, 130, 170, "low", 3, "rune:vex"),
    ]


# ---------------------------------------------------------------------------
# compute_summary
# ---------------------------------------------------------------------------

class TestComputeSummary:
    def test_basic_summary(self, sample_items):
        s = compute_summary(sample_items, high_value_threshold=300)
        assert s.item_count == 5
        assert s.priced_count == 4
        assert s.no_data_count == 1
        assert s.high_value_count == 2  # Shako (350) + Ber (2500)
        assert s.total_value_fg == pytest.approx(350 + 2500 + 80 + 150)

    def test_empty_items(self):
        s = compute_summary([])
        assert s.item_count == 0
        assert s.total_value_fg == 0.0
        assert s.no_data_count == 0

    def test_all_no_data(self):
        items = [_make_item(i, f"Item {i}") for i in range(3)]
        s = compute_summary(items)
        assert s.no_data_count == 3
        assert s.priced_count == 0
        assert s.total_value_fg == 0.0

    def test_custom_threshold(self, sample_items):
        s = compute_summary(sample_items, high_value_threshold=100)
        # Shako(350), Ber(2500), Vex(150) >= 100
        assert s.high_value_count == 3


# ---------------------------------------------------------------------------
# filter_items
# ---------------------------------------------------------------------------

class TestFilterItems:
    def test_no_filter(self, sample_items):
        cfg = ValuationExportConfig()
        result = filter_items(sample_items, cfg)
        assert len(result) == 5

    def test_min_fg_filter(self, sample_items):
        cfg = ValuationExportConfig(min_fg=100)
        result = filter_items(sample_items, cfg)
        # Shako(350), Ber(2500), Vex(150) pass; Tal(80) filtered; Unknown(no data) kept
        names = [it.item_name for it in result]
        assert "Shako" in names
        assert "Ber Rune" in names
        assert "Vex Rune" in names
        assert "Unknown Rare" in names  # no-data kept by default
        assert "Tal Ammy" not in names

    def test_hide_no_data(self, sample_items):
        cfg = ValuationExportConfig(show_no_data=False)
        result = filter_items(sample_items, cfg)
        assert all(it.has_price for it in result)
        assert len(result) == 4

    def test_confidence_filter(self, sample_items):
        cfg = ValuationExportConfig(min_confidence="medium")
        result = filter_items(sample_items, cfg)
        names = [it.item_name for it in result]
        assert "Vex Rune" not in names  # low confidence
        assert "Shako" in names
        assert "Tal Ammy" in names

    def test_confidence_filter_high_only(self, sample_items):
        cfg = ValuationExportConfig(min_confidence="high")
        result = filter_items(sample_items, cfg)
        priced = [it for it in result if it.has_price]
        assert all(it.price_confidence == "high" for it in priced)

    def test_combined_filters(self, sample_items):
        cfg = ValuationExportConfig(min_fg=200, min_confidence="high", show_no_data=False)
        result = filter_items(sample_items, cfg)
        assert len(result) == 2  # Shako + Ber
        names = {it.item_name for it in result}
        assert names == {"Shako", "Ber Rune"}


# ---------------------------------------------------------------------------
# _passes_confidence
# ---------------------------------------------------------------------------

class TestPassesConfidence:
    def test_none_min_passes_all(self):
        assert _passes_confidence("low", None) is True
        assert _passes_confidence(None, None) is True

    def test_exact_match(self):
        assert _passes_confidence("high", "high") is True
        assert _passes_confidence("medium", "medium") is True

    def test_above_threshold(self):
        assert _passes_confidence("high", "low") is True
        assert _passes_confidence("medium", "low") is True

    def test_below_threshold(self):
        assert _passes_confidence("low", "high") is False
        assert _passes_confidence("low", "medium") is False

    def test_none_item_conf(self):
        assert _passes_confidence(None, "low") is False


# ---------------------------------------------------------------------------
# items_from_scan_result (dict list path)
# ---------------------------------------------------------------------------

class TestItemsFromDictList:
    def test_basic_conversion(self):
        raw = [
            {
                "slot_index": 0,
                "item_name": "Shako",
                "canonical_item_id": "unique:harlequin_crest",
                "match_confidence": 0.95,
                "match_type": "exact",
                "price_fg": 350,
                "price_low_fg": 300,
                "price_high_fg": 400,
                "price_confidence": "high",
                "sample_count": 20,
                "has_price": True,
            },
            {
                "slot_index": 1,
                "item_name": "Unknown",
                "has_price": False,
            },
        ]
        items = items_from_scan_result(raw)
        assert len(items) == 2
        assert items[0].item_name == "Shako"
        assert items[0].price_fg == 350
        assert items[0].has_price is True
        assert items[1].has_price is False

    def test_missing_fields_default(self):
        raw = [{"item_name": "Bare Item"}]
        items = items_from_scan_result(raw)
        assert items[0].slot_index == 0
        assert items[0].match_confidence == 0.0
        assert items[0].has_price is False

    def test_infer_has_price_from_price_fg(self):
        raw = [{"item_name": "X", "price_fg": 100}]
        items = items_from_scan_result(raw)
        assert items[0].has_price is True


# ---------------------------------------------------------------------------
# build_valuation_html
# ---------------------------------------------------------------------------

class TestBuildValuationHtml:
    def test_produces_valid_html(self, sample_items):
        html = build_valuation_html(sample_items)
        assert html.startswith("<!doctype html>")
        assert "</html>" in html

    def test_contains_item_names(self, sample_items):
        html = build_valuation_html(sample_items)
        assert "Shako" in html
        assert "Ber Rune" in html
        assert "Unknown Rare" in html

    def test_contains_summary_stats(self, sample_items):
        html = build_valuation_html(sample_items)
        # Total value should appear in summary
        assert "3,080" in html  # 350+2500+80+150
        assert "Items:" in html

    def test_custom_title(self, sample_items):
        cfg = ValuationExportConfig(title="My Stash Tab 1")
        html = build_valuation_html(sample_items, cfg)
        assert "My Stash Tab 1" in html

    def test_high_value_threshold_in_html(self, sample_items):
        cfg = ValuationExportConfig(high_value_threshold=500)
        html = build_valuation_html(sample_items, cfg)
        assert "500" in html  # threshold appears in stats header

    def test_self_contained_no_external_deps(self, sample_items):
        html = build_valuation_html(sample_items)
        # No external CSS/JS links
        assert 'href="http' not in html
        assert 'src="http' not in html
        # Has inline style and script
        assert "<style>" in html
        assert "<script>" in html

    def test_json_payload_embedded(self, sample_items):
        html = build_valuation_html(sample_items)
        # The DATA variable should contain valid JSON with our items
        assert "const DATA=" in html

    def test_empty_items(self):
        html = build_valuation_html([])
        assert "<!doctype html>" in html
        assert "Items:" in html

    def test_export_type_shown(self, sample_items):
        cfg = ValuationExportConfig(export_type="stash")
        html = build_valuation_html(sample_items, cfg)
        assert "type: stash" in html

    def test_html_escapes_title(self):
        cfg = ValuationExportConfig(title='<script>alert("xss")</script>')
        html = build_valuation_html([], cfg)
        assert "<script>alert" not in html.split("<style>")[0]  # title area
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# Integration: filter + build round-trip
# ---------------------------------------------------------------------------

class TestFilterAndBuild:
    def test_filtered_export(self, sample_items):
        cfg = ValuationExportConfig(min_fg=200, show_no_data=False)
        filtered = filter_items(sample_items, cfg)
        html = build_valuation_html(filtered, cfg)
        assert "Shako" in html
        assert "Ber Rune" in html
        # Tal Ammy (80fg) should be filtered out from the JSON payload
        assert "Tal Ammy" not in html
