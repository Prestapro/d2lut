# d2lut

`d2lut` is a local pipeline for Diablo II: Resurrected loot valuation using `d2jsp` forum gold (`fg`) market signals, with a focus on `Ladder Softcore` (`f=271`).

The goal is a practical setup that works while playing:

- Safe mode: generate/update a D2R built-in loot filter profile (hide/show/tiering).
- Advanced mode: local overlay that displays estimated `fg` values over visible item labels/tooltips.

## Important security note

Do not store plaintext `d2jsp` credentials in this repo. If credentials were shared in chat, rotate them.

## Project status

Active local MVP / prototype.

Implemented (repo state):
- Snapshot-based `d2jsp` import pipeline (`forum.php` / `topic.php`) into SQLite
- Heuristic parsing of titles/posts into normalized market observations (FG signals, aliases, commodities)
- Price estimation (`weighted median`) with confidence/category-aware weighting
- Canonical D2R catalog import + alias/slang support
- Overlay-related modules (OCR parsing, item identification, price lookup, stash scan orchestration) with tests

Still incomplete / intentionally stubbed:
- Live `d2jsp` collector in `src/d2lut/collect/d2jsp.py`
- Generic `src/d2lut/pipeline.py` scaffold path (`MarketParser` / collector integration)
- Production-ready in-game overlay capture/render integration (platform-specific runtime wiring)

Important note:
- The primary working entrypoints today are CLI scripts in `scripts/` (especially `build_market_db.py`, `run_d2jsp_snapshot_pipeline.py`, `build_catalog_db.py`), not `src/d2lut/pipeline.py`.

## Structure

- `docs/architecture.md` — system design, constraints, rollout plan (partly historical)
- `scripts/` — main operational CLI entrypoints (market DB import, pipeline orchestration, catalog build, exports)
- `src/d2lut/normalize/d2jsp_market.py` — d2jsp parsing and normalization heuristics
- `src/d2lut/storage/` — SQLite schema + DB access layer
- `src/d2lut/pricing/` — price estimation engine
- `src/d2lut/overlay/` — OCR / identification / lookup / stash scan / overlay orchestration modules
- `tests/` — parser, pricing, overlay, and integration-oriented test suite
- `config/` — example configs
- `data/` — local caches, snapshots, and generated artifacts (repo currently contains sample/dev data)

## Quick Start (Current Workflow)

1. Initialize market DB:

```bash
PYTHONPATH=src python3 scripts/build_market_db.py init-db
```

2. (Optional but recommended) Build the canonical catalog layer:

```bash
PYTHONPATH=src python3 scripts/build_catalog_db.py --db data/cache/d2lut.db build
```

3. Import saved `d2jsp` forum/topic snapshots and compute estimates:

```bash
python3 scripts/run_d2jsp_snapshot_pipeline.py --db data/cache/d2lut.db
```

Notes:
- `PYTHONPATH=src` is required for most `scripts/*` commands that import the package.
- `pyproject.toml` currently does not declare runtime dependencies for OCR/overlay modules; install them manually in your environment if using overlay features.

## Next implementation milestones

1. Replace stub `D2JspCollector` with a supported live/public collector path
2. Consolidate script-first implementations into stable package entrypoints
3. Improve pricing (recency weighting, roll-aware variants, confidence tuning)
4. Harden overlay runtime integration (screen capture/hover detection/render loop)
5. Clean packaging and dependency declaration for reproducible setup

## Process Monitor (CrossOver / Battle.net / D2R)

Quick state check:

```bash
python3 scripts/process_monitor.py --oneshot
```

Continuous monitor (logs only state changes by default):

```bash
python3 scripts/process_monitor.py --interval 2
```

Logs are written to `data/cache/process_monitor.jsonl`.

## Market DB (d2jsp snapshot import MVP)

Cloudflare may block direct `curl` scraping of `d2jsp`. The current MVP supports importing a saved forum HTML page snapshot and extracting thread-title `BIN/SOLD` signals.

Initialize DB:

```bash
PYTHONPATH=src python3 scripts/build_market_db.py init-db
```

Import a saved `f=271` forum page HTML:

```bash
PYTHONPATH=src python3 scripts/build_market_db.py import-forum-html --html forum_271.html --forum-id 271 --market-key d2r_sc_ladder
```

View top estimates:

```bash
PYTHONPATH=src python3 scripts/build_market_db.py dump-top --market-key d2r_sc_ladder --limit 30
```

### Export HTML From Main Chrome (recommended with Cloudflare)

If `curl` gets blocked by Cloudflare, use your normal `Google Chrome` session (where you passed verification / logged in):

```bash
python3 scripts/export_chrome_tab_html.py --print-meta
```

Then import into the DB:

```bash
PYTHONPATH=src python3 scripts/build_market_db.py import-forum-html --html data/raw/d2jsp/forum_271_from_chrome.html --forum-id 271 --market-key d2r_sc_ladder
```

Notes:
- macOS may ask for Automation permission (`Terminal` -> control `Google Chrome`)
- Open the target `d2jsp` forum page in Chrome first (`f=271`)

### Import Topic Pages (more signals than forum list)

Export a loaded `topic.php?t=...` tab from Chrome into an HTML file, then:

```bash
PYTHONPATH=src python3 scripts/build_market_db.py import-topic-html --html data/raw/d2jsp/topic_123.html --forum-id 271 --market-key d2r_sc_ladder
```

If HTML export is inconvenient, you can also import plain copied text:

```bash
PYTHONPATH=src python3 scripts/build_market_db.py import-topic-text --text topic.txt --forum-id 271 --thread-id 123456789 --title "Jah Ber 3x3"
```

### Batch Import (for many snapshots)

Import a directory of `forum.php` page snapshots (supports `--skip-zero-replies` and price filters):

```bash
PYTHONPATH=src python3 scripts/build_market_db.py --db data/cache/d2lut.db import-forum-dir --path data/raw/d2jsp/forum_pages --recursive --pattern '*.html' --forum-id 271 --market-key d2r_sc_ladder --skip-zero-replies --max-fg 500
```

Import a directory of `topic.php` page snapshots (supports `--skip-bump-only-topic`):

```bash
PYTHONPATH=src python3 scripts/build_market_db.py --db data/cache/d2lut.db import-topic-dir --path data/raw/d2jsp/topic_pages --recursive --pattern '*.html' --forum-id 271 --market-key d2r_sc_ladder --max-fg 500 --skip-bump-only-topic
```

Generate topic candidates from imported forum pages and export URLs:

```bash
PYTHONPATH=src python3 scripts/build_market_db.py --db data/cache/d2lut.db dump-topic-candidates --market-key d2r_sc_ladder --forum-id 271 --skip-zero-replies --max-fg 500 --limit 500 --export-urls data/cache/topic_candidates_upto500.txt
```

Optional title filters:

```bash
PYTHONPATH=src python3 scripts/build_market_db.py --db data/cache/d2lut.db dump-topic-candidates --market-key d2r_sc_ladder --forum-id 271 --skip-zero-replies --max-fg 500 --include-terms 'rune,key,torch,anni,facet,charm,lld,ring,amulet' --exclude-terms 'rush,service,grush'
```

### URL Plan (up to page 1000)

Generate main forum pages `1..1000`:

```bash
python3 scripts/generate_forum_url_plan.py --forum-id 271 --pages 1000 > data/raw/d2jsp/forum_271_pages_1_1000.txt
```

Generate priority plan (main + Runes + Charms + Runewords + LLD):

```bash
python3 scripts/generate_forum_url_plan.py --forum-id 271 --pages 1000 --categories 2,3,4,5 --include-main > data/raw/d2jsp/forum_271_priority_pages_1_1000.txt
```

## All-In-One Snapshot Pipeline (recommended)

Runs the local snapshot workflow in one command:

1. import forum page snapshots (`forum.php`) with `--skip-zero-replies`
2. build/export topic candidate URLs
3. import topic page snapshots (`topic.php`) with `--skip-bump-only-topic`
4. print top price estimates

```bash
python3 scripts/run_d2jsp_snapshot_pipeline.py \
  --db data/cache/d2lut.db \
  --forum-pages-dir data/raw/d2jsp/forum_pages \
  --topic-pages-dir data/raw/d2jsp/topic_pages \
  --market-key d2r_sc_ladder \
  --max-fg 500 \
  --candidate-limit 500 \
  --candidate-urls-out data/cache/topic_candidates_focus.txt \
  --top-limit 100
```

Generate page URL plans (`1..1000`) in the same run:

```bash
python3 scripts/run_d2jsp_snapshot_pipeline.py \
  --db data/cache/d2lut.db \
  --forum-pages-dir data/raw/d2jsp/forum_pages \
  --topic-pages-dir data/raw/d2jsp/topic_pages \
  --market-key d2r_sc_ladder \
  --max-fg 500 \
  --generate-url-plans \
  --pages 1000
```

Useful partial modes:

- only rebuild forum data + topic candidate list:
```bash
python3 scripts/run_d2jsp_snapshot_pipeline.py --skip-topic-import --db data/cache/d2lut.db
```

- only import new topic pages and print top:
```bash
python3 scripts/run_d2jsp_snapshot_pipeline.py --skip-forum-import --skip-candidates --db data/cache/d2lut.db
```

## Canonical Catalog DB (Items / Aliases / Affixes)

Build the canonical D2R catalog layer (bases, uniques, sets, aliases, affixes) into the same SQLite DB:

```bash
PYTHONPATH=src python3 scripts/build_catalog_db.py --db data/cache/d2lut.db build
```

What it imports (from `pinkufairy/D2R-Excel`):
- `itemtypes`
- `weapons`, `armor`, `misc`
- `uniqueitems`, `setitems`
- `automagic`, `magicprefix`, `magicsuffix`
- `rareprefix`, `raresuffix`

Quick lookups:

```bash
PYTHONPATH=src python3 scripts/build_catalog_db.py --db data/cache/d2lut.db lookup shako
PYTHONPATH=src python3 scripts/build_catalog_db.py --db data/cache/d2lut.db lookup 'tal belt'
PYTHONPATH=src python3 scripts/build_catalog_db.py --db data/cache/d2lut.db affix-search cruel
PYTHONPATH=src python3 scripts/build_catalog_db.py --db data/cache/d2lut.db type-search warlock
```

Notes:
- `lookup` searches normalized aliases in `catalog_aliases`
- `affix-search` searches imported affix names
- `type-search` searches `itemtypes` (useful for class/item family tokens)
