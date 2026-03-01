"""Inventory overlay for displaying price information on items.

Provides hover-based price display for items in character inventory,
showing median prices, ranges, and detailed breakdowns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from d2lut.models import PriceEstimate
from d2lut.overlay.ocr_parser import ParsedItem


@dataclass
class InventorySlot:
    """Represents a single inventory slot with item and pricing data."""
    slot_id: int
    item_id: str | None
    variant_key: str | None
    parsed_item: ParsedItem | None = None
    price_estimate: PriceEstimate | None = None


@dataclass
class InventoryState:
    """Represents the current state of a character's inventory."""
    slots: list[InventorySlot]
    character_name: str
    total_value_fg: float | None = None


@dataclass
class OverlayDetails:
    """Detailed information for a hovered item."""
    slot_id: int
    item_name: str | None
    median_price: float | None
    price_range: tuple[float, float] | None
    confidence: str | None
    sample_count: int | None
    last_updated: str | None
    market_activity: dict[str, int] | None = None
    color: str = "no_data"
    has_data: bool = False
    item_id: str | None = None


@dataclass
class SlotOverlay:
    """Overlay rendering data for a single inventory slot."""
    slot_id: int
    median_price: float | None
    price_range: tuple[float, float] | None
    color: str  # low, medium, high, no_data
    details: OverlayDetails | None = None


@dataclass
class OverlayRender:
    """Complete overlay rendering data for an inventory."""
    slots: dict[int, SlotOverlay]
    total_value_fg: float | None
    enabled: bool = True


class InventoryOverlay:
    """
    Inventory overlay for displaying price information on items.
    
    Provides hover-based price display with color coding and detailed
    breakdowns for items in character inventory.
    """
    
    def __init__(
        self,
        low_value_threshold: float = 1000.0,
        medium_value_threshold: float = 10000.0
    ):
        """
        Initialize the inventory overlay.
        
        Args:
            low_value_threshold: Price threshold for low value items (in FG)
            medium_value_threshold: Price threshold for medium value items (in FG)
        """
        self.low_value_threshold = low_value_threshold
        self.medium_value_threshold = medium_value_threshold
        self._enabled = True
    
    def render_inventory(self, inventory: InventoryState) -> OverlayRender:
        """
        Render price information for an inventory.
        
        Args:
            inventory: Current inventory state with items and pricing
        
        Returns:
            OverlayRender with slot overlays and total value
        """
        if not self._enabled:
            return OverlayRender(slots={}, total_value_fg=None, enabled=False)
        
        slot_overlays = {}
        total_value = 0.0
        has_any_prices = False
        
        for slot in inventory.slots:
            # Create overlay for this slot
            overlay = self._create_slot_overlay(slot)
            slot_overlays[slot.slot_id] = overlay
            
            # Add to total value if price exists
            if overlay.median_price is not None:
                total_value += overlay.median_price
                has_any_prices = True
        
        # Only set total_value if we have at least one priced item
        final_total = total_value if has_any_prices else None
        
        return OverlayRender(
            slots=slot_overlays,
            total_value_fg=final_total,
            enabled=True
        )
    
    def _create_slot_overlay(self, slot: InventorySlot) -> SlotOverlay:
        """
        Create overlay data for a single slot.
        
        Args:
            slot: Inventory slot with item and pricing data
        
        Returns:
            SlotOverlay with rendering information
        """
        # No price data available
        if slot.price_estimate is None:
            return SlotOverlay(
                slot_id=slot.slot_id,
                median_price=None,
                price_range=None,
                color="no_data",
                details=None
            )
        
        # Extract price information
        median_price = slot.price_estimate.estimate_fg
        price_range = (
            slot.price_estimate.range_low_fg,
            slot.price_estimate.range_high_fg
        )
        
        # Determine color based on value
        color = self._get_value_color(median_price)
        
        return SlotOverlay(
            slot_id=slot.slot_id,
            median_price=median_price,
            price_range=price_range,
            color=color,
            details=None  # Details populated on hover via get_hover_details
        )
    
    def _get_value_color(self, price: float) -> str:
        """
        Determine color code based on item value.
        
        Args:
            price: Item price in FG
        
        Returns:
            Color code: "low", "medium", or "high"
        """
        if price < self.low_value_threshold:
            return "low"
        elif price < self.medium_value_threshold:
            return "medium"
        else:
            return "high"
    
    def get_hover_details(self, slot: InventorySlot) -> OverlayDetails:
        """
        Get detailed information for a hovered item.
        
        Args:
            slot: Inventory slot being hovered
        
        Returns:
            OverlayDetails with comprehensive price breakdown
        """
        # Extract item name
        item_name = None
        if slot.parsed_item is not None:
            item_name = slot.parsed_item.item_name
        elif slot.item_id is not None:
            item_name = slot.item_id
        
        # No price data available
        if slot.price_estimate is None:
            return OverlayDetails(
                slot_id=slot.slot_id,
                item_name=item_name,
                median_price=None,
                price_range=None,
                confidence=None,
                sample_count=None,
                last_updated=None,
                market_activity=None,
                color="no_data",
                has_data=False,
                item_id=slot.item_id,
            )
        
        # Extract price information
        estimate = slot.price_estimate
        median_price = estimate.estimate_fg
        price_range = (estimate.range_low_fg, estimate.range_high_fg)
        
        # Format last updated timestamp
        last_updated = estimate.last_updated.strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine color
        color = self._get_value_color(median_price)
        
        return OverlayDetails(
            slot_id=slot.slot_id,
            item_name=item_name,
            median_price=median_price,
            price_range=price_range,
            confidence=estimate.confidence,
            sample_count=estimate.sample_count,
            last_updated=last_updated,
            market_activity=None,  # Can be populated from PriceLookupEngine.get_market_summary
            color=color,
            has_data=True,
            item_id=slot.item_id,
        )
    
    def toggle_display(self, enabled: bool) -> None:
        """
        Toggle overlay display on/off.
        
        Args:
            enabled: True to enable overlay, False to disable
        """
        self._enabled = enabled
    
    @property
    def is_enabled(self) -> bool:
        """Check if overlay is currently enabled."""
        return self._enabled
