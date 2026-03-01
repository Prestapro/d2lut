# Price Lookup Engine

The `PriceLookupEngine` provides price estimates and market data for identified items in the overlay system. It integrates with the existing d2lut market database to retrieve snapshot-refreshed pricing information.

## Overview

The Price Lookup Engine is responsible for:
- Retrieving price estimates from the market database
- Getting variant-specific pricing for items
- Fetching recent market listings (BIN/SOLD/ASK)
- Providing comprehensive market summaries
- Handling insufficient data cases gracefully

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  PriceLookupEngine                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  get_price()                                             │
│    └─> Query price_estimates table                      │
│        └─> Return PriceEstimate                          │
│                                                          │
│  get_prices_for_variants()                               │
│    └─> Query all variants for item                      │
│        └─> Return dict[variant_key, PriceEstimate]      │
│                                                          │
│  get_fg_listings()                                       │
│    └─> Query observed_prices + threads                  │
│        └─> Return list[FGListing]                       │
│                                                          │
│  get_market_summary()                                    │
│    └─> Combine price + listings + metrics               │
│        └─> Return comprehensive summary                 │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Data Models

### PriceEstimate

Represents a price estimate for an item variant:

```python
@dataclass
class PriceEstimate:
    variant_key: str          # e.g., "rune:jah", "charm:gheed"
    estimate_fg: float        # Weighted median price
    range_low_fg: float       # Minimum observed price
    range_high_fg: float      # Maximum observed price
    confidence: str           # "low", "medium", "high"
    sample_count: int         # Number of observations
    last_updated: datetime    # When estimate was calculated
```

### FGListing

Represents a recent market listing:

```python
@dataclass
class FGListing:
    price_fg: float           # Listing price
    listing_type: str         # "bin", "ask", "co", "sold"
    thread_id: int            # Forum thread ID
    post_id: int | None       # Forum post ID (if available)
    posted_at: datetime | None # When listing was posted
    is_recent: bool           # Within recent_days threshold
    thread_title: str | None  # Thread title (if available)
    source_url: str | None    # URL to listing (if available)
```

## Usage

### Basic Price Lookup

```python
from d2lut.overlay.price_lookup import PriceLookupEngine

# Initialize engine
engine = PriceLookupEngine("data/cache/d2lut.db")

# Get price for an item
price = engine.get_price("rune:jah")
if price:
    print(f"Jah Rune: {price.estimate_fg} FG")
    print(f"Range: {price.range_low_fg} - {price.range_high_fg}")
    print(f"Confidence: {price.confidence}")
    print(f"Samples: {price.sample_count}")
else:
    print("No price data available")

engine.close()
```

### Using Context Manager

```python
with PriceLookupEngine("data/cache/d2lut.db") as engine:
    price = engine.get_price("rune:jah")
    # Engine automatically closed after block
```

### Variant-Specific Pricing

```python
with PriceLookupEngine("data/cache/d2lut.db") as engine:
    # Get all rune variants
    rune_prices = engine.get_prices_for_variants("rune")
    
    for variant_key, price in rune_prices.items():
        print(f"{variant_key}: {price.estimate_fg} FG")
    
    # Output:
    # rune:jah: 5000.0 FG
    # rune:ber: 3500.0 FG
    # rune:sur: 2000.0 FG
    # ...
```

### Recent Market Listings

```python
with PriceLookupEngine("data/cache/d2lut.db") as engine:
    # Get recent listings for Jah rune
    listings = engine.get_fg_listings("rune:jah", limit=10, recent_days=30)
    
    for listing in listings:
        recent_flag = "🔥" if listing.is_recent else "📅"
        print(f"{recent_flag} {listing.listing_type.upper()}: {listing.price_fg} FG")
        if listing.thread_title:
            print(f"   Thread: {listing.thread_title}")
    
    # Output:
    # 🔥 BIN: 5000.0 FG
    #    Thread: FT: Jah Rune
    # 🔥 BIN: 4800.0 FG
    #    Thread: ISO: High Runes
    # 📅 SOLD: 4900.0 FG
    #    Thread: Sold: Jah Rune
```

### Comprehensive Market Summary

```python
with PriceLookupEngine("data/cache/d2lut.db") as engine:
    summary = engine.get_market_summary("rune:jah")
    
    if summary["has_data"]:
        price = summary["price_estimate"]
        print(f"Price: {price.estimate_fg} FG ({price.confidence} confidence)")
        
        activity = summary["market_activity"]
        print(f"Total listings: {activity['total_listings']}")
        print(f"Recent listings: {activity['recent_listings']}")
        print(f"BIN count: {activity['bin_count']}")
        print(f"SOLD count: {activity['sold_count']}")
        print(f"Active market: {activity['has_active_market']}")
    else:
        print("No market data available")
```

## Integration with Overlay System

### With Item Identifier

```python
from d2lut.overlay.item_identifier import ItemIdentifier
from d2lut.overlay.price_lookup import PriceLookupEngine

# Initialize components
identifier = ItemIdentifier("data/cache/d2lut.db")
price_engine = PriceLookupEngine("data/cache/d2lut.db")

# Identify item from parsed tooltip
match_result = identifier.identify(parsed_item)

if match_result.canonical_item_id:
    # Get price for identified item
    price = price_engine.get_price(match_result.canonical_item_id)
    
    if price:
        print(f"Item: {match_result.matched_name}")
        print(f"Price: {price.estimate_fg} FG")
    else:
        print(f"Item: {match_result.matched_name}")
        print("No price data available")
```

### With OCR Parser

```python
from d2lut.overlay.ocr_parser import OCRTooltipParser
from d2lut.overlay.item_identifier import ItemIdentifier
from d2lut.overlay.price_lookup import PriceLookupEngine

# Initialize pipeline
ocr_parser = OCRTooltipParser()
identifier = ItemIdentifier("data/cache/d2lut.db")
price_engine = PriceLookupEngine("data/cache/d2lut.db")

# Parse tooltip from screenshot
parsed_item = ocr_parser.parse_tooltip(screenshot_bytes, coords)

# Identify item
match_result = identifier.identify(parsed_item)

# Get price
if match_result.canonical_item_id:
    price = price_engine.get_price(match_result.canonical_item_id)
    
    if price:
        print(f"Found: {match_result.matched_name}")
        print(f"Price: {price.estimate_fg} FG")
        print(f"Range: {price.range_low_fg} - {price.range_high_fg}")
```

## Error Handling

### Insufficient Data

The engine handles insufficient data cases gracefully:

```python
with PriceLookupEngine("data/cache/d2lut.db") as engine:
    # Non-existent item
    price = engine.get_price("nonexistent:item")
    if price is None:
        print("No price data available")
    
    # Empty listings
    listings = engine.get_fg_listings("nonexistent:item")
    if not listings:
        print("No recent listings")
    
    # Market summary with no data
    summary = engine.get_market_summary("nonexistent:item")
    if not summary["has_data"]:
        print("No market data available")
```

### Database Errors

```python
from pathlib import Path

try:
    engine = PriceLookupEngine("nonexistent.db")
except FileNotFoundError:
    print("Database not found")
```

## Performance Considerations

### Caching

The engine queries the database directly without caching. For overlay use cases with frequent lookups:

```python
from functools import lru_cache

class CachedPriceLookup:
    def __init__(self, db_path: str):
        self.engine = PriceLookupEngine(db_path)
    
    @lru_cache(maxsize=1000)
    def get_price_cached(self, item_id: str, variant: str | None = None):
        return self.engine.get_price(item_id, variant)
    
    def close(self):
        self.engine.close()
```

### Batch Lookups

For multiple items, use a single connection:

```python
with PriceLookupEngine("data/cache/d2lut.db") as engine:
    items = ["rune:jah", "rune:ber", "unique:shako"]
    
    prices = {}
    for item_id in items:
        price = engine.get_price(item_id)
        if price:
            prices[item_id] = price
```

## Database Schema

The engine queries these tables:

### price_estimates

```sql
CREATE TABLE price_estimates (
    id INTEGER PRIMARY KEY,
    market_key TEXT NOT NULL,
    variant_key TEXT NOT NULL,
    estimate_fg REAL NOT NULL,
    range_low_fg REAL NOT NULL,
    range_high_fg REAL NOT NULL,
    confidence TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(market_key, variant_key)
);
```

### observed_prices

```sql
CREATE TABLE observed_prices (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    market_key TEXT NOT NULL,
    forum_id INTEGER NOT NULL,
    thread_id INTEGER,
    post_id INTEGER,
    source_kind TEXT NOT NULL,
    signal_kind TEXT NOT NULL,
    canonical_item_id TEXT NOT NULL,
    variant_key TEXT NOT NULL,
    price_fg REAL NOT NULL,
    confidence REAL NOT NULL,
    observed_at TEXT,
    source_url TEXT,
    raw_excerpt TEXT
);
```

### threads

```sql
CREATE TABLE threads (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    forum_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    UNIQUE(source, thread_id)
);
```

## Testing

Run the test suite:

```bash
# Simple integration test
python tests/test_price_lookup_simple.py

# Full test suite (requires pytest)
pytest tests/test_price_lookup.py -v
```

## Requirements Validation

This implementation satisfies the following requirements:

- **Requirement 3.1**: Price lookups complete within 1 second (direct SQL queries)
- **Requirement 3.2**: Provides weighted median price from existing pricing engine
- **Requirement 3.3**: Provides price range (low/high)
- **Requirement 3.4**: Provides sample count and recent activity volume
- **Requirement 3.5**: Returns prices for multiple variants
- **Requirement 3.6**: Handles insufficient data gracefully (returns None)

## Next Steps

1. **Phase 1 Checkpoint**: Integrate with overlay rendering (Task 6)
2. **Phase 2**: Add demand model integration (Task 17)
3. **Phase 3**: Add price history and trend awareness (Task 18)
4. **Performance**: Add caching layer for frequent lookups (Task 19)

## See Also

- [OCR Parser Documentation](README_OCR.md)
- [Item Identification Documentation](README_ITEM_IDENTIFICATION.md)
- [Overlay Configuration](SETUP.md)
