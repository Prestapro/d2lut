"""Tests for stash scanner functionality."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import io
from PIL import Image
import numpy as np

from d2lut.overlay.stash_scanner import StashScanner, ScannedItem, StashScanResult
from d2lut.overlay.ocr_parser import OCRTooltipParser, TooltipCoords, ParsedItem
from d2lut.overlay.item_identifier import ItemIdentifier, MatchResult, CatalogItem
from d2lut.overlay.price_lookup import PriceLookupEngine
from d2lut.models import PriceEstimate


@pytest.fixture
def mock_ocr_parser():
    """Create a mock OCR parser."""
    parser = Mock(spec=OCRTooltipParser)
    return parser


@pytest.fixture
def mock_item_identifier():
    """Create a mock item identifier."""
    identifier = Mock(spec=ItemIdentifier)
    return identifier


@pytest.fixture
def mock_price_lookup():
    """Create a mock price lookup engine."""
    lookup = Mock(spec=PriceLookupEngine)
    return lookup


@pytest.fixture
def stash_scanner(mock_ocr_parser, mock_item_identifier, mock_price_lookup):
    """Create a stash scanner with mocked dependencies."""
    return StashScanner(
        ocr_parser=mock_ocr_parser,
        item_identifier=mock_item_identifier,
        price_lookup=mock_price_lookup
    )


@pytest.fixture
def sample_screenshot():
    """Create a sample screenshot as bytes."""
    # Create a simple test image
    img = Image.new('RGB', (800, 600), color='black')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


@pytest.fixture
def sample_coords():
    """Create sample tooltip coordinates."""
    return [
        TooltipCoords(x=100, y=100, width=200, height=150),
        TooltipCoords(x=350, y=100, width=200, height=150),
        TooltipCoords(x=100, y=300, width=200, height=150),
    ]


def test_stash_scanner_initialization(stash_scanner, mock_ocr_parser, mock_item_identifier, mock_price_lookup):
    """Test stash scanner initializes correctly."""
    assert stash_scanner.ocr_parser == mock_ocr_parser
    assert stash_scanner.item_identifier == mock_item_identifier
    assert stash_scanner.price_lookup == mock_price_lookup
    assert stash_scanner._last_scan_result is None


def test_scan_stash_tab_basic(stash_scanner, mock_ocr_parser, mock_item_identifier, 
                               mock_price_lookup, sample_screenshot, sample_coords):
    """Test basic stash tab scanning."""
    # Setup mocks
    parsed_items = [
        ParsedItem(raw_text="Jah Rune", item_name="Jah Rune", confidence=0.9),
        ParsedItem(raw_text="Ber Rune", item_name="Ber Rune", confidence=0.85),
        ParsedItem(raw_text="Shako", item_name="Shako", confidence=0.8),
    ]
    mock_ocr_parser.parse_multiple.return_value = parsed_items
    
    match_results = [
        MatchResult(
            canonical_item_id="rune:jah",
            confidence=0.9,
            matched_name="Jah Rune",
            candidates=[],
            match_type="exact"
        ),
        MatchResult(
            canonical_item_id="rune:ber",
            confidence=0.85,
            matched_name="Ber Rune",
            candidates=[],
            match_type="exact"
        ),
        MatchResult(
            canonical_item_id="unique:shako",
            confidence=0.8,
            matched_name="Harlequin Crest",
            candidates=[],
            match_type="slang"
        ),
    ]
    mock_item_identifier.identify.side_effect = match_results
    
    price_estimates = [
        PriceEstimate(
            variant_key="rune:jah",
            estimate_fg=5000.0,
            range_low_fg=4500.0,
            range_high_fg=5500.0,
            confidence="high",
            sample_count=50,
            last_updated=datetime.now()
        ),
        PriceEstimate(
            variant_key="rune:ber",
            estimate_fg=4000.0,
            range_low_fg=3800.0,
            range_high_fg=4200.0,
            confidence="high",
            sample_count=45,
            last_updated=datetime.now()
        ),
        PriceEstimate(
            variant_key="unique:shako",
            estimate_fg=800.0,
            range_low_fg=700.0,
            range_high_fg=900.0,
            confidence="medium",
            sample_count=30,
            last_updated=datetime.now()
        ),
    ]
    mock_price_lookup.get_price.side_effect = price_estimates
    
    # Execute scan
    result = stash_scanner.scan_stash_tab(sample_screenshot, sample_coords)
    
    # Verify result
    assert isinstance(result, StashScanResult)
    assert len(result.items) == 3
    assert result.total_value_fg == 9800.0  # 5000 + 4000 + 800
    assert result.items_with_prices == 3
    assert result.items_without_prices == 0
    assert len(result.scan_errors) == 0
    assert result.scan_duration_ms > 0
    
    # Verify mocks were called correctly
    mock_ocr_parser.parse_multiple.assert_called_once_with(sample_screenshot, sample_coords)
    assert mock_item_identifier.identify.call_count == 3
    assert mock_price_lookup.get_price.call_count == 3


def test_scan_stash_tab_with_missing_prices(stash_scanner, mock_ocr_parser, 
                                             mock_item_identifier, mock_price_lookup,
                                             sample_screenshot, sample_coords):
    """Test scanning with some items missing price data."""
    # Setup mocks
    parsed_items = [
        ParsedItem(raw_text="Jah Rune", item_name="Jah Rune", confidence=0.9),
        ParsedItem(raw_text="Unknown Item", item_name="Unknown Item", confidence=0.5),
    ]
    mock_ocr_parser.parse_multiple.return_value = parsed_items
    
    match_results = [
        MatchResult(
            canonical_item_id="rune:jah",
            confidence=0.9,
            matched_name="Jah Rune",
            candidates=[],
            match_type="exact"
        ),
        MatchResult(
            canonical_item_id=None,
            confidence=0.0,
            matched_name="Unknown Item",
            candidates=[],
            match_type="no_match"
        ),
    ]
    mock_item_identifier.identify.side_effect = match_results
    
    # First item has price, second doesn't
    def get_price_side_effect(item_id, variant=None):
        if item_id == "rune:jah":
            return PriceEstimate(
                variant_key="rune:jah",
                estimate_fg=5000.0,
                range_low_fg=4500.0,
                range_high_fg=5500.0,
                confidence="high",
                sample_count=50,
                last_updated=datetime.now()
            )
        return None
    
    mock_price_lookup.get_price.side_effect = get_price_side_effect
    
    # Execute scan
    result = stash_scanner.scan_stash_tab(sample_screenshot, sample_coords[:2])
    
    # Verify result
    assert len(result.items) == 2
    assert result.total_value_fg == 5000.0
    assert result.items_with_prices == 1
    assert result.items_without_prices == 1


def test_scan_stash_tab_with_errors(stash_scanner, mock_ocr_parser, 
                                     mock_item_identifier, mock_price_lookup,
                                     sample_screenshot, sample_coords):
    """Test scanning with errors during processing."""
    # Setup mocks
    parsed_items = [
        ParsedItem(raw_text="Jah Rune", item_name="Jah Rune", confidence=0.9),
        ParsedItem(raw_text="Error Item", item_name="Error Item", confidence=0.8),
    ]
    mock_ocr_parser.parse_multiple.return_value = parsed_items
    
    # First item succeeds, second raises error
    def identify_side_effect(parsed):
        if parsed.item_name == "Jah Rune":
            return MatchResult(
                canonical_item_id="rune:jah",
                confidence=0.9,
                matched_name="Jah Rune",
                candidates=[],
                match_type="exact"
            )
        raise ValueError("Test error")
    
    mock_item_identifier.identify.side_effect = identify_side_effect
    
    mock_price_lookup.get_price.return_value = PriceEstimate(
        variant_key="rune:jah",
        estimate_fg=5000.0,
        range_low_fg=4500.0,
        range_high_fg=5500.0,
        confidence="high",
        sample_count=50,
        last_updated=datetime.now()
    )
    
    # Execute scan
    result = stash_scanner.scan_stash_tab(sample_screenshot, sample_coords[:2])
    
    # Verify result
    assert len(result.items) == 2
    assert len(result.scan_errors) == 1
    assert "Error processing slot 1" in result.scan_errors[0]
    assert result.items_with_prices == 1


def test_get_last_scan_result(stash_scanner, mock_ocr_parser, mock_item_identifier,
                               mock_price_lookup, sample_screenshot, sample_coords):
    """Test retrieving last scan result."""
    # Setup minimal mocks
    mock_ocr_parser.parse_multiple.return_value = []
    
    # Initially no result
    assert stash_scanner.get_last_scan_result() is None
    
    # Perform scan
    result = stash_scanner.scan_stash_tab(sample_screenshot, sample_coords)
    
    # Now result should be cached
    cached_result = stash_scanner.get_last_scan_result()
    assert cached_result is result
    assert cached_result.scan_timestamp == result.scan_timestamp


def test_clear_last_scan(stash_scanner, mock_ocr_parser, sample_screenshot, sample_coords):
    """Test clearing cached scan result."""
    # Setup minimal mocks
    mock_ocr_parser.parse_multiple.return_value = []
    
    # Perform scan
    stash_scanner.scan_stash_tab(sample_screenshot, sample_coords)
    assert stash_scanner.get_last_scan_result() is not None
    
    # Clear result
    stash_scanner.clear_last_scan()
    assert stash_scanner.get_last_scan_result() is None


def test_format_scan_summary(stash_scanner):
    """Test formatting scan summary."""
    # Create a mock result
    result = StashScanResult(
        items=[
            ScannedItem(
                slot_index=0,
                parsed_item=ParsedItem(raw_text="Jah", item_name="Jah"),
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
        ],
        total_value_fg=5000.0,
        scan_timestamp=0.0,
        scan_duration_ms=100.0,
        items_with_prices=1,
        items_without_prices=0,
        scan_errors=[]
    )
    
    summary = stash_scanner.format_scan_summary(result)
    
    assert "Stash Scan Summary" in summary
    assert "Total Items Scanned: 1" in summary
    assert "Items with Prices: 1" in summary
    assert "Total Stash Value: 5,000 FG" in summary
    assert "Jah Rune" in summary
    assert "5,000 FG" in summary


def test_get_item_value_list(stash_scanner):
    """Test getting structured item value list."""
    # Create a mock result
    result = StashScanResult(
        items=[
            ScannedItem(
                slot_index=0,
                parsed_item=ParsedItem(raw_text="Jah", item_name="Jah"),
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
                parsed_item=ParsedItem(raw_text="Unknown", item_name="Unknown"),
                match_result=MatchResult(
                    canonical_item_id=None,
                    confidence=0.0,
                    matched_name="Unknown",
                    candidates=[],
                    match_type="no_match"
                ),
                price_estimate=None
            ),
        ],
        total_value_fg=5000.0,
        scan_timestamp=0.0,
        scan_duration_ms=100.0,
        items_with_prices=1,
        items_without_prices=1,
        scan_errors=[]
    )
    
    value_list = stash_scanner.get_item_value_list(result)
    
    assert len(value_list) == 2
    
    # First item with price
    assert value_list[0]["slot_index"] == 0
    assert value_list[0]["item_name"] == "Jah Rune"
    assert value_list[0]["canonical_item_id"] == "rune:jah"
    assert value_list[0]["price_fg"] == 5000.0
    assert value_list[0]["has_price"] is True
    
    # Second item without price
    assert value_list[1]["slot_index"] == 1
    assert value_list[1]["item_name"] == "Unknown"
    assert value_list[1]["canonical_item_id"] is None
    assert value_list[1]["price_fg"] is None
    assert value_list[1]["has_price"] is False


def test_scan_empty_stash(stash_scanner, mock_ocr_parser, sample_screenshot):
    """Test scanning an empty stash tab."""
    # Setup mocks for empty stash
    mock_ocr_parser.parse_multiple.return_value = []
    
    # Execute scan with empty coords
    result = stash_scanner.scan_stash_tab(sample_screenshot, [])
    
    # Verify result
    assert len(result.items) == 0
    assert result.total_value_fg == 0.0
    assert result.items_with_prices == 0
    assert result.items_without_prices == 0
    assert len(result.scan_errors) == 0
