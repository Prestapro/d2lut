# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.2.2] - 2026-03-02

### Fixed
- **Critical: AN EVIL FORCE error** - Changed default `--base-json` from `item-names.json` (6 items) to `item-names-full.json` (1273 items)
- **MISSING STRING error** - Full dictionary merge ensures all D2R item keys are present
- **PyInstaller yaml bundling** - Added `--hidden-import yaml` and `--collect-all yaml` to prevent ModuleNotFoundError at runtime
- GitHub Actions workflow now sets `draft: false` and `generate_release_notes: false`

### Added
- `generate_full_build.py` - Static loot filter generator that works without database
- Complete config file packaging in release builds:
  - `rune_prices.yml` - Rune FG prices (33 runes)
  - `gg_affixes.yml` - GG affix prices (29 affixes)
  - `base_potential.yml`, `perfect_rolls.yml`, `static_prices.yml`
  - `comprehensive_prices.yml`, `unique_prices_complete.yml`, `set_prices_complete.yml`
  - `lld_prices.yml`, `magic_affix_prices.yml`, `affix_database.yml`
- Complete template file packaging:
  - `item-names-full.json` - **CRITICAL** 1273 D2R items
  - `item-runes.json`, `item-nameaffixes.json`, `item-magic-combos.json`, `item-affix-hints.json`
- `docs/z.ai.md` - Complete chat history export for troubleshooting reference

### Stats
- 1273 base items in dictionary
- 266 items with FG prices from static configs
- 33 runes with prices (Jah=50FG, Ber=55FG, etc.)
- 29 GG affixes with prices (Jeweler's=2000FG, etc.)

---

## [0.2.1] - 2026-03-01

### Fixed
- v0.2.0 exe build now bundles yaml and ships config files

### Added
- Rune/runeword pricing tools and pipeline hardening
- Magic item combos integration into loot filter build
- GG affixes reference from MrLlamaSC (2021)
- Magic item combinations with FG prices for loot filter
- Quick static build script for loot filter generation
- Static price database with FG prices

### Stats
- 725 items priced (57% coverage)
- 693 items with detailed price database
- 305 items with comprehensive prices

---

## [0.2.0] - 2026-02-27

### Added
- Standalone executable build scripts (`build_exe.bat`, `build_exe.sh`)
- Remote overlay server for real-time item streaming via WebSocket
- blizzhackers/d2data JSON files importer (721 prefixes, 785 suffixes)
- Complete D2R affix database from original game files
- Complete affix database from D2R Maxroll CSV
- D2R Arreat Summit / Maxroll affix name corrections
- Class-specific circlet pricing (+3 skills / 20 FCR combos)
- Magic Item Pricer with FG estimates and ilvl display
- Live Collector using Playwright for web scraping
- ML Item Classifier for automatic item categorization
- Smart Base Detection for ethereal/superior bases
- LLD (Low Level Dueling) pricing module
- d2jsp Inventory Sync functionality
- D2R Loot Filter extensions:
  - GG affixes highlighting
  - Base hints for crafting
  - Perfect rolls display
  - Rune prices in item names
- Full catalog export and generated filter
- Safe full item-names FG merge helper

### Fixed
- Magic item pricer now loads complete affix database
- Color tier tests match TZ spec (`ÿc;` for high, `ÿc1` for GG)
- Pricing logic updated to realistic FG prices
- Missing dependencies and D2R template files added

### Changed
- Removed egg-info from git
- Updated .gitignore

---

## [0.1.6] - 2026-02-27

### Added
- Refresh-on-exit flow for monitor-game mode
- Market snapshot refresh before filter rebuild

---

## [0.1.5] - 2026-02-27

### Added
- Monitor-game mode to rebuild filter after D2R exit
- Automatic detection of game process (D2R.exe)
- Polling interval configuration (`--poll-seconds`)

---

## [0.1.4] - 2026-02-27

### Added
- Monitor-game mode foundation
- Game process detection for Windows and Linux

---

## [0.1.3] - 2026-02-27

### Added
- **Roguecore preset** - Endgame-sparse styling, focus on trade items
- 100+ FG threshold by default
- Always includes: runes, keys, tokens, jewels, bases

---

## [0.1.2] - 2026-02-27

### Added
- Explain/debug audit mode for D2R filter generator
- `--explain` flag for detailed injection logging
- `--explain-limit` parameter for sample size control
- `--audit-json` output for programmatic analysis

---

## [0.1.1] - 2026-02-27

### Fixed
- GitHub Actions release workflow shell matrix validation
- Build matrix for Linux, Windows, macOS platforms

---

## [0.1.0] - 2026-02-27

### Added
- Initial release
- D2R filter generator with multiple presets:
  - `leveling` - Show all items, highlight runes/gems
  - `crafting` - Hide trash, show bases/jewels/gems
  - `endgame` - Hide trash, show keys/tokens
  - `wealth` - Show only Jah/Ber (200+ FG)
- FG price injection into item names
- Color coding based on FG tiers
- GitHub Actions workflow for automated releases
- PyInstaller packaging for standalone executables
- SQLite database support for price storage

### Features
- `--min-fg` threshold configuration
- `--format-str` for custom price tag format
- `--tag-style` presets (bracket, pipe, bare)
- `--hide-junk` to filter low-value items
- `--use-short-names` for compact display
- `--apply-colors` for D2R color codes

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| 0.2.2 | 2026-03-02 | Fix AN EVIL FORCE, include all configs |
| 0.2.1 | 2026-03-01 | Stability, rune pricing, 725 items |
| 0.2.0 | 2026-02-27 | Overlay server, ML classifier, smart detection |
| 0.1.6 | 2026-02-27 | Refresh-on-exit flow |
| 0.1.5 | 2026-02-27 | Monitor-game mode |
| 0.1.4 | 2026-02-27 | Game process detection |
| 0.1.3 | 2026-02-27 | Roguecore preset |
| 0.1.2 | 2026-02-27 | Explain/debug mode |
| 0.1.1 | 2026-02-27 | GitHub Actions fix |
| 0.1.0 | 2026-02-27 | Initial release |

---

## Upgrade Guide

### From v0.2.1 to v0.2.2
1. Download new release
2. Replace all files
3. Verify `data/templates/item-names-full.json` exists (1273 items)
4. All config files now included automatically

### From v0.1.x to v0.2.x
1. Download new release for your platform
2. Extract to new folder (don't merge with old)
3. Config files now bundled in release
4. No database required for static pricing

---

## Known Issues

- d2jsp Cloudflare protection blocks automated price scraping
- Dynamic pricing requires game exit to update
- Roll-sensitive items show `?FG` until inspected

---

## Links

- [GitHub Repository](https://github.com/Prestapro/d2lut)
- [Releases](https://github.com/Prestapro/d2lut/releases)
- [Issues](https://github.com/Prestapro/d2lut/issues)

---

[0.2.2]: https://github.com/Prestapro/d2lut/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Prestapro/d2lut/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Prestapro/d2lut/compare/v0.1.6...v0.2.0
[0.1.6]: https://github.com/Prestapro/d2lut/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/Prestapro/d2lut/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Prestapro/d2lut/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Prestapro/d2lut/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Prestapro/d2lut/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Prestapro/d2lut/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Prestapro/d2lut/releases/tag/v0.1.0
