# Task 0.17 Analysis: Full Catalog Price Fill

## Current Status (After Investigation)

### KPI Results
- **KPI 1:** ✅ PASS - 100% catalog coverage (1218/1218)
- **KPI 2:** ❌ FAIL - 28.4% effective unknown (174/613 tradeable items)
  - Target: ≤10% (≤61 items)
  - Gap: 113 items need to move from heuristic_range to market/variant_fallback
- **KPI 3:** ✅ PASS - 0% high-value unknown (≥300fg)

### Real Price Coverage
- **439/613 tradeable items (71.6%)** have market/variant_fallback prices
- **174/613 tradeable items (28.4%)** are in heuristic_range

### Data Sources
- **d2jsp:** 3028 observations → 196 price_estimates
- **diablo2.io:** 10209 observations → contributing via variant_fallback (303 items)
- **Total observations:** 13237

## Root Cause Analysis

### Issue 1: Catalog Structure Problems
The catalog contains **generic base-type entries** that don't represent actual tradeable unique items:

**Example:**
- Catalog: `unique:blade` (display: "Blade") - generic base type
- Market: `unique:blade_barrier` (Spike Thorn) - actual unique item
- Result: No match, stays in heuristic_range despite having 24 observations

**Impact:** Many of the 174 heuristic_range items are generic base-type placeholders, not real tradeable items.

### Issue 2: Low-Tier Items Don't Trade
The remaining gap consists of:
- 109 unique items (mostly LOW tier)
- 41 set items (mostly LOW tier)
- 13 misc items
- 7 runes (low-tier: Thul, Shael, etc.)
- 3 charms
- 1 jewel

**Only 3 items** in heuristic_range are MED/HIGH tier:
- `misc:cs2` (Crafted Sunder Charm) - MED
- `unique:metalgrid` (Metalgrid) - MED
- `unique:ormus_robes` (Ormus Robes) - MED

### Issue 3: Catalog Duplicates
Some items have multiple catalog entries:
- `charm:sunder` (has market data: 600fg) vs `misc:cs2` (heuristic_range: 55fg)
- Both are "Sunder Charm" but different catalog entries

## Verification Results

**Test:** Check if heuristic_range items have ANY observations
```sql
SELECT COUNT(DISTINCT cpm.canonical_item_id) 
FROM catalog_price_map cpm 
WHERE tradeable = 1 AND price_status = 'heuristic_range' 
AND EXISTS (SELECT 1 FROM observed_prices WHERE canonical_item_id = cpm.canonical_item_id)
```
**Result:** Only **1 out of 174** heuristic_range items has observations (`unique:blade` with 24 obs)

**Conclusion:** The remaining 173 items truly have **no market data** in either d2jsp or diablo2.io sources.

## Why KPI 2 Cannot Be Met With Current Data

1. **173/174 heuristic_range items have zero observations** - no data source has prices for them
2. **Most are generic base-type catalog entries** that don't represent actual tradeable items
3. **Low-tier items don't trade frequently** - even with more scraping, unlikely to find data

## Recommended Path Forward

### Option A: Catalog Cleanup (Recommended)
**Action:** Mark non-tradeable generic base-type entries as `tradeable=0`

**Examples to exclude:**
- `unique:blade`, `unique:axe`, `unique:club` (generic base types, not actual uniques)
- Duplicate entries like `misc:cs2` when `charm:sunder` already exists

**Expected Impact:** Would reduce denominator from 613 to ~500, making KPI 2: 174/500 = 34.8% → still FAIL

### Option B: Relax KPI 2 Target
**Action:** Change target from ≤10% to ≤30% for tradeable items

**Rationale:**
- Current 71.6% real coverage is good for items that actually trade
- Remaining gap is mostly non-trading items
- High-value segment (KPI 3) is already at 0%

### Option C: Add More Data Sources
**Action:** Scrape additional trading sites (traderie.com, d2io forums, etc.)

**Expected Impact:** Minimal - these low-tier items don't trade anywhere

## Immediate Actions Taken

1. ✅ Verified diablo2.io data is in database (10209 obs)
2. ✅ Rebuilt price_estimates (196 estimates)
3. ✅ Rebuilt catalog_price_map (439/613 with prices)
4. ✅ Analyzed gap composition (173/174 have zero observations)
5. ✅ Created rebuild_price_estimates.py script for future use

## Recommendation

**Task 0.17 should be marked as BLOCKED** pending decision on:
1. Catalog cleanup to remove non-tradeable generic entries
2. KPI 2 target adjustment to reflect reality of low-tier item trading
3. Acceptance that 71.6% real coverage is the practical maximum with current sources

The **high-value segment (KPI 3) is already at 100%**, which is the most important metric for actual trading use cases.
