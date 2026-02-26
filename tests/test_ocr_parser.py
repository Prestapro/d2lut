"""Unit tests for OCR tooltip parser."""

import pytest
import numpy as np
from PIL import Image
import io

from d2lut.overlay import (
    OCRTooltipParser,
    ParsedItem,
    TooltipCoords,
)


@pytest.fixture
def sample_screenshot():
    """Create a sample screenshot for testing."""
    # Create a simple white image with black text
    img = Image.new('RGB', (800, 600), color='white')
    return img


@pytest.fixture
def sample_coords():
    """Create sample tooltip coordinates."""
    return TooltipCoords(x=100, y=100, width=200, height=150)


def image_to_bytes(img: Image.Image) -> bytes:
    """Convert PIL Image to bytes."""
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class TestTooltipCoords:
    """Tests for TooltipCoords dataclass."""
    
    def test_coords_creation(self):
        """Test creating tooltip coordinates."""
        coords = TooltipCoords(x=10, y=20, width=100, height=50)
        assert coords.x == 10
        assert coords.y == 20
        assert coords.width == 100
        assert coords.height == 50


class TestParsedItem:
    """Tests for ParsedItem dataclass."""
    
    def test_parsed_item_creation(self):
        """Test creating a parsed item."""
        item = ParsedItem(
            raw_text="Test Item",
            item_name="Test Item",
            confidence=0.95
        )
        assert item.raw_text == "Test Item"
        assert item.item_name == "Test Item"
        assert item.confidence == 0.95
        assert item.error is None
        assert len(item.affixes) == 0
        assert len(item.base_properties) == 0
    
    def test_parsed_item_with_error(self):
        """Test creating a parsed item with error."""
        item = ParsedItem(
            raw_text="",
            error="OCR failed",
            confidence=0.0
        )
        assert item.error == "OCR failed"
        assert item.confidence == 0.0


class TestOCRTooltipParser:
    """Tests for OCRTooltipParser class."""
    
    def test_parser_initialization_pytesseract(self):
        """Test parser initialization with pytesseract."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            assert parser.engine == "pytesseract"
            assert parser.confidence_threshold == 0.7
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_parser_initialization_easyocr(self):
        """Test parser initialization with easyocr."""
        try:
            parser = OCRTooltipParser(engine="easyocr")
            assert parser.engine == "easyocr"
            assert parser.confidence_threshold == 0.7
        except ImportError:
            pytest.skip("easyocr not installed")
    
    def test_parser_invalid_engine(self):
        """Test parser initialization with invalid engine."""
        with pytest.raises(ValueError, match="Unsupported OCR engine"):
            OCRTooltipParser(engine="invalid")
    
    def test_parser_custom_config(self):
        """Test parser with custom configuration."""
        config = {
            "contrast_enhance": False,
            "denoise": False,
            "resize_factor": 1.5
        }
        try:
            parser = OCRTooltipParser(
                engine="pytesseract",
                confidence_threshold=0.8,
                preprocess_config=config
            )
            assert parser.confidence_threshold == 0.8
            assert parser.preprocess_config == config
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_preprocess_image(self, sample_screenshot):
        """Test image preprocessing."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            img_array = np.array(sample_screenshot)
            preprocessed = parser._preprocess_image(img_array)
            
            # Check that preprocessing returns an image
            assert isinstance(preprocessed, np.ndarray)
            assert len(preprocessed.shape) == 2  # Should be grayscale
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_parse_tooltip_basic(self, sample_screenshot, sample_coords):
        """Test basic tooltip parsing."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot_bytes = image_to_bytes(sample_screenshot)
            
            result = parser.parse_tooltip(screenshot_bytes, sample_coords)
            
            # Check result structure
            assert isinstance(result, ParsedItem)
            assert isinstance(result.raw_text, str)
            assert isinstance(result.confidence, float)
            assert 0.0 <= result.confidence <= 1.0
            assert isinstance(result.diagnostic, dict)
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_parse_tooltip_invalid_coords(self, sample_screenshot):
        """Test parsing with invalid coordinates."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot_bytes = image_to_bytes(sample_screenshot)
            
            # Coordinates outside image bounds
            invalid_coords = TooltipCoords(x=1000, y=1000, width=100, height=100)
            result = parser.parse_tooltip(screenshot_bytes, invalid_coords)
            
            # Should return error result
            assert result.error is not None
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_parse_multiple_tooltips(self, sample_screenshot):
        """Test parsing multiple tooltips."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot_bytes = image_to_bytes(sample_screenshot)
            
            coords_list = [
                TooltipCoords(x=10, y=10, width=100, height=50),
                TooltipCoords(x=150, y=10, width=100, height=50),
            ]
            
            results = parser.parse_multiple(screenshot_bytes, coords_list)
            
            assert len(results) == 2
            assert all(isinstance(r, ParsedItem) for r in results)
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_get_diagnostic_info(self):
        """Test getting diagnostic information."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            diagnostic = parser.get_diagnostic_info()
            
            assert "engine" in diagnostic
            assert "confidence_threshold" in diagnostic
            assert "preprocess_config" in diagnostic
            assert diagnostic["engine"] == "pytesseract"
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_low_confidence_handling(self, sample_screenshot, sample_coords):
        """Test handling of low confidence OCR results."""
        try:
            # Set high confidence threshold
            parser = OCRTooltipParser(engine="pytesseract", confidence_threshold=0.99)
            screenshot_bytes = image_to_bytes(sample_screenshot)
            
            result = parser.parse_tooltip(screenshot_bytes, sample_coords)
            
            # With blank image, confidence should be low
            # Error should be set for low confidence
            if result.confidence < 0.99:
                assert "low_confidence" in result.diagnostic
        except ImportError:
            pytest.skip("pytesseract not installed")


class TestOCRIntegration:
    """Integration tests for OCR parsing."""
    
    def test_end_to_end_parsing(self, sample_screenshot):
        """Test complete parsing workflow."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot_bytes = image_to_bytes(sample_screenshot)
            coords = TooltipCoords(x=50, y=50, width=200, height=100)
            
            # Parse tooltip
            result = parser.parse_tooltip(screenshot_bytes, coords)
            
            # Verify result structure
            assert isinstance(result, ParsedItem)
            assert hasattr(result, 'raw_text')
            assert hasattr(result, 'item_name')
            assert hasattr(result, 'confidence')
            assert hasattr(result, 'diagnostic')
            
            # Get diagnostic info
            diagnostic = parser.get_diagnostic_info()
            assert "last_parse" in diagnostic
        except ImportError:
            pytest.skip("pytesseract not installed")
