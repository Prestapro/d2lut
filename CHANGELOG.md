# Changelog

All notable changes to this project will be documented in this file.

## [0.3.8] - 2026-03-02

### Fixed
- **Critical**: Fixed typo `"runeword:oice"` → `"runeword:oath"` (was breaking canonical ID lookups)
- **Critical**: Fixed duplicate Phoenix patterns with different case (weapon vs shield now properly separated)
- **Critical**: Removed `hoto` from CTA pattern (was causing HotO posts to be misidentified as CTA)
- **High**: Fixed `"base: elite"` with space → `"base:elite"` (was causing canonical ID mismatch)
- **High**: Fixed `"unique:soul drain"` with space → `"unique:souldrain"` (consistency)
- **High**: Fixed overly broad `\bskin\b` pattern in `skinofvipermagi` (was matching "snakeskin boots")
- **High**: Fixed overly broad `\bss\b` pattern in `stormshield` (was matching random "ss" occurrences)
- **High**: Fixed greedy `e?` patterns in `ebotd`/`edeath` (was matching non-eth versions)
- **Medium**: Fixed `raw_text` containing raw HTML instead of actual text in `live_collector.py`

### Added
- Added `_extract_text_from_html()` helper in live_collector.py for proper text extraction
- Added `runeword:phoenixshield` for Phoenix shield specifically
- Added negative lookahead to `runeword:phoenix` to prevent matching "phoenix shield"

### Changed
- All item keys now follow consistent `category:itemname` format without spaces after colon
- `raw_text` now contains extracted text content instead of HTML boilerplate

## [0.3.7] - 2026-03-02

### Fixed
- **Critical**: Removed hardcoded `_ITEM_LOOKUP` (11 items) - live_collector was "blind" to 99% of items
- **Critical**: Fixed SQL schema compatibility in `build_d2r_filter.py` - now auto-detects and supports multiple DB schemas

### Added
- Expanded `ITEM_PATTERNS` from ~20 to 200+ patterns covering:
  - All runes (Jah to Hel)
  - Uniques: helms, armor, belts, boots, gloves, shields, weapons, jewelry, rings
  - Runewords: armor, weapons, shields, caster items
  - Set items: Tal Rasha, Immortal King, Natalya, Aldur, Trang-Oul, etc.
  - Craft items: blood, caster, hitpower, safety recipes
  - Magic/rare items: jewels, charms, bases
  - Facets (fire/cold/light/poison)
- Helper functions `find_items_in_text()` and `find_best_price_in_text()` in patterns.py
- Multi-schema SQL support: tries 4 different query patterns for backwards compatibility

### Changed
- Both `parser.py` and `live_collector.py` now use shared `ITEM_PATTERNS` from `patterns.py`
- Single source of truth for all item detection - no more duplication
- `build_d2r_filter.py` auto-detects database schema instead of hardcoding queries

## [0.3.6] - 2026-03-02

### Fixed
- **Critical**: `signal_kind` was always `"bin"` in `ObservedPrice` - now properly extracted from price pattern
- **Medium**: Removed unused `beautifulsoup4` dependency from `[scraper]` extras
- **Medium**: Fixed duplicated price patterns between `parser.py` and `live_collector.py`
- **Low**: Removed redundant `observations = []` initialization in `_scan_topic`
- **Low**: Improved exception handling in `_scan_topic` - now catches `TimeoutError` separately

### Added
- New `patterns.py` module with shared `PRICE_PATTERNS` and `SIGNAL_CONFIDENCE` constants
- `signal_kind` field now properly populated with "sold", "bin", "ask", "co", or "fg"

### Changed
- Refactored `models.py` to use `from __future__ import annotations` and `|` union syntax
- Both `parser.py` and `live_collector.py` now use shared patterns from `patterns.py`
- Improved DRY compliance - single source of truth for price patterns

## [0.3.5] - 2026-03-02

### Fixed
- Removed unused `json` import in `build_d2r_filter.py`
- Removed unused `datetime` import in `d2jsp.py`
- Removed unused `loop` variable assignment in `d2jsp.py`

### Added
- Created missing `LICENSE` file (MIT License)

## [0.3.4] - 2026-03-02

### Fixed
- **Critical**: Fixed `sqlite3.Row.get()` AttributeError in `build_d2r_filter.py` - `sqlite3.Row` doesn't have `.get()` method
- **Medium**: Fixed duplicate price observations in `live_collector.py` - `break` only exited inner loop, causing duplicates
- **Medium**: Fixed confidence values mismatch between `parser.py` and `live_collector.py` - now both use sold=0.9, bin=0.8, fg=0.7

### Changed
- Refactored `_parse_topic_content()` to find best price signal once per topic instead of iterating all patterns

## [0.3.3] - 2026-03-02

### Fixed
- **Critical**: Added missing `datetime` import in `normalize/parser.py` (was causing `NameError`)
- **Critical**: Added `__init__.py` to `collect/` and `normalize/` packages (Python package recognition)
- **High**: Created `live_collector.py` with full Playwright implementation (was missing entirely)
- **High**: Fixed double `asyncio.run()` issue - now uses single async context with `async with` pattern
- **Medium**: Added `atexit` handler for `ThreadPoolExecutor` cleanup (was leaking threads)
- **Medium**: Created missing `README.md` (was referenced in pyproject.toml)

### Changed
- Refactored `d2jsp.py` to use context manager pattern for LiveCollector
- Improved error handling in collector lifecycle

## [0.3.2] - 2026-03-02

### Fixed
- **Critical**: Added `permissions: contents: write` to release workflow (was causing 403 error on release creation)

## [0.3.1] - 2026-03-02

### Fixed
- **Critical**: Removed invalid `PytestReturnNotNoneWarning` from pytest config (was causing CI to crash)
- **Critical**: Added missing `scripts/build_d2r_filter.py` entry point (was causing build to fail)

### Added
- Filter builder script with CLI interface (--preset, --db, --output)
- config/base_potential.yml - Crafting and runeword base definitions
- config/perfect_rolls.yml - Perfect stat definitions for valuable items
- config/presets.yml - Filter preset configurations (default, roguecore, minimal, verbose)
- data/templates/item-names-full.json - Complete item name mappings

## [0.3.0] - 2026-03-02

### Fixed
- **Critical**: CI workflow now installs all required dependencies (cv2, PIL, numpy, hypothesis)
- **Critical**: asyncio fallback uses ThreadPoolExecutor instead of broken run_until_complete on running loop
- **Critical**: MarketPost model fields now match actual usage (body_text, datetime timestamp, thread_category_id)
- **Critical**: Parser uses post.body_text instead of non-existent post.body
- **High**: WebSocket handler signature fixed for websockets 15.x compatibility
- **High**: deterministic_id() now uses 64 bits instead of 32 to prevent collisions
- **High**: SQL lookups now properly extract item ID from variant_key
- **Medium**: Exporter now adds section headers for all tiers (GG, HIGH, MID, LOW, TRASH)
- **Medium**: highlight_suffix() now uses config colors instead of hardcoded ÿc9
- **Medium**: Added logging to collector instead of silent error swallowing

### Added
- CI workflow with full dependency installation
- conftest.py with db_path fixture for all tests
- thread_category_id support throughout pipeline

### Changed
- pyproject.toml now includes all optional dependencies properly
- Version synced across all files

## [0.2.9] - 2026-03-01

### Fixed
- asyncio fallback using ThreadPoolExecutor
- WebSocket handler signature for websockets 15.x
- Exporter section headers

## [0.2.8] - 2026-03-01

### Fixed
- SQL variant_key lookup now extracts ID properly
- Added logging to collector

## [0.2.7] - 2026-03-01

### Fixed
- deterministic_id() 64-bit collision fix
- row_factory auto-set in D2RJsonFilterExporter
- runes_mod_data_out initialization
- highlight_suffix() config support
- Module caching for magic_item_pricer

## [0.2.6] - 2026-03-01

### Fixed
- MarketPost: body → body_text
- MarketPost: timestamp as datetime
- Parser: post.body → post.body_text
- thread_category_id propagation
- asyncio.get_event_loop() deprecated warning

## [0.2.5] - 2026-02-28

### Fixed
- CI workflow now requires passing tests before build
- Removed continue-on-error from test step

## [0.2.4] - 2026-02-28

### Fixed
- Use item-names-full.json as default base template (fixes "AN EVIL FORCE" errors)
- Include all config files in release package

## [0.2.3] - 2026-02-28

### Added
- P1: Extended base_potential.yml with craft bases (glv, xtp, etc.)
- P2: Added ÿc3 (blue) color for TZ price format
- P3: Expanded perfect_rolls.yml with Torch, Anni, Facets, Runewords

## [0.2.2] - 2026-02-28

### Fixed
- AN EVIL FORCE error by using item-names-full.json
- MISSING STRING error by including all templates
- PyInstaller yaml bundling

## [0.2.1] - 2026-02-27

### Added
- Stability improvements
- Rune and runeword pricing
- 725 items priced

## [0.2.0] - 2026-02-27

### Added
- Standalone exe build
- Overlay server
- ML classifier
- Smart base detection

## [0.1.6] - 2026-02-27

### Added
- Refresh-on-exit flow

## [0.1.5] - 2026-02-27

### Added
- Monitor-game mode

## [0.1.4] - 2026-02-26

### Added
- Game process detection

## [0.1.3] - 2026-02-26

### Added
- Roguecore preset

## [0.1.2] - 2026-02-26

### Added
- Explain/debug mode

## [0.1.1] - 2026-02-26

### Fixed
- GitHub Actions workflow

## [0.1.0] - 2026-02-26

### Added
- Initial release
