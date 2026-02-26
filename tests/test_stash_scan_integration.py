"""Integration tests for stash scanning workflow."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import io
from PIL import Image

from d2lut.overlay.stash_scan_integration import StashScanSession
from d2lut.overlay.ocr_parser import TooltipCoords
from d2lut.overlay.stash_scanner import StashScanResult


@pytest.fixture
def sample_screenshot():
    """Create a sample screenshot as bytes."""
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
    ]


@pytest.fixture
def mock_db_path(tmp_path):
    """Create a mock database path."""
    db_path = tmp_path / "test.db"
    # Create an empty file
    db_path.touch()
    return db_path


def test_stash_scan_session_initialization(mock_db_path):
    """Test stash scan session initializes correctly."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        
        assert session.db_path == mock_db_path
        assert session.ocr_parser is not None
        assert session.item_identifier is not None
        assert session.price_lookup is not None
        assert session.scanner is not None
        assert session.trigger is not None


def test_stash_scan_session_with_custom_config(mock_db_path):
    """Test stash scan session with custom configuration."""
    ocr_config = {
        "engine": "easyocr",
        "confidence_threshold": 0.8,
        "preprocess": {"contrast_enhance": False}
    }
    
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser') as MockOCR, \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path, ocr_config=ocr_config)
        
        # Verify OCR was initialized with custom config
        MockOCR.assert_called_once()
        call_kwargs = MockOCR.call_args[1]
        assert call_kwargs["engine"] == "easyocr"
        assert call_kwargs["confidence_threshold"] == 0.8


def test_prepare_scan(mock_db_path, sample_screenshot, sample_coords):
    """Test preparing scan data."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        
        # Initially no data
        assert session._current_screenshot is None
        assert session._current_coords is None
        
        # Prepare scan
        session.prepare_scan(sample_screenshot, sample_coords)
        
        # Data should be set
        assert session._current_screenshot == sample_screenshot
        assert session._current_coords == sample_coords


def test_execute_scan_without_prepare(mock_db_path):
    """Test that execute_scan raises error without prepare."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        
        with pytest.raises(ValueError, match="Scan data not prepared"):
            session.execute_scan()


def test_execute_scan_with_prepare(mock_db_path, sample_screenshot, sample_coords):
    """Test executing scan after prepare."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        
        # Mock the scanner
        mock_result = StashScanResult(
            items=[],
            total_value_fg=0.0,
            scan_timestamp=0.0,
            scan_duration_ms=100.0,
            items_with_prices=0,
            items_without_prices=0
        )
        session.scanner.scan_stash_tab = Mock(return_value=mock_result)
        
        # Prepare and execute
        session.prepare_scan(sample_screenshot, sample_coords)
        result = session.execute_scan()
        
        assert result == mock_result
        session.scanner.scan_stash_tab.assert_called_once_with(
            sample_screenshot, sample_coords
        )


def test_scan_one_call(mock_db_path, sample_screenshot, sample_coords):
    """Test scanning in one call without separate prepare."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        
        # Mock the scanner
        mock_result = StashScanResult(
            items=[],
            total_value_fg=0.0,
            scan_timestamp=0.0,
            scan_duration_ms=100.0,
            items_with_prices=0,
            items_without_prices=0
        )
        session.scanner.scan_stash_tab = Mock(return_value=mock_result)
        
        # Scan in one call
        result = session.scan(sample_screenshot, sample_coords)
        
        assert result == mock_result
        session.scanner.scan_stash_tab.assert_called_once()


def test_get_last_result(mock_db_path, sample_screenshot, sample_coords):
    """Test getting last scan result."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        
        # Mock the scanner
        mock_result = StashScanResult(
            items=[],
            total_value_fg=0.0,
            scan_timestamp=0.0,
            scan_duration_ms=100.0,
            items_with_prices=0,
            items_without_prices=0
        )
        session.scanner.get_last_scan_result = Mock(return_value=mock_result)
        
        result = session.get_last_result()
        
        assert result == mock_result
        session.scanner.get_last_scan_result.assert_called_once()


def test_clear_results(mock_db_path):
    """Test clearing scan results."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        session.scanner.clear_last_scan = Mock()
        
        session.clear_results()
        
        session.scanner.clear_last_scan.assert_called_once()


def test_format_summary(mock_db_path):
    """Test formatting scan summary."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        
        mock_result = StashScanResult(
            items=[],
            total_value_fg=0.0,
            scan_timestamp=0.0,
            scan_duration_ms=100.0,
            items_with_prices=0,
            items_without_prices=0
        )
        session.scanner.format_scan_summary = Mock(return_value="Test Summary")
        
        summary = session.format_summary(mock_result)
        
        assert summary == "Test Summary"
        session.scanner.format_scan_summary.assert_called_once_with(mock_result)


def test_format_summary_no_result(mock_db_path):
    """Test formatting summary with no result."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        session.scanner.get_last_scan_result = Mock(return_value=None)
        
        summary = session.format_summary()
        
        assert summary == "No scan results available"


def test_get_value_list(mock_db_path):
    """Test getting value list."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        
        mock_result = StashScanResult(
            items=[],
            total_value_fg=0.0,
            scan_timestamp=0.0,
            scan_duration_ms=100.0,
            items_with_prices=0,
            items_without_prices=0
        )
        mock_value_list = [{"item": "test"}]
        session.scanner.get_item_value_list = Mock(return_value=mock_value_list)
        
        value_list = session.get_value_list(mock_result)
        
        assert value_list == mock_value_list
        session.scanner.get_item_value_list.assert_called_once_with(mock_result)


def test_get_value_list_no_result(mock_db_path):
    """Test getting value list with no result."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        session.scanner.get_last_scan_result = Mock(return_value=None)
        
        value_list = session.get_value_list()
        
        assert value_list == []


def test_setup_trigger_callback(mock_db_path, sample_screenshot, sample_coords):
    """Test setting up trigger callback."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(db_path=mock_db_path)
        
        # Prepare scan data
        session.prepare_scan(sample_screenshot, sample_coords)
        
        # Setup trigger callback
        session.setup_trigger_callback()
        
        # Verify callback was set
        assert session.trigger._scan_callback is not None


def test_context_manager(mock_db_path):
    """Test using session as context manager."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        with StashScanSession(db_path=mock_db_path) as session:
            assert session is not None
            session.price_lookup.close = Mock()
        
        # Verify close was called
        session.price_lookup.close.assert_called_once()


def test_session_with_presentation_config(mock_db_path):
    """Test session initialization with presentation config."""
    from d2lut.overlay.stash_scan_presenter import PresentationConfig
    
    presentation_config = PresentationConfig(
        sort_by="value",
        show_confidence=True,
        currency_symbol="Gold"
    )
    
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        session = StashScanSession(
            db_path=mock_db_path,
            presentation_config=presentation_config
        )
        
        assert session.presenter is not None
        assert session.presenter.config.sort_by == "value"
        assert session.presenter.config.currency_symbol == "Gold"


def test_format_detailed_summary(mock_db_path, sample_screenshot, sample_coords):
    """Test detailed summary formatting."""
    from d2lut.overlay.ocr_parser import ParsedItem
    from d2lut.overlay.item_identifier import MatchResult
    from d2lut.models import PriceEstimate
    from datetime import datetime
    
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser') as mock_ocr, \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier') as mock_id, \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine') as mock_price:
        
        # Setup mocks
        mock_ocr.return_value.parse_multiple.return_value = [
            ParsedItem(raw_text="Jah", item_name="Jah Rune", confidence=0.9)
        ]
        
        mock_id.return_value.identify.return_value = MatchResult(
            canonical_item_id="rune:jah",
            confidence=0.9,
            matched_name="Jah Rune",
            candidates=[],
            match_type="exact"
        )
        
        mock_price.return_value.get_price.return_value = PriceEstimate(
            variant_key="rune:jah",
            estimate_fg=5000.0,
            range_low_fg=4500.0,
            range_high_fg=5500.0,
            confidence="high",
            sample_count=50,
            last_updated=datetime.now()
        )
        
        with StashScanSession(db_path=mock_db_path) as session:
            result = session.scan(sample_screenshot, sample_coords[:1])
            summary = session.format_detailed_summary(result)
            
            assert "STASH SCAN RESULTS" in summary
            assert "Jah Rune" in summary
            assert "5,000" in summary
            assert "FG" in summary


def test_format_compact_summary(mock_db_path, sample_screenshot, sample_coords):
    """Test compact summary formatting."""
    from d2lut.overlay.ocr_parser import ParsedItem
    from d2lut.overlay.item_identifier import MatchResult
    from d2lut.models import PriceEstimate
    from datetime import datetime
    
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser') as mock_ocr, \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier') as mock_id, \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine') as mock_price:
        
        # Setup mocks
        mock_ocr.return_value.parse_multiple.return_value = [
            ParsedItem(raw_text="Jah", item_name="Jah Rune", confidence=0.9)
        ]
        
        mock_id.return_value.identify.return_value = MatchResult(
            canonical_item_id="rune:jah",
            confidence=0.9,
            matched_name="Jah Rune",
            candidates=[],
            match_type="exact"
        )
        
        mock_price.return_value.get_price.return_value = PriceEstimate(
            variant_key="rune:jah",
            estimate_fg=5000.0,
            range_low_fg=4500.0,
            range_high_fg=5500.0,
            confidence="high",
            sample_count=50,
            last_updated=datetime.now()
        )
        
        with StashScanSession(db_path=mock_db_path) as session:
            result = session.scan(sample_screenshot, sample_coords[:1])
            summary = session.format_compact_summary(result)
            
            assert "Stash Scan:" in summary
            assert "1 items" in summary
            assert "1 priced" in summary
            assert "5,000 FG" in summary


def test_rescan(mock_db_path, sample_screenshot, sample_coords):
    """Test re-scan functionality."""
    from d2lut.overlay.ocr_parser import ParsedItem
    from d2lut.overlay.item_identifier import MatchResult
    from d2lut.models import PriceEstimate
    from datetime import datetime
    
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser') as mock_ocr, \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier') as mock_id, \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine') as mock_price:
        
        # Setup mocks
        mock_ocr.return_value.parse_multiple.return_value = [
            ParsedItem(raw_text="Jah", item_name="Jah Rune", confidence=0.9)
        ]
        
        mock_id.return_value.identify.return_value = MatchResult(
            canonical_item_id="rune:jah",
            confidence=0.9,
            matched_name="Jah Rune",
            candidates=[],
            match_type="exact"
        )
        
        mock_price.return_value.get_price.return_value = PriceEstimate(
            variant_key="rune:jah",
            estimate_fg=5000.0,
            range_low_fg=4500.0,
            range_high_fg=5500.0,
            confidence="high",
            sample_count=50,
            last_updated=datetime.now()
        )
        
        with StashScanSession(db_path=mock_db_path) as session:
            # First scan
            result1 = session.scan(sample_screenshot, sample_coords[:1])
            assert result1.total_value_fg == 5000.0
            
            # Re-scan
            result2 = session.rescan()
            assert result2 is not None
            assert result2.total_value_fg == 5000.0
            
            # Verify parse_multiple was called twice
            assert mock_ocr.return_value.parse_multiple.call_count == 2


def test_rescan_without_data(mock_db_path):
    """Test re-scan without prepared data."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        with StashScanSession(db_path=mock_db_path) as session:
            # Try to re-scan without any scan data
            result = session.rescan()
            assert result is None


def test_show_controls_help(mock_db_path):
    """Test showing controls help."""
    with patch('d2lut.overlay.stash_scan_integration.OCRTooltipParser'), \
         patch('d2lut.overlay.stash_scan_integration.ItemIdentifier'), \
         patch('d2lut.overlay.stash_scan_integration.PriceLookupEngine'):
        
        with StashScanSession(db_path=mock_db_path) as session:
            help_text = session.show_controls_help()
            
            assert "CONTROLS" in help_text
            assert "Re-scan" in help_text
            assert "Clear" in help_text
