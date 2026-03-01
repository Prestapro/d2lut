"""Unit tests for InventoryOverlay class."""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from d2lut.models import PriceEstimate
from d2lut.overlay.inventory_overlay import (
    InventoryOverlay,
    InventorySlot,
    InventoryState,
    OverlayDetails,
    OverlayRender,
    SlotOverlay,
)
from d2lut.overlay.ocr_parser import ParsedItem


def create_overlay():
    """Create a basic inventory overlay instance."""
    return InventoryOverlay(
        low_value_threshold=1000.0,
        medium_value_threshold=10000.0
    )


def create_sample_price_estimate():
    """Create a sample price estimate."""
    return PriceEstimate(
        variant_key="rune:jah",
        estimate_fg=5000.0,
        range_low_fg=4500.0,
        range_high_fg=5500.0,
        confidence="high",
        sample_count=25,
        last_updated=datetime(2024, 1, 15, 12, 0, 0)
    )


def create_sample_parsed_item():
    """Create a sample parsed item."""
    return ParsedItem(
        raw_text="Jah Rune",
        item_name="Jah Rune",
        item_type="rune",
        quality="normal",
        rarity=None,
        affixes=[],
        base_properties=[],
        error=None,
        confidence=0.95
    )


def test_initialization():
    """Test overlay initialization with custom thresholds."""
    print("Testing initialization...")
    overlay = InventoryOverlay(
        low_value_threshold=500.0,
        medium_value_threshold=5000.0
    )
    
    assert overlay.low_value_threshold == 500.0
    assert overlay.medium_value_threshold == 5000.0
    assert overlay.is_enabled is True
    print("✓ Initialization test passed")


def test_toggle_display():
    """Test toggling overlay display on/off."""
    print("Testing toggle display...")
    overlay = create_overlay()
    assert overlay.is_enabled is True
    
    overlay.toggle_display(False)
    assert overlay.is_enabled is False
    
    overlay.toggle_display(True)
    assert overlay.is_enabled is True
    print("✓ Toggle display test passed")


def test_render_inventory_empty():
    """Test rendering an empty inventory."""
    print("Testing empty inventory rendering...")
    overlay = create_overlay()
    inventory = InventoryState(
        slots=[],
        character_name="TestChar"
    )
    
    result = overlay.render_inventory(inventory)
    
    assert isinstance(result, OverlayRender)
    assert result.slots == {}
    assert result.total_value_fg is None
    assert result.enabled is True
    print("✓ Empty inventory test passed")


def test_render_inventory_disabled():
    """Test rendering when overlay is disabled."""
    print("Testing disabled overlay...")
    overlay = create_overlay()
    overlay.toggle_display(False)
    
    inventory = InventoryState(
        slots=[
            InventorySlot(slot_id=1, item_id="rune:jah", variant_key="rune:jah")
        ],
        character_name="TestChar"
    )
    
    result = overlay.render_inventory(inventory)
    
    assert result.slots == {}
    assert result.total_value_fg is None
    assert result.enabled is False
    print("✓ Disabled overlay test passed")


def test_render_inventory_with_priced_items():
    """Test rendering inventory with priced items."""
    print("Testing inventory with priced items...")
    overlay = create_overlay()
    sample_price_estimate = create_sample_price_estimate()
    
    slots = [
        InventorySlot(
            slot_id=1,
            item_id="rune:jah",
            variant_key="rune:jah",
            price_estimate=sample_price_estimate
        ),
        InventorySlot(
            slot_id=2,
            item_id="rune:ber",
            variant_key="rune:ber",
            price_estimate=PriceEstimate(
                variant_key="rune:ber",
                estimate_fg=3000.0,
                range_low_fg=2800.0,
                range_high_fg=3200.0,
                confidence="medium",
                sample_count=15,
                last_updated=datetime.now()
            )
        )
    ]
    
    inventory = InventoryState(slots=slots, character_name="TestChar")
    result = overlay.render_inventory(inventory)
    
    assert len(result.slots) == 2
    assert result.total_value_fg == 8000.0  # 5000 + 3000
    assert result.enabled is True
    
    # Check slot 1
    slot1 = result.slots[1]
    assert slot1.median_price == 5000.0
    assert slot1.price_range == (4500.0, 5500.0)
    assert slot1.color == "medium"
    
    # Check slot 2
    slot2 = result.slots[2]
    assert slot2.median_price == 3000.0
    assert slot2.color == "medium"
    print("✓ Priced items test passed")


def test_render_inventory_with_no_price_data():
    """Test rendering inventory with items that have no price data."""
    print("Testing inventory with no price data...")
    overlay = create_overlay()
    slots = [
        InventorySlot(
            slot_id=1,
            item_id="unknown:item",
            variant_key="unknown:item",
            price_estimate=None
        )
    ]
    
    inventory = InventoryState(slots=slots, character_name="TestChar")
    result = overlay.render_inventory(inventory)
    
    assert len(result.slots) == 1
    assert result.total_value_fg is None  # No priced items
    
    slot1 = result.slots[1]
    assert slot1.median_price is None
    assert slot1.price_range is None
    assert slot1.color == "no_data"
    print("✓ No price data test passed")


def test_render_inventory_mixed_data():
    """Test rendering inventory with mix of priced and unpriced items."""
    print("Testing inventory with mixed data...")
    overlay = create_overlay()
    sample_price_estimate = create_sample_price_estimate()
    
    slots = [
        InventorySlot(
            slot_id=1,
            item_id="rune:jah",
            variant_key="rune:jah",
            price_estimate=sample_price_estimate
        ),
        InventorySlot(
            slot_id=2,
            item_id="unknown:item",
            variant_key="unknown:item",
            price_estimate=None
        )
    ]
    
    inventory = InventoryState(slots=slots, character_name="TestChar")
    result = overlay.render_inventory(inventory)
    
    assert len(result.slots) == 2
    assert result.total_value_fg == 5000.0  # Only priced item
    
    assert result.slots[1].color == "medium"
    assert result.slots[2].color == "no_data"
    print("✓ Mixed data test passed")


def test_get_value_color():
    """Test color coding for different value ranges."""
    print("Testing value color coding...")
    overlay = create_overlay()
    
    # Low value
    color = overlay._get_value_color(500.0)
    assert color == "low"
    
    # Medium value
    color = overlay._get_value_color(5000.0)
    assert color == "medium"
    
    # High value
    color = overlay._get_value_color(15000.0)
    assert color == "high"
    
    # Boundary tests
    assert overlay._get_value_color(1000.0) == "medium"  # At threshold
    assert overlay._get_value_color(999.99) == "low"  # Just below
    assert overlay._get_value_color(10000.0) == "high"  # At threshold
    assert overlay._get_value_color(9999.99) == "medium"  # Just below
    
    print("✓ Value color coding test passed")


def test_get_hover_details_with_price():
    """Test getting hover details for item with price data."""
    print("Testing hover details with price...")
    overlay = create_overlay()
    sample_price_estimate = create_sample_price_estimate()
    sample_parsed_item = create_sample_parsed_item()
    
    slot = InventorySlot(
        slot_id=1,
        item_id="rune:jah",
        variant_key="rune:jah",
        parsed_item=sample_parsed_item,
        price_estimate=sample_price_estimate
    )
    
    details = overlay.get_hover_details(slot)
    
    assert isinstance(details, OverlayDetails)
    assert details.slot_id == 1
    assert details.item_name == "Jah Rune"
    assert details.median_price == 5000.0
    assert details.price_range == (4500.0, 5500.0)
    assert details.confidence == "high"
    assert details.sample_count == 25
    assert details.last_updated == "2024-01-15 12:00:00"
    assert details.color == "medium"
    assert details.has_data is True
    print("✓ Hover details with price test passed")


def test_get_hover_details_without_price():
    """Test getting hover details for item without price data."""
    print("Testing hover details without price...")
    overlay = create_overlay()
    sample_parsed_item = create_sample_parsed_item()
    
    slot = InventorySlot(
        slot_id=1,
        item_id="unknown:item",
        variant_key="unknown:item",
        parsed_item=sample_parsed_item,
        price_estimate=None
    )
    
    details = overlay.get_hover_details(slot)
    
    assert details.slot_id == 1
    assert details.item_name == "Jah Rune"
    assert details.median_price is None
    assert details.price_range is None
    assert details.confidence is None
    assert details.sample_count is None
    assert details.last_updated is None
    assert details.color == "no_data"
    assert details.has_data is False
    print("✓ Hover details without price test passed")


def test_get_hover_details_without_parsed_item():
    """Test getting hover details when parsed item is not available."""
    print("Testing hover details without parsed item...")
    overlay = create_overlay()
    sample_price_estimate = create_sample_price_estimate()
    
    slot = InventorySlot(
        slot_id=1,
        item_id="rune:jah",
        variant_key="rune:jah",
        parsed_item=None,
        price_estimate=sample_price_estimate
    )
    
    details = overlay.get_hover_details(slot)
    
    # Should use item_id as fallback for name
    assert details.item_name == "rune:jah"
    assert details.median_price == 5000.0
    assert details.has_data is True
    print("✓ Hover details without parsed item test passed")


def test_get_hover_details_no_item_info():
    """Test getting hover details with minimal slot information."""
    print("Testing hover details with no item info...")
    overlay = create_overlay()
    
    slot = InventorySlot(
        slot_id=1,
        item_id=None,
        variant_key=None,
        parsed_item=None,
        price_estimate=None
    )
    
    details = overlay.get_hover_details(slot)
    
    assert details.slot_id == 1
    assert details.item_name is None
    assert details.has_data is False
    print("✓ Hover details with no item info test passed")


def test_create_slot_overlay():
    """Test creating slot overlay with and without price data."""
    print("Testing slot overlay creation...")
    overlay = create_overlay()
    sample_price_estimate = create_sample_price_estimate()
    
    # With price
    slot = InventorySlot(
        slot_id=1,
        item_id="rune:jah",
        variant_key="rune:jah",
        price_estimate=sample_price_estimate
    )
    
    slot_overlay = overlay._create_slot_overlay(slot)
    
    assert isinstance(slot_overlay, SlotOverlay)
    assert slot_overlay.slot_id == 1
    assert slot_overlay.median_price == 5000.0
    assert slot_overlay.price_range == (4500.0, 5500.0)
    assert slot_overlay.color == "medium"
    assert slot_overlay.details is None  # Populated on hover
    
    # Without price
    slot2 = InventorySlot(
        slot_id=2,
        item_id="unknown:item",
        variant_key="unknown:item",
        price_estimate=None
    )
    
    slot_overlay2 = overlay._create_slot_overlay(slot2)
    
    assert slot_overlay2.slot_id == 2
    assert slot_overlay2.median_price is None
    assert slot_overlay2.price_range is None
    assert slot_overlay2.color == "no_data"
    print("✓ Slot overlay creation test passed")


def test_custom_thresholds():
    """Test overlay with custom value thresholds."""
    print("Testing custom thresholds...")
    overlay = InventoryOverlay(
        low_value_threshold=100.0,
        medium_value_threshold=1000.0
    )
    
    assert overlay._get_value_color(50.0) == "low"
    assert overlay._get_value_color(500.0) == "medium"
    assert overlay._get_value_color(5000.0) == "high"
    print("✓ Custom thresholds test passed")


def test_total_value_calculation_precision():
    """Test total value calculation with multiple items."""
    print("Testing total value calculation...")
    overlay = create_overlay()
    
    slots = [
        InventorySlot(
            slot_id=i,
            item_id=f"item:{i}",
            variant_key=f"item:{i}",
            price_estimate=PriceEstimate(
                variant_key=f"item:{i}",
                estimate_fg=float(i * 100),
                range_low_fg=float(i * 90),
                range_high_fg=float(i * 110),
                confidence="medium",
                sample_count=10,
                last_updated=datetime.now()
            )
        )
        for i in range(1, 6)  # 5 items: 100, 200, 300, 400, 500
    ]
    
    inventory = InventoryState(slots=slots, character_name="TestChar")
    result = overlay.render_inventory(inventory)
    
    # Total should be 100 + 200 + 300 + 400 + 500 = 1500
    assert result.total_value_fg == 1500.0
    print("✓ Total value calculation test passed")


def run_all_tests():
    """Run all tests."""
    print("="*60)
    print("Running InventoryOverlay Tests")
    print("="*60)
    
    test_initialization()
    test_toggle_display()
    test_render_inventory_empty()
    test_render_inventory_disabled()
    test_render_inventory_with_priced_items()
    test_render_inventory_with_no_price_data()
    test_render_inventory_mixed_data()
    test_get_value_color()
    test_get_hover_details_with_price()
    test_get_hover_details_without_price()
    test_get_hover_details_without_parsed_item()
    test_get_hover_details_no_item_info()
    test_create_slot_overlay()
    test_custom_thresholds()
    test_total_value_calculation_precision()
    
    print("\n" + "="*60)
    print("✅ All tests passed!")
    print("="*60)


if __name__ == "__main__":
    try:
        run_all_tests()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
