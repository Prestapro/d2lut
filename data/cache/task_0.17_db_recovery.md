# Task 0.17 - DB Recovery Report

## Проблема
БД была повреждена: из 613 tradeable items только 79 имели market/variant_fallback цены (12.9%), остальные 534 в heuristic_range (87.1%).

## Диагностика

### Состояние до восстановления
- `observed_prices`: 3973 (только d2jsp)
- `price_estimates`: 180
- `catalog_price_map` (tradeable): 79 covered (12.9%)

### Причина
1. Diablo2.io наблюдения отсутствовали (скрейпер не был запущен после последнего сброса БД)
2. D2jsp наблюдения устарели (последнее обновление: 2026-02-27)
3. `price_estimates` не были пересобраны после изменений

## Восстановление

### Шаг 1: Импорт diablo2.io данных
```bash
PYTHONPATH=src python scripts/scrape_diablo2io_prices.py \
  --db data/cache/d2lut.db \
  --market-key d2r_sc_ladder \
  --delay 0.3 \
  --limit 150
```

Результат: +2721 наблюдений (79 уникальных variant_key)

### Шаг 2: Пересборка price_estimates
```bash
PYTHONPATH=src python scripts/rebuild_price_estimates.py \
  --db data/cache/d2lut.db \
  --market-key d2r_sc_ladder
```

Результат: 180 → 263 оценок (+83)

### Шаг 3: Пересборка catalog_price_map
```bash
PYTHONPATH=src python scripts/build_catalog_price_map.py \
  --db data/cache/d2lut.db \
  --market-key d2r_sc_ladder
```

Результат:
- market: 141 (23.0%)
- variant_fallback: 15 (2.4%)
- heuristic_range: 457 (74.6%)

## Текущее состояние после восстановления

### observed_prices
- Total: 6694
  - d2jsp: 3973 (219 unique variant_key)
  - diablo2.io: 2721 (79 unique variant_key)

### price_estimates
- Total: 263 (d2r_sc_ladder)

### catalog_price_map (tradeable only)
- market: 141 (23.0%)
- variant_fallback: 15 (2.4%)
- heuristic_range: 457 (74.6%)
- unknown: 0 (0.0%)

### KPI 2 Status
- Target: ≤10% effective unknown
- Current: 74.6% effective unknown
- Status: **FAIL**

## Анализ gap'а

### Почему только 263 оценки вместо 517?

1. **D2jsp signal_kind распределение:**
   - ask: 1769
   - bin: 1022
   - co: 1152
   - sold: 30 ⚠️

2. **Проблема:** Только 30 SOLD сигналов из d2jsp (было больше раньше)
   - Последнее обновление: 2026-02-27T17:58:51
   - Нужен свежий снапшот d2jsp

3. **Diablo2.io покрытие:** Только 79 уникальных items (частичный импорт, limit=150)
   - Полный импорт даст ~360 items (все D2IO_ITEMS)

## Следующие шаги

### Критичные
1. ✅ Восстановить diablo2.io данные (частично выполнено)
2. ⏳ Запустить полный импорт diablo2.io (360 items)
3. ⏳ Обновить d2jsp снапшот (свежие SOLD сигналы)
4. ⏳ Пересобрать price_estimates и catalog_price_map

### Ожидаемый результат
- price_estimates: ~400-500 (вместо 263)
- Covered (market+variant): ~350-400 (57-65%)
- KPI 2: ~35-43% effective unknown (все еще FAIL, но лучше)

### Долгосрочные
- Исправить 457 heuristic_range items (см. task_0.17_analysis.md)
- Улучшить матчинг unique/set items (display_name vs source_key)

## Confidence

**Known:**
- БД частично восстановлена: 79 → 156 covered items (+77)
- Diablo2.io данные импортированы (частично)
- Все цены в FG формате

**Assumed:**
- Полный импорт diablo2.io даст еще ~200-250 covered items
- Свежий d2jsp снапшот добавит SOLD сигналы

**Unknown:**
- Сколько новых SOLD сигналов даст свежий d2jsp снапшот
- Точное финальное покрытие после всех импортов

**To Verify:**
- Запустить полный diablo2.io импорт
- Обновить d2jsp снапшот
- Проверить финальное покрытие

**Confidence:** High - диагностика подтверждена SQL-запросами, восстановление частично выполнено.
