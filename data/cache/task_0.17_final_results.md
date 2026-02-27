# Task 0.17 Final Results

## Выполненная работа

### 1. Исправлен критический баг в build_market_db.py
**Проблема:** signal_kind от diablo2.io был в uppercase ('SOLD'), а код проверял lowercase ('sold')
**Решение:** Добавлена нормализация `.lower()` в `row_to_observed()`
**Результат:** diablo2.io observations теперь создают price_estimates

### 2. Исправлен mapping в scrape_diablo2io_prices.py
**Проблема:** Metalgrid и Ormus Robes мапились на неправильные canonical IDs
- Metalgrid: `unique:amulet` → `unique:metalgrid` ✅
- Ormus Robes: `unique:dusk_shroud` → `unique:ormus_robes` ✅

### 3. Пересобраны price estimates и catalog_price_map
```bash
PYTHONPATH=src python3 scripts/rebuild_price_estimates.py --db data/cache/d2lut.db
PYTHONPATH=src python3 scripts/build_catalog_price_map.py --db data/cache/d2lut.db
```

## Финальные метрики

### KPI Results
- **KPI 1:** ✅ PASS - 100% catalog coverage (1218/1218)
- **KPI 2:** ❌ FAIL - 28.1% effective unknown (172/613 tradeable items)
  - Target: ≤10% (≤61 items)
  - Gap: 111 items need to move from heuristic_range to market/variant_fallback
- **KPI 3:** ✅ PASS - 0% high-value unknown (≥300fg)

### Coverage Improvements
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| market | 113 (18.4%) | 415 (67.7%) | **+302 items** |
| variant_fallback | 326 (53.2%) | 26 (4.2%) | -300 items |
| heuristic_range | 174 (28.4%) | 172 (28.1%) | -2 items |
| Real coverage | 439 (71.6%) | 441 (72.0%) | **+2 items** |
| price_estimates | 196 | 517 | **+321 estimates** |

### Data Sources
- **d2jsp:** 3028 observations → 196 estimates (primary source)
- **diablo2.io:** 10359 observations → 321 estimates (fallback, rune→FG conversion)
- **Total:** 13387 observations → 517 estimates

## Анализ оставшегося gap'а

### Состав 172 items в heuristic_range:
- 107 unique items (mostly generic base types like `unique:blade`, `unique:cap`)
- 41 set items (mostly generic base types like `set:belt`, `set:buckler`)
- 13 misc items (uber materials, keys)
- 7 runes (low-tier: Dol, Eld, Eth, Ith, Nef, Ort, Tir)
- 3 charms (generic bases: Small/Large/Grand Charm)
- 1 jewel (Colossal Jewel)

### Проверка observations:
```sql
SELECT COUNT(DISTINCT cpm.canonical_item_id) 
FROM catalog_price_map cpm 
WHERE tradeable = 1 AND price_status = 'heuristic_range' 
AND EXISTS (SELECT 1 FROM observed_prices WHERE canonical_item_id = cpm.canonical_item_id)
```
**Результат:** 1 из 172 items имеет observations (unique:blade с 24 obs, но не создан estimate из-за других причин)

### Root Cause
**171/172 items (99.4%) имеют НОЛЬ observations** в любом источнике (d2jsp или diablo2.io)

Это означает что:
1. Большинство — это **generic base-type catalog entries** (не реальные tradeable items)
2. Оставшиеся — **low-tier items** которые просто не торгуются на рынке

## Рекомендации

### Option A: Catalog Cleanup (Recommended)
Пометить generic base-type entries как `tradeable=0`:
- `unique:blade`, `unique:cap`, `unique:armor` и т.д.
- `set:belt`, `set:buckler`, `set:cap` и т.д.

**Expected Impact:** Denominator уменьшится с 613 до ~500, KPI 2: 172/500 = 34.4% → still FAIL

### Option B: Relax KPI 2 Target
Изменить target с ≤10% на ≤30%

**Rationale:**
- Текущее покрытие 72.0% хорошее для items которые реально торгуются
- Оставшийся gap — это non-trading items
- High-value segment (KPI 3) уже на 100%

### Option C: Accept Current State
Признать что 72.0% real coverage — это **практический максимум** для текущих источников данных

## Критический успех

**High-value segment (KPI 3) на 100% coverage** — это самая важная метрика для реального использования в трейдинге.

Все items ≥300fg имеют реальные market prices в FG формате.
