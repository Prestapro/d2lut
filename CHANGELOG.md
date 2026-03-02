# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.2] - 2026-03-01

### Fixed
- **Critical: AN EVIL FORCE error** - Fixed by using `item-names-full.json` as default base template (1273 items instead of 6)
- **MISSING STRING error** - Full dictionary merge ensures all item keys are present
- **PyInstaller yaml bundling** - Added `--hidden-import yaml` and `--collect-all yaml` to prevent ModuleNotFoundError

### Added
- `generate_full_build.py` - Static build generator for loot filter without database
- Complete config file packaging in release builds:
  - `rune_prices.yml` - Rune FG prices
  - `gg_affixes.yml` - GG affix prices
  - `base_potential.yml` - Base item potential values
  - `perfect_rolls.yml` - Perfect roll definitions
  - `static_prices.yml` - Static item prices
  - `comprehensive_prices.yml` - Comprehensive price database
  - `unique_prices_complete.yml` - Unique item prices
  - `set_prices_complete.yml` - Set item prices
  - `lld_prices.yml` - Low Level Dueling prices
  - `magic_affix_prices.yml` - Magic affix prices
  - `affix_database.yml` - Complete affix database
- Complete template file packaging:
  - `item-names-full.json` - **CRITICAL** for AN EVIL FORCE fix
  - `item-runes.json`
  - `item-nameaffixes.json`
  - `item-magic-combos.json`
  - `item-affix-hints.json`
- Chat history export documentation (`docs/z.ai.md`)

### Changed
- Default `--base-json` parameter changed from `item-names.json` (6 items) to `item-names-full.json` (1273 items)
- Release workflow now includes all templates and configs for complete FG pricing

### Stats
- **1273** base items in dictionary
- **266** items with FG prices from static configs
- **33** runes with prices
- **29** GG affixes with prices

---

## [0.2.1] - 2026-03-01

### Added
- Rune/runeword pricing tools and pipeline hardening
- Magic item combos integration into loot filter build
- GG affixes reference from MrLlamaSC (2021)
- Magic item combinations with FG prices for loot filter

### Changed
- Stability improvements for loot-filter pipeline

### Stats
- **725** items priced (57% coverage)

---

## [0.2.0] - 2026-02-28

### Added
- Standalone executable build scripts
- Remote overlay server for real-time item streaming
- blizzhackers/d2data JSON files and importer
- Complete affix database from D2R Maxroll CSV
- D2R Arreat Summit / Maxroll affix name corrections
- Class-specific circlet pricing (+3 skills / 20 FCR combos)
- Magic Item Pricer with FG estimates and ilvl display
- Live Collector (Playwright) and ML Item Classifier
- Smart Base Detection, LLD Pricing, and d2jsp Inventory Sync
- D2R Loot Filter extensions (GG affixes, base hints, perfect rolls, rune prices)
- Full catalog export and generated filter

### Fixed
- Magic item pricer to load complete affix database
- Color tier tests to match TZ spec (ÿc; for high, ÿc1 for GG)
- Pricing logic updated to realistic FG prices

### Changed
- Removed egg-info from git, updated .gitignore

---

## [0.1.6] - 2026-02-27

### Added
- Refresh-on-exit flow for monitor-game mode

---

## [0.1.5] - 2026-02-27

### Added
- Monitor-game mode to rebuild filter after D2R exit

---

## [0.1.4] - 2026-02-26

### Added
- Initial release with basic loot filter generation
- Support for multiple presets (leveling, crafting, endgame, wealth, roguecore)
- FG price injection into item names
- Color coding based on FG tiers

---

## Release Notes

### v0.2.2 - Critical Fix Release

This release fixes the **AN EVIL FORCE** and **MISSING STRING** errors that appeared when items couldn't be found in the localization dictionary.

**Root Cause:** The build script was using `item-names.json` as the default base template, which only contained 6 entries. The fix changes the default to `item-names-full.json` which contains all 1273 D2R base items.

**Installation:**
1. Download the release for your platform (Windows/Linux/macOS)
2. Extract to your preferred location
3. Run `D2R_Loot_Filter_Builder.exe` (Windows) or `D2R_Loot_Filter_Builder` (Linux/macOS)
4. Select a preset or use command-line arguments
5. Copy generated files to your D2R mod folder

**Upgrade from v0.2.1:**
- Replace all files
- Ensure `data/templates/item-names-full.json` exists
- All config files are now included in the release package

---

[0.2.2]: https://github.com/Prestapro/d2lut/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Prestapro/d2lut/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Prestapro/d2lut/compare/v0.1.6...v0.2.0
[0.1.6]: https://github.com/Prestapro/d2lut/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/Prestapro/d2lut/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Prestapro/d2lut/releases/tag/v0.1.4
