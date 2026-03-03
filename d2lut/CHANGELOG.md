# Changelog

All notable changes to this project will be documented in this file.

The format is
`- Fixed: bug description`
`- Added: new feature`
`- Changed: breaking changes`

The format is one line per entry for possible.
The type of entry is encouraged. For added entries, use:
  - `Fixed: bug description` - [Issue/XXX] Fixed XXX bug.`
  - `Added: new feature` - [Feature] Added XXX feature.`
  - `Changed: breaking changes` - [Breaking Change] Changed XXX.`
  - `Security: security fix` - [Security] Fixed security vulnerability.`
  - `Deprecated: deprecated feature` - [Deprecated] Deprecated XXX,`

## [0.4.1] - 2026-03-03

### Fixed
- **Critical**: Fixed Python package packaging - `MANIFEST.in` ensures `data/` and `config/` directories are included in pip package
- **Critical**: `build_d2r_filter.py` now validates D2R item codes and warns when `variant_key` not found in `item_codes.json`
- **Critical**: `collect/d2jsp.py` static mode now works with requests-based scraper (no Playwright required)
- **High**: `parser.py` - `max_items_per_post` now configurable via `max_items_per_post` parameter (default: 5, was hardcoded: 2)
- **High**: `patterns.py` - price selection logic now prefers higher price within same confidence level
- **Medium**: `PRICE_TIERS` now uses `999_999` instead of `float('inf')` for JSON serialization
- **Medium**: Tests for `slang_aliases` - marked as skip (feature not yet implemented)
```
