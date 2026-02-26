# Design Document: d2lut In-Game Pricing/Overlay System

## Overview

This document describes the design for transforming d2lut from a market data pipeline into a practical in-game pricing and overlay tool for Diablo 2 Resurrected. The system will parse in-game item tooltips via OCR, display price information on inventory/stash overlays, show snapshot-refreshed market data, provide crafting profitability analysis, and surface expert-seed / potential-high-value guidance for frequently overlooked magic/rare/LLD/PvP items.

The design builds on existing d2lut infrastructure including:
- SQLite-based market database with forum/topic snapshot ingestion (well beyond the initial ~500/~500 baseline; bulk `topic.php` backfill is an active operational task)
- Catalog database with item definitions, aliases, and affixes
- Pricing engine using weighted median calculations
- Slang dictionary groundwork for item name variations
- Browser diagnostics exports for item and property/combination pricing

### Current Market-Data Operating Notes (Coverage vs Property QA)

- `price_table.html` is the primary browser QA surface for market coverage (variant/item rows).
- `property_price_table.html` is a secondary QA surface for property extraction quality and high-value combo discovery; low row counts there do not imply low overall market coverage.
- Coverage KPIs should be tracked separately from property-combo counts, especially for `>=300fg` observations:
  - observations
  - variants
  - canonical items
  - item-plus-premium-variant rows (e.g., include `monarch`, plus `monarch:4os` if premium >= 50%)
- Large forum corpora produce many commodity and multi-item topics; parser quality and `topic.php` body coverage are both first-order bottlenecks.

## Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              d2lut Overlay System                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐│
│  │   OCR Parser │────>│ Item Identi- │────>│ Price Lookup │────>│  Overlay  ││
│  │              │     │   fier       │     │   Engine     │     │  Layer    ││
│  └──────────────┘     └──────────────┘     └──────────────┘     └───────────┘│
│         │                    │                    │                    │      │
│         ▼                    ▼                    ▼                    ▼      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐│
│  │ Tooltip      │     │ Catalog DB   │     │ Market DB    │     │ Game UI   ││
│  │ Capture      │     │ + Slang Dict │     │ + Pricing    │     │ Overlay   ││
│  └──────────────┘     └──────────────┘     └──────────────┘     └───────────┘│
│                                                                               │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                 │
│  │ Bundle       │     │ Rule Engine  │     │ Demand       │                 │
│  │ Parser v2    │     │ (LLD/Craft/  │     │ Model        │                 │
│  │              │     │  Potential)  │     │              │                 │
│  └──────────────┘     └──────────────┘     └──────────────┘                 │
│                                                                               │
│  ┌──────────────┐     ┌──────────────┐                                       │
│  │ Expert Seed  │     │ Browser      │                                       │
│  │ (Trade Value │     │ Diagnostics  │                                       │
│  │ + Stat Hints)│     │ Tables       │                                       │
│  └──────────────┘     └──────────────┘                                       │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **OCR Pipeline**: Game screenshot → Tooltip extraction → Text parsing → Structured item data
2. **Item Identification**: Parsed data → Slang normalization → Catalog matching → Canonical item ID
3. **Market Ingestion / QA Loop (offline)**: `forum.php/topic.php` snapshots → parser normalization → `observed_prices` / `price_estimates` → browser diagnostics + coverage report
4. **Price Lookup**: Canonical item ID → Market query (snapshot-refreshed) → Weighted median calculation → Price estimate (or seed/heuristic fallback)
5. **Overlay Rendering**: Price data + Game state → UI overlay → Player view

### Integration Points

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Existing d2lut Infrastructure                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Market DB (SQLite)                    Catalog DB (SQLite)                  │
│  - observed_prices                     - catalog_items                      │
│  - price_estimates                     - catalog_aliases                    │
│  - threads                             - catalog_affixes                    │
│  - source_snapshots                    - catalog_bases                      │
│                                                                               │
│  Pricing Engine                        Slang Dictionary                     │
│  - weighted median                     - slang_aliases                      │
│  - confidence scoring                  - slang_candidates                   │
│                                                                               │
│  Expert Seed / Trade Value               Browser Diagnostics                │
│  - qualitative tiers (HIGH..TRASH)      - price_table.html (coverage KPI)   │
│  - stat priorities / seasonality notes   - property_price_table.html (QA)   │
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    New Overlay System Integration                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### OCR Tooltip Parser

**Purpose**: Capture and parse item tooltips from the game screen

**Key Responsibilities**:
- Screen capture at specified coordinates
- Text extraction using OCR
- Tooltip structure parsing
- Error handling for unclear/corrupted tooltips

**Input**: Game screenshot, tooltip coordinates
**Output**: ParsedItem object with all extracted properties

**Interface**:
```python
class OCRTooltipParser:
    def parse_tooltip(self, screenshot: bytes, coords: TooltipCoords) -> ParsedItem:
        """Parse a single tooltip from a screenshot"""
    
    def parse_multiple(self, screenshot: bytes, coords_list: list[TooltipCoords]) -> list[ParsedItem]:
        """Parse multiple tooltips from a screenshot"""
    
    def get_diagnostic_info(self) -> dict:
        """Return diagnostic information for troubleshooting"""
```

**Data Structures**:
```python
@dataclass
class TooltipCoords:
    x: int
    y: int
    width: int
    height: int

@dataclass
class ParsedItem:
    raw_text: str
    item_name: str | None
    item_type: str | None
    quality: str | None  # normal, magic, rare, set, unique
    rarity: str | None
    affixes: list[Affix]
    base_properties: list[Property]
    error: str | None = None
    confidence: float = 0.0
    diagnostic: dict = field(default_factory=dict)
```

**Technical Approach**:
- Use `pytesseract` or `easyocr` for OCR
- Pre-process images with OpenCV for better text extraction
- Use template matching for known tooltip structures
- Implement fallback parsing for ambiguous cases

### Item Identifier

**Purpose**: Match parsed tooltips to catalog entries

**Key Responsibilities**:
- Slang term resolution
- Catalog matching with fuzzy logic
- Ambiguity resolution using context
- Returning closest matches when exact match not found

**Input**: ParsedItem
**Output**: MatchResult with canonical_item_id and confidence

**Interface**:
```python
class ItemIdentifier:
    def identify(self, parsed: ParsedItem) -> MatchResult:
        """Identify an item from parsed data"""
    
    def resolve_slang(self, text: str) -> str:
        """Resolve slang terms to standard names"""
    
    def find_candidates(self, item_name: str, item_type: str) -> list[CatalogItem]:
        """Find potential catalog matches"""
```

**Data Structures**:
```python
@dataclass
class MatchResult:
    canonical_item_id: str | None
    confidence: float
    matched_name: str
    candidates: list[CatalogItem]  # For ambiguous cases
    match_type: str  # exact, fuzzy, slang, partial
    context_used: dict = field(default_factory=dict)
```

### Price Lookup Engine

**Purpose**: Retrieve market prices for identified items

**Key Responsibilities**:
- Query market database for price estimates
- Calculate weighted median and ranges
- Return variant-specific pricing
- Handle insufficient data cases

**Input**: canonical_item_id, variant_key (optional)
**Output**: PriceEstimate with all pricing data

**Interface**:
```python
class PriceLookupEngine:
    def get_price(self, item_id: str, variant: str | None = None) -> PriceEstimate:
        """Get price estimate for an item"""
    
    def get_prices_for_variants(self, item_id: str) -> dict[str, PriceEstimate]:
        """Get prices for all variants of an item"""
    
    def get_fg_listings(self, item_id: str, variant: str | None = None) -> list[FGListing]:
        """Get recent observed FG listings for an item from snapshots"""
```

**Data Structures**:
```python
@dataclass
class PriceEstimate:
    variant_key: str
    estimate_fg: float | None
    range_low_fg: float | None
    range_high_fg: float | None
    confidence: str  # low, medium, high
    sample_count: int
    last_updated: datetime
    demand_score: float | None = None
    observed_velocity: float | None = None  # observations per day
    pricing_source: str = "market"  # market, seed_fallback, hybrid
    trade_value_seed: str | None = None  # HIGH/MED/LOW/NONE/TRASH
    heuristic_low_fg: float | None = None
    heuristic_high_fg: float | None = None
    seed_tags: list[str] = field(default_factory=list)

@dataclass
class FGListing:
    price_fg: float
    listing_type: str  # bin, ask, co
    thread_id: int
    post_id: int
    posted_at: datetime
    is_recent: bool
```

### Inventory Overlay

**Purpose**: Display price information on items in character inventory

**Key Responsibilities**:
- Render price overlays on inventory slots
- Color-code items by value
- Show detailed breakdown on hover
- Handle items with no market data

**Input**: Inventory state, price estimates
**Output**: Rendered overlay on game UI

**Interface**:
```python
class InventoryOverlay:
    def render_inventory(self, inventory: InventoryState) -> OverlayRender:
        """Render price information for an inventory"""
    
    def get_hover_details(self, slot: InventorySlot) -> OverlayDetails:
        """Get detailed information for a hovered item"""
    
    def toggle_display(self, enabled: bool) -> None:
        """Toggle overlay display on/off"""
```

**Data Structures**:
```python
@dataclass
class InventoryState:
    slots: list[InventorySlot]
    character_name: str
    total_value_fg: float | None = None

@dataclass
class InventorySlot:
    slot_id: int
    item_id: str | None
    variant_key: str | None
    parsed_item: ParsedItem | None = None
    price_estimate: PriceEstimate | None = None

@dataclass
class OverlayRender:
    slots: dict[int, SlotOverlay]
    total_value_fg: float | None

@dataclass
class SlotOverlay:
    slot_id: int
    median_price: float | None
    price_range: tuple[float, float] | None
    color: str  # low, medium, high, no_data
    details: OverlayDetails | None = None
```

### Stash Overlay

**Purpose**: Display price information on items in stash tabs

**Key Responsibilities**:
- Render price information across multiple stash tabs
- Calculate total stash value
- Support filtering by price threshold
- Toggle display on/off

**Input**: Stash state, price estimates
**Output**: Rendered overlay on stash UI

**Interface**:
```python
class StashOverlay:
    def render_stash(self, stash: StashState) -> StashOverlayRender:
        """Render price information for a stash"""
    
    def calculate_total_value(self, stash: StashState) -> float:
        """Calculate total stash value"""
    
    def filter_by_price(self, stash: StashState, min_price: float) -> StashState:
        """Filter stash items by minimum price"""
```

**Data Structures**:
```python
@dataclass
class StashState:
    tabs: list[StashTab]
    character_name: str

@dataclass
class StashTab:
    tab_id: int
    tab_name: str
    slots: list[InventorySlot]

@dataclass
class StashOverlayRender:
    tabs: dict[int, TabOverlay]
    total_value_fg: float
    filtered: bool
```

### FG Display

**Purpose**: Show current market listings for similar items

**Key Responsibilities**:
- Display BIN and ask prices separately
- Show market comparison (under/over valued)
- Update when local market snapshots are refreshed
- Handle empty listing states

**Input**: Selected item, market listings
**Output**: FG display overlay

**Interface**:
```python
class FGDisplay:
    def show_listings(self, item_id: str, variant: str | None = None) -> FGDisplayRender:
        """Show current listings for an item"""
    
    def calculate_market_comparison(self, item_id: str, price: float) -> MarketComparison:
        """Calculate how an item compares to market"""
    
    def subscribe_to_updates(self, callback: Callable) -> None:
        """Subscribe to local snapshot refresh updates"""
```

**Data Structures**:
```python
@dataclass
class FGDisplayRender:
    bin_listings: list[FGListing]
    ask_listings: list[FGListing]
    market_comparison: MarketComparison
    has_listings: bool

@dataclass
class MarketComparison:
    item_price: float
    market_median: float
    difference_percent: float
    status: str  # under_valued, over_valued, fair_market
    confidence: str
```

### Category-Aware Parser

**Purpose**: Apply category-specific parsing rules

**Key Responsibilities**:
- Detect item category from parsed data
- Apply category-specific extraction rules
- Extract category-relevant properties
- Handle naming conventions per category

**Input**: ParsedItem
**Output**: Enhanced ParsedItem with category-specific data

**Interface**:
```python
class CategoryAwareParser:
    def parse_with_category(self, parsed: ParsedItem) -> ParsedItem:
        """Parse item with category-specific rules"""
    
    def get_category_rules(self, category: str) -> CategoryRules:
        """Get parsing rules for a category"""
```

**Data Structures**:
```python
@dataclass
class CategoryRules:
    name_patterns: list[Pattern]
    property_extraction: dict[str, Callable]
    affix_limits: dict[str, int]
    special_handling: list[str]  # e.g., "runewords", "set items"
```

### Slang Integration

**Purpose**: Map slang terms to standard item names

**Key Responsibilities**:
- Check parsed names against slang dictionary
- Map slang to standard names
- Handle ambiguous slang terms
- Support extensible slang definitions

**Input**: Text with potential slang
**Output**: Normalized text with slang resolved

**Interface**:
```python
class SlangNormalizer:
    def normalize(self, text: str) -> str:
        """Normalize text by resolving slang"""
    
    def find_slang_matches(self, text: str) -> list[SlangMatch]:
        """Find slang terms in text"""
    
    def get_all_matches(self, slang_term: str) -> list[CanonicalItem]:
        """Get all possible matches for ambiguous slang"""
```

**Data Structures**:
```python
@dataclass
class SlangMatch:
    term_raw: str
    term_norm: str
    canonical_item_id: str | None
    replacement_text: str
    confidence: float
    match_position: tuple[int, int]  # start, end indices
```

### Bundle Parser v2

**Purpose**: Identify and price item bundles

**Key Responsibilities**:
- Detect bundle patterns in parsed items
- Handle rune bundles, set items, and other bundle types
- Return bundle-specific pricing
- Support extensible bundle definitions

**Input**: List of ParsedItem
**Output**: BundleResult with pricing

**Interface**:
```python
class BundleParser:
    def detect_bundles(self, items: list[ParsedItem]) -> BundleResult:
        """Detect bundles in a list of items"""
    
    def get_bundle_price(self, bundle_id: str) -> PriceEstimate:
        """Get price for a bundle"""
    
    def add_bundle_definition(self, bundle: BundleDefinition) -> None:
        """Add a new bundle definition"""
```

**Data Structures**:
```python
@dataclass
class BundleResult:
    bundles: list[DetectedBundle]
    ungrouped_items: list[ParsedItem]

@dataclass
class DetectedBundle:
    bundle_id: str
    bundle_name: str
    items: list[ParsedItem]
    price_estimate: PriceEstimate

@dataclass
class BundleDefinition:
    bundle_id: str
    bundle_name: str
    item_requirements: list[ItemRequirement]
    pricing_strategy: str  # sum, discount, premium
```

### LLD/Craft/Rule Engine

**Purpose**: Identify special item properties and adjust pricing

**Key Responsibilities**:
- Check for LLD (Low Level Dueling) properties
- Check for craft item properties
- Apply affix rules for value adjustments
- Support configurable rule definitions
- Flag potential-high-value overlooked items (magic/rare/LLD/PvP/trophy bases)
- Apply expert seed guidance (qualitative only) when market data is weak or missing

**Input**: ParsedItem
**Output**: AdjustedPriceEstimate

**Interface**:
```python
class RuleEngine:
    def apply_rules(self, item: ParsedItem, base_price: PriceEstimate) -> AdjustedPriceEstimate:
        """Apply all relevant rules to an item"""
    
    def check_lld(self, item: ParsedItem) -> LLDResult:
        """Check if item has LLD properties"""
    
    def check_craft(self, item: ParsedItem) -> CraftResult:
        """Check if item is a craft"""
    
    def get_relevant_rules(self, item: ParsedItem) -> list[Rule]:
        """Get rules applicable to an item"""

    def get_potential_tags(self, item: ParsedItem) -> list[str]:
        """Return overlooked/high-value heuristic tags (e.g., skiller, jmod_family, pvp_circlet)"""

    def get_seed_guidance(self, item: ParsedItem) -> SeedGuidance | None:
        """Return qualitative trade-value seed and stat-priority hints (not a market price)"""
```

**Data Structures**:
```python
@dataclass
class AdjustedPriceEstimate:
    base_price: PriceEstimate
    adjustments: list[PriceAdjustment]
    final_price: PriceEstimate

@dataclass
class PriceAdjustment:
    rule_name: str
    adjustment_type: str  # percentage, flat, multiplier
    value: float
    reason: str

@dataclass
class LLDResult:
    is_lld: bool
    level: int | None
    reason: str
    price_impact: float

@dataclass
class CraftResult:
    is_craft: bool
    craft_type: str | None
    components: list[str] | None
    price_impact: float

@dataclass
class SeedGuidance:
    trade_value_tier: str  # HIGH/MED/LOW/NONE/TRASH
    stat_priority: list[str]
    seasonality_notes: str | None
    source_name: str  # e.g., "expert_seed"
    source_reference: str | None
```

## Data Models

### Database Schema Extensions

#### New Tables for Overlay System

```sql
-- In-game item captures for training and validation
CREATE TABLE IF NOT EXISTS overlay_item_captures (
  id INTEGER PRIMARY KEY,
  captured_at TEXT NOT NULL,
  screenshot_path TEXT,
  tooltip_coords TEXT NOT NULL,  -- JSON array [x, y, width, height]
  raw_ocr_text TEXT,
  parsed_item_json TEXT,  -- JSON of ParsedItem
  matched_item_id TEXT,
  confidence REAL,
  user_verified_item_id TEXT,
  verified_at TEXT,
  FOREIGN KEY(matched_item_id) REFERENCES catalog_items(canonical_item_id)
);

CREATE INDEX IF NOT EXISTS idx_overlay_captures_time ON overlay_item_captures(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_overlay_captures_verified ON overlay_item_captures(user_verified_item_id);

-- Overlay configuration
CREATE TABLE IF NOT EXISTS overlay_config (
  id INTEGER PRIMARY KEY,
  config_key TEXT NOT NULL UNIQUE,
  config_value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Price history for trend analysis
CREATE TABLE IF NOT EXISTS price_history (
  id INTEGER PRIMARY KEY,
  market_key TEXT NOT NULL,
  variant_key TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  median_fg REAL NOT NULL,
  low_fg REAL NOT NULL,
  high_fg REAL NOT NULL,
  sample_count INTEGER NOT NULL,
  demand_score REAL,
  FOREIGN KEY(market_key, variant_key) REFERENCES price_estimates(market_key, variant_key)
);

CREATE INDEX IF NOT EXISTS idx_price_history_time ON price_history(recorded_at DESC, market_key, variant_key);

-- Bundle pricing cache
CREATE TABLE IF NOT EXISTS bundle_pricing (
  bundle_id TEXT PRIMARY KEY,
  bundle_name TEXT NOT NULL,
  item_ids_json TEXT NOT NULL,  -- JSON array of canonical_item_id
  price_estimate_fg REAL NOT NULL,
  last_updated TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'calculated'
);

-- Rule engine rules
CREATE TABLE IF NOT EXISTS pricing_rules (
  rule_id TEXT PRIMARY KEY,
  rule_name TEXT NOT NULL,
  rule_type TEXT NOT NULL,  -- lld, craft, affix, bundle
  condition_json TEXT NOT NULL,  -- JSON condition specification
  adjustment_type TEXT NOT NULL,  -- percentage, flat, multiplier
  adjustment_value REAL NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_pricing_rules_type ON pricing_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_pricing_rules_enabled ON pricing_rules(enabled);

-- Expert seed guidance (qualitative, not direct pricing)
CREATE TABLE IF NOT EXISTS expert_trade_value_seeds (
  seed_id TEXT PRIMARY KEY,
  canonical_item_id TEXT,
  variant_hint TEXT,
  trade_value_tier TEXT NOT NULL,      -- HIGH, MED, LOW, NONE, TRASH
  stat_priority_json TEXT,             -- JSON array of strings
  seasonality_notes TEXT,
  source_name TEXT NOT NULL,           -- e.g., "maxroll", "community_guide"
  source_reference TEXT,
  enabled INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_expert_trade_seeds_item ON expert_trade_value_seeds(canonical_item_id);
CREATE INDEX IF NOT EXISTS idx_expert_trade_seeds_tier ON expert_trade_value_seeds(trade_value_tier);
```

#### Views for Overlay System

```sql
-- Current market status for items
CREATE VIEW IF NOT EXISTS overlay_market_status AS
SELECT 
    pe.market_key,
    pe.variant_key,
    pe.estimate_fg AS median_price,
    pe.range_low_fg,
    pe.range_high_fg,
    pe.confidence,
    pe.sample_count,
    COUNT(DISTINCT op.thread_id) AS active_listings,
    MAX(op.observed_at) AS last_observed,
    CASE 
        WHEN pe.sample_count >= 10 THEN 'stable'
        WHEN pe.sample_count >= 5 THEN 'moderate'
        ELSE 'volatile'
    END AS market_stability
FROM price_estimates pe
LEFT JOIN observed_prices op ON pe.market_key = op.market_key AND pe.variant_key = op.variant_key
GROUP BY pe.market_key, pe.variant_key;

-- Bundle pricing with item details
CREATE VIEW IF NOT EXISTS bundle_pricing_details AS
SELECT 
    bp.bundle_id,
    bp.bundle_name,
    bp.price_estimate_fg,
    bp.last_updated,
    ci.display_name AS item_name,
    ci.category,
    ci.quality_class
FROM bundle_pricing bp
JOIN json_each(bp.item_ids_json) je ON 1=1
JOIN catalog_items ci ON ci.canonical_item_id = je.value;
```

### Indexing Strategy

1. **Overlay Captures**: Index on captured_at for recent captures, user_verified_item_id for validation
2. **Price History**: Composite index on recorded_at, market_key, variant_key for trend analysis
3. **Pricing Rules**: Index on rule_type and enabled for fast rule lookup
4. **Market Status View**: Cached/precomputed for fast overlay queries

## Data Flow Diagrams

### OCR to Parsed Item

```
Game Screenshot
     │
     ├─> [OCR Engine] ──> Raw Text
     │                      │
     │                      ├─> [Structure Parser] ──> ParsedItem
     │                      │                              │
     │                      │                              ├─> [Category Detector] ──> CategoryRules
     │                      │                              │
     │                      │                              └─> [Slang Normalizer] ──> NormalizedText
     │                      │
     │                      └─> [Error Handler] ──> Diagnostic Info
```

### Item Identification Flow

```
ParsedItem
     │
     ├─> [Slang Normalizer] ──> NormalizedName
     │                              │
     │                              ├─> [Catalog Lookup] ──> Candidates
     │                              │                      │
     │                              │                      ├─> [Fuzzy Matcher] ──> MatchScore
     │                              │                      │
     │                              │                      └─> [Context Resolver] ──> BestMatch
     │                              │
     │                              └─> [Ambiguity Handler] ──> MultipleMatches
     │
     └─> [Match Result] ──> CanonicalItemID
```

### Price Lookup Flow

```
CanonicalItemID
     │
     ├─> [Market DB Query] ──> ObservedPrices
     │                              │
     │                              ├─> [Weighted Median] ──> PriceEstimate
     │                              │                      │
     │                              │                      ├─> [Demand Model] ──> DemandScore
     │                              │
     │                              └─> [FG Listings] ──> CurrentListings
     │
     └─> [PriceEstimate] ──> OverlayData
```

## Technical Approach

### OCR Technology Choices

**Primary Choice**: `easyocr` or `pytesseract` with OpenCV preprocessing

**Rationale**:
- EasyOCR: Better accuracy on varied text, GPU acceleration available
- Tesseract: More mature, better documentation, faster on CPU

**Implementation Strategy**:
1. Pre-process images with OpenCV (contrast enhancement, noise reduction)
2. Use region-of-interest extraction for tooltips
3. Apply OCR with confidence filtering
4. Use template matching for known tooltip structures
5. Implement fallback parsing for ambiguous cases

**Performance Targets**:
- OCR processing: ≤500ms per item
- Memory usage: ≤100MB for OCR operations

### Overlay Implementation Strategy

**Platform**: Python with game-specific integration

**Approach**:
1. **Screen Capture**: Use `mss` for fast screen capture
2. **Overlay Rendering**: 
   - Windows: Win32 API or transparent window overlay
   - Linux: X11 overlay
   - macOS: NSWindow with transparent background
3. **Game Integration**: 
   - Coordinate mapping for different resolutions
   - Dynamic tooltip detection
   - Hover interaction handling

**Performance Considerations**:
- Cache frequently accessed data
- Use async operations for screen capture
- Implement frame rate throttling
- Minimize memory allocations during rendering

### Error Handling

**OCR Errors**:
- Low confidence detection with fallback parsing
- Diagnostic information for troubleshooting
- User feedback for unclear tooltips

**Matching Errors**:
- Fuzzy matching with confidence scores
- Multiple candidate return for ambiguous items
- Graceful degradation with partial matches

**Pricing Errors**:
- Insufficient data detection
- Confidence scoring for estimates
- Range-based pricing when median unavailable

### Performance Considerations

**Memory Management**:
- Limit cached data size
- Implement LRU caching for price estimates
- Stream large result sets

**CPU Usage**:
- Async operations for screen capture
- Parallel processing for multiple items
- Lazy loading of detailed information

**Frame Rate**:
- Throttle overlay updates to 30 FPS
- Minimize rendering overhead
- Use hardware acceleration where available

## Testing Strategy

### Unit Tests

**OCR Parser**:
- Test parsing of known tooltip structures
- Test error handling for corrupted tooltips
- Test multi-item parsing

**Item Identifier**:
- Test slang resolution
- Test fuzzy matching
- Test ambiguity handling

**Price Lookup**:
- Test weighted median calculation
- Test variant-specific pricing
- Test insufficient data handling

**Overlay**:
- Test rendering on different resolutions
- Test hover interaction
- Test toggle functionality

### Property-Based Tests

**OCR Parsing**:
- Property 1: Parsing round trip
  *For any* valid tooltip structure, parsing and re-rendering should produce equivalent data
  **Validates: Requirements 1.1-1.6**

- Property 2: Quality classification
  *For any* item, the parsed quality should match the item's actual quality class
  **Validates: Requirements 1.4**

**Item Identification**:
- Property 1: Slang normalization
  *For any* slang term, normalization should produce the standard item name
  **Validates: Requirements 2.2**

- Property 2: Fuzzy matching accuracy
  *For any* item with partial matches, the best match should have higher confidence than alternatives
  **Validates: Requirements 2.4**

**Price Lookup**:
- Property 1: Weighted median correctness
  *For any* set of observed prices, the weighted median should be between the min and max values
  **Validates: Requirements 3.2**

- Property 2: Sample count accuracy
  *For any* price estimate, the sample count should match the number of observed prices used
  **Validates: Requirements 3.4**

**Overlay Rendering**:
- Property 1: Color coding consistency
  *For any* item, the color code should match the value tier (low/medium/high)
  **Validates: Requirements 4.4**

- Property 2: Hover detail completeness
  *For any* hovered item, the hover details should include all available pricing information
  **Validates: Requirements 4.5**

### Integration Tests

**End-to-End Flow**:
- Full OCR → Identification → Pricing → Overlay flow
- Multiple items in inventory/stash
- Snapshot refresh / local market data updates

**Performance Tests**:
- 60 FPS rendering without degradation
- Price lookups under 1 second
- Memory usage under 500MB

## Implementation Phases

### Phase 1: Core Overlay MVP

**Objective**: Basic overlay functionality with existing pricing (hover-first MVP)

**Deliverables**:
- OCR tooltip parser (basic implementation)
- Item identifier with slang support
- Hover tooltip overlay (inventory/stash)
- Optional stash scan mode (single-tab, manual trigger)
- Price lookup integration

**Success Criteria**:
- OCR achieves ≥80% accuracy on common items
- Overlay displays price information with ≤200ms latency
- System handles 30 FPS without performance issues

### Phase 2: Enhanced Parsing

**Objective**: Improve parsing accuracy and add advanced features

**Deliverables**:
- Category-aware parser
- Bundle parser v2
- LLD/Craft/Rule engine (+ potential-high-value overlooked item heuristics)
- FG display with market comparison
- Expert seed (trade value / stat-priority) integration for no-data or weak-data cases
- Browser diagnostics table integration (item-price + property/combination auditing)

**Success Criteria**:
- OCR achieves ≥90% accuracy on common items
- Bundle detection works for ≥90% of common bundle types
- Rule engine correctly identifies ≥95% of LLD/craft items

### Phase 3: Advanced Features

**Objective**: Advanced pricing and market awareness

**Deliverables**:
- Demand model integration
- Price history and trend awareness
- Snapshot refresh automation / faster refresh workflows
- Configurable rule engine

**Success Criteria**:
- Price estimates within 10% of actual sale prices
- Overlay updates after snapshot refresh with ≤1 second local lookup latency
- System handles 60 FPS without performance degradation

## Configuration

### Overlay Configuration

```json
{
  "ocr": {
    "engine": "easyocr",
    "confidence_threshold": 0.7,
    "preprocess": {
      "contrast_enhance": true,
      "denoise": true,
      "resize_factor": 2.0
    }
  },
  "overlay": {
    "enabled": true,
    "color_thresholds": {
      "low": 1000,
      "medium": 10000
    },
    "update_interval_ms": 1000,
    "max_cache_age_seconds": 300
  },
  "pricing": {
    "min_samples": 3,
    "confidence_levels": {
      "low": 0.5,
      "medium": 0.7,
      "high": 0.9
    }
  },
  "rules": {
    "lld_enabled": true,
    "craft_enabled": true,
    "affix_adjustments": true
  }
}
```

## Error Handling

### OCR Errors

- **Low Confidence**: Return diagnostic info, suggest manual verification
- **Corrupted Text**: Fallback parsing with template matching
- **Multiple Items**: Process each independently with separate diagnostics

### Matching Errors

- **No Match**: Return closest candidates with confidence scores
- **Ambiguous**: Return all possible matches with context-based ranking
- **Partial Match**: Return partial match with confidence score

### Pricing Errors

- **Insufficient Data**: Return "insufficient data" indicator
- **High Variance**: Return wide range with low confidence
- **No Recent Data**: Return oldest available with age indicator

## Success Criteria

### Functional Success

- OCR parser achieves ≥95% accuracy on common item types
- Item identification matches correct catalog entry ≥90% of the time
- Price estimates are directionally accurate for common items with sufficient observations (target: within 10-20% for well-traded items)
- Overlay displays price information with low perceived latency (target: ≤200ms for cached lookups in MVP)
- System handles overlay rendering without noticeable gameplay degradation (30 FPS target for MVP; 60 FPS is stretch)

### Data Quality Success

- Market database contains ≥10,000 unique item entries
- Price estimates available for ≥80% of common items
- Slang dictionary covers ≥90% of common item name variations
- Bundle parser correctly identifies ≥95% of common bundle types

### User Experience Success

- Overlay is usable without game performance issues
- Price information is accurate and up-to-date
- System is easy to configure and maintain
- Documentation is comprehensive and accessible

## Constraints and Assumptions

### Technical Constraints

- Must work within D2R's game mechanics and UI limitations
- Must not violate D2R's terms of service
- Must be compatible with existing d2lut infrastructure
- Must handle various screen resolutions and aspect ratios
- Must work with different game settings and UI configurations

### Performance Constraints

- Overlay must not cause noticeable frame rate drops
- Price lookups must complete within 1 second
- OCR processing must complete within 500ms per item
- Memory usage must remain under 500MB

### Data Constraints

- Market data should be refreshable on demand and periodically (daily or better recommended)
- Price confidence should consider observation count and signal quality (BIN/SOLD/CO/ASK), not only sales count
- Slang dictionary must be maintained by community contributions
- Bundle definitions must be updated for new item patterns

### Assumptions

- D2R's UI remains relatively stable across patches
- OCR technology can reliably extract text from game screenshots
- Market data from d2jsp is representative of overall market
- Players have reasonable understanding of item values
- Community will contribute to slang dictionary maintenance

## Out of Scope

- Automated trading or botting functionality
- Integration with third-party marketplaces
- Real-time price updates from external sources
- Character progression tracking
- Quest or achievement tracking
- Multi-account synchronization
- Mobile or desktop companion app
- Historical price charts UI and advanced analytics dashboards
- Price prediction algorithms
