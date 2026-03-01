"""OCR tooltip parser for extracting item information from game screenshots."""

from dataclasses import dataclass, field
from typing import Any
import cv2
import numpy as np
from PIL import Image
import io


@dataclass
class TooltipCoords:
    """Coordinates for a tooltip region in a screenshot."""
    x: int
    y: int
    width: int
    height: int


@dataclass
class Affix:
    """Represents an item affix (prefix or suffix)."""
    name: str
    value: str | None = None
    affix_type: str | None = None  # prefix, suffix


@dataclass
class Property:
    """Represents a base item property."""
    name: str
    value: str | None = None


@dataclass
class ParsedItem:
    """Parsed item data from OCR extraction."""
    raw_text: str
    item_name: str | None = None
    item_type: str | None = None
    quality: str | None = None  # normal, magic, rare, set, unique
    rarity: str | None = None
    affixes: list[Affix] = field(default_factory=list)
    base_properties: list[Property] = field(default_factory=list)
    error: str | None = None
    confidence: float = 0.0
    diagnostic: dict[str, Any] = field(default_factory=dict)


class OCRTooltipParser:
    """
    Parser for extracting item information from game tooltips using OCR.
    
    Supports pytesseract and easyocr engines with OpenCV preprocessing.
    """
    
    def __init__(self, engine: str = "pytesseract", confidence_threshold: float = 0.7,
                 preprocess_config: dict[str, Any] | None = None):
        """
        Initialize the OCR tooltip parser.
        
        Args:
            engine: OCR engine to use ("pytesseract" or "easyocr")
            confidence_threshold: Minimum confidence for OCR results
            preprocess_config: Preprocessing configuration (contrast_enhance, denoise, resize_factor)
        """
        self.engine = engine
        self.confidence_threshold = confidence_threshold
        self.preprocess_config = preprocess_config or {
            "contrast_enhance": True,
            "denoise": True,
            "resize_factor": 2.0
        }
        
        # Initialize OCR engine
        self._ocr_engine = None
        self._init_ocr_engine()
        
        # Diagnostic information
        self._last_diagnostic: dict[str, Any] = {}
    
    def _init_ocr_engine(self) -> None:
        """Initialize the selected OCR engine."""
        if self.engine == "pytesseract":
            try:
                import pytesseract
                self._ocr_engine = pytesseract
            except ImportError as e:
                raise ImportError(
                    "pytesseract is not installed. Install with: pip install pytesseract"
                ) from e
        elif self.engine == "easyocr":
            try:
                import easyocr
                self._ocr_engine = easyocr.Reader(['en'], gpu=False)
            except ImportError as e:
                raise ImportError(
                    "easyocr is not installed. Install with: pip install easyocr"
                ) from e
        else:
            raise ValueError(f"Unsupported OCR engine: {self.engine}")
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR results.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Preprocessed image
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Resize for better OCR
        if self.preprocess_config.get("resize_factor", 1.0) != 1.0:
            resize_factor = self.preprocess_config["resize_factor"]
            new_width = int(image.shape[1] * resize_factor)
            new_height = int(image.shape[0] * resize_factor)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        # Contrast enhancement
        if self.preprocess_config.get("contrast_enhance", False):
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            image = clahe.apply(image)
        
        # Denoising
        if self.preprocess_config.get("denoise", False):
            image = cv2.fastNlMeansDenoising(image, h=10)
        
        # Thresholding for better text extraction
        _, image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return image
    
    def _extract_text(self, image: np.ndarray) -> tuple[str, float]:
        """
        Extract text from preprocessed image using OCR.
        
        Args:
            image: Preprocessed image
            
        Returns:
            Tuple of (extracted_text, confidence)
        """
        if self.engine == "pytesseract":
            # Get text with confidence
            data = self._ocr_engine.image_to_data(image, output_type=self._ocr_engine.Output.DICT)
            text_parts = []
            confidences = []
            
            for i, conf in enumerate(data['conf']):
                if conf > 0:  # Valid confidence
                    text = data['text'][i].strip()
                    if text:
                        text_parts.append(text)
                        confidences.append(conf / 100.0)  # Normalize to 0-1
            
            full_text = ' '.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return full_text, avg_confidence
        
        elif self.engine == "easyocr":
            results = self._ocr_engine.readtext(image)
            text_parts = []
            confidences = []
            
            for (bbox, text, conf) in results:
                text_parts.append(text)
                confidences.append(conf)
            
            full_text = ' '.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return full_text, avg_confidence
        
        return "", 0.0
    
    def _parse_item_structure(self, text: str, confidence: float) -> ParsedItem:
        """
        Parse the extracted text into structured item data.
        
        Args:
            text: Extracted text from OCR
            confidence: OCR confidence score
            
        Returns:
            ParsedItem with extracted information
        """
        # Basic parsing - this will be enhanced in later phases
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        parsed = ParsedItem(
            raw_text=text,
            confidence=confidence
        )
        
        # Always add basic diagnostic info first
        parsed.diagnostic.update({
            "line_count": len(lines),
            "text_length": len(text),
            "ocr_engine": self.engine,
            "preprocessing": self.preprocess_config.copy(),
            "extracted_lines": lines[:5] if lines else []  # First 5 lines for debugging
        })
        
        # Check confidence threshold
        if confidence < self.confidence_threshold:
            parsed.error = f"Low OCR confidence: {confidence:.2f} < {self.confidence_threshold}"
            parsed.diagnostic["low_confidence"] = True
            parsed.diagnostic["confidence_score"] = confidence
            parsed.diagnostic["threshold"] = self.confidence_threshold
            parsed.diagnostic["recommendation"] = "Consider adjusting preprocessing settings or confidence threshold"

        # Check for empty or corrupted text
        if not text or not text.strip():
            # Preserve low-confidence diagnostics if already set above.
            if not parsed.error:
                parsed.error = "No text extracted from tooltip (empty or corrupted)"
            parsed.diagnostic["empty_text"] = True
            parsed.diagnostic["possible_causes"] = [
                "Tooltip region is blank",
                "OCR failed to detect any text",
                "Image preprocessing removed all content"
            ]
            return parsed
        
        # Basic item name extraction (first non-empty line)
        if lines:
            parsed.item_name = lines[0]
        else:
            parsed.error = "Unable to extract item name from text"
            parsed.diagnostic["no_lines"] = True
        
        return parsed
    
    def parse_tooltip(self, screenshot: bytes, coords: TooltipCoords) -> ParsedItem:
        """
        Parse a single tooltip from a screenshot.
        
        Args:
            screenshot: Screenshot image as bytes
            coords: Coordinates of the tooltip region
            
        Returns:
            ParsedItem with extracted information
        """
        # Reset diagnostic info
        self._last_diagnostic = {}
        
        try:
            # Convert bytes to image
            image = Image.open(io.BytesIO(screenshot))
            image_np = np.array(image)
            
            # Validate coordinates
            img_height, img_width = image_np.shape[:2]
            if (coords.x < 0 or coords.y < 0 or 
                coords.x + coords.width > img_width or 
                coords.y + coords.height > img_height):
                error_item = ParsedItem(
                    raw_text="",
                    error=f"Invalid coordinates: region ({coords.x}, {coords.y}, {coords.width}, {coords.height}) outside image bounds ({img_width}, {img_height})",
                    confidence=0.0
                )
                error_item.diagnostic.update({
                    "invalid_coords": True,
                    "image_size": (img_width, img_height),
                    "requested_region": (coords.x, coords.y, coords.width, coords.height),
                    "troubleshooting": [
                        "Verify tooltip rectangle calibration coordinates",
                        "Ensure screenshot dimensions match the expected game window",
                        "Check scaling / fullscreen mode changes since calibration",
                    ],
                })
                return error_item
            
            # Extract tooltip region
            tooltip_region = image_np[
                coords.y:coords.y + coords.height,
                coords.x:coords.x + coords.width
            ]
            
            # Check if region is empty
            if tooltip_region.size == 0:
                error_item = ParsedItem(
                    raw_text="",
                    error="Tooltip region is empty",
                    confidence=0.0
                )
                error_item.diagnostic["empty_region"] = True
                return error_item
            
            # Store original region for diagnostics
            self._last_diagnostic["original_region_shape"] = tooltip_region.shape
            self._last_diagnostic["image_size"] = (img_width, img_height)
            self._last_diagnostic["coords"] = {
                "x": coords.x,
                "y": coords.y,
                "width": coords.width,
                "height": coords.height
            }
            
            # Preprocess
            preprocessed = self._preprocess_image(tooltip_region)
            self._last_diagnostic["preprocessed_shape"] = preprocessed.shape
            
            # Extract text
            text, confidence = self._extract_text(preprocessed)
            self._last_diagnostic["extracted_text_length"] = len(text)
            self._last_diagnostic["confidence"] = confidence
            
            # Parse structure
            parsed = self._parse_item_structure(text, confidence)
            parsed.diagnostic.update(self._last_diagnostic)
            
            return parsed
            
        except Exception as e:
            # Return error result with detailed diagnostic info
            error_item = ParsedItem(
                raw_text="",
                error=f"OCR parsing failed: {str(e)}",
                confidence=0.0
            )
            error_item.diagnostic.update({
                "exception": str(e),
                "exception_type": type(e).__name__,
                "coords": {
                    "x": coords.x,
                    "y": coords.y,
                    "width": coords.width,
                    "height": coords.height
                },
                "troubleshooting": [
                    "Verify screenshot is valid image data",
                    "Check coordinates are within image bounds",
                    "Ensure OCR engine is properly installed",
                    "Try adjusting preprocessing settings"
                ]
            })
            error_item.diagnostic.update(self._last_diagnostic)
            return error_item
    
    def parse_multiple(self, screenshot: bytes, coords_list: list[TooltipCoords]) -> list[ParsedItem]:
        """
        Parse multiple tooltips from a screenshot.
        
        Args:
            screenshot: Screenshot image as bytes
            coords_list: List of tooltip coordinates
            
        Returns:
            List of ParsedItem objects
        """
        results = []
        for coords in coords_list:
            parsed = self.parse_tooltip(screenshot, coords)
            results.append(parsed)
        return results
    
    def get_diagnostic_info(self) -> dict[str, Any]:
        """
        Return diagnostic information for troubleshooting.
        
        Returns:
            Dictionary with diagnostic information
        """
        return {
            "engine": self.engine,
            "confidence_threshold": self.confidence_threshold,
            "preprocess_config": self.preprocess_config,
            "last_parse": self._last_diagnostic.copy()
        }
