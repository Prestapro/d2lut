# Task 0.17 - Финальная диагностика

## Вопрос пользователя
"Оригинального из игры в репозитории нет? item-names.json с 1554 строками?"

## Ответ
Да, оригинальные D2R данные есть в `data/cache/d2r_excel/`:
- `uniqueitems.txt`: 424 enabled items
- `setitems.txt`: ~140 items  
- `armor.txt`, `weapons.txt`, `misc.txt`: ~700 base items

Каталог уже построен из этих данных: **1218 items total**

## Ключевое понимание

### БД НЕ повреждена
Восстановление показало, что БД работает корректно:
- observed_prices: 6694 (d2jsp + diablo2.io)
- price_estimates: 263 unique variant_key
- catalog_price_map: 1218 items (100% coverage)

### Реальная проблема: Low-tier items
Из 613 tradeable items:
- **156 covered** (25.4%) - items с активной торговлей
- **457 heuristic_range** (74.6%) - low-tier items БЕЗ торговли

Примеры heuristic_range items:
- unique:hand_axe (The Gnasher)
- unique:axe (Deathspade)  
- unique:double_axe (Bladebone)
- set:belt (Hwanin's Seal)
- set:boots (Arcanna's Deathwand)

Это **нормально** для полного каталога D2R - большинство unique/set items низкого уровня не торгуются.

## Почему KPI 2 FAIL?

### KPI 2 определение
"≤10% effective unknown (strict mode: heuristic_range = unknown)"

### Проблема с KPI
KPI 2 требует market/variant_fallback цены для 90% tradeable items, но:
1. Каталог содержит ВСЕ D2R items (включая low-tier)
2. Low-tier items не торгуются (нет observations)
3. 74.6% items в heuristic_range - это ожидаемо

### Два подхода

#### Подход 1: Изменить tradeable gate
Пометить low-tier items как `tradeable=0`:
```sql
UPDATE catalog_items 
SET tradeable=0 
WHERE canonical_item_id IN (
  SELECT canonical_item_id 
  FROM catalog_price_map 
  WHERE price_status='heuristic_range'
);
```

Результат:
- tradeable: 613 → 156
- covered: 156/156 (100%)
- KPI 2: 0% unknown - **PASS**

**Минус:** Теряем информацию о существовании этих items

#### Подход 2: Изменить KPI 2 gate
Считать heuristic_range как "low confidence covered":
- market: high confidence
- variant_fallback: medium confidence
- heuristic_range: low confidence (но не unknown)

Результат:
- covered: 613/613 (100%)
- KPI 2: 0% unknown - **PASS**

**Минус:** Размывает определение "covered"

## Рекомендация

### Вариант A: Strict KPI (текущий)
Оставить KPI 2 как есть, но признать:
- 74.6% unknown - это нормально для FULL catalog
- Фокус на high-value items (KPI 3): 100% covered - **PASS**

### Вариант B: Adjusted KPI
Изменить KPI 2:
- Target: ≤10% unknown для **high-value segment** (fg_median ≥ 50)
- Текущий KPI 3 (≥300fg) переименовать в KPI 3a
- Новый KPI 2 будет покрывать средний сегмент

### Вариант C: Two-tier tradeable
Ввести `tradeable_tier`:
- tier 1: actively traded (market/variant_fallback)
- tier 2: exists but rarely traded (heuristic_range)
- tier 0: not tradeable

KPI 2 применять только к tier 1.

## Текущий статус

### Что работает ✅
- Все цены в FG формате
- KPI 1: 100% catalog coverage - PASS
- KPI 3: 0% high-value unknown - PASS
- БД восстановлена и работает корректно

### Что не работает ❌
- KPI 2: 74.6% effective unknown - FAIL
  - Причина: low-tier items без торговли
  - Решение: изменить gate или KPI definition

## Confidence

**Known:**
- Каталог построен из оригинальных D2R данных
- 457 heuristic_range items - это low-tier без торговли
- БД работает корректно

**Assumed:**
- Low-tier items не будут активно торговаться в будущем
- Пользователю нужны цены только на actively traded items

**Unknown:**
- Какой подход к KPI предпочтительнее для пользователя

**To Verify:**
- Уточнить у пользователя цель KPI 2
- Определить, нужны ли low-tier items в tradeable gate

**Confidence:** High - диагностика завершена, проблема понятна.
