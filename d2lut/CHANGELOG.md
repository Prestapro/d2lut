# Changelog

All notable changes to this project will be documented in this file.

Format:
- `Added`: new functionality
- `Changed`: behavior or architecture changes
- `Fixed`: bug fixes
- `Security`: security-related fixes

## [Unreleased]

### Added
- Guarded OpenCode helper scripts with shared validation utilities and smoke tests for exit-code behavior.

### Changed
- Release workflow now generates notes from the matching `CHANGELOG.md` version section and publishes from `RELEASE_NOTES.md`.

### Fixed
- CI now installs a platform-aware Tailwind Oxide native binding to avoid optional-dependency install gaps on GitHub Actions.
- Next.js CI install compatibility restored by pinning ESLint to the range required by `eslint-config-next@14`.
- Web item filtering now keeps TRASH-tier rows queryable (`minPrice=0`), and price-history modal handles non-200 API responses safely.
- Prisma runtime now enforces `DATABASE_URL` in production runtime while preserving safe local/build fallback behavior.

## [0.6.0] - 2026-03-03

### Added
- Integrated Prisma-backed storage and Python bridge plumbing for web/API flows.

### Changed
- Release line pivoted from file-based flows toward DB-backed data access.

## [0.5.0] - 2026-03-03

### Fixed
- Applied audit-driven fixes for runtime correctness and API/UI reliability.

## [0.4.1] - 2026-03-03

### Fixed
- **Critical**: Fixed Python package packaging - `MANIFEST.in` ensures `data/` and `config/` directories are included in pip package
- **Critical**: `build_d2r_filter.py` now validates D2R item codes and warns when `variant_key` not found in `item_codes.json`
- **Critical**: `collect/d2jsp.py` static mode now works with requests-based scraper (no Playwright required)
- **High**: `parser.py` - `max_items_per_post` now configurable via `max_items_per_post` parameter (default: 5, was hardcoded: 2)
- **High**: `patterns.py` - price selection logic now prefers higher price within same confidence level
- **Medium**: `PRICE_TIERS` now uses `999_999` instead of `float('inf')` for JSON serialization
- **Medium**: Tests for `slang_aliases` - marked as skip (feature not yet implemented)
