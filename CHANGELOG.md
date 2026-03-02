# Changelog

---

## v0.2.4

Bug Fixes
- Fixed broken console_scripts in pyproject.toml (pointed to non-existent d2lut.scripts.* modules)
- Fixed RefreshDaemon.get_status() returning wrong is_running value (self._refreshing instead of self._running)
- Fixed --skip-zero-replies and --skip-bump-only-topic flags that couldn't be disabled
- Fixed test_slang_simple.py - no pytest fixture for db_path (6 errors)
- Fixed test_integration_e2e.py - returning int instead of None (PytestReturnNotNoneWarning)

Changes
- Removed broken entry points from pyproject.toml (scripts are standalone in scripts/)
- Added --no-skip-zero-replies and --no-skip-bump-only-topic flags to allow disabling defaults
- Converted test_slang_simple.py to pytest class with fixture support
- Created tests/conftest.py with db_path fixture for slang tests
- Fixed test_integration_e2e.py to use raise instead of return int

CI/CD
- Removed soft test mode in CI - tests now properly block releases (removed || true and continue-on-error)

Changelog
Full Changelog: v0.2.3...v0.2.4

#bbdbf97 fix: resolve 7 code review issues @Z User
#4fb22c3 fix(ci): remove soft test mode - tests now block releases @Z User

---

## v0.2.3

New Features
- Added crafting bases to base_potential.yml (glv, lrg, xvg, xhg for blood/hitpower crafts)
- Added TZ (Trade Zone) color system with ÿc3 blue color for prices
- Added complete perfect_rolls.yml with Torches, Annihilus, Rainbow Facets, and Runewords
- Added new 'tz' preset with blue color pricing
- Added gg_craft flag for craft-relevant items in base_potential.yml

Changes
- Expanded base_potential.yml from 36 to 90+ base items
- Expanded perfect_rolls.yml from 26 to 80+ entries
- Updated all presets to use TZ color styles
- Added 7 new color styles: tz-blue, tz-gold, tz-orange, tz-red, tz-green, tz-blue-compact, tz-red-compact

Stats
- 1273 base items in dictionary
- 90+ base potential hints
- 80+ perfect roll definitions
- 7 new color styles

Changelog
Full Changelog: v0.2.2...v0.2.3

#b19cb79 feat: P1-P3 improvements for v0.2.3 @Z User

---

## v0.2.2

New Features
- Added `generate_full_build.py` for static loot filter generation without database
- Added complete FG pricing with 266 items, 33 runes, and 29 GG affixes
- Added `docs/z.ai.md` - complete chat history export for troubleshooting

Bug Fixes
- Fixed critical AN EVIL FORCE error by using `item-names-full.json` (1273 items) as default base template instead of 6-item minimal template
- Fixed MISSING STRING error with full dictionary merge for all D2R item keys
- Fixed PyInstaller yaml bundling by adding `--hidden-import yaml` and `--collect-all yaml`
- Fixed GitHub Actions workflow to set `draft: false` and `generate_release_notes: false`

Documentation
- Added complete CHANGELOG.md with full version history (v0.1.0-v0.2.2)
- Updated chat history with Session 2 work log

Chores
- Included all templates and config files in release build package
- Added 10+ config files: rune_prices.yml, gg_affixes.yml, base_potential.yml, perfect_rolls.yml, static_prices.yml, comprehensive_prices.yml, unique_prices_complete.yml, set_prices_complete.yml, lld_prices.yml, magic_affix_prices.yml, affix_database.yml

Changelog
Full Changelog: v0.2.1...v0.2.2

#c82ed71 fix: use item-names-full.json as default base template @Z User
#2187791 feat: add generate_full_build.py for static loot filter generation @Z User
#20ad04f docs: update chat history with Session 2 work log @Z User
#52042ea docs: add complete chat history export (z.ai.md) @Z User
#b573e46 fix: include all templates and configs in release build @Z User
#468460f docs: add CHANGELOG.md with v0.2.2 release notes @Z User
#11c4903 fix: set draft=false and disable auto release notes in workflow @Z User

---

## v0.2.1

New Features
- Added static price database and generate item-names.json with FG prices
- Added comprehensive price database with 305 items priced
- Added massive price database expansion - 693 items priced (54%)
- Added more set and unique prices - 725 items priced (57%)
- Added magic item combinations with FG prices for loot filter
- Added GG affixes reference from MrLlamaSC (2021)
- Added quick static build script for loot filter generation

Bug Fixes
- Fixed v0.2.0 exe build: bundle yaml and ship config
- Fixed build scripts to use static prices when database not available

Documentation
- Added chat history export for current support session

Chores
- Integrated magic item combos into loot filter build
- Hardened loot-filter pipeline and added rune/runeword pricing tools

Changelog
Full Changelog: v0.2.0...v0.2.1

#ae708da Fix v0.2.0 exe build: bundle yaml and ship config @Alexator
#196462c docs: add chat history export for current support session @Alexator
#f81f39e feat: Add static price database and generate item-names.json with FG prices @Z User
#f154f74 fix: Update build scripts to use static prices when database not available @Z User
#6629d7d feat: Add quick static build script for loot filter generation @Z User
#dcf02b0 feat: Add comprehensive price database with 305 items priced @Z User
#62a2037 feat: Massive price database expansion - 693 items priced (54%) @Z User
#e7911ed feat: Add more set and unique prices - 725 items priced (57%) @Z User
#9dd2d71 Add magic item combinations with FG prices for loot filter @Z User
#00f97b1 Add GG affixes reference from MrLlamaSC (2021) @Z User
#ab29880 Integrate magic item combos into loot filter build @Z User
#edafdab stability: harden loot-filter pipeline and add rune/runeword pricing tools @Alexator

---

## v0.2.0

New Features
- Added build scripts for standalone executable (build_exe.bat, build_exe.sh)
- Added remote overlay server for real-time item streaming via WebSocket
- Added blizzhackers/d2data JSON files and importer
- Added complete D2R affix database from original game files
- Added complete affix database from D2R Maxroll CSV
- Added D2R Arreat Summit / Maxroll affix name corrections
- Added class-specific circlet pricing (+3 skills / 20 FCR combos)
- Added Magic Item Pricer with FG estimates and ilvl display
- Added Live Collector (Playwright) for web scraping
- Added ML Item Classifier for automatic item categorization
- Added Smart Base Detection for ethereal/superior bases
- Added LLD (Low Level Dueling) pricing module
- Added d2jsp Inventory Sync functionality
- Implemented D2R Loot Filter extensions (GG affixes, base hints, perfect rolls, rune prices)
- Added full catalog export and generated filter

Bug Fixes
- Fixed magic_item_pricer to load d2data affix database
- Fixed magic_item_pricer to load complete affix database
- Fixed pricing logic and updated to realistic FG prices
- Fixed color tier tests to match TZ spec (ÿc; for high, ÿc1 for GG)
- Fixed missing dependencies and D2R template files
- Relaxed test assertions for headless environment compatibility

Chores
- Added safe full item-names FG merge helper
- Restored DB and improved price coverage
- Moved generated filter to examples folder
- Updated .gitignore to allow example output/item-names.json
- Removed egg-info from git, updated .gitignore

Changelog
Full Changelog: v0.1.6...v0.2.0

#b355f16 Add safe full item-names FG merge helper @Alexator
#c512bbf feat: restore DB and improve price coverage @Prestapro
#4f59e53 feat: implement D2R Loot Filter extensions (GG affixes, base hints, perfect rolls, rune prices) @Prestapro
#3027a62 Add full catalog export and generated filter @Prestapro
#9eed1de Move generated filter to examples folder @Prestapro
#67a40ac Update .gitignore to allow example output/item-names.json @Prestapro
#c111f55 fix: add missing dependencies and D2R template files @Z User
#8b80bb4 fix: update color tier tests to match TZ spec (ÿc; for high, ÿc1 for GG) @Z User
#d8a16ac feat: implement Smart Base Detection, LLD Pricing, and d2jsp Inventory Sync @Z User
#10b64b1 feat: implement Live Collector (Playwright) and ML Item Classifier @Z User
#115f69c feat: add Magic Item Pricer with FG estimates and ilvl display @Z User
#68bdf53 chore: remove egg-info from git, update .gitignore @Z User
#adc436b fix: relax test assertions for headless environment compatibility @Z User
#1141152 feat: add class-specific circlet pricing (+3 skills / 20 FCR combos) @Z User
#9c9f0b7 fix: correct pricing logic and update to realistic FG prices @Z User
#9904aea feat: correct affix names based on D2R Arreat Summit / Maxroll @Z User
#80b77fd feat: Add complete affix database from D2R Maxroll CSV @Z User
#34c8666 feat: Add complete D2R affix database from original game files @Z User
#c83f4c1 fix: Update magic_item_pricer to load complete affix database @Z User
#3fa30f6 feat: Add blizzhackers/d2data JSON files and importer @Z User
#918da86 fix: Update magic_item_pricer to load d2data affix database @Z User
#5d9e499 feat: Add remote overlay server for real-time item streaming @Z User
#d866460 feat: Add build scripts for standalone executable @Z User

---

## v0.1.6

New Features
- Added refresh-on-exit flow for monitor-game mode
- Added market snapshot refresh before filter rebuild

Changelog
Full Changelog: v0.1.5...v0.1.6

#434a3cd Add refresh-on-exit flow for monitor-game mode @Prestapro

---

## v0.1.5

New Features
- Added monitor-game mode to rebuild filter after D2R exit
- Added automatic detection of game process (D2R.exe)
- Added polling interval configuration (`--poll-seconds`)

Changelog
Full Changelog: v0.1.4...v0.1.5

#434a3cd Add refresh-on-exit flow for monitor-game mode @Prestapro

---

## v0.1.4

New Features
- Added monitor-game mode foundation
- Added game process detection for Windows and Linux

Changelog
Full Changelog: v0.1.3...v0.1.4

#ac97fba Add monitor-game mode to rebuild filter after D2R exit @Prestapro

---

## v0.1.3

New Features
- Added Roguecore preset - endgame-sparse styling, focus on trade items
- Added 100+ FG threshold by default for Roguecore preset
- Added always-include: runes, keys, tokens, jewels, bases for Roguecore

Changelog
Full Changelog: v0.1.2...v0.1.3

#90d2e2b Add roguecore endgame preset for D2R filter builder @Prestapro

---

## v0.1.2

New Features
- Added explain/debug audit mode for D2R filter generator
- Added `--explain` flag for detailed injection logging
- Added `--explain-limit` parameter for sample size control
- Added `--audit-json` output for programmatic analysis

Changelog
Full Changelog: v0.1.1...v0.1.2

#b4bf3c4 Add explain/debug audit mode for D2R filter generator @Prestapro

---

## v0.1.1

Bug Fixes
- Fixed GitHub Actions release workflow shell matrix validation
- Fixed build matrix for Linux, Windows, macOS platforms

Changelog
Full Changelog: v0.1.0...v0.1.1

#305527b Fix GitHub Actions release workflow shell matrix validation @Prestapro

---

## v0.1.0

New Features
- Added D2R filter generator with multiple presets:
  - leveling - Show all items, highlight runes/gems
  - crafting - Hide trash, show bases/jewels/gems
  - endgame - Hide trash, show keys/tokens
  - wealth - Show only Jah/Ber (200+ FG)
- Added FG price injection into item names
- Added color coding based on FG tiers
- Added GitHub Actions workflow for automated releases
- Added PyInstaller packaging for standalone executables
- Added SQLite database support for price storage
- Added `--min-fg` threshold configuration
- Added `--format-str` for custom price tag format
- Added `--tag-style` presets (bracket, pipe, bare)
- Added `--hide-junk` to filter low-value items
- Added `--use-short-names` for compact display
- Added `--apply-colors` for D2R color codes

Changelog
Full Changelog: v0.1.0

#4bdbe7a Add d2r filter generator hardening, exe packaging, and release workflow @Prestapro
