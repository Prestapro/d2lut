# Восстановление БД - Краткий отчет

## Что случилось
БД повредилась: вместо 441 covered items (72%) осталось только 79 (12.9%).

## Причина
1. Diablo2.io наблюдения пропали (скрейпер не запускался)
2. D2jsp данные устарели (последнее обновление 27 февраля)
3. price_estimates не пересобирались

## Что сделано

### ✅ Восстановлено
- Импортировано 2721 diablo2.io наблюдений (79 уникальных items)
- Пересобраны price_estimates: 180 → 263 (+83)
- Пересобрана catalog_price_map
- Covered items: 79 → 156 (+77, теперь 25.4%)

### ⏳ В процессе
- Полный импорт diablo2.io (360 items, ~3 часа)
- После завершения: пересборка price_estimates и catalog_price_map

## Текущее состояние

```
observed_prices: 6694
  - d2jsp: 3973 (219 unique items)
  - diablo2.io: 2721 (79 unique items)

price_estimates: 263

catalog_price_map (tradeable=613):
  - market: 141 (23.0%)
  - variant_fallback: 15 (2.4%)
  - heuristic_range: 457 (74.6%)

KPI 2: 74.6% effective unknown (target ≤10%) - FAIL
```

## Следующие шаги

1. Дождаться завершения diablo2.io импорта (~2-3 часа)
2. Пересобрать price_estimates и catalog_price_map
3. Обновить d2jsp снапшот (свежие SOLD сигналы)
4. Финальная проверка покрытия

## Ожидаемый результат
- Covered: ~350-400 items (57-65%)
- KPI 2: ~35-43% effective unknown (улучшение, но все еще FAIL)

## Примечание
Для достижения KPI 2 (≤10%) нужно решить проблему 457 heuristic_range items - это low-tier предметы без активной торговли.
