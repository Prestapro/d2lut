# Changelog

All notable changes to this project will be documented in this file.

Format:
- `Added`: new functionality
- `Changed`: behavior or architecture changes
- `Fixed`: bug fixes
- `Security`: security-related fixes

## [Unreleased]

## [0.6.3] - 2026-03-05

### Added
- Isolated live-scanner worker (`live_scanner_worker.sh`) with a dedicated health-check script for autonomous price monitoring.
- End-to-end filter API verification script (`e2e-filter-api-check.sh`) and runtime wiring verifier (`verify-runtime-wiring.sh`).
- Edge-case test suites for pipeline estimate calculations and filter generation scenarios.
- Global error boundary (`global-error.tsx`) and custom 404 page (`not-found.tsx`) for Next.js app.
- Prisma initial schema migration (`20260304120944_init_schema`).
- Scheduled GitHub Actions workflow for live price refresh (`live-refresh-prices.yml`).

### Changed
- Filter build API (`/api/filter/build`) now supports multiple build modes and validates tier logic end-to-end.
- Cron observation persistence batched and capped to prevent unbounded DB growth.
- Price refresh pipeline hardened with dedupe guards and fail-fast on zero-post collector scans.
- Chart and resizable UI components updated for compatibility with current `recharts` and `react-resizable-panels` APIs.
- Release workflow now generates notes from the matching `CHANGELOG.md` version section and publishes from `RELEASE_NOTES.md`.

### Fixed
- Restored full TypeScript typecheck by adding missing UI dependencies (`@radix-ui/react-dialog`, `cmdk`, etc.).
- Stabilized Next.js prerender by enforcing `NODE_ENV=production` during build.
- Closed residual API boundary gaps and hardened cron endpoint error handling.
- CI now installs a platform-aware Tailwind Oxide native binding to avoid optional-dependency install gaps on GitHub Actions.
- Prisma runtime now enforces `DATABASE_URL` in production while preserving safe local/build fallback behavior.

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
