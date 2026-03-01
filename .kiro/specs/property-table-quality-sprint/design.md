# Property Table Quality Sprint — Bugfix Design

## Overview

The property table (`property_price_table.html`) is the primary KPI artifact for D2R trading decisions. This sprint addresses a cluster of interrelated bugs and gaps across the parsing pipeline, table display, and data quality tooling. The core bug condition is: **many observed d2jsp listings with valid trade data produce no property signature or an incorrect one**, resulting in missing/wrong rows in the property table. Secondary bugs include stash scan presenter regressions, missing display modes, absent LLD segmentation, and no data quality feedback loop.

The fix strategy is layered:
1. Fix regressions first (stash scan presenter tests)
2. Harden parsers (req-level, runeword rolls, torch/anni, base, jewel/charm/circlet)
3. Add missing table features (filters, display modes, signal columns, freshness)
4. Build quality tooling (coverage report, suspicious row detector, topic replay, regression corpus)

## Glossary

- **Bug_Condition (C)**: An observed d2jsp listing that should produce a valid, accurate property signature but currently does not — either because `extract_props()` fails to parse key fields, `props_signature()` returns `None`, or the signature is incorrect (e.g. kit vs finished confusion, missing roll values, wrong req-level).
- **Property (P)**: For any listing matching C, the fixed parser SHALL produce a correct property signature with all trade-relevant fields extracted, and the property table SHALL display the row with correct metadata (row_kind, lld_bucket, class_tags, signal columns).
- **Preservation**: All existing correctly-parsed property signatures, variant fallback rows, market-gap rows, mouse/UI interactions, CLI flags, and DB schema must remain unchanged by the fix.
- **extract_props()**: Function in `scripts/export_property_price_table_html.py` (line 319) that extracts `ExtractedProps` from a raw d2jsp excerpt string.
- **props_signature()**: Function in `scripts/export_property_price_table_html.py` (line 470) that converts `ExtractedProps` into a canonical signature string.
- **RE_REQ_LVL**: Regex list (line 82) for parsing required level — currently only handles `req N`, `req lvl N`, `lvl req N` formats.
- **_build_html()**: Function (line 565) that generates the full HTML table with embedded JavaScript for filtering/sorting.
- **StashScanPresenter**: Class in `src/d2lut/overlay/stash_scan_presenter.py` providing formatted stash scan output; has 2 failing tests.
- **property_allowed_by_category_constraints()**: Function in `src/d2lut/normalize/modifier_lexicon.py` (line 262) that validates whether a property is legal for a given item category.

## Bug Details

### Fault Condition

The bug manifests across multiple parsing and display paths. The primary fault condition is that `extract_props()` fails to extract trade-relevant properties from valid d2jsp excerpts, causing `props_signature()` to return `None` or an incomplete/incorrect signature.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {excerpt: str, variant_key: str | None, context: str}
  OUTPUT: boolean

  props := extract_props(input.excerpt, input.variant_key)
  sig := props_signature(props)

  -- Parser gap: valid listing produces no signature
  IF sig IS None AND input.excerpt contains trade-relevant content THEN
    RETURN true

  -- Req-level miss: common formats not recognized
  IF input.excerpt matches common req-level patterns (rlvl, lv, req:, OCR-corrupted)
     AND props.req_lvl IS None THEN
    RETURN true

  -- Runeword confusion: kit classified same as finished
  IF input.excerpt is a runeword kit listing
     AND sig does not distinguish kit from finished THEN
    RETURN true

  -- Roll-aware gap: runeword rolls present but not in signature
  IF input.excerpt contains CTA/HOTO/Grief/Infinity/Spirit/Fortify/BOTD roll values
     AND sig does not include roll detail THEN
    RETURN true

  -- Torch/anni OCR miss: class or rolls not parsed due to OCR noise
  IF input.excerpt is torch/anni with OCR-corrupted rolls (O for 0, l for 1)
     AND props.torch_attrs IS None AND props.anni_attrs IS None THEN
    RETURN true

  -- Stash scan presenter regression
  IF input.context == "stash_scan_presenter"
     AND (get_value_breakdown fails assertion OR sort_by_name fails assertion) THEN
    RETURN true

  RETURN false
END FUNCTION
```

### Examples

- `"eth 4 os GT"` → currently `extract_props` returns `base=None` because `GT` abbreviation is matched but `4 os` regex works; however `_ocr_low_quality_signature` may drop it. Expected: `giant_thresher + eth + 4os` signature.
- `"req 1v1 9"` (OCR-corrupted `lvl`) → `RE_REQ_LVL` does not match. Expected: `req_lvl=9`.
- `"CTA +6 BO / +1 BC"` → currently produces generic runeword signature without roll detail. Expected: `runeword:cta + +6BO`.
- `"jah ith ber + eth archon plate"` (Enigma kit) → currently classified same as finished Enigma. Expected: `kit` label, separate grouping.
- `"20/2O/1O anni"` (OCR: `O` for `0`) → `RE_ANNI_TRIPLE` fails because `2O` is not a digit. Expected: `anni_attrs=20, anni_res=20, anni_xp=10`.
- `test_get_value_breakdown` → assertion error on tier counts or total values due to presenter regression.
- `test_sort_by_name` → assertion error on alphabetical ordering due to presenter regression.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- All existing correctly-parsed property signatures must produce identical output after the fix
- Variant fallback rows and market-gap rows logic in `main()` must remain unchanged
- CLI flags (`--db`, `--market-key`, `--out`, `--min-fg`, `--limit`, `--variant-fallback-min-obs`) must remain compatible
- DB schema (`observed_prices`, `threads` tables) must not be altered
- Mouse/keyboard interactions in the HTML table (search, sort, scroll) must continue working
- All currently-passing tests must continue to pass
- `_ocr_low_quality_signature()` filtering must continue to reject genuinely noisy signatures
- `_potential_tags()` and `_maxroll_magic_seed_tags()` scoring must remain unchanged for existing inputs

**Scope:**
All inputs that do NOT involve the bug conditions above should be completely unaffected by this fix. This includes:
- Excerpts that already produce correct property signatures
- Bundle/commodity variant parsing in `d2jsp_market.py`
- Slang normalization pipeline
- Image OCR pipeline (overlay modules other than stash_scan_presenter)
- Forum HTML parsing and thread extraction

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

1. **Req-Level Regex Too Narrow** (`RE_REQ_LVL` at line 82): Only matches `req N`, `req lvl N`, `lvl req N`. Missing: `rlvl N`, `lv N`, `lv1 N` (OCR), `req:N`, `req=N`, `required level N`. This is a simple regex gap — the patterns list needs expansion.

2. **No Runeword Kit Detection**: `extract_props()` has no concept of kit vs finished. The `_infer_runeword_kit_variant()` function exists in `d2jsp_market.py` (line 167) but is not used by the property table export. Need to either call it or replicate the logic in `extract_props()`.

3. **No Roll-Aware Runeword Extraction**: `extract_props()` extracts generic stats (ED, all_res, FCR) but doesn't map them to runeword-specific roll semantics (e.g. CTA's BO level, HOTO's all-res as the defining roll). Need runeword-specific extraction rules that produce roll-qualified signatures.

4. **Torch/Anni OCR Noise Not Handled**: `RE_ANNI_TRIPLE` and `RE_TORCH_ROLL` use `\d{1,2}` which rejects OCR-corrupted digits like `2O` (capital O for 0). Need OCR-folding pre-pass or relaxed digit patterns.

5. **Stash Scan Presenter Regressions**: The `get_value_breakdown` test expects specific tier counts/values and `sort_by_name` expects alphabetical order. The regression is likely in `_get_value_tier()` threshold logic or `_sort_items()` key function — possibly a change to `PresentationConfig` defaults or `ScannedItem` field access that broke the expected behavior.

6. **No Display Mode Support**: `_build_html()` generates a single grouped view. The JavaScript `render()` function has no concept of expanded-by-variant or expanded-by-listing modes. Need to embed per-observation data in the JSON payload and add JS display mode switching.

7. **No LLD Bucket Assignment**: `extract_props()` sets `lld=True` heuristically but doesn't assign a bucket label. Need a post-extraction step that maps `req_lvl` to `LLD9/LLD18/LLD30/MLD/HLD/unknown`.

8. **No Signal Split Columns**: `_signals_mix()` produces a summary string like `bin:3 sold:2`. Need to compute per-signal-type medians and expose them as separate JSON fields for the HTML table.

## Correctness Properties

Property 1: Fault Condition — Parser Gap Closure

_For any_ d2jsp excerpt where trade-relevant content is present (runeword rolls, req-level in common formats, torch/anni with OCR noise, base item shorthand, jewel/charm/circlet LLD combos), the fixed `extract_props()` SHALL extract all relevant fields and `props_signature()` SHALL return a non-None signature that includes the extracted fields.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 12.1, 12.2, 13.1, 13.2, 13.3, 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.3, 15.4**

Property 2: Preservation — Existing Signature Stability

_For any_ d2jsp excerpt that currently produces a correct, non-None property signature, the fixed `extract_props()` and `props_signature()` SHALL produce the identical signature string, preserving all existing property table rows and their metadata.

**Validates: Requirements 1.3, 3.5, 4.4**

Property 3: Fault Condition — Stash Scan Presenter Correctness

_For any_ `StashScanResult` input, the fixed `StashScanPresenter.get_value_breakdown()` SHALL return tier counts and total values consistent with the item data, and `_sort_items()` with `sort_by="name"` SHALL return items in alphabetical order by matched name.

**Validates: Requirements 1.1, 1.2, 1.3**

Property 4: Fault Condition — Kit vs Finished Discrimination

_For any_ excerpt containing a runeword name where the listing is a kit (base + individual runes without roll stats), the fixed parser SHALL classify the row as `kit`, and where the listing contains roll-specific stats, SHALL classify as `finished`. Kit and finished rows with the same runeword name SHALL appear as separate groups.

**Validates: Requirements 9.1, 9.2, 9.3, 10.2**

Property 5: Fault Condition — LLD Bucket Assignment

_For any_ row with a parsed `req_lvl`, the fixed parser SHALL assign the correct `lld_bucket` label (`LLD9` for ≤9, `LLD18` for 10-18, `LLD30` for 19-30, `MLD` for 31-49, `HLD` for ≥50). For rows with `lld=True` but no `req_lvl`, SHALL assign `LLD30` as default.

**Validates: Requirements 8.1, 8.2**

Property 6: Preservation — Filter and Sort State Across Display Modes

_For any_ filter/sort configuration active in the property table, switching between `grouped`, `expanded_by_variant`, and `expanded_by_listing` display modes SHALL preserve the current filter and sort state, and all non-display-mode UI interactions SHALL behave identically to the current implementation.

**Validates: Requirements 4.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `scripts/export_property_price_table_html.py`

**Function**: `extract_props()` and supporting regex/data structures

**Specific Changes**:

1. **Expand RE_REQ_LVL** (line 82): Add patterns for `rlvl N`, `lv N`, `lvN`, `required level N`, `req:N`, `req=N`, `rlvl:N`. Add OCR-noise variants where `l` → `1` or `I` (e.g. `req 1v1 N`, `rv1 N`). Add range validation (1-99) with discard for out-of-range.

2. **Add Runeword Kit Detection**: Add a `kit` boolean field to `ExtractedProps`. Implement detection logic: if excerpt contains base item name + individual rune names (from `_infer_runeword_kit_variant` patterns in `d2jsp_market.py`) without runeword-specific roll stats → `kit=True`. Update `props_signature()` to prefix kit signatures with `kit:`.

3. **Add Roll-Aware Runeword Extraction**: Add `ExtractedProps` fields for runeword-specific rolls: `rw_name`, `rw_bo_lvl`, `rw_all_res`, `rw_ias`, `rw_dmg`, `rw_enemy_res`, `rw_med_lvl`, `rw_ed`, `rw_fcr`. Add targeted regex patterns for CTA (BO level), HOTO (all res), Grief (IAS + damage), Infinity (-enemy res), Insight (meditation level), Spirit (FCR + all res), Fortitude (ED), BOTD (ED). Update `props_signature()` to include roll detail when present.

4. **Add OCR Digit Folding for Torch/Anni**: Before applying `RE_ANNI_TRIPLE` and `RE_TORCH_ROLL`, apply an OCR-fold pass that replaces common OCR digit confusions: `O` → `0`, `l` → `1`, `I` → `1` in numeric contexts. Reuse `ocr_fold_text()` from `modifier_lexicon.py` or implement a targeted version.

5. **Add LLD Bucket Assignment**: Add `lld_bucket` field to `ExtractedProps` or compute it in `main()` after extraction. Implement bucket logic: `req_lvl ≤ 9` → `LLD9`, `10-18` → `LLD18`, `19-30` → `LLD30`, `31-49` → `MLD`, `≥ 50` → `HLD`, `None` → `unknown` (or `LLD30` if `lld` heuristic is true).

6. **Add Signal Split Columns**: In `main()`, compute per-signal-type median FG values for each group. Add `bin_fg`, `co_fg`, `ask_fg`, `sold_fg` fields to `out_rows` dicts. Update `_build_html()` JavaScript to render separate columns.

7. **Add Display Mode Support**: Embed per-observation data (source_url, raw_excerpt, signal_kind, price_fg, observed_at) in the JSON payload. Add JavaScript display mode toggle (grouped/expanded_by_variant/expanded_by_listing) that re-renders the table while preserving filter/sort state.

8. **Add Filter Controls**: Add JavaScript filter dropdowns for row_kind, type_l1, class_tags, lld_bucket, kit/finished, unid. Implement multi-select chip UI for req-level, class, and type. Implement logical AND across dimensions, OR within dimensions.

9. **Add Last Seen Column**: Include `last_seen` (max `observed_at`) in each row dict. Add JavaScript relative-time formatting and stale-row styling (>7 days).

**File**: `src/d2lut/overlay/stash_scan_presenter.py`

**Specific Changes**:

10. **Fix get_value_breakdown**: Debug the tier assignment logic in `_get_value_tier()` against the test fixture data (Jah=5000 → high, Ber=4000 → should be medium per thresholds but test expects high). Likely the test fixture thresholds or the presenter defaults diverged. Fix to match test expectations.

11. **Fix sort_by_name**: Verify `_sort_items()` key function handles `None` matched_name correctly and produces stable alphabetical ordering matching test expectations.

**New Files**:

12. **`scripts/report_property_table_coverage.py`**: KPI report script computing property_rows, fallback_rows, market_gap_rows, property_sig_coverage, % with source link, % with req_lvl, % with class_tags, top 20 missing variants. Accepts `--min-fg` and `--json` flags.

13. **`scripts/audit_tasks_vs_tests.py`**: Compares tasks.md completion markers against pytest results. Reports regressed/completable tasks.

14. **`scripts/backfill_source_urls.py`**: Idempotent backfill of source_url from thread_id for legacy observed_prices rows.

15. **`scripts/replay_topic.py`**: Topic replay tool that reparses a thread_id and shows before/after diff. Supports `--dry-run`.

16. **`scripts/detect_suspicious_rows.py`**: Flags rows with impossible property combos, extreme price anomalies (>5x category median), contradictory type assignments. Accepts `--min-fg`.

17. **`tests/fixtures/parser_regression_corpus.py`**: Curated corpus of ≥30 real d2jsp excerpts with expected signatures covering kit/finished confusion, OCR req-levels, torch/anni misclassification, base misparsing, LLD shorthand failures.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fixes work correctly and preserve existing behavior.

### Exploratory Fault Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing fixes. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write targeted tests that exercise `extract_props()` and `props_signature()` with known-failing excerpts, and run the stash scan presenter tests. Run on UNFIXED code to observe failures.

**Test Cases**:
1. **Req-Level OCR Formats**: `extract_props("rlvl 9 sc 3/20/20")` → expect `req_lvl=9` (will fail on unfixed code: `RE_REQ_LVL` doesn't match `rlvl`)
2. **Runeword Kit Detection**: `extract_props("jah ith ber + eth archon plate")` → expect `kit=True` (will fail: no kit field exists)
3. **CTA Roll Extraction**: `extract_props("CTA +6 BO / +1 BC")` → expect roll-qualified signature (will fail: no runeword roll logic)
4. **Anni OCR Noise**: `extract_props("anni 20/2O/1O")` → expect `anni_attrs=20` (will fail: `2O` not a digit)
5. **Stash Scan Presenter**: Run `test_get_value_breakdown` and `test_sort_by_name` (will fail: known regressions)

**Expected Counterexamples**:
- `extract_props("rlvl 9 ...").req_lvl` returns `None` instead of `9`
- `extract_props("anni 20/2O/1O").anni_attrs` returns `None` instead of `20`
- `props_signature(extract_props("CTA +6 BO"))` lacks BO level detail
- `StashScanPresenter.get_value_breakdown()` returns wrong tier counts

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed functions produce the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  props := extract_props_fixed(input.excerpt, input.variant_key)
  sig := props_signature_fixed(props)
  ASSERT sig IS NOT None
  ASSERT all trade-relevant fields are extracted
  ASSERT sig includes expected roll/kit/bucket detail
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed functions produce the same result as the original functions.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT extract_props_original(input) == extract_props_fixed(input)
  ASSERT props_signature_original(extract_props_original(input))
      == props_signature_fixed(extract_props_fixed(input))
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many excerpt strings automatically across the input domain
- It catches edge cases where new regex patterns accidentally match existing content
- It provides strong guarantees that existing signatures are unchanged

**Test Plan**: Capture current `extract_props()` / `props_signature()` output for all existing test fixtures and a sample of real excerpts from the DB, then write property-based tests asserting identical output after the fix.

**Test Cases**:
1. **Existing Signature Preservation**: For every excerpt in `test_property_price_table_parser.py`, verify the fixed code produces identical `ExtractedProps` and signature
2. **Variant Fallback Preservation**: Verify variant fallback row logic produces identical rows for a sample DB snapshot
3. **HTML Filter/Sort Preservation**: Verify existing search, sort, and scroll behavior in the generated HTML is unchanged
4. **Stash Scan Non-Regression**: Verify all currently-passing `test_stash_scan_presenter.py` tests continue to pass

### Unit Tests

- Test `RE_REQ_LVL` expanded patterns against all formats in Requirement 6.1, 6.2, 6.3
- Test req-level range validation (1-99 accepted, outside discarded) per Requirement 6.4, 6.5
- Test kit vs finished detection for multi-line recipe cases per Requirement 9.1, 9.2, 9.5
- Test roll-aware extraction for each of 8 target runewords per Requirement 12.1, 12.4
- Test torch class prefix/suffix parsing per Requirement 13.1
- Test anni OCR-noise tolerance per Requirement 13.2
- Test torch/anni tier classification per Requirement 13.3
- Test base item parser for superior, eth, socketed, ED, defense per Requirement 14.1-14.5
- Test jewel/charm/circlet combo parsing per Requirement 15.1-15.4
- Test LLD bucket assignment per Requirement 8.1, 8.2
- Test `get_value_breakdown` and `sort_by_name` fixes per Requirement 1.1, 1.2

### Property-Based Tests

- Generate random d2jsp-like excerpt strings and verify `extract_props()` never crashes and `req_lvl` is always in range 1-99 or None
- Generate random `ExtractedProps` instances and verify `props_signature()` round-trips consistently (same input → same output)
- For a corpus of known-good excerpts, verify fixed code produces identical signatures (preservation property)
- Generate random LLD bucket inputs and verify bucket assignment is exhaustive and mutually exclusive

### Integration Tests

- Run `scripts/export_property_price_table_html.py` against a test DB snapshot and verify output row count ≥ current baseline
- Run `scripts/report_property_table_coverage.py` and verify KPI metrics are computed without errors
- Run `scripts/detect_suspicious_rows.py` and verify it produces output without crashes
- Run `scripts/replay_topic.py --dry-run` against a known thread_id and verify diff output
- Verify the generated HTML loads in a browser and all filter/sort/display-mode controls function
