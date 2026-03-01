# Category-Aware Market Weighting

## Overview

This document describes the category-aware parsing and weighting system implemented for the d2lut market data pipeline. The system extracts forum category context from d2jsp URLs and uses it to improve item disambiguation and pricing accuracy.

## Implementation

### 1. Category Extraction from URLs

Forum threads on d2jsp can be organized into categories using the `c=` URL parameter (e.g., `c=2`, `c=3`, `c=4`, `c=5`). These categories typically represent:

- **c=2**: Weapons, armor, and bases
- **c=3**: Charms and jewels
- **c=4**: Runes, keys, tokens, and essences
- **c=5**: Low Level Dueling (LLD) items

The parser now extracts this category information from thread URLs and stores it in the database.

#### Code Changes

**File: `src/d2lut/normalize/d2jsp_market.py`**

Enhanced `parse_forum_threads_from_html()` to extract category from URLs:

```python
# Extract category from URL if present (e.g., c=2, c=3, etc.)
cat_m = re.search(r"(?:^|[?&])c=(\d+)(?:&|$)", href)
if cat_m:
    try:
        topic_category_id = int(cat_m.group(1))
    except ValueError:
        pass
```

### 2. Database Schema

The database already had support for category tracking via the `thread_category_id` column in both `threads` and `observed_prices` tables. This implementation leverages that existing schema.

### 3. Category-Aware Weighting in Pricing Engine

The pricing engine now applies category-specific weight multipliers to improve price estimate accuracy.

#### Code Changes

**File: `src/d2lut/pricing/engine.py`**

Added `_calculate_category_weight()` method that applies multipliers based on item type and category:

```python
def _calculate_category_weight(self, variant_key: str, category_id: int | None) -> float:
    """Calculate category-specific weight multiplier for improved disambiguation."""
    if category_id is None:
        return 1.0  # Neutral weight
    
    item_type = variant_key.split(":")[0] if ":" in variant_key else ""
    
    # Category 4: Boost runes/keys/tokens/essences
    if category_id == 4:
        if item_type in ("rune", "key", "keyset", "token", "essence"):
            return 1.3  # 30% boost
        else:
            return 0.7  # Reduce weight for non-matching items
    
    # Category 3: Boost charms/jewels
    if category_id == 3:
        if item_type in ("charm", "jewel"):
            return 1.3
        else:
            return 0.7
    
    # Category 5: Boost LLD items
    if category_id == 5:
        return 1.2
    
    # Category 2: Boost weapons/armor/bases
    if category_id == 2:
        if item_type in ("base", "unique", "set"):
            return 1.2
        else:
            return 0.8
    
    return 1.0  # Default neutral weight
```

### 4. Model Updates

**File: `src/d2lut/models.py`**

Added `thread_category_id` field to `ObservedPrice` dataclass:

```python
@dataclass(slots=True)
class ObservedPrice:
    canonical_item_id: str
    variant_key: str
    ask_fg: Optional[float] = None
    bin_fg: Optional[float] = None
    sold_fg: Optional[float] = None
    confidence: float = 0.0
    source_url: str = ""
    thread_category_id: Optional[int] = None  # NEW
```

**File: `scripts/build_market_db.py`**

Updated `row_to_observed()` to pass category ID to ObservedPrice:

```python
return ObservedPrice(
    canonical_item_id=row["canonical_item_id"],
    variant_key=row["variant_key"],
    ask_fg=value if sig == "ask" else None,
    bin_fg=value if sig == "bin" else None,
    sold_fg=value if sig == "sold" else None,
    confidence=confidence,
    source_url=row.get("source_url", ""),
    thread_category_id=c,  # NEW
)
```

## Benefits

### 1. Improved Disambiguation

Category context helps distinguish between items with similar names:

- **Tal rune** vs **Tal Rasha's items**: Runes in category 4 get boosted weight, while set items in category 2 get different treatment
- **Charms** vs **other items**: Charms in category 3 are weighted more heavily for charm-related searches

### 2. Better Price Accuracy

By boosting observations from the correct category and reducing weight for mismatched categories, the pricing engine produces more accurate estimates:

- Rune prices are more influenced by observations from the runes category (c=4)
- Charm prices are more influenced by observations from the charms category (c=3)
- LLD items get appropriate weighting in category 5

### 3. Reduced Noise

Observations from incorrect categories (e.g., a rune mentioned in a weapons thread) receive reduced weight, minimizing their impact on price estimates.

## Testing

Comprehensive tests verify the implementation:

**File: `tests/test_category_simple.py`**

Tests cover:
1. Category extraction from URLs
2. Category weight calculations
3. Pricing engine integration
4. Disambiguation scenarios

All tests pass successfully.

## Usage

The category-aware weighting is automatically applied during the market data pipeline:

1. **Forum page import**: Categories are extracted from URLs and stored in the database
2. **Price estimation**: The pricing engine applies category weights when building price estimates
3. **No configuration needed**: The system works automatically with existing data

## Future Enhancements

Potential improvements for future iterations:

1. **Dynamic category mapping**: Learn category-to-item-type mappings from data
2. **Category-specific confidence scoring**: Adjust confidence levels based on category match quality
3. **Cross-category analysis**: Detect when items appear in multiple categories and adjust accordingly
4. **User-configurable weights**: Allow users to tune category weight multipliers

## Requirements Satisfied

This implementation satisfies the following requirements from the spec:

- **Requirement 7.1**: Category-Aware Parsing - Parser applies category-specific rules
- **Requirement 7.2**: Category-Specific Extraction - Extracts category-relevant properties
- **Requirement 11.2**: Weight Tuning - Pricing engine adjusts weights based on market activity and category context
- **Requirement 12.5**: Data Pipeline Integration - System extends the pipeline appropriately

## Related Files

- `src/d2lut/normalize/d2jsp_market.py` - Forum parsing with category extraction
- `src/d2lut/pricing/engine.py` - Category-aware weighting logic
- `src/d2lut/models.py` - Data models with category support
- `scripts/build_market_db.py` - Database import with category handling
- `tests/test_category_simple.py` - Comprehensive test suite
