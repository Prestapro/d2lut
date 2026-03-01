# d2lut Overlay System

## Overview

The d2lut overlay system provides in-game pricing and item valuation for Diablo 2 Resurrected. It uses OCR-based tooltip parsing to identify items and display market prices directly in the game interface.

## Features

### Phase 1 MVP (Current)

- **OCR Tooltip Parsing**: Extract item information from game screenshots
- **Item Identification**: Match parsed items to catalog entries with slang support
- **Price Lookup**: Retrieve market prices from local database
- **Hover Overlay**: Display prices on hovered items in inventory
- **Stash Scanning**: Manual scan mode for single stash tab valuation

### Components

- **OCR Parser** ([README_OCR.md](README_OCR.md)): Tooltip text extraction
- **Item Identifier** ([README_ITEM_IDENTIFICATION.md](README_ITEM_IDENTIFICATION.md)): Catalog matching with slang
- **Price Lookup** ([README_PRICE_LOOKUP.md](README_PRICE_LOOKUP.md)): Market data integration
- **Inventory Overlay**: Hover-based price display
- **Stash Scanner** ([README_STASH_SCAN.md](README_STASH_SCAN.md)): Manual stash tab scanning

## Quick Start

### Windows MVP (In-Game Hover Price)

Use the local market DB and a fixed tooltip rectangle to display `fg` in a small topmost window.

1. Calibrate tooltip rectangle (drag over a visible D2R tooltip):

```bash
python scripts/calibrate_tooltip_rect.py
```

This prints and copies to clipboard a value like:

```text
1200,300,420,260
```

2. Run the Windows MVP overlay (console mode first):

```bash
python scripts/run_overlay_windows_mvp.py --db data/cache/d2lut.db --tooltip 1200,300,420,260 --console-only --ocr-engine pytesseract
```

3. Run with a small topmost overlay window:

```bash
python scripts/run_overlay_windows_mvp.py --db data/cache/d2lut.db --tooltip 1200,300,420,260 --ocr-engine pytesseract
```

4. Compact inline label mode (looks like a suffix next to the tooltip), e.g. `Archon Plate - 5fg`:

```bash
python scripts/run_overlay_windows_mvp.py --db data/cache/d2lut.db --tooltip 1200,300,420,260 --ocr-engine pytesseract --compact --no-approx-prefix
```

Useful runtime flags for in-game use:
- `--hide-no-data` hide overlay when no price is found
- `--label-x-offset 8 --label-y-offset 0` adjust compact label position
- `--hotkey-toggle f8` pause/resume overlay (requires `pip install keyboard`)
- `--hotkey-quit f10` quit runner (requires `pip install keyboard`)

Example (compact + hide no-data + hotkeys):

```bash
python scripts/run_overlay_windows_mvp.py --db data/cache/d2lut.db --tooltip 1200,300,420,260 --ocr-engine pytesseract --compact --no-approx-prefix --hide-no-data
```

Runtime deps (Windows):
- `pip install pillow mss opencv-python`
- OCR:
  - `pip install pytesseract` (plus Tesseract installed in Windows), or
  - `pip install easyocr`

### Basic Hover Overlay

```python
from d2lut.overlay.inventory_overlay import InventoryOverlay, InventoryState, InventorySlot

# Create overlay
overlay = InventoryOverlay(
    low_value_threshold=1000.0,
    medium_value_threshold=10000.0
)

# Render inventory with prices
render = overlay.render_inventory(inventory_state)

# Get hover details
details = overlay.get_hover_details(slot)
```

### Stash Scanning

```python
from d2lut.overlay.stash_scan_integration import StashScanSession
from d2lut.overlay.ocr_parser import TooltipCoords

# Create scan session
with StashScanSession(db_path="data/d2lut.db") as session:
    # Define visible item coordinates
    coords = [
        TooltipCoords(x=100, y=100, width=200, height=150),
        TooltipCoords(x=350, y=100, width=200, height=150),
    ]
    
    # Scan stash tab
    result = session.scan(screenshot_bytes, coords)
    
    # Display summary
    print(session.format_summary(result))
    print(f"Total Value: {result.total_value_fg:,.0f} FG")
```

## Architecture

### Pipeline

1. **Capture**: Screenshot of D2R window with tooltips
2. **OCR**: Text extraction using pytesseract/easyocr
3. **Parse**: Structure extraction (item name, type, affixes)
4. **Identify**: Catalog matching with slang resolution
5. **Price**: Market data lookup from local database
6. **Render**: Overlay display with color coding

### Data Flow

```
Screenshot → OCR Parser → ParsedItem
                            ↓
                      Item Identifier → MatchResult
                                          ↓
                                    Price Lookup → PriceEstimate
                                                      ↓
                                                  Overlay Render
```

## MVP Constraints

- **OCR-based**: No memory reading or game injection
- **Visible items only**: Only price what can be seen/read
- **Local data**: Uses local market database snapshots
- **Confidence display**: Shows price ranges and confidence levels
- **Manual triggers**: User-initiated scans (no automation)

## Configuration

See [SETUP.md](SETUP.md) for detailed setup instructions.

### OCR Configuration

```python
ocr_config = {
    "engine": "pytesseract",
    "confidence_threshold": 0.7,
    "preprocess": {
        "contrast_enhance": True,
        "denoise": True,
        "resize_factor": 2.0
    }
}
```

### Overlay Configuration

```python
overlay_config = {
    "low_value_threshold": 1000,
    "medium_value_threshold": 10000,
    "enabled": True
}
```

## Documentation

- [OCR Parser](README_OCR.md) - Tooltip text extraction
- [Item Identification](README_ITEM_IDENTIFICATION.md) - Catalog matching
- [Price Lookup](README_PRICE_LOOKUP.md) - Market data integration
- [Stash Scanner](README_STASH_SCAN.md) - Manual stash scanning
- [Setup Guide](SETUP.md) - Installation and configuration

## Future Enhancements

- Multi-tab stash scanning
- Persistent scan results
- Hotkey binding for triggers
- Category-aware parsing
- Bundle detection
- LLD/Craft rule engine
- Demand modeling
- Price history and trends

## Requirements

- Python 3.10+
- pytesseract or easyocr
- OpenCV (cv2)
- PIL/Pillow
- SQLite database with market data

## See Also

- [Design Document](../../../.kiro/specs/d2lut-overlay/design.md)
- [Requirements](../../../.kiro/specs/d2lut-overlay/requirements.md)
- [Tasks](../../../.kiro/specs/d2lut-overlay/tasks.md)
