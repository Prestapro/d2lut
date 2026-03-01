#!/usr/bin/env python3
"""Manual test script for InventoryOverlay."""

import sys
sys.path.insert(0, 'src')

from datetime import datetime
from d2lut.models import PriceEstimate
from d2lut.overlay.inventory_overlay import (
    InventoryOverlay,
    InventorySlot,
    InventoryState,
)
from d2lut.overlay.ocr_parser import ParsedItem


def test_basic_functionality():
    """Test basic overlay functionality."""
    print("Testing InventoryOverlay basic functionality...")
    
    # Create overlay
    overlay = InventoryOverlay(
        low_value_threshold=1000.0,
        medium_value_threshold=10000.0
    )
    
    assert overlay.is_enabled is True
    print("✓ Overlay initialized and enabled")
    
    # Test toggle
    overlay.toggle_display(False)
    assert overlay.is_enabled is False
    overlay.toggle_display(True)
    assert overlay.is_enabled is True
    print("✓ Toggle display works")
    
    # Create test data
    price_estimate = PriceEstimate(
        variant_key="rune:jah",
        estimate_fg=5000.0,
        range_low_fg=4500.0,
        range_high_fg=5500.0,
        confidence="high",
        sample_count=25,
        last_updated=datetime(2024, 1, 15, 12, 0, 0)
    )
    
    parsed_item = ParsedItem(
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
    
    # Create inventory with items
    slots = [
        InventorySlot(
            slot_id=1,
            item_id="rune:jah",
            variant_key="rune:jah",
            parsed_item=parsed_item,
            price_estimate=price_estimate
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
        ),
        InventorySlot(
            slot_id=3,
            item_id="unknown:item",
            variant_key="unknown:item",
            price_estimate=None
        )
    ]
    
    inventory = InventoryState(slots=slots, character_name="TestChar")
    
    # Render inventory
    result = overlay.render_inventory(inventory)
    
    assert len(result.slots) == 3
    assert result.total_value_fg == 8000.0  # 5000 + 3000
    assert result.enabled is True
    print("✓ Inventory rendering works")
    
    # Check slot 1 (medium value)
    slot1 = result.slots[1]
    assert slot1.median_price == 5000.0
    assert slot1.price_range == (4500.0, 5500.0)
    assert slot1.color == "medium"
    print("✓ Slot 1 (medium value) rendered correctly")
    
    # Check slot 2 (medium value)
    slot2 = result.slots[2]
    assert slot2.median_price == 3000.0
    assert slot2.color == "medium"
    print("✓ Slot 2 (medium value) rendered correctly")
    
    # Check slot 3 (no data)
    slot3 = result.slots[3]
    assert slot3.median_price is None
    assert slot3.color == "no_data"
    print("✓ Slot 3 (no data) rendered correctly")
    
    # Test hover details
    details = overlay.get_hover_details(slots[0])
    assert details.item_name == "Jah Rune"
    assert details.median_price == 5000.0
    assert details.price_range == (4500.0, 5500.0)
    assert details.confidence == "high"
    assert details.sample_count == 25
    assert details.has_data is True
    print("✓ Hover details work correctly")
    
    # Test color coding
    assert overlay._get_value_color(500.0) == "low"
    assert overlay._get_value_color(5000.0) == "medium"
    assert overlay._get_value_color(15000.0) == "high"
    print("✓ Color coding works correctly")
    
    print("\n✅ All tests passed!")


def test_edge_cases():
    """Test edge cases."""
    print("\nTesting edge cases...")
    
    overlay = InventoryOverlay()
    
    # Empty inventory
    inventory = InventoryState(slots=[], character_name="TestChar")
    result = overlay.render_inventory(inventory)
    assert result.slots == {}
    assert result.total_value_fg is None
    print("✓ Empty inventory handled")
    
    # Disabled overlay
    overlay.toggle_display(False)
    inventory = InventoryState(
        slots=[InventorySlot(slot_id=1, item_id="test", variant_key="test")],
        character_name="TestChar"
    )
    result = overlay.render_inventory(inventory)
    assert result.enabled is False
    assert result.slots == {}
    print("✓ Disabled overlay handled")
    
    # Hover details without price
    slot = InventorySlot(
        slot_id=1,
        item_id="unknown",
        variant_key="unknown",
        price_estimate=None
    )
    details = overlay.get_hover_details(slot)
    assert details.has_data is False
    assert details.median_price is None
    print("✓ Hover details without price handled")
    
    print("\n✅ All edge case tests passed!")


if __name__ == "__main__":
    try:
        test_basic_functionality()
        test_edge_cases()
        print("\n" + "="*50)
        print("SUCCESS: All manual tests passed!")
        print("="*50)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
