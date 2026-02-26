# Stash Scanner Documentation

## Overview

The stash scanner provides manual single-tab item scanning functionality for the d2lut overlay system. It allows users to trigger a scan of visible items in a stash tab, capturing and parsing tooltips to produce value summaries.

## Features

- **Manual Scan Trigger**: Trigger scans via hotkey or button press
- **Tooltip Capture**: Parse multiple item tooltips from a single screenshot
- **Item Identification**: Match parsed items to catalog entries
- **Price Lookup**: Retrieve market prices for identified items
- **Value Summary**: Calculate total stash value and per-item breakdowns
- **Error Handling**: Gracefully handle parsing errors and missing data
- **Rich Presentation**: Multiple display formats (detailed, compact, table)
- **Value Tiers**: Automatic classification by value (low/medium/high)
- **Flexible Sorting**: Sort by value, name, or slot position
- **Re-scan Support**: Easy re-scanning with cached data
- **Clear Results**: Clear cached results on demand

## Components

### StashScanner

Core scanning engine that orchestrates OCR parsing, item identification, and price lookup.

```python
from d2lut.overlay.stash_scanner import StashScanner

scanner = StashScanner(
    ocr_parser=ocr_parser,
    item_identifier=item_identifier,
    price_lookup=price_lookup
)

# Scan a stash tab
result = scanner.scan_stash_tab(screenshot, tooltip_coords)

# Get summary
summary = scanner.format_scan_summary(result)
print(summary)
```

### ScanTrigger

Manual trigger interface with cooldown support.

```python
from d2lut.overlay.scan_trigger import ScanTrigger, ScanTriggerConfig

# Configure trigger
config = ScanTriggerConfig(
    hotkey="ctrl+shift+s",
    enabled=True,
    cooldown_ms=1000  # 1 second cooldown
)

trigger = ScanTrigger(config=config)

# Set callback
trigger.set_scan_callback(lambda: perform_scan())

# Trigger manually
success = trigger.trigger()
```

### StashScanSession

High-level integration interface that wires everything together.

```python
from d2lut.overlay.stash_scan_integration import StashScanSession
from d2lut.overlay.stash_scan_presenter import PresentationConfig

# Create session with custom presentation config
presentation_config = PresentationConfig(
    sort_by="value",  # Sort by value (highest first)
    show_confidence=True,
    show_price_range=True,
    value_thresholds={
        "low": 100.0,
        "medium": 1000.0,
        "high": 5000.0
    }
)

with StashScanSession(
    db_path="data/d2lut.db",
    presentation_config=presentation_config
) as session:
    # Scan in one call
    result = session.scan(screenshot, tooltip_coords)
    
    # Display detailed summary
    print(session.format_detailed_summary(result))
    
    # Display compact summary
    print(session.format_compact_summary(result))
    
    # Display as table
    print(session.format_item_table(result))
    
    # Get structured summaries
    summaries = session.get_item_summaries(result)
    
    # Get value breakdown by tier
    breakdown = session.get_value_breakdown(result)
```

### StashScanPresenter

Presentation layer for formatting scan results.

```python
from d2lut.overlay.stash_scan_presenter import StashScanPresenter, PresentationConfig

# Configure presentation
config = PresentationConfig(
    show_confidence=True,
    show_sample_count=True,
    show_price_range=True,
    sort_by="value",
    currency_symbol="FG"
)

presenter = StashScanPresenter(config=config)

# Format detailed summary
detailed = presenter.format_detailed_summary(result)

# Format compact summary
compact = presenter.format_compact_summary(result)

# Format as table
table = presenter.format_item_table(result)

# Get item summaries
summaries = presenter.get_item_summaries(result)

# Get value breakdown
breakdown = presenter.get_value_breakdown(result)
```

## Data Structures

### StashScanResult

Complete result of a stash scan operation.

```python
@dataclass
class StashScanResult:
    items: list[ScannedItem]           # All scanned items
    total_value_fg: float              # Total stash value in FG
    scan_timestamp: float              # When scan was performed
    scan_duration_ms: float            # How long scan took
    items_with_prices: int             # Count of items with price data
    items_without_prices: int          # Count of items without prices
    scan_errors: list[str]             # Any errors encountered
```

### ScannedItem

Individual scanned item with identification and pricing.

```python
@dataclass
class ScannedItem:
    slot_index: int                    # Position in stash
    parsed_item: ParsedItem            # OCR parsed data
    match_result: MatchResult          # Catalog match result
    price_estimate: PriceEstimate | None  # Market price (if available)
    scan_timestamp: float              # When item was scanned
```

## Usage Examples

### Basic Scan with Detailed Presentation

```python
from d2lut.overlay.stash_scan_integration import StashScanSession
from d2lut.overlay.ocr_parser import TooltipCoords

# Define tooltip coordinates for visible items
coords = [
    TooltipCoords(x=100, y=100, width=200, height=150),
    TooltipCoords(x=350, y=100, width=200, height=150),
    TooltipCoords(x=600, y=100, width=200, height=150),
]

# Scan with detailed presentation
with StashScanSession(db_path="data/d2lut.db") as session:
    result = session.scan(screenshot_bytes, coords)
    
    # Show detailed summary with per-item breakdowns
    print(session.format_detailed_summary(result))
    
    # Or show compact one-line summary
    print(session.format_compact_summary(result))
    
    # Or show as table
    print(session.format_item_table(result))
```

### Per-Item Price Summaries

```python
with StashScanSession(db_path="data/d2lut.db") as session:
    result = session.scan(screenshot, coords)
    
    # Get structured per-item summaries
    summaries = session.get_item_summaries(result)
    
    for summary in summaries:
        print(f"Slot {summary['slot_number']}: {summary['item_name']}")
        print(f"  Value Tier: {summary['value_tier']}")  # low, medium, high, no_data
        print(f"  Price: {summary['price_display']}")
        if summary['has_price']:
            print(f"  Range: {summary['price_range_display']}")
            print(f"  Confidence: {summary['price_confidence']}")
```

### Total Tab Value with Breakdown

```python
with StashScanSession(db_path="data/d2lut.db") as session:
    result = session.scan(screenshot, coords)
    
    # Get value breakdown by tier
    breakdown = session.get_value_breakdown(result)
    
    print(f"Total Stash Value: {breakdown['total_value']:,.0f} FG")
    print(f"Total Items: {breakdown['total_items']}")
    print(f"Items with Prices: {breakdown['items_with_prices']}")
    print(f"Items without Prices: {breakdown['items_without_prices']}")
    
    # Breakdown by value tier
    for tier, data in breakdown['by_tier'].items():
        if tier != "no_data":
            print(f"{tier.upper()}: {data['count']} items, {data['total_value']:,.0f} FG")
```

### Re-scan Support

```python
with StashScanSession(db_path="data/d2lut.db") as session:
    # First scan
    result1 = session.scan(screenshot, coords)
    print(session.format_compact_summary(result1))
    
    # Re-scan using cached data (no need to pass screenshot/coords again)
    result2 = session.rescan()
    if result2:
        print(session.format_compact_summary(result2))
```

### Clear Results

```python
with StashScanSession(db_path="data/d2lut.db") as session:
    # Perform scan
    result = session.scan(screenshot, coords)
    
    # Get cached result
    cached = session.get_last_result()
    
    # Clear cache
    session.clear_results()
    
    # Cached result is now None
    assert session.get_last_result() is None
```

### Manual Trigger with Cooldown

```python
from d2lut.overlay.stash_scan_integration import StashScanSession
from d2lut.overlay.scan_trigger import ScanTriggerConfig

# Configure trigger
trigger_config = ScanTriggerConfig(
    hotkey="ctrl+shift+s",
    cooldown_ms=1000
)

with StashScanSession(db_path="data/d2lut.db", trigger_config=trigger_config) as session:
    # Prepare scan data
    session.prepare_scan(screenshot, coords)
    session.setup_trigger_callback()
    
    # Trigger scan
    if session.trigger.trigger():
        result = session.get_last_result()
        print(session.format_summary(result))
    else:
        print("Scan on cooldown")
```

### Re-scan and Clear

```python
with StashScanSession(db_path="data/d2lut.db") as session:
    # First scan
    result1 = session.scan(screenshot, coords)
    
    # Get cached result
    cached = session.get_last_result()
    
    # Clear cache
    session.clear_results()
    
    # Scan again
    result2 = session.scan(screenshot, coords)
```

### Structured Value List

```python
with StashScanSession(db_path="data/d2lut.db") as session:
    result = session.scan(screenshot, coords)
    
    # Get structured list
    value_list = session.get_value_list(result)
    
    for item in value_list:
        print(f"Slot {item['slot_index']}: {item['item_name']}")
        if item['has_price']:
            print(f"  Price: {item['price_fg']:,.0f} FG")
            print(f"  Range: {item['price_low_fg']:,.0f} - {item['price_high_fg']:,.0f}")
            print(f"  Confidence: {item['price_confidence']}")
        else:
            print(f"  No price data")
```

## Configuration

### OCR Configuration

```python
ocr_config = {
    "engine": "pytesseract",  # or "easyocr"
    "confidence_threshold": 0.7,
    "preprocess": {
        "contrast_enhance": True,
        "denoise": True,
        "resize_factor": 2.0
    }
}

session = StashScanSession(db_path="data/d2lut.db", ocr_config=ocr_config)
```

### Trigger Configuration

```python
trigger_config = ScanTriggerConfig(
    hotkey="ctrl+shift+s",  # Future: hotkey binding
    enabled=True,
    cooldown_ms=1000  # Minimum time between scans
)

session = StashScanSession(db_path="data/d2lut.db", trigger_config=trigger_config)
```

### Presentation Configuration

```python
from d2lut.overlay.stash_scan_presenter import PresentationConfig

presentation_config = PresentationConfig(
    show_confidence=True,        # Show price confidence levels
    show_sample_count=True,      # Show number of market observations
    show_price_range=True,       # Show low-high price range
    show_scan_duration=True,     # Show scan duration in summary
    show_errors=True,            # Show scan errors
    max_errors_displayed=5,      # Maximum errors to display
    sort_by="value",             # Sort by: "value", "name", or "slot"
    currency_symbol="FG",        # Currency symbol to display
    value_thresholds={           # Value tier thresholds
        "low": 100.0,
        "medium": 1000.0,
        "high": 5000.0
    }
)

session = StashScanSession(
    db_path="data/d2lut.db",
    presentation_config=presentation_config
)
```

### Custom Value Thresholds

Adjust value tiers based on your trading style:

```python
# Conservative trader (lower thresholds)
conservative_config = PresentationConfig(
    value_thresholds={
        "low": 50.0,
        "medium": 500.0,
        "high": 2000.0
    }
)

# High-value trader (higher thresholds)
high_value_config = PresentationConfig(
    value_thresholds={
        "low": 1000.0,
        "medium": 5000.0,
        "high": 10000.0
    }
)
```

### Sorting Options

```python
# Sort by value (highest first) - default
config_value = PresentationConfig(sort_by="value")

# Sort by name (alphabetical)
config_name = PresentationConfig(sort_by="name")

# Sort by slot position
config_slot = PresentationConfig(sort_by="slot")
```

## Error Handling

The scanner handles errors gracefully:

- **OCR Errors**: Items with parsing errors are included with error info
- **Identification Errors**: Items that can't be matched are marked as "no_match"
- **Price Lookup Errors**: Items without price data show `None` for price_estimate
- **Processing Errors**: Errors are logged in `scan_errors` list

```python
result = session.scan(screenshot, coords)

# Check for errors
if result.scan_errors:
    print(f"Encountered {len(result.scan_errors)} errors:")
    for error in result.scan_errors:
        print(f"  - {error}")

# Handle items without prices
for item in result.items:
    if item.price_estimate is None:
        print(f"No price for: {item.match_result.matched_name}")
```

## Performance

- **Scan Duration**: Typically 100-500ms for 10-20 items
- **Cooldown**: Default 1000ms prevents excessive scanning
- **Memory**: Results are cached but can be cleared
- **Concurrency**: Thread-safe trigger with lock protection

## Integration with Overlay

The stash scanner is designed to integrate with the overlay system:

1. **Hover Detection**: Detect when user hovers over stash
2. **Coordinate Detection**: Identify visible item positions
3. **Trigger Binding**: Bind hotkey to trigger scan
4. **Result Display**: Show summary in overlay UI
5. **Value Highlighting**: Color-code items by value

## Future Enhancements

- **Multi-tab Scanning**: Scan multiple stash tabs in sequence
- **Persistent Storage**: Save scan results to database
- **Hotkey Binding**: Actual keyboard hotkey integration
- **Auto-scan**: Automatic scanning on stash open
- **Export**: Export scan results to CSV/JSON
- **Filtering**: Filter items by value threshold
- **Sorting**: Sort items by value, name, or type

## Requirements

- **Requirements 5.1**: Manual scan trigger (hotkey/button) ✓
- **Requirements 5.3**: Calculate and display total stash value ✓
- **Requirements 5.5**: Toggle display on/off (via clear results) ✓
- **Phase 1 MVP**: Single visible tab scanning ✓
- **Task 7.2**: Per-item price summaries and total tab value ✓
- **Task 7.2**: Re-scan and clear results support ✓

## See Also

- [OCR Parser Documentation](README_OCR.md)
- [Item Identification Documentation](README_ITEM_IDENTIFICATION.md)
- [Price Lookup Documentation](README_PRICE_LOOKUP.md)
- [Inventory Overlay Documentation](README.md)
