# Overlay Infrastructure Setup

This document describes the overlay infrastructure and database schema for the d2lut overlay system.

## Overview

The overlay infrastructure provides the foundational components for the d2lut in-game pricing overlay:

1. **Database Schema Extensions** - Tables and views for overlay data
2. **Configuration Module** - JSON-based configuration with validation

## Database Schema

The overlay system extends the existing d2lut database with the following components:

### Tables

#### `overlay_item_captures`
Stores in-game item captures for training and validation:
- `id` - Primary key
- `captured_at` - Timestamp of capture
- `screenshot_path` - Path to screenshot file
- `tooltip_coords` - JSON array [x, y, width, height]
- `raw_ocr_text` - Raw OCR output
- `parsed_item_json` - JSON of ParsedItem
- `matched_item_id` - Matched catalog item ID
- `confidence` - Match confidence score
- `user_verified_item_id` - User-verified item ID
- `verified_at` - Verification timestamp

#### `overlay_config`
Stores overlay configuration:
- `id` - Primary key
- `config_key` - Configuration key (unique)
- `config_value` - Configuration value (JSON)
- `updated_at` - Last update timestamp

### Views

#### `overlay_market_status`
Provides current market status for items:
- `market_key` - Market identifier
- `variant_key` - Item variant identifier
- `median_price` - Weighted median price
- `range_low_fg` - Low price range
- `range_high_fg` - High price range
- `confidence` - Price confidence level
- `sample_count` - Number of samples
- `active_listings` - Count of active listings
- `last_observed` - Last observation timestamp
- `market_stability` - Market stability indicator (stable/moderate/volatile)

### Applying the Schema

To apply the overlay schema to your database:

```python
import sqlite3
from pathlib import Path

# Connect to your database
db_path = Path("data/market.db")
conn = sqlite3.connect(db_path)

# Read and execute schema
schema_path = Path("src/d2lut/overlay/schema.sql")
with open(schema_path, "r") as f:
    schema_sql = f.read()

conn.executescript(schema_sql)
conn.commit()
conn.close()
```

## Configuration Module

The configuration module provides a type-safe way to manage overlay settings.

### Configuration Structure

```python
from d2lut.overlay import OverlayConfig

# Create default configuration
config = OverlayConfig()

# Access configuration sections
print(config.ocr.engine)  # "easyocr"
print(config.overlay.enabled)  # True
print(config.pricing.min_samples)  # 3
print(config.rules.lld_enabled)  # True
```

### Configuration Sections

#### OCR Configuration
- `engine` - OCR engine to use ("easyocr" or "pytesseract")
- `confidence_threshold` - Minimum confidence threshold (0.0-1.0)
- `preprocess` - Preprocessing options (dict)

#### Overlay Display Configuration
- `enabled` - Enable/disable overlay
- `color_thresholds` - Price thresholds for color coding (dict)
- `update_interval_ms` - Update interval in milliseconds
- `max_cache_age_seconds` - Maximum cache age in seconds

#### Pricing Configuration
- `min_samples` - Minimum samples for price estimates
- `confidence_levels` - Confidence level thresholds (dict)

#### Rules Configuration
- `lld_enabled` - Enable LLD (Low Level Dueling) rules
- `craft_enabled` - Enable craft item rules
- `affix_adjustments` - Enable affix-based price adjustments

### Loading Configuration

```python
from d2lut.overlay import load_config

# Load from file
config = load_config("config/overlay.json")

# Load default configuration
config = load_config(None)
```

### Creating Configuration Files

```python
from d2lut.overlay import create_default_config

# Create default configuration file
config = create_default_config("config/overlay.json")
```

### Validation

Configuration is automatically validated when loaded:

```python
from d2lut.overlay import OverlayConfig

config = OverlayConfig()
errors = config.validate()

if errors:
    for error in errors:
        print(f"Error: {error}")
```

### Example Configuration File

See `config/overlay.example.json` for a complete example configuration file.

## Next Steps

With the infrastructure in place, the next phases will implement:

1. OCR tooltip parser
2. Item identifier with slang support
3. Price lookup integration
4. Overlay rendering components

## Requirements Validation

This implementation satisfies the following requirements:

- **Requirement 12.1**: Uses existing SQLite market database
- **Requirement 12.2**: Uses existing catalog database
- **Requirement 12.5**: Extends pipeline with overlay-specific tables and configuration

The schema includes only MVP-safe tables and indexes as specified in the design document, deferring advanced features like `price_history`, `bundle_pricing`, and `pricing_rules` to later phases.
