# Item Identification System

The item identification system matches parsed item tooltips to catalog entries using slang resolution, fuzzy matching, and catalog lookups.

## Components

### SlangNormalizer

Resolves slang terms to standard item names using the `slang_aliases` database table.

**Features:**
- Case-insensitive slang matching
- Handles overlapping terms (longest match first)
- Returns confidence scores for matches
- Supports ambiguous slang terms

**Example:**
```python
from d2lut.overlay import SlangNormalizer

normalizer = SlangNormalizer("path/to/database.db")

# Normalize text with slang
text = "Trading Shako for SoJ"
normalized = normalizer.normalize(text)
# Result: "Trading Harlequin Crest for Stone of Jordan"

# Find all slang matches
matches = normalizer.find_slang_matches(text)
for match in matches:
    print(f"{match.term_raw} -> {match.replacement_text} (confidence: {match.confidence})")
```

### ItemIdentifier

Identifies items by matching parsed tooltips to catalog entries.

**Features:**
- Exact matching via catalog aliases
- Slang term resolution
- Fuzzy matching for typos/OCR errors
- Item type filtering
- Returns multiple candidates for ambiguous matches

**Matching Strategy:**
1. Check for parsing errors
2. Try slang resolution (if slang term found with canonical_item_id, return immediately)
3. Try exact match via catalog aliases
4. Try fuzzy matching (if similarity >= threshold)
5. Return no_match if nothing found

**Example:**
```python
from d2lut.overlay import ItemIdentifier, ParsedItem

identifier = ItemIdentifier("path/to/database.db", fuzzy_threshold=0.8)

# Identify an item from parsed data
parsed = ParsedItem(
    raw_text="Harlequin Crest\nShako\nDefense: 141",
    item_name="Harlequin Crest",
    item_type="unique",
    quality="unique",
    confidence=0.95
)

result = identifier.identify(parsed)
print(f"Item: {result.matched_name}")
print(f"ID: {result.canonical_item_id}")
print(f"Match type: {result.match_type}")
print(f"Confidence: {result.confidence}")
```

## Data Structures

### SlangMatch
```python
@dataclass
class SlangMatch:
    term_raw: str                    # Original matched text
    term_norm: str                   # Normalized term
    canonical_item_id: str | None    # Direct catalog ID (if available)
    replacement_text: str            # Standard name to use
    confidence: float                # Match confidence (0.0-1.0)
    match_position: tuple[int, int]  # Start and end indices in text
```

### MatchResult
```python
@dataclass
class MatchResult:
    canonical_item_id: str | None    # Matched catalog item ID
    confidence: float                # Overall confidence (0.0-1.0)
    matched_name: str                # Display name of matched item
    candidates: list[CatalogItem]    # Alternative matches (for ambiguous cases)
    match_type: str                  # exact, fuzzy, slang, partial, no_match, error
    context_used: dict               # Context information used for matching
```

### CatalogItem
```python
@dataclass
class CatalogItem:
    canonical_item_id: str           # Unique item identifier
    display_name: str                # Human-readable name
    category: str                    # Item category (rune, unique, base, etc.)
    quality_class: str               # Quality class (unique, set, base, misc)
    base_code: str | None            # Base item code
    tradeable: bool                  # Whether item is tradeable
    metadata: dict                   # Additional metadata
```

## Database Schema

### slang_aliases Table
```sql
CREATE TABLE slang_aliases (
    id INTEGER PRIMARY KEY,
    term_norm TEXT NOT NULL,              -- Normalized slang term
    term_raw TEXT NOT NULL,               -- Raw slang term
    term_type TEXT NOT NULL,              -- item_alias, base_alias, stat_alias, etc.
    canonical_item_id TEXT NOT NULL,      -- Direct catalog ID (empty for non-item terms)
    replacement_text TEXT NOT NULL,       -- Standard name
    confidence REAL NOT NULL DEFAULT 0.5, -- Confidence score
    source TEXT NOT NULL DEFAULT 'manual',
    notes TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    UNIQUE(term_norm, canonical_item_id, replacement_text)
);
```

### catalog_items Table
```sql
CREATE TABLE catalog_items (
    canonical_item_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL,
    quality_class TEXT NOT NULL,
    base_code TEXT,
    source_table TEXT NOT NULL,
    source_key TEXT,
    tradeable INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT
);
```

### catalog_aliases Table
```sql
CREATE TABLE catalog_aliases (
    id INTEGER PRIMARY KEY,
    alias_norm TEXT NOT NULL,             -- Normalized alias
    alias_raw TEXT NOT NULL,              -- Raw alias
    canonical_item_id TEXT NOT NULL,      -- Catalog item ID
    alias_type TEXT NOT NULL DEFAULT 'name',
    priority INTEGER NOT NULL DEFAULT 100, -- Lower = higher priority
    source TEXT NOT NULL DEFAULT 'catalog_seed',
    UNIQUE(alias_norm, canonical_item_id),
    FOREIGN KEY(canonical_item_id) REFERENCES catalog_items(canonical_item_id)
);
```

## Match Types

- **exact**: Direct match via catalog alias
- **slang**: Matched via slang dictionary
- **fuzzy**: Matched via fuzzy string matching (similarity >= threshold)
- **partial**: Partial match (not currently used)
- **no_match**: No match found
- **error**: Parsing error prevented identification

## Configuration

### Fuzzy Matching Threshold
The `fuzzy_threshold` parameter controls the minimum similarity score for fuzzy matches:
- `0.8` (default): Allows minor typos
- `0.9`: Stricter matching
- `0.7`: More lenient matching

### Cache Management
Both components cache database data in memory for performance:
```python
# Reload cache after database updates
normalizer.reload_cache()
identifier.reload_cache()
```

## Integration with OCR Parser

The item identification system integrates with the OCR parser:

```python
from d2lut.overlay import OCRTooltipParser, ItemIdentifier

# Parse tooltip
parser = OCRTooltipParser(engine="easyocr")
parsed = parser.parse_tooltip(screenshot_bytes, coords)

# Identify item
identifier = ItemIdentifier("database.db")
result = identifier.identify(parsed)

if result.canonical_item_id:
    print(f"Identified: {result.matched_name}")
else:
    print(f"Could not identify item: {parsed.item_name}")
```

## Performance Considerations

- **Memory**: Both components cache database data in memory
  - SlangNormalizer: ~1-10 KB per 100 slang terms
  - ItemIdentifier: ~10-100 KB per 1000 catalog items
  
- **Speed**: 
  - Exact matches: O(1) via dictionary lookup
  - Slang resolution: O(n) where n = number of slang terms
  - Fuzzy matching: O(m) where m = number of catalog aliases
  
- **Optimization**:
  - Slang terms are sorted by length (longest first) for efficient matching
  - Catalog lookups use indexed dictionaries
  - Fuzzy matching only runs if exact match fails

## Testing

Comprehensive test suites are available:
- `tests/test_slang_normalizer.py`: Unit tests for SlangNormalizer
- `tests/test_item_identifier.py`: Unit tests for ItemIdentifier
- `tests/test_item_identification_integration.py`: Integration tests

Run tests:
```bash
pytest tests/test_slang_normalizer.py -v
pytest tests/test_item_identifier.py -v
pytest tests/test_item_identification_integration.py -v
```

## Requirements Validation

This implementation satisfies:
- **Requirement 2.1**: Matches valid tooltips to catalog entries ✓
- **Requirement 2.2**: Handles item name variations and slang terms ✓
- **Requirement 2.3**: Resolves ambiguous items using context ✓
- **Requirement 2.4**: Returns closest matches when no exact match found ✓
- **Requirement 2.5**: Considers item type, quality, and affix patterns ✓
- **Requirement 8.1**: Checks against slang dictionary ✓
- **Requirement 8.2**: Maps slang terms to standard names ✓
- **Requirement 8.3**: Returns all possible matches for ambiguous slang ✓
