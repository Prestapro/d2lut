# Overlay Application - Main Entry Point

## Overview

The `overlay_app.py` module provides the main application entry point for the d2lut overlay system. It orchestrates the complete OCR → Identification → Pricing → Overlay workflow by initializing and coordinating all components.

## Architecture

The `OverlayApp` class is the central coordinator that:

1. **Initializes all components**:
   - OCR Parser for tooltip extraction
   - Item Identifier for catalog matching
   - Price Lookup Engine for market data
   - Inventory Overlay for display
   - Stash Scanner for batch scanning

2. **Manages application lifecycle**:
   - Start/stop the application
   - Pause/resume updates
   - Handle threading for background processing

3. **Coordinates the workflow**:
   - Screen capture loop
   - Hover detection and tooltip parsing
   - Item identification
   - Price lookup
   - Overlay rendering

## Usage

### Basic Usage

```python
from pathlib import Path
from d2lut.overlay.overlay_app import create_app
from d2lut.overlay.ocr_parser import TooltipCoords

# Create the overlay app
db_path = Path("data/d2lut.db")
app = create_app(db_path)

# Set up callbacks
def get_screenshot():
    # Your screenshot capture logic
    return screenshot_bytes

def render_overlay(overlay_render):
    # Your overlay rendering logic
    print(f"Rendering {len(overlay_render.slots)} items")

app.set_screenshot_callback(get_screenshot)
app.set_render_callback(render_overlay)

# Start the app
app.start()

# Simulate hover event
coords = TooltipCoords(x=100, y=100, width=200, height=150)
app.on_hover_start(coords)

# Get hover details
details = app.get_hover_details()
if details and details.has_data:
    print(f"Item: {details.item_name}")
    print(f"Price: {details.median_price} FG")

# End hover
app.on_hover_end()

# Stop the app
app.stop()
app.close()
```

### Context Manager Usage

```python
from d2lut.overlay.overlay_app import create_app

with create_app("data/d2lut.db") as app:
    # App is automatically started and stopped
    app.start()
    
    # Your application logic here
    
    app.stop()
# App is automatically closed
```

### Stash Scanning

```python
from d2lut.overlay.overlay_app import create_app
from d2lut.overlay.ocr_parser import TooltipCoords

with create_app("data/d2lut.db") as app:
    # Define tooltip coordinates for visible items
    coords_list = [
        TooltipCoords(x=100, y=100, width=200, height=150),
        TooltipCoords(x=350, y=100, width=200, height=150),
        TooltipCoords(x=600, y=100, width=200, height=150),
    ]
    
    # Perform scan
    result = app.scan_stash_tab(screenshot_bytes, coords_list)
    
    # Display results
    print(f"Total value: {result.total_value_fg:,.0f} FG")
    print(f"Items with prices: {result.items_with_prices}")
    
    # Get formatted summary
    summary = app.stash_scanner.format_scan_summary(result)
    print(summary)
```

## Configuration

The overlay app uses the `OverlayConfig` class for configuration:

```python
from d2lut.overlay.overlay_app import create_app
from d2lut.overlay.config import OverlayConfig

# Create custom config
config = OverlayConfig()
config.ocr.engine = "easyocr"
config.ocr.confidence_threshold = 0.7
config.overlay.update_interval_ms = 1000
config.overlay.color_thresholds = {"low": 1000, "medium": 10000}

# Create app with custom config
app = create_app("data/d2lut.db")
app.config = config
```

Or load from a JSON file:

```python
from d2lut.overlay.overlay_app import create_app

# Load config from file
app = create_app("data/d2lut.db", config_path="config/overlay.json")
```

## Callbacks

The overlay app supports three types of callbacks:

### 1. Screenshot Callback

Called to capture the current game screen:

```python
def get_screenshot() -> bytes:
    # Capture screenshot using mss, PIL, or other library
    return screenshot_bytes

app.set_screenshot_callback(get_screenshot)
```

### 2. Hover Callback

Called when a hover event is detected:

```python
def on_hover(coords: TooltipCoords) -> None:
    print(f"Hovering at ({coords.x}, {coords.y})")

app.set_hover_callback(on_hover)
```

### 3. Render Callback

Called when overlay data is ready to be rendered:

```python
def render_overlay(overlay_render: OverlayRender) -> None:
    for slot_id, slot_overlay in overlay_render.slots.items():
        if slot_overlay.median_price:
            print(f"Slot {slot_id}: {slot_overlay.median_price} FG")

app.set_render_callback(render_overlay)
```

## Application State

Get the current application state:

```python
state = app.get_state()
print(f"Running: {state['running']}")
print(f"Paused: {state['paused']}")
print(f"FPS: {state['fps']:.1f}")
print(f"Frame count: {state['frame_count']}")
```

## Lifecycle Management

```python
# Start the app
app.start()

# Pause updates (stops processing but keeps app running)
app.pause()

# Resume updates
app.resume()

# Toggle pause state
is_paused = app.toggle_pause()

# Stop the app
app.stop()

# Close and clean up resources
app.close()
```

## Threading

The overlay app runs an update loop in a background thread when started. The update loop:

1. Captures screenshots at the configured interval
2. Processes hover events if hovering
3. Parses tooltips via OCR
4. Identifies items via catalog matching
5. Looks up prices from the market database
6. Triggers render callbacks with overlay data

The update interval is configurable via `config.overlay.update_interval_ms` (default: 1000ms).

## Error Handling

The overlay app handles errors gracefully:

- OCR parsing errors are captured in `ParsedItem.error`
- Item identification failures return `MatchResult` with `match_type="error"`
- Price lookup failures return `None` for `price_estimate`
- Update loop errors are logged but don't crash the app

## Performance

The overlay app is designed for minimal performance impact:

- Configurable update interval (default: 1000ms)
- Background threading for non-blocking updates
- Efficient caching of catalog and price data
- FPS tracking for performance monitoring

Target performance:
- Update latency: ≤200ms for cached lookups
- Memory usage: ≤500MB
- Frame rate: 30 FPS minimum (60 FPS stretch goal)

## Integration with Existing Components

The overlay app integrates with all existing components:

- **OCRTooltipParser**: Parses tooltips from screenshots
- **ItemIdentifier**: Matches parsed items to catalog entries
- **PriceLookupEngine**: Retrieves price estimates from market database
- **InventoryOverlay**: Manages overlay display and color coding
- **StashScanner**: Performs batch scanning of stash tabs

## Examples

See `examples/overlay_app_demo.py` for complete working examples:

- Basic hover functionality
- Stash scanning
- Application lifecycle management
- Configuration management

## Testing

See `tests/test_overlay_app.py` for unit tests covering:

- Application initialization
- Lifecycle management
- Hover event handling
- Stash scanning
- State management
- Configuration validation

## Requirements

The overlay app satisfies the following requirements from the spec:

- **Requirement 1.1**: OCR tooltip parser integration
- **Requirement 2.1**: Item identification integration
- **Requirement 3.1**: Price lookup integration
- **Requirement 4.1**: Inventory overlay display

## Future Enhancements

Planned enhancements for future phases:

- Automatic hover detection from game UI
- Screen capture integration with game overlay libraries
- Hotkey support for manual triggers
- Multi-monitor support
- Performance profiling and optimization
- Advanced caching strategies
