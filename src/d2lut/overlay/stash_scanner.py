"""Stash scanner for manual single-tab item scanning and valuation.

Provides manual scan trigger functionality to capture and parse visible
item tooltips in a single stash tab, producing value summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import time

from d2lut.overlay.ocr_parser import OCRTooltipParser, TooltipCoords, ParsedItem
from d2lut.overlay.item_identifier import ItemIdentifier, MatchResult
from d2lut.overlay.price_lookup import PriceLookupEngine
from d2lut.models import PriceEstimate


@dataclass
class ScannedItem:
    """Represents a single scanned item with identification and pricing."""
    slot_index: int
    parsed_item: ParsedItem
    match_result: MatchResult
    price_estimate: PriceEstimate | None = None
    scan_timestamp: float = field(default_factory=time.time)


@dataclass
class StashScanResult:
    """Result of a stash tab scan operation."""
    items: list[ScannedItem]
    total_value_fg: float
    scan_timestamp: float
    scan_duration_ms: float
    items_with_prices: int
    items_without_prices: int
    scan_errors: list[str] = field(default_factory=list)


class StashScanner:
    """
    Manual stash scanner for single-tab item scanning.
    
    Provides functionality to trigger a scan of visible items in a stash tab,
    parse tooltips, identify items, and produce value summaries.
    """
    
    def __init__(
        self,
        ocr_parser: OCRTooltipParser,
        item_identifier: ItemIdentifier,
        price_lookup: PriceLookupEngine
    ):
        """
        Initialize the stash scanner.
        
        Args:
            ocr_parser: OCR parser for tooltip extraction
            item_identifier: Item identifier for catalog matching
            price_lookup: Price lookup engine for market data
        """
        self.ocr_parser = ocr_parser
        self.item_identifier = item_identifier
        self.price_lookup = price_lookup
        
        # Last scan result for re-display
        self._last_scan_result: StashScanResult | None = None
    
    def scan_stash_tab(
        self,
        screenshot: bytes,
        tooltip_coords_list: list[TooltipCoords]
    ) -> StashScanResult:
        """
        Scan a single stash tab and produce value summary.
        
        This is the main entry point for manual stash scanning. It:
        1. Parses all visible item tooltips
        2. Identifies each item via catalog matching
        3. Looks up price estimates
        4. Produces a summary with total value
        
        Args:
            screenshot: Screenshot image as bytes
            tooltip_coords_list: List of tooltip coordinates for visible items
        
        Returns:
            StashScanResult with scanned items and value summary
        """
        start_time = time.time()
        scanned_items: list[ScannedItem] = []
        scan_errors: list[str] = []
        
        # Parse all tooltips
        parsed_items = self.ocr_parser.parse_multiple(screenshot, tooltip_coords_list)
        
        # Process each parsed item
        for slot_index, parsed_item in enumerate(parsed_items):
            try:
                # Identify the item
                match_result = self.item_identifier.identify(parsed_item)
                
                # Look up price if item was identified
                price_estimate = None
                if match_result.canonical_item_id:
                    price_estimate = self.price_lookup.get_price(
                        match_result.canonical_item_id,
                        variant=None  # Use default variant for now
                    )
                
                # Create scanned item
                scanned_item = ScannedItem(
                    slot_index=slot_index,
                    parsed_item=parsed_item,
                    match_result=match_result,
                    price_estimate=price_estimate
                )
                scanned_items.append(scanned_item)
                
            except Exception as e:
                error_msg = f"Error processing slot {slot_index}: {str(e)}"
                scan_errors.append(error_msg)
                
                # Still add the item with error info
                scanned_item = ScannedItem(
                    slot_index=slot_index,
                    parsed_item=parsed_item,
                    match_result=MatchResult(
                        canonical_item_id=None,
                        confidence=0.0,
                        matched_name="",
                        candidates=[],
                        match_type="error",
                        context_used={"error": str(e)}
                    ),
                    price_estimate=None
                )
                scanned_items.append(scanned_item)
        
        # Calculate summary statistics
        total_value = 0.0
        items_with_prices = 0
        items_without_prices = 0
        
        for item in scanned_items:
            if item.price_estimate is not None:
                total_value += item.price_estimate.estimate_fg
                items_with_prices += 1
            else:
                items_without_prices += 1
        
        # Calculate scan duration
        end_time = time.time()
        scan_duration_ms = (end_time - start_time) * 1000
        
        # Create result
        result = StashScanResult(
            items=scanned_items,
            total_value_fg=total_value,
            scan_timestamp=start_time,
            scan_duration_ms=scan_duration_ms,
            items_with_prices=items_with_prices,
            items_without_prices=items_without_prices,
            scan_errors=scan_errors
        )
        
        # Cache the result
        self._last_scan_result = result
        
        return result
    
    def get_last_scan_result(self) -> StashScanResult | None:
        """
        Get the last scan result.
        
        Returns:
            Last StashScanResult or None if no scan has been performed
        """
        return self._last_scan_result
    
    def clear_last_scan(self) -> None:
        """Clear the cached last scan result."""
        self._last_scan_result = None
    
    def format_scan_summary(self, result: StashScanResult) -> str:
        """
        Format a scan result as a human-readable summary.
        
        Args:
            result: StashScanResult to format
        
        Returns:
            Formatted summary string
        """
        lines = []
        lines.append("=== Stash Scan Summary ===")
        lines.append(f"Total Items Scanned: {len(result.items)}")
        lines.append(f"Items with Prices: {result.items_with_prices}")
        lines.append(f"Items without Prices: {result.items_without_prices}")
        lines.append(f"Total Stash Value: {result.total_value_fg:,.0f} FG")
        lines.append(f"Scan Duration: {result.scan_duration_ms:.0f}ms")
        
        if result.scan_errors:
            lines.append(f"\nErrors: {len(result.scan_errors)}")
            for error in result.scan_errors[:5]:  # Show first 5 errors
                lines.append(f"  - {error}")
        
        lines.append("\n=== Item Details ===")
        
        # Sort items by value (highest first)
        sorted_items = sorted(
            result.items,
            key=lambda x: x.price_estimate.estimate_fg if x.price_estimate else 0.0,
            reverse=True
        )
        
        for item in sorted_items:
            item_name = item.match_result.matched_name or item.parsed_item.item_name or "Unknown"
            
            if item.price_estimate:
                price_str = f"{item.price_estimate.estimate_fg:,.0f} FG"
                range_str = f"({item.price_estimate.range_low_fg:,.0f} - {item.price_estimate.range_high_fg:,.0f})"
                confidence_str = f"[{item.price_estimate.confidence}]"
                lines.append(f"  {item.slot_index + 1}. {item_name}: {price_str} {range_str} {confidence_str}")
            else:
                lines.append(f"  {item.slot_index + 1}. {item_name}: No price data")
        
        return "\n".join(lines)
    
    def get_item_value_list(self, result: StashScanResult) -> list[dict[str, Any]]:
        """
        Get a structured list of item values from scan result.
        
        Args:
            result: StashScanResult to extract values from
        
        Returns:
            List of dictionaries with item details and prices
        """
        value_list = []
        
        for item in result.items:
            item_dict = {
                "slot_index": item.slot_index,
                "item_name": item.match_result.matched_name or item.parsed_item.item_name,
                "canonical_item_id": item.match_result.canonical_item_id,
                "match_confidence": item.match_result.confidence,
                "match_type": item.match_result.match_type,
            }
            
            if item.price_estimate:
                item_dict.update({
                    "price_fg": item.price_estimate.estimate_fg,
                    "price_low_fg": item.price_estimate.range_low_fg,
                    "price_high_fg": item.price_estimate.range_high_fg,
                    "price_confidence": item.price_estimate.confidence,
                    "sample_count": item.price_estimate.sample_count,
                    "has_price": True
                })
            else:
                item_dict.update({
                    "price_fg": None,
                    "price_low_fg": None,
                    "price_high_fg": None,
                    "price_confidence": None,
                    "sample_count": None,
                    "has_price": False
                })
            
            value_list.append(item_dict)
        
        return value_list
