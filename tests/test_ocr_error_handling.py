"""Tests for OCR parser error handling and diagnostic information."""

import pytest
from PIL import Image
import io

from d2lut.overlay import OCRTooltipParser, ParsedItem, TooltipCoords


def create_test_image(width: int = 200, height: int = 100, color: str = 'white') -> bytes:
    """Create a test image and return as bytes."""
    img = Image.new('RGB', (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class TestErrorHandling:
    """Tests for error handling in OCR parser."""
    
    def test_invalid_coordinates_outside_bounds(self):
        """Test handling of coordinates outside image bounds."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot = create_test_image(200, 100)
            
            # Coordinates outside bounds
            coords = TooltipCoords(x=1000, y=1000, width=100, height=100)
            result = parser.parse_tooltip(screenshot, coords)
            
            assert result.error is not None
            assert "Invalid coordinates" in result.error
            assert "invalid_coords" in result.diagnostic
            assert "image_size" in result.diagnostic
            assert result.diagnostic["image_size"] == (200, 100)
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_empty_tooltip_region(self):
        """Test handling of empty tooltip text."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot = create_test_image(200, 100, 'white')
            
            coords = TooltipCoords(x=10, y=10, width=100, height=50)
            result = parser.parse_tooltip(screenshot, coords)
            
            # Empty white image should produce empty text
            if not result.raw_text.strip():
                assert result.error is not None
                assert "empty_text" in result.diagnostic
                assert "possible_causes" in result.diagnostic
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_low_confidence_detection(self):
        """Test detection of low confidence OCR results."""
        try:
            # Set very high confidence threshold
            parser = OCRTooltipParser(engine="pytesseract", confidence_threshold=0.99)
            screenshot = create_test_image(200, 100)
            
            coords = TooltipCoords(x=10, y=10, width=100, height=50)
            result = parser.parse_tooltip(screenshot, coords)
            
            # With blank image, confidence should be low
            if result.confidence < 0.99:
                assert "low_confidence" in result.diagnostic
                assert "confidence_score" in result.diagnostic
                assert "threshold" in result.diagnostic
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_diagnostic_information_completeness(self):
        """Test that diagnostic information is complete."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot = create_test_image(200, 100)
            
            coords = TooltipCoords(x=10, y=10, width=100, height=50)
            result = parser.parse_tooltip(screenshot, coords)
            
            # Check required diagnostic fields
            assert "original_region_shape" in result.diagnostic
            assert "image_size" in result.diagnostic
            assert "coords" in result.diagnostic
            assert "preprocessed_shape" in result.diagnostic
            assert "extracted_text_length" in result.diagnostic
            assert "confidence" in result.diagnostic
            assert "line_count" in result.diagnostic
            assert "text_length" in result.diagnostic
            assert "ocr_engine" in result.diagnostic
            assert "preprocessing" in result.diagnostic
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_get_diagnostic_info_method(self):
        """Test get_diagnostic_info() method."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot = create_test_image(200, 100)
            coords = TooltipCoords(x=10, y=10, width=100, height=50)
            
            # Parse a tooltip
            parser.parse_tooltip(screenshot, coords)
            
            # Get diagnostic info
            diagnostic = parser.get_diagnostic_info()
            
            assert "engine" in diagnostic
            assert "confidence_threshold" in diagnostic
            assert "preprocess_config" in diagnostic
            assert "last_parse" in diagnostic
            assert diagnostic["engine"] == "pytesseract"
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_multiple_tooltips_independent_errors(self):
        """Test that errors in one tooltip don't affect others."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot = create_test_image(400, 200)
            
            coords_list = [
                TooltipCoords(x=10, y=10, width=100, height=50),  # Valid
                TooltipCoords(x=1000, y=1000, width=100, height=50),  # Invalid
                TooltipCoords(x=150, y=10, width=100, height=50),  # Valid
            ]
            
            results = parser.parse_multiple(screenshot, coords_list)
            
            assert len(results) == 3
            # Second result should have error
            assert results[1].error is not None
            assert "Invalid coordinates" in results[1].error
            # First and third should not have coordinate errors
            assert "invalid_coords" not in results[0].diagnostic
            assert "invalid_coords" not in results[2].diagnostic
        except ImportError:
            pytest.skip("pytesseract not installed")


class TestDiagnosticInformation:
    """Tests for diagnostic information in parsed items."""
    
    def test_diagnostic_includes_preprocessing_config(self):
        """Test that diagnostic includes preprocessing configuration."""
        try:
            config = {
                "contrast_enhance": True,
                "denoise": False,
                "resize_factor": 1.5
            }
            parser = OCRTooltipParser(engine="pytesseract", preprocess_config=config)
            screenshot = create_test_image(200, 100)
            coords = TooltipCoords(x=10, y=10, width=100, height=50)
            
            result = parser.parse_tooltip(screenshot, coords)
            
            assert "preprocessing" in result.diagnostic
            assert result.diagnostic["preprocessing"]["resize_factor"] == 1.5
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_diagnostic_includes_extracted_lines(self):
        """Test that diagnostic includes extracted lines for debugging."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot = create_test_image(200, 100)
            coords = TooltipCoords(x=10, y=10, width=100, height=50)
            
            result = parser.parse_tooltip(screenshot, coords)
            
            assert "extracted_lines" in result.diagnostic
            assert isinstance(result.diagnostic["extracted_lines"], list)
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_error_includes_troubleshooting_tips(self):
        """Test that errors include troubleshooting information."""
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot = create_test_image(200, 100)
            
            # Invalid coordinates to trigger error
            coords = TooltipCoords(x=1000, y=1000, width=100, height=100)
            result = parser.parse_tooltip(screenshot, coords)
            
            assert result.error is not None
            assert "troubleshooting" in result.diagnostic
            assert isinstance(result.diagnostic["troubleshooting"], list)
            assert len(result.diagnostic["troubleshooting"]) > 0
        except ImportError:
            pytest.skip("pytesseract not installed")


class TestRequirementValidation:
    """Tests validating specific requirements."""
    
    def test_requirement_1_5_unclear_tooltip_error(self):
        """
        Requirement 1.5: IF tooltip is unclear/corrupted, 
        THEN Parser SHALL return error with diagnostic info
        """
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot = create_test_image(200, 100, 'white')  # Blank/unclear
            
            coords = TooltipCoords(x=10, y=10, width=100, height=50)
            result = parser.parse_tooltip(screenshot, coords)
            
            # Should detect unclear/empty tooltip
            if not result.raw_text.strip():
                assert result.error is not None
                assert len(result.diagnostic) > 0
                assert "possible_causes" in result.diagnostic or "troubleshooting" in result.diagnostic
        except ImportError:
            pytest.skip("pytesseract not installed")
    
    def test_requirement_1_6_multiple_items_independent(self):
        """
        Requirement 1.6: WHERE multiple items are visible, 
        Parser SHALL process each item independently
        """
        try:
            parser = OCRTooltipParser(engine="pytesseract")
            screenshot = create_test_image(400, 200)
            
            coords_list = [
                TooltipCoords(x=10, y=10, width=100, height=50),
                TooltipCoords(x=150, y=10, width=100, height=50),
                TooltipCoords(x=290, y=10, width=100, height=50),
            ]
            
            results = parser.parse_multiple(screenshot, coords_list)
            
            # Each item should be processed independently
            assert len(results) == 3
            assert all(isinstance(r, ParsedItem) for r in results)
            
            # Each should have its own diagnostic info
            for result in results:
                assert "coords" in result.diagnostic
                assert isinstance(result.diagnostic, dict)
            
            # Diagnostic info should be different for each
            coords_0 = results[0].diagnostic["coords"]
            coords_1 = results[1].diagnostic["coords"]
            assert coords_0["x"] != coords_1["x"]
        except ImportError:
            pytest.skip("pytesseract not installed")
