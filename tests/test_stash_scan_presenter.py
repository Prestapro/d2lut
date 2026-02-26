"""Tests for stash scan presentation layer."""

import pytest
from datetime import datetime

from d2lut.overlay.stash_scan_presenter import (
    StashScanPresenter,
    PresentationConfig
)
from d2lut.overlay.stash_scanner import StashScanResult, ScannedItem
from d2lut.overlay.ocr_parser import ParsedItem
from d2lut.overlay.item_identifier import MatchResult
from d2lut.models import PriceEstimate


@pytest.fixture
def presentation_config():
    """Create a test presentation configuration."""
    return PresentationConfig(
        show_confidence=True,
        show_sample_count=True,
        show_price_range=True,
        show_scan_duration=True,
        show_errors=True,
        max_errors_displayed=5,
        sort_by="value",
        currency_symbol="FG",
        value_thresholds={
            "low": 100.0,
            "medium": 1000.0,
            "high": 5000.0
        }
    )


@pytest.fixture
def presenter(presentation_config):
    """Create a presenter with test configuration."""
    return StashScanPresenter(config=presentation_config)


@pytest.fixture
def sample_scan_result():
    """Create a sample scan result for testing."""
    items = [
        ScannedItem(
            slot_index=0,
            parsed_item=ParsedItem(raw_text="Jah Rune", item_name="Jah Rune"),
            match_result=MatchResult(
                canonical_item_id="rune:jah",
                confidence=0.9,
                matched_name="Jah Rune",
                candidates=[],
                match_type="exact"
            ),
            price_estimate=PriceEstimate(
                variant_key="rune:jah",
                estimate_fg=5000.0,
                range_low_fg=4500.0,
                range_high_fg=5500.0,
                confidence="high",
                sample_count=50,
                last_updated=datetime.now()
            )
        ),
        ScannedItem(
            slot_index=1,
            parsed_item=ParsedItem(raw_text="Ber Rune", item_name="Ber Rune"),
            match_result=MatchResult(
                canonical_item_id="rune:ber",
                confidence=0.85,
                matched_name="Ber Rune",
                candidates=[],
                match_type="exact"
            ),
            price_estimate=PriceEstimate(
                variant_key="rune:ber",
                estimate_fg=4000.0,
                range_low_fg=3800.0,
                range_high_fg=4200.0,
                confidence="high",
                sample_count=45,
                last_updated=datetime.now()
            )
        ),
        ScannedItem(
            slot_index=2,
            parsed_item=ParsedItem(raw_text="Shako", item_name="Shako"),
            match_result=MatchResult(
                canonical_item_id="unique:shako",
                confidence=0.8,
                matched_name="Harlequin Crest",
                candidates=[],
                match_type="slang"
            ),
            price_estimate=PriceEstimate(
                variant_key="unique:shako",
                estimate_fg=800.0,
                range_low_fg=700.0,
                range_high_fg=900.0,
                confidence="medium",
                sample_count=30,
                last_updated=datetime.now()
            )
        ),
        ScannedItem(
            slot_index=3,
            parsed_item=ParsedItem(raw_text="Unknown Item", item_name="Unknown Item"),
            match_result=MatchResult(
                canonical_item_id=None,
                confidence=0.0,
                matched_name="Unknown Item",
                candidates=[],
                match_type="no_match"
            ),
            price_estimate=None
        ),
    ]
    
    return StashScanResult(
        items=items,
        total_value_fg=9800.0,
        scan_timestamp=datetime.now().timestamp(),
        scan_duration_ms=150.0,
        items_with_prices=3,
        items_without_prices=1,
        scan_errors=["Error processing slot 3: Test error"]
    )


def test_presenter_initialization():
    """Test presenter initializes with default config."""
    presenter = StashScanPresenter()
    assert presenter.config is not None
    assert presenter.config.currency_symbol == "FG"
    assert presenter.config.sort_by == "value"


def test_presenter_custom_config(presentation_config):
    """Test presenter initializes with custom config."""
    presenter = StashScanPresenter(config=presentation_config)
    assert presenter.config == presentation_config
    assert presenter.config.show_confidence is True
    assert presenter.config.max_errors_displayed == 5


def test_format_detailed_summary(presenter, sample_scan_result):
    """Test detailed summary formatting."""
    summary = presenter.format_detailed_summary(sample_scan_result)
    
    # Check header
    assert "STASH SCAN RESULTS" in summary
    
    # Check summary statistics
    assert "Total Items Scanned:" in summary
    assert "4" in summary  # 4 items
    assert "Items with Prices:" in summary
    assert "3" in summary  # 3 with prices
    assert "Items without Prices:" in summary
    assert "1" in summary  # 1 without
    assert "Total Stash Value:" in summary
    assert "9,800" in summary
    assert "FG" in summary
    
    # Check scan duration
    assert "Scan Duration:" in summary
    assert "150ms" in summary
    
    # Check errors section
    assert "Errors" in summary or "error" in summary.lower()
    assert "Test error" in summary
    
    # Check item details
    assert "Jah Rune" in summary
    assert "Ber Rune" in summary
    assert "Harlequin Crest" in summary
    assert "5,000" in summary  # Jah price
    assert "4,000" in summary  # Ber price


def test_format_compact_summary(presenter, sample_scan_result):
    """Test compact summary formatting."""
    summary = presenter.format_compact_summary(sample_scan_result)
    
    assert "Stash Scan:" in summary
    assert "4 items" in summary
    assert "3 priced" in summary
    assert "9,800 FG" in summary
    assert "150ms" in summary


def test_format_item_table(presenter, sample_scan_result):
    """Test item table formatting."""
    table = presenter.format_item_table(sample_scan_result)
    
    # Check table structure
    assert "┌" in table and "┐" in table  # Top border
    assert "│" in table  # Vertical borders
    assert "Item Name" in table
    assert "Price (FG)" in table
    assert "Confidence" in table
    
    # Check item data
    assert "Jah Rune" in table
    assert "Ber Rune" in table
    assert "Harlequin Crest" in table
    assert "5,000" in table
    assert "4,000" in table
    assert "800" in table
    
    # Check total
    assert "Total Value:" in table
    assert "9,800" in table


def test_get_item_summaries(presenter, sample_scan_result):
    """Test getting structured item summaries."""
    summaries = presenter.get_item_summaries(sample_scan_result)
    
    assert len(summaries) == 4
    
    # Check first item (Jah Rune)
    jah_summary = summaries[0]  # Should be first due to value sorting
    assert jah_summary["item_name"] == "Jah Rune"
    assert jah_summary["canonical_item_id"] == "rune:jah"
    assert jah_summary["price_fg"] == 5000.0
    assert jah_summary["has_price"] is True
    assert jah_summary["value_tier"] == "high"
    assert "5,000 FG" in jah_summary["price_display"]
    assert "4,500 - 5,500 FG" in jah_summary["price_range_display"]
    
    # Check item without price
    no_price_summary = next(s for s in summaries if not s["has_price"])
    assert no_price_summary["item_name"] == "Unknown Item"
    assert no_price_summary["price_fg"] is None
    assert no_price_summary["price_display"] == "No data"
    assert no_price_summary["value_tier"] == "no_data"


def test_get_value_breakdown(presenter, sample_scan_result):
    """Test value breakdown by tier."""
    breakdown = presenter.get_value_breakdown(sample_scan_result)
    
    assert breakdown["total_value"] == 9800.0
    assert breakdown["total_items"] == 4
    assert breakdown["items_with_prices"] == 3
    assert breakdown["items_without_prices"] == 1
    
    # Check tier breakdown
    assert "by_tier" in breakdown
    assert "high" in breakdown["by_tier"]
    assert "medium" in breakdown["by_tier"]
    assert "low" in breakdown["by_tier"]
    assert "no_data" in breakdown["by_tier"]
    
    # High tier (Jah + Ber = 9000)
    assert breakdown["by_tier"]["high"]["count"] == 2
    assert breakdown["by_tier"]["high"]["total_value"] == 9000.0
    
    # Medium tier (Shako = 800)
    assert breakdown["by_tier"]["medium"]["count"] == 1
    assert breakdown["by_tier"]["medium"]["total_value"] == 800.0
    
    # No data tier
    assert breakdown["by_tier"]["no_data"]["count"] == 1


def test_format_controls_help(presenter):
    """Test controls help formatting."""
    help_text = presenter.format_controls_help()
    
    assert "CONTROLS" in help_text
    assert "Re-scan" in help_text
    assert "Clear" in help_text
    assert "Export" in help_text


def test_sort_by_value(presentation_config, sample_scan_result):
    """Test sorting items by value."""
    presentation_config.sort_by = "value"
    presenter = StashScanPresenter(config=presentation_config)
    
    summaries = presenter.get_item_summaries(sample_scan_result)
    
    # Should be sorted by value descending
    assert summaries[0]["item_name"] == "Jah Rune"  # 5000
    assert summaries[1]["item_name"] == "Ber Rune"  # 4000
    assert summaries[2]["item_name"] == "Harlequin Crest"  # 800
    assert summaries[3]["item_name"] == "Unknown Item"  # no price


def test_sort_by_name(presentation_config, sample_scan_result):
    """Test sorting items by name."""
    presentation_config.sort_by = "name"
    presenter = StashScanPresenter(config=presentation_config)
    
    summaries = presenter.get_item_summaries(sample_scan_result)
    
    # Should be sorted alphabetically
    names = [s["item_name"] for s in summaries]
    assert names == sorted(names)


def test_sort_by_slot(presentation_config, sample_scan_result):
    """Test sorting items by slot."""
    presentation_config.sort_by = "slot"
    presenter = StashScanPresenter(config=presentation_config)
    
    summaries = presenter.get_item_summaries(sample_scan_result)
    
    # Should be sorted by slot index
    for i, summary in enumerate(summaries):
        assert summary["slot_index"] == i


def test_value_tier_classification(presenter):
    """Test value tier classification."""
    # High tier item
    high_item = ScannedItem(
        slot_index=0,
        parsed_item=ParsedItem(raw_text="High", item_name="High"),
        match_result=MatchResult(
            canonical_item_id="test:high",
            confidence=0.9,
            matched_name="High Value Item",
            candidates=[],
            match_type="exact"
        ),
        price_estimate=PriceEstimate(
            variant_key="test:high",
            estimate_fg=10000.0,
            range_low_fg=9000.0,
            range_high_fg=11000.0,
            confidence="high",
            sample_count=50,
            last_updated=datetime.now()
        )
    )
    
    assert presenter._get_value_tier(high_item) == "high"
    
    # Medium tier item
    medium_item = ScannedItem(
        slot_index=1,
        parsed_item=ParsedItem(raw_text="Medium", item_name="Medium"),
        match_result=MatchResult(
            canonical_item_id="test:medium",
            confidence=0.9,
            matched_name="Medium Value Item",
            candidates=[],
            match_type="exact"
        ),
        price_estimate=PriceEstimate(
            variant_key="test:medium",
            estimate_fg=2000.0,
            range_low_fg=1800.0,
            range_high_fg=2200.0,
            confidence="medium",
            sample_count=30,
            last_updated=datetime.now()
        )
    )
    
    assert presenter._get_value_tier(medium_item) == "medium"
    
    # Low tier item
    low_item = ScannedItem(
        slot_index=2,
        parsed_item=ParsedItem(raw_text="Low", item_name="Low"),
        match_result=MatchResult(
            canonical_item_id="test:low",
            confidence=0.9,
            matched_name="Low Value Item",
            candidates=[],
            match_type="exact"
        ),
        price_estimate=PriceEstimate(
            variant_key="test:low",
            estimate_fg=50.0,
            range_low_fg=40.0,
            range_high_fg=60.0,
            confidence="low",
            sample_count=10,
            last_updated=datetime.now()
        )
    )
    
    assert presenter._get_value_tier(low_item) == "low"


def test_tier_symbols(presenter):
    """Test tier symbol mapping."""
    assert presenter._get_tier_symbol("high") == "★"
    assert presenter._get_tier_symbol("medium") == "◆"
    assert presenter._get_tier_symbol("low") == "○"
    assert presenter._get_tier_symbol("no_data") == "?"


def test_empty_scan_result(presenter):
    """Test formatting empty scan result."""
    empty_result = StashScanResult(
        items=[],
        total_value_fg=0.0,
        scan_timestamp=datetime.now().timestamp(),
        scan_duration_ms=50.0,
        items_with_prices=0,
        items_without_prices=0,
        scan_errors=[]
    )
    
    summary = presenter.format_detailed_summary(empty_result)
    assert "Total Items Scanned:" in summary
    assert "0" in summary
    
    compact = presenter.format_compact_summary(empty_result)
    assert "0 items" in compact
    
    summaries = presenter.get_item_summaries(empty_result)
    assert len(summaries) == 0


def test_custom_currency_symbol(presentation_config):
    """Test custom currency symbol."""
    presentation_config.currency_symbol = "Gold"
    presenter = StashScanPresenter(config=presentation_config)
    
    result = StashScanResult(
        items=[
            ScannedItem(
                slot_index=0,
                parsed_item=ParsedItem(raw_text="Test", item_name="Test"),
                match_result=MatchResult(
                    canonical_item_id="test:item",
                    confidence=0.9,
                    matched_name="Test Item",
                    candidates=[],
                    match_type="exact"
                ),
                price_estimate=PriceEstimate(
                    variant_key="test:item",
                    estimate_fg=1000.0,
                    range_low_fg=900.0,
                    range_high_fg=1100.0,
                    confidence="high",
                    sample_count=20,
                    last_updated=datetime.now()
                )
            )
        ],
        total_value_fg=1000.0,
        scan_timestamp=datetime.now().timestamp(),
        scan_duration_ms=100.0,
        items_with_prices=1,
        items_without_prices=0,
        scan_errors=[]
    )
    
    summary = presenter.format_detailed_summary(result)
    assert "Gold" in summary
    assert "FG" not in summary


def test_max_errors_displayed(presentation_config, sample_scan_result):
    """Test limiting displayed errors."""
    # Add more errors
    sample_scan_result.scan_errors = [f"Error {i}" for i in range(10)]
    
    presentation_config.max_errors_displayed = 3
    presenter = StashScanPresenter(config=presentation_config)
    
    summary = presenter.format_detailed_summary(sample_scan_result)
    
    # Should show first 3 errors
    assert "Error 0" in summary
    assert "Error 1" in summary
    assert "Error 2" in summary
    
    # Should indicate more errors
    assert "and 7 more error(s)" in summary


def test_hide_optional_fields(presentation_config, sample_scan_result):
    """Test hiding optional display fields."""
    presentation_config.show_confidence = False
    presentation_config.show_sample_count = False
    presentation_config.show_price_range = False
    presentation_config.show_scan_duration = False
    presentation_config.show_errors = False
    
    presenter = StashScanPresenter(config=presentation_config)
    summary = presenter.format_detailed_summary(sample_scan_result)
    
    # These should not appear
    assert "Confidence:" not in summary
    assert "Samples:" not in summary
    assert "Range:" not in summary
    assert "Scan Duration:" not in summary
    assert "Errors" not in summary or "error" not in summary.lower()
