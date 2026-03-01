# D2LUT Architecture (D2R + d2jsp fg)

## Objective

Show item economic value (in `fg`) during D2R gameplay, prioritizing `Ladder Softcore` market (`d2jsp forum f=271`).

## Key constraint (important)

The official D2R built-in loot filter is suitable for visibility/tiering, but not for live dynamic price suffixes per item roll. Exact `fg` values "in the label" for arbitrary rolled items require a runtime component (overlay) and a price model.

## Recommended architecture (hybrid)

### 1) Market Data Pipeline (offline/background)

Purpose: build a continuously refreshed local price index in `fg`.

Stages:

1. `collect`
   - Source: public threads/posts from `d2jsp` target forum (`f=271`)
   - Inputs: title, body preview, timestamp, author, URL
   - Output: raw snapshots (`jsonl`)

2. `normalize`
   - Parse item mentions and sale intents (`ISO`, `BIN`, sold markers, ranges)
   - Map aliases to canonical D2R item IDs / categories
   - Extract roll-sensitive attributes when present (e.g., ED%, FCR, sockets)

3. `pricing`
   - Build estimators by item type:
     - fixed-unique/set/rune/base items: direct median/trimmed mean
     - rolled items (rare/magic/jewel/charm): rule-based + comps
   - Weight by recency and listing confidence
   - Store: `price_index.json`

4. `export`
   - Export tier metadata for in-game use:
     - D2R filter tier buckets (`S/A/B/C`)
     - overlay lookup tables

### 2) In-Game Presentation (two modes)

#### Mode A: Safe / supported (official built-in loot filter)

- Use generated rules to hide junk and highlight value candidates.
- Represents value as tiers, not exact `fg` suffixes.
- Lowest risk, easiest maintenance.

#### Mode B: Advanced overlay (recommended for exact fg estimates)

- External desktop overlay over D2R window.
- Reads visible item labels/tooltips using OCR (MVP).
- Looks up normalized item in local `price_index`.
- Renders compact tag, e.g. `[~120 fg]`.

Notes:
- OCR avoids memory reading and binary injection.
- Exact price for unidentified/hidden rolls is impossible from ground label alone.
- For roll-dependent items, overlay should display `range/confidence`, not fake precision.

## Why not "only a loot filter"

Because value depends on:

- ladder mode (`Softcore` vs `Hardcore`)
- recency (market moves fast)
- exact rolls/sockets/eth/sup
- demand by build meta

A static filter can classify candidates but cannot truthfully append live `fg` per item roll.

## Data model (minimal)

### `MarketPost`

- `source`: `d2jsp`
- `forum_id`: `271`
- `thread_id`
- `post_id`
- `timestamp`
- `title`
- `body_text`
- `author`
- `url`

### `ObservedPrice`

- `canonical_item_id`
- `variant_key` (e.g. `shako`, `grief:eth=0:base=pb`)
- `ask_fg`
- `bin_fg`
- `sold_fg` (optional, higher confidence)
- `currency`: `fg`
- `source_post_ref`
- `confidence`

### `PriceEstimate`

- `variant_key`
- `estimate_fg`
- `range_low_fg`
- `range_high_fg`
- `confidence` (`high|medium|low`)
- `sample_count`
- `last_updated`

## Item classes and strategy

### Strong candidates for MVP (good signal quality)

- Runes
- Keys / essences / tokens / boss sets
- Popular uniques (Shako, Griffon's, etc.)
- Common tradable bases (eth/non-eth, sockets, elite bases)
- Common runeword bases
- Torches / Anni (range-based, roll-aware)

### Hard classes (phase 2+)

- Rare rings/amulets
- Magic jewels / blue monarchs / class-specific rares
- Crafted items
- Rare circlets

These need richer parsing and often image/manual input to price accurately.

## Operational design

### Update cadence

- Collector: every 5-15 min
- Pricing rebuild: every 5 min (incremental)
- Overlay cache reload: auto-reload on file change

### Local storage

- `data/raw/*.jsonl`
- `data/processed/*.jsonl`
- `data/cache/price_index.json`

### Failure behavior

- If no fresh data: show last known estimate with stale badge
- If item parse fails: show `unpriced`
- If low confidence: show range only

## Security / compliance

- Prefer public pages; do not hardcode credentials.
- If authenticated access is later required, use local env vars and OS keychain.
- Keep a no-login mode as default.
- Avoid memory reading/injection in MVP overlay.

## Rollout plan (smallest-first)

### Phase 0 (current scaffold)

- Repo skeleton
- Config and interfaces
- Architecture documented

### Phase 1 (MVP usable)

- Public collector for forum `271`
- Parser for obvious `BIN x fg` lines
- Price index for runes/keys/uniques/bases
- D2R filter tier export

### Phase 2 (in-game fg overlay)

- OCR label capture
- Normalization + lookup
- Overlay rendering and hotkey toggle

### Phase 3 (better pricing)

- Recency-weighted comps
- Roll-specific rules
- Confidence scoring and feedback loop

## Conversion note (USD -> fg)

User-provided `buyGold` samples show a non-linear rate (bulk discount). Treat this as a reference metric only; item pricing should remain native in `fg`.

