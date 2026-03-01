"""Demo script for stash scan presentation features.

This script demonstrates the new presentation layer for stash scanning:
1. Detailed summary with per-item breakdowns
2. Compact one-line summary
3. Item table format
4. Value breakdown by tier
5. Re-scan and clear operations
"""

import io
from pathlib import Path
from PIL import Image
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from d2lut.overlay.stash_scan_integration import StashScanSession
from d2lut.overlay.ocr_parser import TooltipCoords
from d2lut.overlay.stash_scan_presenter import PresentationConfig


def create_demo_screenshot():
    """Create a demo screenshot for testing."""
    img = Image.new('RGB', (1024, 768), color='black')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


def demo_presentation_formats():
    """Demonstrate different presentation formats."""
    print("=" * 60)
    print("STASH SCAN PRESENTATION DEMO")
    print("=" * 60)
    print()
    
    db_path = Path("data/d2lut.db")
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        print("Please adjust the db_path to point to your d2lut database.")
        return
    
    # Create custom presentation config
    presentation_config = PresentationConfig(
        show_confidence=True,
        show_sample_count=True,
        show_price_range=True,
        show_scan_duration=True,
        show_errors=True,
        max_errors_displayed=5,
        sort_by="value",  # Sort by value (highest first)
        currency_symbol="FG",
        value_thresholds={
            "low": 100.0,
            "medium": 1000.0,
            "high": 5000.0
        }
    )
    
    # Create session with presentation config
    with StashScanSession(
        db_path=db_path,
        presentation_config=presentation_config
    ) as session:
        # Prepare demo data
        screenshot = create_demo_screenshot()
        coords = [
            TooltipCoords(x=100, y=100, width=200, height=150),
            TooltipCoords(x=350, y=100, width=200, height=150),
            TooltipCoords(x=600, y=100, width=200, height=150),
        ]
        
        # Perform scan
        print("Performing stash scan...")
        result = session.scan(screenshot, coords)
        print()
        
        # 1. Detailed Summary
        print("1. DETAILED SUMMARY")
        print("-" * 60)
        print(session.format_detailed_summary(result))
        print()
        
        # 2. Compact Summary
        print("2. COMPACT SUMMARY")
        print("-" * 60)
        print(session.format_compact_summary(result))
        print()
        print()
        
        # 3. Item Table
        print("3. ITEM TABLE")
        print("-" * 60)
        print(session.format_item_table(result))
        print()
        
        # 4. Item Summaries (structured data)
        print("4. ITEM SUMMARIES (Structured Data)")
        print("-" * 60)
        summaries = session.get_item_summaries(result)
        for summary in summaries:
            print(f"Slot {summary['slot_number']}: {summary['item_name']}")
            print(f"  Value Tier: {summary['value_tier']}")
            print(f"  Price: {summary['price_display']}")
            if summary['has_price']:
                print(f"  Range: {summary['price_range_display']}")
                print(f"  Confidence: {summary['price_confidence']}")
            print()
        
        # 5. Value Breakdown
        print("5. VALUE BREAKDOWN BY TIER")
        print("-" * 60)
        breakdown = session.get_value_breakdown(result)
        print(f"Total Value: {breakdown['total_value']:,.0f} FG")
        print(f"Total Items: {breakdown['total_items']}")
        print()
        print("By Tier:")
        for tier, data in breakdown['by_tier'].items():
            if tier == "no_data":
                print(f"  {tier.upper()}: {data['count']} items")
            else:
                print(f"  {tier.upper()}: {data['count']} items, {data['total_value']:,.0f} FG")
        print()
        
        # 6. Controls Help
        print("6. CONTROLS HELP")
        print("-" * 60)
        print(session.show_controls_help())


def demo_rescan_and_clear():
    """Demonstrate re-scan and clear operations."""
    print("=" * 60)
    print("RE-SCAN AND CLEAR DEMO")
    print("=" * 60)
    print()
    
    db_path = Path("data/d2lut.db")
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return
    
    with StashScanSession(db_path=db_path) as session:
        screenshot = create_demo_screenshot()
        coords = [TooltipCoords(x=100, y=100, width=200, height=150)]
        
        # First scan
        print("1. Performing initial scan...")
        result1 = session.scan(screenshot, coords)
        print(session.format_compact_summary(result1))
        print()
        
        # Get last result
        print("2. Retrieving last scan result...")
        last_result = session.get_last_result()
        if last_result:
            print(f"   Last scan had {len(last_result.items)} items")
            print(f"   Total value: {last_result.total_value_fg:,.0f} FG")
        print()
        
        # Re-scan (using cached screenshot/coords)
        print("3. Re-scanning...")
        result2 = session.rescan()
        if result2:
            print(session.format_compact_summary(result2))
        else:
            print("   No scan data available for re-scan")
        print()
        
        # Clear results
        print("4. Clearing results...")
        session.clear_results()
        last_result = session.get_last_result()
        print(f"   Last result after clear: {last_result}")
        print()
        
        # Scan again
        print("5. Performing new scan after clear...")
        result3 = session.scan(screenshot, coords)
        print(session.format_compact_summary(result3))
        print()


def demo_custom_sorting():
    """Demonstrate different sorting options."""
    print("=" * 60)
    print("CUSTOM SORTING DEMO")
    print("=" * 60)
    print()
    
    db_path = Path("data/d2lut.db")
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return
    
    screenshot = create_demo_screenshot()
    coords = [
        TooltipCoords(x=100, y=100, width=200, height=150),
        TooltipCoords(x=350, y=100, width=200, height=150),
        TooltipCoords(x=600, y=100, width=200, height=150),
    ]
    
    # Sort by value
    print("1. SORTED BY VALUE (Highest First)")
    print("-" * 60)
    config_value = PresentationConfig(sort_by="value")
    with StashScanSession(db_path=db_path, presentation_config=config_value) as session:
        result = session.scan(screenshot, coords)
        print(session.format_item_table(result))
    print()
    
    # Sort by name
    print("2. SORTED BY NAME (Alphabetical)")
    print("-" * 60)
    config_name = PresentationConfig(sort_by="name")
    with StashScanSession(db_path=db_path, presentation_config=config_name) as session:
        result = session.scan(screenshot, coords)
        print(session.format_item_table(result))
    print()
    
    # Sort by slot
    print("3. SORTED BY SLOT (Position)")
    print("-" * 60)
    config_slot = PresentationConfig(sort_by="slot")
    with StashScanSession(db_path=db_path, presentation_config=config_slot) as session:
        result = session.scan(screenshot, coords)
        print(session.format_item_table(result))
    print()


def demo_custom_thresholds():
    """Demonstrate custom value thresholds."""
    print("=" * 60)
    print("CUSTOM VALUE THRESHOLDS DEMO")
    print("=" * 60)
    print()
    
    db_path = Path("data/d2lut.db")
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return
    
    # Custom thresholds for different trading styles
    configs = [
        ("Conservative Trader", {
            "low": 50.0,
            "medium": 500.0,
            "high": 2000.0
        }),
        ("High-Value Trader", {
            "low": 1000.0,
            "medium": 5000.0,
            "high": 10000.0
        }),
    ]
    
    screenshot = create_demo_screenshot()
    coords = [TooltipCoords(x=100, y=100, width=200, height=150)]
    
    for name, thresholds in configs:
        print(f"{name} Thresholds:")
        print(f"  Low: {thresholds['low']:,.0f} FG")
        print(f"  Medium: {thresholds['medium']:,.0f} FG")
        print(f"  High: {thresholds['high']:,.0f} FG")
        print()
        
        config = PresentationConfig(value_thresholds=thresholds)
        with StashScanSession(db_path=db_path, presentation_config=config) as session:
            result = session.scan(screenshot, coords)
            breakdown = session.get_value_breakdown(result)
            
            print("Value Breakdown:")
            for tier, data in breakdown['by_tier'].items():
                if tier != "no_data" and data['count'] > 0:
                    print(f"  {tier.upper()}: {data['count']} items")
        print()


if __name__ == "__main__":
    print("Stash Scan Presentation Demo\n")
    print("This demo showcases the new presentation features for stash scanning.")
    print("Note: Requires a valid d2lut database with market data.\n")
    
    try:
        demo_presentation_formats()
        print("\n" + "=" * 60 + "\n")
        demo_rescan_and_clear()
        print("\n" + "=" * 60 + "\n")
        demo_custom_sorting()
        print("\n" + "=" * 60 + "\n")
        demo_custom_thresholds()
    except Exception as e:
        print(f"\nError running demo: {e}")
        print("\nThis is expected if the database doesn't exist or doesn't have the required tables.")
        print("The presentation layer is complete and ready to use with a proper database.")
