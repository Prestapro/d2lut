# Requirements Document

## Introduction

d2lut is a market data pipeline for Diablo 2 Resurrected that parses d2jsp forum snapshots to extract item pricing data. The system already includes a SQLite-based market database, parsing pipeline, normalization logic, catalog database, and a pricing engine using weighted median calculations. The current implementation has moved beyond the initial ~500/~500 baseline and now supports larger forum/topic snapshot corpora, browser diagnostics exports, and coverage instrumentation for market parsing quality.

The goal of this feature is to transform d2lut into a practical in-game pricing and overlay tool that provides snapshot-refreshed market information directly within the game interface. This includes parsing in-game item tooltips via OCR, displaying price information on inventory/stash overlays, and showing recent observed market data in-game.

## Glossary

- **d2lut**: Diablo 2 Resurrected market data pipeline and pricing system
- **D2R**: Diablo 2 Resurrected
- **d2jsp**: Popular Diablo 2 marketplace forum
- **BIN**: Buy It Now (instant purchase)
- **SOLD**: Completed sale
- **c/o**: Call or Offer (negotiation)
- **ask**: Ask price (seller's desired price)
- **FT**: For Trade (seller listing)
- **ISO**: In Search Of (buyer request)
- **PC**: Price Check
- **LLD**: Low Level Dueling
- **Craft**: Crafted item
- **Affix**: Prefix or suffix on an item
- **Weighted Median**: Pricing method that weights observations by confidence/context
- **OCR**: Optical Character Recognition
- **Overlay**: In-game UI layer displaying market data
- **Trade Value Seed**: Expert qualitative value category (e.g., High/Med/Low/None/TRASH) used as a fallback or priority hint when market data is sparse
- **Potential-High-Value**: Heuristic flag indicating a likely valuable item/property combo even without a reliable market price

## Current State

### Implemented Capabilities

- **Market Database**: SQLite-based storage for parsed market data
- **Parsing Pipeline**: Forum page and topic page parsing
- **Normalization**: BIN/SOLD/c/o/ask price categorization
- **Quality Fixes**: 
  - Tal ambiguity resolution
  - BIN 1 false positive filtering
  - Ral'd false positive filtering
  - Rune bundle detection
- **Context Handling**: FT/ISO/service/PC context awareness
- **Pricing Engine**: Weighted median calculation for price estimates
- **Catalog Database**: Item catalog with definitions
- **Slang Dictionary**: groundwork for item name variations
- **Browser Diagnostics Tables**: Searchable HTML exports for item prices and property combinations
- **Potential Heuristics**: Rules/tags for overlooked high-value items (blue/magic, rare, LLD/PvP, trophy bases)

### Data Volume

- Current local corpus (changes over time during backfill):
  - ~`800+` forum pages (`forum.php` snapshots)
  - ~`900+` topic pages (`topic.php` snapshots; bulk backfill in progress toward full local thread corpus)
- Current parsed market baseline (example recent run, SC ladder):
  - `observed_prices` ~`1100+`
  - `price_estimates` ~`70-80` variant rows
  - `canonical_item_id` coverage still under target and treated as an active KPI
- Working price estimates for items and browser diagnostics exports for market QA

## User Needs and Use Cases

### Primary Use Cases

1. **In-Game Price Lookup**
   - As a player, I want to see current market prices for items in my inventory or stash, so that I can make informed buying/selling decisions

2. **Quick Item Valuation**
   - As a trader, I want to quickly assess item value without leaving the game, so that I can identify profitable opportunities

3. **No-Price Fallback Guidance**
   - As a player, I want a fallback trade tier and/or approximate FG range when exact market pricing is missing, so that I can still decide whether to keep, identify, or trade an item

4. **Market Trend Awareness**
   - As a serious trader, I want to see recent price trends and market activity, so that I can time my transactions optimally

5. **Crafting Profitability**
   - As a crafter, I want to see material costs and output item prices, so that I can determine if crafting is profitable

6. **Stash Management**
   - As a player with multiple characters, I want to see item values across my stash, so that I can prioritize which items to sell

7. **Overlooked Item Detection**
   - As a player, I want the system to flag commonly overlooked but potentially elite items (e.g., blue monarchs/circlets, 6/40 javs, pelts, claws, rare belts/boots/jewels, trophy bases), so that I do not vendor or ignore high-value drops

## Target Vision

### In-Game Overlay System

The system will provide an in-game overlay that:

1. **OCR Tooltip Parser**
   - Captures and parses item tooltips directly from the game screen
   - Handles various item types: weapons, armor, jewels, runes, charms, etc.
   - Extracts all affixes, stats, and item properties
   - Identifies item type, quality, and rarity

2. **Inventory Overlay**
   - Displays price estimates on items in character inventory
   - Shows price range (low/high) and weighted median
   - Indicates market activity level (recent observed activity)
   - Color-codes items by value (low/medium/high)

3. **Stash Overlay**
   - Displays price estimates on items in stash tabs
   - Supports multiple stash tabs and character inventories
   - Allows filtering by price threshold
   - Shows total stash value

4. **In-Game FG (For Sale) Display**
   - Shows recent observed BIN listings for similar items
   - Displays ask prices and BIN prices separately
   - Indicates how current item compares to market (under/over valued)

5. **Trade Value / Expert Seed Fallback**
   - Shows qualitative trade tier (High/Med/Low/None/TRASH) when exact market pricing is unavailable
   - Optionally shows heuristic FG range derived from current market rows and seed tier
   - Clearly distinguishes expert-seed guidance from observed market pricing

6. **Price History**
   - Shows recent price movements
   - Displays observed activity velocity (observations per day)
   - Indicates market stability (consistent vs volatile pricing)

## Requirements

### Requirement 1: OCR Tooltip Parser

**User Story:** As a player, I want the system to parse item tooltips from the game screen, so that I can identify items and look up their market prices.

#### Acceptance Criteria

1. WHEN the OCR parser is activated, THE Parser SHALL capture and parse item tooltips from the game screen
2. THE Parser SHALL extract item name, type, quality, and rarity
3. THE Parser SHALL identify all affixes and their values
4. THE Parser SHALL handle normal, magic, rare, set, and unique items
5. IF the tooltip is unclear or corrupted, THEN THE Parser SHALL return an error with diagnostic information
6. WHERE multiple items are visible, THE Parser SHALL process each item independently

### Requirement 2: Item Identification

**User Story:** As a player, I want the system to identify items from parsed tooltips, so that I can look up their market prices.

#### Acceptance Criteria

1. WHEN a valid tooltip is parsed, THE Identifier SHALL match it to a catalog entry
2. THE Identifier SHALL handle item name variations and slang terms
3. THE Identifier SHALL resolve ambiguous items using context (e.g., "rune" vs specific rune name)
4. IF no exact match is found, THE Identifier SHALL return the closest matching catalog entries
5. WHILE matching, THE Identifier SHALL consider item type, quality, and affix patterns

### Requirement 3: Price Lookup

**User Story:** As a player, I want the system to look up market prices for identified items, so that I can understand their value.

#### Acceptance Criteria

1. WHEN an item is identified, THE Pricing Engine SHALL return snapshot-refreshed market prices
2. THE Pricing Engine SHALL provide weighted median price
3. THE Pricing Engine SHALL provide price range (low/high)
4. THE Pricing Engine SHALL provide recent observed activity volume (and sale counts where available)
5. WHERE multiple item variations exist, THE Pricing Engine SHALL return prices for each variation
6. IF insufficient market data exists, THEN THE Pricing Engine SHALL indicate "insufficient data"
7. IF no reliable market estimate exists, THEN THE Pricing Engine SHALL return a fallback trade value tier and MAY return a heuristic FG range
8. THE Pricing Engine SHALL distinguish market-derived prices from heuristic/seed-derived estimates in its output metadata

### Requirement 4: Inventory Overlay Display

**User Story:** As a player, I want price information displayed on items in my inventory, so that I can see values without manual lookup.

#### Acceptance Criteria

1. WHEN an inventory is displayed, THE Overlay SHALL render price information on items
2. THE Overlay SHALL display weighted median price
3. THE Overlay SHALL display price range (low/high)
4. THE Overlay SHALL color-code items by value (low/medium/high)
5. WHILE hovering over an item, THE Overlay SHALL show detailed price breakdown
6. WHERE an item has no market data, THE Overlay SHALL indicate "no data"

### Requirement 5: Stash Overlay Display

**User Story:** As a player, I want price information displayed on items in my stash, so that I can assess my total wealth.

#### Acceptance Criteria

1. WHEN a stash tab is displayed, THE Overlay SHALL render price information on items
2. THE Overlay SHALL support multiple stash tabs
3. THE Overlay SHALL calculate and display total stash value
4. WHERE stash tabs are filtered, THE Overlay SHALL update displayed prices accordingly
5. THE Overlay SHALL allow toggling price display on/off

### Requirement 6: In-Game FG Display

**User Story:** As a trader, I want to see current market listings for similar items, so that I can price my items competitively.

#### Acceptance Criteria

1. WHEN an item is selected, THE FG Display SHALL show recent observed BIN listings
2. THE FG Display SHALL show ask prices separately from BIN prices
3. THE FG Display SHALL indicate how current item compares to market (under/over valued)
4. WHERE no listings exist, THE FG Display SHALL indicate "no active listings"
5. THE FG Display SHALL update when local market snapshots are refreshed
6. IF no market price exists, THEN THE FG Display SHALL show Trade Value Seed tier and/or heuristic FG range (clearly marked as approximate)

### Requirement 7: Category-Aware Parsing

**User Story:** As a developer, I want the parser to handle different item categories appropriately, so that parsing accuracy is maximized.

#### Acceptance Criteria

1. WHEN parsing items, THE Parser SHALL apply category-specific rules
2. THE Parser SHALL handle weapons, armor, jewels, runes, charms, and other item types
3. FOR each category, THE Parser SHALL extract category-relevant properties
4. WHERE item categories have naming conventions, THE Parser SHALL apply those conventions

### Requirement 8: Slang Integration

**User Story:** As a player, I want the system to understand item slang terms, so that I can identify items with non-standard names.

#### Acceptance Criteria

1. WHEN parsing item names, THE Normalizer SHALL check against slang dictionary
2. THE Normalizer SHALL map slang terms to standard item names
3. WHERE slang terms are ambiguous, THE Normalizer SHALL return all possible matches
4. THE Slang Dictionary SHALL be extensible without code changes

### Requirement 9: Bundle Parser

**User Story:** As a player, I want the system to recognize item bundles, so that I can price them correctly.

#### Acceptance Criteria

1. WHEN multiple items are parsed together, THE Bundle Parser SHALL identify bundle patterns
2. THE Bundle Parser SHALL handle rune bundles, set items, and other bundle types
3. WHERE bundles are identified, THE Bundle Parser SHALL return bundle-specific pricing
4. THE Bundle Parser SHALL support extensible bundle definitions

### Requirement 10: LLD/Craft/Rule Engine

**User Story:** As a player, I want the system to identify special item properties, so that I can price them appropriately.

#### Acceptance Criteria

1. WHEN an item is parsed, THE Rule Engine SHALL check for LLD properties
2. THE Rule Engine SHALL check for craft item properties
3. THE Rule Engine SHALL apply affix rules for value adjustments
4. WHERE rules apply, THE Rule Engine SHALL adjust price estimates accordingly
5. THE Rule Engine SHALL be configurable without code changes
6. THE Rule Engine SHALL support potential-high-value flags for overlooked item categories (e.g., magic circlets/monarchs, jewels, pelts, claws, rare belts/boots, trophy bases)
7. THE Rule Engine SHALL support expert seed rules (community guides/lists) as qualitative signals without treating them as direct market prices

### Requirement 11: Weight Tuning and Demand Model

**User Story:** As a trader, I want price estimates to reflect market demand, so that I can make better trading decisions.

#### Acceptance Criteria

1. WHEN pricing items, THE Pricing Engine SHALL consider demand vs sale ratios
2. THE Pricing Engine SHALL adjust weights based on market activity
3. WHERE demand is high, THE Pricing Engine SHALL prioritize recent sales
4. WHERE demand is low, THE Pricing Engine SHALL use broader time windows
5. THE Pricing Engine SHALL provide demand/sale metrics alongside prices

### Requirement 12: Expert Seed / Trade Value Integration

**User Story:** As a player, I want expert trade-value guidance and stat-priority hints when market data is sparse, so that I can avoid missing or mispricing valuable items.

#### Acceptance Criteria

1. THE System SHALL support qualitative seed tiers (e.g., HIGH/MED/LOW/NONE/TRASH) for catalog items and/or item families
2. THE System SHALL support stat-priority hints for seeded items (e.g., All Resistances, ED, sockets, life rolls, class-value dependency)
3. WHERE seed guidance is shown, THE UI SHALL indicate it is expert-seed guidance and not an observed market price
4. THE seed definitions SHALL support seasonality notes (e.g., early ladder vs later ladder)
5. THE seed layer SHALL be extensible without changing core pricing logic

### Requirement 13: Browser Diagnostics Tables

**User Story:** As a developer/trader, I want searchable browser tables for item prices and property combinations, so that I can audit market data and tune parsing/rules quickly.

#### Acceptance Criteria

1. THE System SHALL export a searchable item price table HTML from local market snapshots
2. THE item price table SHALL support sorting/filtering by FG, confidence, and seed tier
3. THE item price table SHALL support seed-only rows with heuristic FG fallback ranges when configured
4. THE System SHALL export a searchable property/combination price table HTML from local observations
5. THE property table SHALL support potential-high-value filtering and display potential tags
6. THE property table SHALL support overlooked magic/rare/LLD/PvP categories (e.g., skillers, jewels, circlets, facets, charms, trophy bases) via parser/rule coverage
7. THE item price table SHALL be treated as the primary market coverage audit surface (variant/item coverage), and the property table SHALL be treated as a secondary parser-QA surface (property extraction coverage)
8. THE System SHALL provide a coverage report for price observations (e.g., `>=300fg`) including counts for observations, variants, canonical items, and item-plus-premium-variant rows

### Requirement 14: Data Pipeline Integration

**User Story:** As a developer, I want the overlay system to integrate with the existing data pipeline, so that I can leverage existing infrastructure.

#### Acceptance Criteria

1. THE System SHALL use the existing SQLite market database
2. THE System SHALL use the existing catalog database
3. THE System SHALL use the existing slang dictionary
4. THE System SHALL integrate with the existing pricing engine
5. WHERE new data is needed, THE System SHALL extend the pipeline appropriately
6. THE market ingestion pipeline SHALL support large-scale `topic.php` backfills (with resumable/skip-existing behavior) to reduce forum/topic coverage gaps during parser tuning

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
- Expert seed tiers and stat-priority hints must be maintained as qualitative guidance, not authoritative prices

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
- Treating expert guides/community lists as direct price sources (they are qualitative seed signals only)
- Character progression tracking
- Quest or achievement tracking
- Multi-account synchronization
- Mobile or desktop companion app
- Historical price charts UI and advanced analytics dashboards
- Price prediction algorithms
