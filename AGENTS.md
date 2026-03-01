# AGENTS.md

## Scope

This file defines repo-local guidance for coding agents working in `d2lut`.

Priority order:
1. System instructions
2. Developer instructions
3. User request
4. This file

## Project Reality (Important)

- `src/d2lut/pipeline.py` is a scaffold entrypoint and still depends on stubs.
- The main working workflows currently live in `scripts/`:
  - `scripts/build_market_db.py`
  - `scripts/run_d2jsp_snapshot_pipeline.py`
  - `scripts/build_catalog_db.py`
- Core parsing logic is concentrated in `src/d2lut/normalize/d2jsp_market.py`.
- Overlay logic is implemented in `src/d2lut/overlay/*` and is test-heavy but environment-dependent (OCR/OpenCV/Pillow/easyocr/pytesseract).

## Working Rules

- Prefer minimal, reversible changes.
- Do not refactor unrelated modules while fixing a targeted issue.
- Preserve existing CLI flags and DB schema compatibility unless change is explicitly requested.
- Treat local `data/` contents as developer artifacts; do not delete or rewrite caches/snapshots unless asked.
- Avoid claiming a feature is "fixed" without a concrete validation step.

## Confidence Contract (for non-trivial tasks)

Separate conclusions into:
- `Known`
- `Assumed`
- `Unknown`
- `To Verify`

State confidence as `High` / `Medium` / `Low` with one short reason.

## Validation Expectations

- Prefer targeted tests first (module/file-specific) before broad test runs.
- If `pytest` fails before project test collection due to environment plugins, retry with:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`
- For most repo scripts, use:
  - `PYTHONPATH=src`
- If full tests cannot run, state what was validated and the residual risk.

## Anti-Degradation

- If two attempts fail without measurable progress, narrow scope.
- Fix regressions before adding improvements.
- Do not expand scope under uncertainty.

## Editing Guidance

- Keep code deterministic and readable.
- Add comments only where logic is non-obvious.
- Prefer patch-style edits over broad rewrites.
- Do not change user data, credentials, or local environment configuration without explicit approval.

