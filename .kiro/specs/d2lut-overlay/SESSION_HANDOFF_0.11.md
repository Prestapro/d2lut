# Session Handoff (Phase 0.11)

## SPEC

Минимальный handoff для новой сессии по состоянию `tasks.md` (Phase 0, пункты `0.10` / `0.11`).

## Known

- `tasks.md` синхронизирован:
  - `0.10` (`liquid singleton candidate filtering`) = `[x]`
  - `0.11` (`One-shot data refresh before uncapped reparse`) = `[x]` for the current planned scope
- Hidden default `--max-fg 500` cap в all-in-one pipeline уже снят в коде.
- Category forum snapshots (`c=2/3/4/5`) now collected in `data/raw/d2jsp/forum_pages`:
  - `c2=100`, `c3=100`, `c4=100`, `c5=9` valid pages (`c5` ran out of valid pages after ~`o=200`)
- Focused topic candidate corpus for `Charms/LLD + high-value` is fully downloaded:
  - `data/cache/topic_candidates_charms_lld.txt` => `184/184` downloaded (`unseen=0`)
- Uncapped reparse after category forum refresh + focused topic refresh (по текущей БД `data/cache/d2lut.db`), then parser-QA rerun:
  - `observed_prices` count = `1039`
  - current observed `max(price_fg)` = `5500.0` (no hard cap; max depends on collected corpus)
  - `count(price_fg > 500)` = `407`
  - raw outlier `unique:hellfire_torch c/o 44444` was removed by parser heuristics (no rows `price_fg >= 10000`)
- HTML-таблицы пересобраны и присутствуют:
  - `data/cache/price_table.html`
  - `data/cache/property_price_table.html`
  - latest export counts: `price_table rows=101 (seed_only=23)`, `property_rows=53 (from_observations=843)`
- Подготовлен focused candidate URL list для следующего topic scrape:
  - `data/cache/topic_candidates_charms_lld.txt` (`184` URL, fresh-first + liquid-singleton dedupe)
- Focused candidate list разбит на scrape batches (после автосбора все батчи закрыты, `unseen=0`):
  - `data/cache/topic_candidates_charms_lld_batch_unseen.txt` (`0`)
  - `data/cache/topic_candidates_charms_lld_batch_charms.txt` (`0`)
  - `data/cache/topic_candidates_charms_lld_batch_lld.txt` (`0`)
  - `data/cache/topic_candidates_charms_lld_batch_mixed.txt` (`0`)
  - `data/cache/topic_candidates_charms_lld_batch_other.txt` (`0`)
- `scripts/fetch_d2jsp_forum_pages.py` и `scripts/fetch_d2jsp_forum_pages_cdp.py` теперь рано останавливают короткую категорию после первого `invalid page` (убирает длинные серии фейлов на `c=5`)
- Оба forum fetcher'а поддерживают category-specific page limits:
  - флаг `--category-page-limits`, пример: `--category-page-limits '4:10,3:100,2:100,5:20'`
  - практическая эвристика: `c=4` (runes/keys) обычно достаточно `5-10` страниц для top-rune сигналов
- Added automatic topic page collector (Playwright, URL-file based):
  - `scripts/fetch_d2jsp_topic_pages.py`
- Added helper to split topic scrape batches:
  - `scripts/prepare_topic_scrape_batches.py`

## Assumed

- Следующая сессия, вероятно, будет идти в parser QA / quality tuning (а не data collection `0.11`).
- Приоритетный риск сместился с конкретного `44444` кейса на общую проверку extreme `co/offer` noise в replies.

## Unknown

- Будет ли добираться корпус `topic.php` перед следующим reparse, или сначала только `forum.php` category pages.

## To Verify

- Проверить полезность обновлённых browser tables после расширения корпуса.
- Мониторить новые экстремальные `co/offer` значения без `fg` (шум vs реальные high-end asks).

## Confidence

High (статусы и DB-метрики перепроверены локально SQL/файлами в этой сессии).

## Current Commands (Baseline)

Uncapped all-in-one reparse (candidate dedupe + fresh-first):

```bash
python3 scripts/run_d2jsp_snapshot_pipeline.py \
  --db data/cache/d2lut.db \
  --forum-pages-dir data/raw/d2jsp/forum_pages \
  --topic-pages-dir data/raw/d2jsp/topic_pages \
  --market-key d2r_sc_ladder \
  --clear-market \
  --candidate-limit 500 \
  --candidate-skip-liquid-singletons \
  --candidate-singleton-recent-hours 24 \
  --candidate-singleton-min-recent-observations 5 \
  --candidate-urls-out data/cache/topic_candidates_focus.txt \
  --top-limit 100
```

Quick DB verification:

```bash
sqlite3 data/cache/d2lut.db "select count(*), max(price_fg), sum(case when price_fg>500 then 1 else 0 end) from observed_prices where market_key='d2r_sc_ladder';"
```

Re-export tables:

```bash
python3 scripts/export_price_table_html.py --db data/cache/d2lut.db --market-key d2r_sc_ladder --out data/cache/price_table.html
python3 scripts/export_property_price_table_html.py --db data/cache/d2lut.db --market-key d2r_sc_ladder --min-fg 50 --out data/cache/property_price_table.html
```

## Next Step (Most Useful)

1. QA parser на новых noisy replies (extreme `co/offer` values без `fg`) и следить за false positives.
2. При необходимости расширить unit tests вокруг `ask/co` extraction.
3. После следующего data refresh повторить uncapped pipeline + table exports.
