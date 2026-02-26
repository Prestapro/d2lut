# Slang Alias Integration

## Overview

The d2jsp normalizer now integrates with the `slang_aliases` table to automatically expand common shorthand terms during title and post normalization. This reduces unresolved shorthand noise and improves item identification accuracy.

## How It Works

### 1. Slang Cache Initialization

When a `D2LutDB` instance is created, it automatically initializes a global slang cache by loading enabled aliases from the `slang_aliases` table:

```python
from d2lut.storage import D2LutDB

# Cache is automatically initialized when DB is opened
db = D2LutDB("data/cache/d2lut.db")
```

### 2. Normalization During Parsing

The `normalize_item_hint()` function now applies slang normalization before pattern matching:

```python
from d2lut.normalize.d2jsp_market import normalize_item_hint

# "gt" is expanded to "giant thresher" before pattern matching
result = normalize_item_hint("4os gt eth bin 150")
# Returns: ('base:giant_thresher', 'base:giant_thresher:eth:4os')
```

### 3. Supported Alias Types

The integration currently applies two types of slang aliases:

- **base_alias**: Base item shorthand (e.g., "gt" → "giant thresher")
- **item_alias**: Item name variations (e.g., "amy" → "ammy")

Other alias types (`noise`, `trade_term`, `stat_alias`) are stored but not yet applied during normalization.

## Seeding Slang Aliases

Use the `seed_slang_aliases.py` script to populate common d2jsp slang:

```bash
PYTHONPATH=src python scripts/seed_slang_aliases.py --db data/cache/d2lut.db seed
```

This seeds:
- Base shorthand (gt, cv, pb, ba, ap, mp, etc.)
- Item aliases (amy, shako, arach, torch, anni, etc.)
- Stat shorthand (fcr, frw, ias, ed, etc.)
- Noise terms (fg, please, fast trade, etc.)
- Trade terms (ft, iso, bin, c/o, etc.)

## Manual Alias Management

You can add custom aliases directly to the database:

```sql
INSERT INTO slang_aliases(
  term_norm, term_raw, term_type, 
  canonical_item_id, replacement_text, 
  confidence, source, enabled
) VALUES (
  'hoz', 'hoz', 'item_alias',
  'unique:herald_of_zakarum', 'herald of zakarum',
  0.99, 'manual', 1
);
```

After adding aliases, reinitialize the cache:

```python
from d2lut.normalize.d2jsp_market import init_slang_cache

init_slang_cache("data/cache/d2lut.db")
```

## Cache Behavior

- **Global Cache**: Slang aliases are loaded once per process and cached globally
- **Automatic Initialization**: Cache is initialized when `D2LutDB` is opened
- **Manual Refresh**: Call `init_slang_cache(db_path)` to reload after changes
- **Graceful Degradation**: If the table doesn't exist, normalization continues without slang expansion

## Performance

- **Load Time**: ~1-5ms for typical alias sets (100-500 entries)
- **Lookup Time**: O(1) dictionary lookup per term
- **Memory**: ~10-50KB for typical alias sets

## Testing

Run the integration tests to verify slang normalization:

```bash
# Simple unit tests
python tests/test_slang_simple.py

# End-to-end integration tests
python tests/test_integration_e2e.py
```

## Examples

### Before Slang Integration

```python
normalize_item_hint("4os gt eth")
# Returns: None (unrecognized shorthand)
```

### After Slang Integration

```python
normalize_item_hint("4os gt eth")
# Returns: ('base:giant_thresher', 'base:giant_thresher:eth:4os')
```

### Thread Parsing Example

```python
thread = {
    "title": "4os cv eth bin 200",
    "forum_id": 271,
    "thread_id": 12345,
    # ...
}

observations = observations_from_thread_row(thread, market_key="d2r_sc_ladder")
# Now correctly identifies "cv" as "colossus voulge"
# observations[0]['canonical_item_id'] == 'base:colossus_voulge'
```

## Future Enhancements

Planned improvements for slang integration:

1. **Noise Filtering**: Apply `noise` type aliases to filter out non-item terms
2. **Stat Normalization**: Use `stat_alias` for affix parsing in Phase 2
3. **Ambiguity Resolution**: Handle multiple matches with confidence scoring
4. **Context-Aware Expansion**: Apply different expansions based on thread context
5. **Learning System**: Auto-discover new slang from high-frequency unmatched terms

## Related Requirements

This implementation addresses:

- **Requirement 2.2**: Handle item name variations and slang terms
- **Requirement 8.1**: Check against slang dictionary during parsing
- **Requirement 8.2**: Map slang terms to standard item names
- **Requirement 12.3**: Integrate with existing slang dictionary

## Related Files

- `src/d2lut/normalize/d2jsp_market.py` - Normalization logic with slang integration
- `src/d2lut/storage/sqlite.py` - Database layer with cache initialization
- `src/d2lut/catalog/slang_schema.sql` - Slang table schema
- `scripts/seed_slang_aliases.py` - Slang seeding script
- `tests/test_slang_simple.py` - Unit tests
- `tests/test_integration_e2e.py` - Integration tests
