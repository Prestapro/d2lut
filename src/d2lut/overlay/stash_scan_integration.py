"""Integration module for stash scanning functionality.

Provides a high-level interface that wires together OCR parsing,
item identification, price lookup, and scan triggering for easy use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from d2lut.overlay.ocr_parser import OCRTooltipParser, TooltipCoords
from d2lut.overlay.item_identifier import ItemIdentifier
from d2lut.overlay.price_lookup import PriceLookupEngine
from d2lut.overlay.stash_scanner import StashScanner, StashScanResult
from d2lut.overlay.scan_trigger import ScanTrigger, ScanTriggerConfig
from d2lut.overlay.stash_scan_presenter import StashScanPresenter, PresentationConfig


class StashScanSession:
    """
    High-level interface for stash scanning sessions.
    
    Manages the complete stash scanning workflow including OCR,
    identification, pricing, and result presentation.
    """
    
    def __init__(
        self,
        db_path: str | Path,
        ocr_config: dict[str, Any] | None = None,
        trigger_config: ScanTriggerConfig | None = None,
        presentation_config: PresentationConfig | None = None
    ):
        """
        Initialize a stash scan session.
        
        Args:
            db_path: Path to the d2lut database
            ocr_config: OCR configuration (engine, confidence_threshold, preprocess)
            trigger_config: Scan trigger configuration (hotkey, cooldown)
            presentation_config: Presentation configuration for result display
        """
        self.db_path = Path(db_path)
        
        # Initialize components
        ocr_config = ocr_config or {}
        self.ocr_parser = OCRTooltipParser(
            engine=ocr_config.get("engine", "pytesseract"),
            confidence_threshold=ocr_config.get("confidence_threshold", 0.7),
            preprocess_config=ocr_config.get("preprocess", None)
        )
        
        self.item_identifier = ItemIdentifier(
            db_path=self.db_path,
            fuzzy_threshold=0.8
        )
        
        self.price_lookup = PriceLookupEngine(db_path=self.db_path)
        
        self.scanner = StashScanner(
            ocr_parser=self.ocr_parser,
            item_identifier=self.item_identifier,
            price_lookup=self.price_lookup
        )
        
        # Initialize scan trigger
        self.trigger = ScanTrigger(config=trigger_config)
        
        # Initialize presenter
        self.presenter = StashScanPresenter(config=presentation_config)
        
        # Current scan state
        self._current_screenshot: bytes | None = None
        self._current_coords: list[TooltipCoords] | None = None
    
    def prepare_scan(
        self,
        screenshot: bytes,
        tooltip_coords: list[TooltipCoords]
    ) -> None:
        """
        Prepare for a scan by setting screenshot and coordinates.
        
        Args:
            screenshot: Screenshot image as bytes
            tooltip_coords: List of tooltip coordinates for visible items
        """
        self._current_screenshot = screenshot
        self._current_coords = tooltip_coords
    
    def execute_scan(self) -> StashScanResult:
        """
        Execute a stash scan with prepared data.
        
        Returns:
            StashScanResult with scanned items and summary
        
        Raises:
            ValueError: If scan data not prepared
        """
        if self._current_screenshot is None or self._current_coords is None:
            raise ValueError("Scan data not prepared. Call prepare_scan() first.")
        
        return self.scanner.scan_stash_tab(
            self._current_screenshot,
            self._current_coords
        )
    
    def scan(
        self,
        screenshot: bytes,
        tooltip_coords: list[TooltipCoords]
    ) -> StashScanResult:
        """
        Perform a complete scan in one call.
        
        Args:
            screenshot: Screenshot image as bytes
            tooltip_coords: List of tooltip coordinates for visible items
        
        Returns:
            StashScanResult with scanned items and summary
        """
        self.prepare_scan(screenshot, tooltip_coords)
        return self.execute_scan()
    
    def get_last_result(self) -> StashScanResult | None:
        """
        Get the last scan result.
        
        Returns:
            Last StashScanResult or None
        """
        return self.scanner.get_last_scan_result()
    
    def clear_results(self) -> None:
        """Clear cached scan results."""
        self.scanner.clear_last_scan()
    
    def format_summary(self, result: StashScanResult | None = None) -> str:
        """
        Format a scan result as a summary string.
        
        Args:
            result: StashScanResult to format (uses last result if None)
        
        Returns:
            Formatted summary string
        """
        if result is None:
            result = self.get_last_result()
        
        if result is None:
            return "No scan results available"
        
        return self.scanner.format_scan_summary(result)
    
    def get_value_list(self, result: StashScanResult | None = None) -> list[dict[str, Any]]:
        """
        Get structured value list from scan result.
        
        Args:
            result: StashScanResult to extract from (uses last result if None)
        
        Returns:
            List of item value dictionaries
        """
        if result is None:
            result = self.get_last_result()
        
        if result is None:
            return []
        
        return self.scanner.get_item_value_list(result)
    
    def format_detailed_summary(self, result: StashScanResult | None = None) -> str:
        """
        Format a detailed presentation summary with per-item details.
        
        Args:
            result: StashScanResult to format (uses last result if None)
        
        Returns:
            Formatted detailed summary string
        """
        if result is None:
            result = self.get_last_result()
        
        if result is None:
            return "No scan results available"
        
        return self.presenter.format_detailed_summary(result)
    
    def format_compact_summary(self, result: StashScanResult | None = None) -> str:
        """
        Format a compact one-line summary.
        
        Args:
            result: StashScanResult to format (uses last result if None)
        
        Returns:
            Compact summary string
        """
        if result is None:
            result = self.get_last_result()
        
        if result is None:
            return "No scan results available"
        
        return self.presenter.format_compact_summary(result)
    
    def format_item_table(self, result: StashScanResult | None = None) -> str:
        """
        Format items as a table.
        
        Args:
            result: StashScanResult to format (uses last result if None)
        
        Returns:
            Formatted table string
        """
        if result is None:
            result = self.get_last_result()
        
        if result is None:
            return "No scan results available"
        
        return self.presenter.format_item_table(result)
    
    def get_item_summaries(self, result: StashScanResult | None = None) -> list[dict[str, Any]]:
        """
        Get per-item summaries with presentation formatting.
        
        Args:
            result: StashScanResult to extract from (uses last result if None)
        
        Returns:
            List of item summary dictionaries with display formatting
        """
        if result is None:
            result = self.get_last_result()
        
        if result is None:
            return []
        
        return self.presenter.get_item_summaries(result)
    
    def get_value_breakdown(self, result: StashScanResult | None = None) -> dict[str, Any]:
        """
        Get value breakdown by tier.
        
        Args:
            result: StashScanResult to analyze (uses last result if None)
        
        Returns:
            Dictionary with value breakdown by tier
        """
        if result is None:
            result = self.get_last_result()
        
        if result is None:
            return {
                "total_value": 0.0,
                "total_items": 0,
                "items_with_prices": 0,
                "items_without_prices": 0,
                "by_tier": {}
            }
        
        return self.presenter.get_value_breakdown(result)
    
    def show_controls_help(self) -> str:
        """
        Show help text for interactive controls.
        
        Returns:
            Help text string
        """
        return self.presenter.format_controls_help()
    
    def rescan(self) -> StashScanResult | None:
        """
        Re-scan using the last prepared screenshot and coordinates.
        
        This is a convenience method for re-scanning without
        having to call prepare_scan() again.
        
        Returns:
            StashScanResult if scan data is available, None otherwise
        """
        if self._current_screenshot is None or self._current_coords is None:
            return None
        
        return self.execute_scan()
    
    def setup_trigger_callback(self) -> None:
        """
        Set up the scan trigger to execute scans automatically.
        
        Note: Requires prepare_scan() to be called first with valid data.
        """
        def trigger_callback():
            if self._current_screenshot and self._current_coords:
                return self.execute_scan()
            return None
        
        self.trigger.set_scan_callback(trigger_callback)
    
    def close(self) -> None:
        """Clean up resources."""
        self.price_lookup.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
