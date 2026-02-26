# Implementation Plan

## Completed

- [x] 1. Write bug condition exploration test
  - 8/11 failed (confirming bugs), 3 passed (torch prefix, GT base, ias/ed jewel already work)
  - _Requirements: 1.1, 1.2, 6.1, 6.2, 6.3, 8.1, 8.2, 9.1, 9.2, 12.1, 12.2, 13.1, 13.2, 14.2, 14.3, 15.1, 15.4_

- [x] 2. Write preservation property tests
  - 62 tests passing on baseline code
  - _Requirements: 1.3, 3.5, 4.4_

- [x] 3. Fix stash scan presenter regressions
  - Fixed `_get_value_tier()` midpoint cutoff and `_sort_items()` call; 17/17 pass
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 4. Parser regression corpus
  - Created `tests/fixtures/parser_regression_corpus.py` (34 entries) and `tests/test_parser_regression_corpus.py` (20 pass, 14 xfail)
  - _Requirements: 25.1, 25.2, 25.3, 25.4_

- [x] 5. Req-level parser hardening
  - Expanded `RE_REQ_LVL` with rlvl, lv, OCR-noise (1v1, rv1), colon/equals variants; range validation 1-99
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

## Active sprint — Parser & data model (normalize layer)

- [x] 6. Runeword kit vs finished detection
  - NOTE: Kit detection logic belongs in normalize layer (`src/d2lut/normalize/d2jsp_market.py` already has `_infer_runeword_kit_variant`). Expose kit flag for exporter consumption.
  - [x] 6.1 Add `kit` boolean to `ExtractedProps`; wire kit detection from normalize layer into `extract_props()` path
    - _Requirements: 9.1, 9.2_
  - [x] 6.2 Update `props_signature()` to prefix kit signatures with `kit:` — kit and finished rows with same runeword name → different signatures
    - _Requirements: 9.3, 10.2_
  - [x] 6.3 Add kit/finished filter option to existing UI filter bar; render `KIT` pill badge on kit rows
    - _Requirements: 9.4, 10.1_
  - [x] 6.4 Regression test fixtures for multi-line recipe cases
    - _Requirements: 9.5_

- [x] 7. LLD bucket assignment
  - [x] 7.1 Add `lld_bucket` field to `ExtractedProps` with assignment logic: `≤9` → LLD9, `10-18` → LLD18, `19-30` → LLD30, `31-49` → MLD, `≥50` → HLD, `None` → unknown (or LLD30 if `lld=True`)
    - _Requirements: 8.1, 8.2_
  - [x] 7.2 Extend existing `lldLevel` dropdown with LLD18, MLD, HLD options; add bucket column/badge to table
    - _Requirements: 8.3, 8.4_
  - [x] 7.3 Unit tests for LLD bucket assignment
    - _Requirements: 8.1, 8.2_

- [x] 8. Roll-aware runeword property extraction
  - Target runewords: CTA (BO level), HOTO (all res), Grief (IAS + dmg), Infinity (-enemy res), Insight (meditation), Spirit (FCR + all res), Fortitude (ED), BOTD (ED)
  - [x] 8.1 Add runeword-specific regex patterns and `ExtractedProps` fields (`rw_name`, `rw_bo_lvl`, `rw_all_res`, etc.)
    - _Requirements: 12.1_
  - [x] 8.2 Update `props_signature()` to include roll detail when present (e.g. `"runeword:cta + +6BO"`)
    - _Requirements: 12.2, 12.3_
  - [x] 8.3 Regression test fixtures for each target runeword (rolled + unrolled excerpts)
    - _Requirements: 12.4_

- [x] 9. Torch/anni OCR digit folding
  - [x] 9.1 Add OCR-fold pre-pass before `RE_ANNI_TRIPLE` / `RE_TORCH_ROLL` (O→0, l→1, I→1 in numeric contexts)
    - _Requirements: 13.2_
  - [x] 9.2 Add torch/anni tier classification (perfect / near-perfect / good / average / low)
    - _Requirements: 13.3_
  - [x] 9.3 Validate roll ranges (torch: 10-20 attrs/res; anni: 10-20 attrs/res, 5-10 xp) — discard out-of-range
    - _Requirements: 13.5_
  - [x] 9.4 Regression tests for OCR-corrupted torch/anni excerpts
    - _Requirements: 13.2, 13.4_

- [x] 10. Base item parser v2
  - [x] 10.1 Add `superior`/`sup` prefix detection; parse defense from `Ndef`, `def N`, `defense: N`
    - _Requirements: 14.1, 14.2_
  - [x] 10.2 Improve socket parsing: `N os`, `Nos`, `N soc`, `N socket`, `socketed (N)`
    - _Requirements: 14.3_
  - [x] 10.3 Prioritize trade-relevant bases (monarch, archon plate, mage plate, thresher, GT, cryptic axe, CV, GPA, phase blade, berserker axe)
    - _Requirements: 14.5_
  - [x] 10.4 Regression tests for OCR-corrupted base excerpts
    - _Requirements: 14.6_

- [x] 11. Jewel, charm, and circlet parser v2
  - [x] 11.1 Parse jewel combos: `ias/ed`, `max/ar/life`, `fhr`, `frw` + req-level
    - _Requirements: 15.1_
  - [x] 11.2 Parse charm combos: `3/20/20`, `fhr/res`, `life/res`, `mf/res` for SC/LC/GC
    - _Requirements: 15.2_
  - [x] 11.3 Parse circlet combos: `2/20`, `3/20/20`, class-specific trees, FRW, sockets
    - _Requirements: 15.3_
  - [x] 11.4 Handle slash-separated shorthand when item context is present
    - _Requirements: 15.4_
  - [x] 11.5 Regression tests: ≥5 real d2jsp LLD excerpts per item type
    - _Requirements: 15.5_

## Tooling & reporting

- [x] 12. Property table coverage KPI reporter (`scripts/report_property_table_coverage.py`)
  - Compute: property_rows, fallback_rows, market_gap_rows, sig_coverage, % source link, % req_lvl, % class_tags, top 20 missing variants
  - Flags: `--min-fg`, `--json`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 13. Suspicious row detector (`scripts/detect_suspicious_rows.py`)
  - Flag: impossible property combos, >5x category median price anomaly, contradictory type assignment
  - Flags: `--min-fg`
  - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5_

- [x] 14. Topic replay tool (`scripts/replay_topic.py`)
  - Reparse a thread_id, show before/after diff of extracted observations
  - Flags: `--dry-run`
  - _Requirements: 24.1, 24.2, 24.3, 24.4_

## Table display & UX

- [x] 15. Display modes: expanded_by_variant and expanded_by_listing
  - [x] 15.1 Embed per-observation data (source_url, raw_excerpt, signal_kind, price_fg, observed_at) in JSON payload
    - _Requirements: 4.2, 4.3_
  - [x] 15.2 Add JS display mode toggle (grouped / expanded_by_variant / expanded_by_listing) preserving filter/sort state
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [x] 15.3 Unit tests for display mode switching
    - _Requirements: 4.4_

- [x] 16. Last Seen / freshness column
  - [x] 16.1 Include `last_seen` (max `observed_at`) in each row dict; add relative-time JS formatting
    - _Requirements: 21.1, 21.2_
  - [x] 16.2 Stale-row styling (>7 days → muted text); sortable column
    - _Requirements: 21.3, 21.4_

- [x] 17. Signal split columns (BIN / c/o / ASK / SOLD)
  - [x] 17.1 Compute per-signal-type median FG; add `bin_fg`, `co_fg`, `ask_fg`, `sold_fg` to row dicts
    - _Requirements: 22.1, 22.2, 22.3_
  - [x] 17.2 Render separate sortable columns in HTML table
    - _Requirements: 22.4_

- [x] 18. Saved filter presets
  - [x] 18.1 Built-in presets: Commodities, Runewords, Torches/Annis, LLD, Bases, No source link, High FG + low confidence
    - _Requirements: 19.1, 19.2_
  - [x] 18.2 Custom preset save/delete via localStorage
    - _Requirements: 19.3, 19.4_

## Data quality tooling (P1)

- [x] 19. Modifier lexicon integration for property parsing
  - [x] 19.1 Validate extracted property names against modifier lexicon in `extract_props()`
    - _Requirements: 17.1_
  - [x] 19.2 Discard impossible property combos for detected item category
    - _Requirements: 17.2_
  - [x] 19.3 Use lexicon scoring for ambiguous regex matches
    - _Requirements: 17.3_
  - [x] 19.4 Log rejected properties with reason codes
    - _Requirements: 17.4_

- [x] 20. OCR miss triage queue (`scripts/report_ocr_miss_triage.py`)
  - Group failures by pattern: no_variant_hint, wrong_class, ocr_corruption, base_only_vs_finished_rw, no_property_signature
  - Rank by total FG lost; 5 sample excerpts per group; `--min-fg` flag
  - _Requirements: 16.1, 16.2, 16.3, 16.4_

- [x] 21. OCR quality dashboard (`scripts/report_ocr_quality.py`)
  - Precision/recall by item class; 3 mismatch samples per class; compare sig vs variant_hint; `--json` flag
  - _Requirements: 18.1, 18.2, 18.3, 18.4_

- [x] 22. Source link backfill (`scripts/backfill_source_urls.py`)
  - Idempotent backfill of source_url from thread_id; log unresolvable rows
  - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 23. Task audit script (`scripts/audit_tasks_vs_tests.py`)
  - Compare tasks.md markers vs pytest results; report regressed/completable; non-zero exit on regressions
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

## Checkpoint

- [x] 24. Final checkpoint
  - Run full test suite; verify preservation tests still pass; run coverage KPI reporter; confirm no regressions
