# Requirements Document

## Introduction

This spec covers a focused quality sprint for the `property_price_table.html` output, parser hardening, LLD support, and data correctness tooling in d2lut. The goal is to increase the usefulness and accuracy of the property table as the primary KPI-driven artifact for D2R trading decisions. The sprint addresses parser gaps (req-level, runeword rolls, torch/anni/base/jewel/charm), adds display modes and filters, introduces LLD segmentation, and builds data quality tooling (coverage reports, suspicious row detection, topic replay).

Key KPIs driving this sprint:
- `property_rows` (total useful rows in property table)
- `property_sig_coverage` (% of observed prices that produce a valid property signature)
- `rows_with_source_link` (% of rows with a clickable d2jsp thread link)
- `rows_with_req_lvl` (% of rows where req level is parsed)
- `top_missing_variants` (high-FG variants with no property signature)
- `ocr_mismatch_rate_by_class` (precision/recall of OCR parsing per item class)

## Glossary

- **Property_Table**: The `property_price_table.html` browser artifact exported by `scripts/export_property_price_table_html.py`, showing aggregated property-combo pricing from observed d2jsp listings.
- **Property_Signature**: A structured string produced by `props_signature()` summarizing extracted item properties (e.g. `"sorc_cold_skiller + GC + 40life"`).
- **Property_Parser**: The `extract_props()` function and associated regex patterns in `scripts/export_property_price_table_html.py` that extract item properties from raw d2jsp excerpts.
- **Req_Level_Parser**: The subset of Property_Parser responsible for extracting required level from excerpts (currently `RE_REQ_LVL` patterns).
- **LLD_Bucket**: A categorical label (`LLD9`, `LLD18`, `LLD30`, `MLD`, `HLD`, `unknown`) assigned to property rows based on parsed or heuristic required level.
- **Row_Kind**: Classification of a property table row as `property` (has valid signature), `fallback` (uses item-level fallback pricing), or `market_gap` (high-FG variant with no property signature).
- **Coverage_Reporter**: The `scripts/report_property_table_coverage.py` script that computes and prints property table KPI metrics.
- **Stash_Scan_Presenter**: The `src/d2lut/overlay/stash_scan_presenter.py` module providing formatted stash scan output.
- **Suspicious_Row_Detector**: A component that flags property table rows with likely-wrong data (impossible property combos, category pollution, extreme price anomalies).
- **Topic_Replay_Tool**: A CLI tool that reparses a targeted d2jsp topic and shows before/after diff of extracted observations.
- **Kit**: A listing where base item + runes are sold as components (not a finished runeword).
- **Roll_Signature**: Property signature extension that includes specific roll values for runewords (e.g. CTA `+6BO`, HOTO `40@`).
- **OCR_Excerpt**: The `raw_excerpt` field in `observed_prices` containing the original text from which properties are extracted.
- **Display_Mode**: One of `grouped` (default aggregated view), `expanded_by_variant` (one row per variant), or `expanded_by_listing` (one row per observation).

## Requirements

### Requirement 1: Fix Stash Scan Presenter Regressions

**User Story:** As a developer, I want the stash scan presenter tests to pass, so that task 27 in the overlay spec can be marked complete and the test suite stays green.

#### Acceptance Criteria

1. WHEN the test suite is executed, THE Stash_Scan_Presenter SHALL pass `test_get_value_breakdown` without assertion errors
2. WHEN the test suite is executed, THE Stash_Scan_Presenter SHALL pass `test_sort_by_name` without assertion errors
3. WHEN both regressions are fixed, THE test suite SHALL report zero failures across all `test_stash_scan_presenter.py` tests

### Requirement 2: Automated Task Audit Script

**User Story:** As a developer, I want an automated script that verifies tasks.md completion status against actual test results, so that I can detect stale task markers without manual cross-referencing.

#### Acceptance Criteria

1. THE Coverage_Reporter SHALL provide a `scripts/audit_tasks_vs_tests.py` script that compares task completion markers in `tasks.md` against pytest results
2. WHEN a task is marked `[x]` but its associated tests fail, THE script SHALL report the task as `regressed`
3. WHEN a task is marked `[ ]` but its associated tests pass, THE script SHALL report the task as `completable`
4. THE script SHALL exit with a non-zero code when any regressions are detected

### Requirement 3: Property Table Display Mode Filters

**User Story:** As a trader, I want to filter property table rows by kind, item type, class, and identification status, so that I can focus on the subset of data relevant to my current trading activity.

#### Acceptance Criteria

1. THE Property_Table SHALL provide a Row_Kind filter with options: `property`, `fallback`, `market-gap`, and `all`
2. THE Property_Table SHALL provide a Type1 filter with options: `runeword`, `bundle`, `unique`, `base`, `rune`, and `all`
3. THE Property_Table SHALL provide a Class filter matching the seven D2R character classes plus `all`
4. THE Property_Table SHALL provide an Unidentified filter to show or hide rows tagged as unidentified items
5. WHEN multiple filters are active simultaneously, THE Property_Table SHALL apply all filters as a logical AND

### Requirement 4: Property Table Expanded Display Modes

**User Story:** As a trader, I want to see raw observations behind aggregated rows, so that I can judge price spread and identify outliers without relying solely on median values.

#### Acceptance Criteria

1. THE Property_Table SHALL support a `grouped` display mode that aggregates observations by property signature (current default behavior)
2. THE Property_Table SHALL support an `expanded_by_variant` display mode that shows one row per unique variant key within each property signature group
3. THE Property_Table SHALL support an `expanded_by_listing` display mode that shows one row per individual observation with its source link and raw excerpt
4. WHEN switching between display modes, THE Property_Table SHALL preserve the current filter and sort state

### Requirement 5: Property Table Coverage KPI Report

**User Story:** As a developer, I want a coverage report script that quantifies property table quality metrics, so that I can measure progress and identify the highest-impact gaps.

#### Acceptance Criteria

1. THE Coverage_Reporter SHALL compute and print: `property_rows`, `fallback_rows`, `market_gap_rows`, `property_sig_coverage` (ratio of observed prices producing a valid signature)
2. THE Coverage_Reporter SHALL compute and print: `% rows with source link`, `% rows with req_lvl`, `% rows with class_tags`
3. THE Coverage_Reporter SHALL list the top 20 missing variants by FG value (variants with `>=50fg` that lack a property signature)
4. THE Coverage_Reporter SHALL accept `--min-fg` flag to filter metrics to rows above a FG threshold
5. THE Coverage_Reporter SHALL output results to stdout in a human-readable format and optionally to JSON with `--json` flag

### Requirement 6: Req-Level Parser Hardening

**User Story:** As a trader, I want the parser to recognize all common d2jsp and OCR-corrupted required-level formats, so that LLD filtering works on real-world listings.

#### Acceptance Criteria

1. THE Req_Level_Parser SHALL recognize the following formats: `req 9`, `req9`, `rlvl 9`, `lvl9`, `lv9`, `required lvl 9`, `required level 9`, `lvl req 9`
2. THE Req_Level_Parser SHALL recognize OCR-noise variants where `l` is substituted with `1` or `I` (e.g. `req 1v1 9`, `rv1 9`)
3. THE Req_Level_Parser SHALL recognize formats with colons and equals signs (e.g. `req:9`, `req=9`, `rlvl:9`)
4. WHEN a req-level value is parsed, THE Req_Level_Parser SHALL produce an integer in the range 1-99
5. IF the parsed req-level value is outside the range 1-99, THEN THE Req_Level_Parser SHALL discard the value and set `req_lvl` to None
6. THE Req_Level_Parser SHALL include regression test fixtures covering charms, jewels, circlets, and LLD excerpts

### Requirement 7: LLD Heuristic Filter and Tagging

**User Story:** As an LLD trader, I want items tagged with LLD relevance even when no explicit req level is present, so that I can find LLD-tradeable items that lack explicit level annotations.

#### Acceptance Criteria

1. WHEN the text contains the keyword `lld` (case-insensitive), THE Property_Parser SHALL set the `lld` flag to true
2. WHEN a charm or jewel has properties typical of LLD trading (max/ar/life, fhr, single-res combos) and no req level exceeds 30, THE Property_Parser SHALL set the `lld` flag to true
3. WHEN a circlet, coronet, tiara, or diadem has `2/20` or class-skill + FCR combo and req level is absent or <=30, THE Property_Parser SHALL set the `lld` flag to true
4. THE Property_Table SHALL provide an LLD filter mode with options: `exact` (only rows with parsed req_lvl), `heuristic` (includes inferred LLD), `both`, and `off`

### Requirement 8: LLD Bucket Segmentation

**User Story:** As an LLD trader, I want items segmented into standard LLD brackets (9, 18, 30) and MLD/HLD, so that I can filter for the specific level bracket I trade in.

#### Acceptance Criteria

1. THE Property_Parser SHALL assign an `lld_bucket` label to each row: `LLD9` (req_lvl <= 9), `LLD18` (req_lvl 10-18), `LLD30` (req_lvl 19-30), `MLD` (req_lvl 31-49), `HLD` (req_lvl >= 50), `unknown` (no req_lvl parsed)
2. WHEN `lld_bucket` is `unknown` but the `lld` heuristic flag is true, THE Property_Parser SHALL assign `LLD30` as the default bucket
3. THE Property_Table SHALL provide an LLD Bucket filter dropdown with all six bucket options plus `all`
4. THE Property_Table SHALL display the `lld_bucket` value as a visible column or pill badge on each row

### Requirement 9: Runeword Kit vs Finished Detection

**User Story:** As a trader, I want the parser to distinguish kit listings (base + runes sold separately) from finished runewords, so that pricing is not polluted by kit-vs-finished confusion.

#### Acceptance Criteria

1. WHEN a listing contains base item name plus individual rune names without runeword-specific roll stats, THE Property_Parser SHALL classify the row as `kit`
2. WHEN a listing contains a runeword name with roll-specific stats (e.g. ED%, all res, BO level), THE Property_Parser SHALL classify the row as `finished`
3. THE Property_Table SHALL display a `KIT` label on rows classified as kit listings
4. THE Property_Table SHALL allow filtering by `kit` vs `finished` vs `all` for runeword-type rows
5. THE Property_Parser SHALL include regression test fixtures for multi-line recipe cases where runes are spread across lines

### Requirement 10: Kit-Aware Table Display

**User Story:** As a trader, I want kit rows visually distinguished from finished runeword rows, so that I do not confuse component pricing with completed item pricing.

#### Acceptance Criteria

1. THE Property_Table SHALL render kit rows with a distinct visual indicator (colored `KIT` pill badge)
2. WHEN a kit row and a finished row share the same runeword name, THE Property_Table SHALL display them as separate groups in grouped mode
3. THE Property_Table SHALL include kit/finished status in the exported JSON data for programmatic consumers

### Requirement 11: Source Link Backfill

**User Story:** As a developer, I want to backfill missing thread_id and source_url for legacy observed_prices rows, so that more property table rows have clickable source links.

#### Acceptance Criteria

1. THE Coverage_Reporter SHALL report the current `% rows with source link` before and after backfill
2. WHEN a row in `observed_prices` lacks `source_url` but has a matching `thread_id` in the `threads` table, THE backfill script SHALL populate the `source_url` from the thread URL
3. WHEN a row cannot be backfilled (no matching thread), THE backfill script SHALL log the row as unresolvable
4. THE backfill script SHALL be idempotent (running it multiple times produces the same result)

### Requirement 12: Roll-Aware Runeword Property Extraction

**User Story:** As a trader, I want property signatures for top runewords that include their specific roll values, so that I can distinguish premium rolls from average ones in the property table.

#### Acceptance Criteria

1. THE Property_Parser SHALL extract roll-specific properties for CTA (Battle Orders level), HOTO (all res), Grief (IAS, damage), Infinity (-enemy res), Insight (meditation level), Spirit (FCR, all res), Fortitude (ED), and BOTD (ED)
2. WHEN roll values are present in the excerpt, THE Property_Parser SHALL include them in the Property_Signature (e.g. `"runeword:cta + +6BO"`)
3. WHEN roll values are absent, THE Property_Parser SHALL produce a generic runeword signature without roll detail
4. THE Property_Parser SHALL include regression test fixtures for each of the eight target runewords with both rolled and unrolled excerpts

### Requirement 13: Torch and Anni Parser v2

**User Story:** As a trader, I want improved torch and anni parsing that handles OCR noise, class detection, and tier classification, so that the property table accurately reflects torch/anni market segments.

#### Acceptance Criteria

1. THE Property_Parser SHALL parse torch class from both prefix and suffix positions (e.g. `"sorc torch"` and `"torch sorc"`)
2. THE Property_Parser SHALL parse anni triple rolls in format `attrs/res/xp` with OCR-noise tolerance (e.g. `"20/2O/1O"` where `O` is misread `0`)
3. THE Property_Parser SHALL classify torch and anni rolls into tiers: `perfect` (max rolls), `near-perfect` (within 1-2 of max), `good`, `average`, `low`
4. THE Property_Parser SHALL detect `unid` torch and anni listings and tag them distinctly from identified ones
5. IF the parsed roll values fall outside valid game ranges (torch: 10-20 attrs/res; anni: 10-20 attrs/res, 5-10 xp), THEN THE Property_Parser SHALL discard the roll values

### Requirement 14: Base Item Parser v2

**User Story:** As a trader, I want the base item parser to handle superior, ethereal, socketed, ED, and defense values with OCR-noise tolerance, so that base item property signatures are accurate.

#### Acceptance Criteria

1. THE Property_Parser SHALL recognize `superior` and `sup` prefixes on base items
2. THE Property_Parser SHALL parse defense values from formats: `Ndef`, `def N`, `defense N`, `defense: N`
3. THE Property_Parser SHALL parse socket counts from formats: `N os`, `Nos`, `N soc`, `N socket`, `socketed (N)`
4. THE Property_Parser SHALL parse ED from formats: `N% ed`, `Ned`, `N% enhanced damage`
5. THE Property_Parser SHALL prioritize trade-relevant bases: monarch, archon plate, mage plate, thresher, giant thresher, cryptic axe, colossus voulge, great poleaxe, phase blade, berserker axe
6. THE Property_Parser SHALL include regression test fixtures for OCR-corrupted base excerpts (e.g. `"eth 4 os GT"`, `"sup mp 15ed"`)

### Requirement 15: Jewel, Charm, and Circlet Parser v2

**User Story:** As a trader, I want improved parsing for jewels, charms, and circlets covering LLD/PvP shorthand combos, so that the property table captures the full value of these items.

#### Acceptance Criteria

1. THE Property_Parser SHALL parse jewel combos: `ias/ed` (e.g. `"15ias/40ed"`), `max/ar/life`, `fhr`, `frw`, and req-level
2. THE Property_Parser SHALL parse charm combos: `3/20/20` (max/ar/life), `fhr/res`, `life/res`, `mf/res` for SC/LC/GC sizes
3. THE Property_Parser SHALL parse circlet combos: `2/20` (skills/fcr), `3/20/20` (skills/fcr/other), class-specific skill trees, FRW, sockets
4. THE Property_Parser SHALL handle slash-separated shorthand (e.g. `"15/40"` for ias/ed jewel) when item context (jewel/charm/circlet) is present
5. THE Property_Parser SHALL include regression test fixtures for at least 5 real d2jsp LLD excerpts per item type (jewel, SC, LC, GC, circlet)

### Requirement 16: OCR Miss Triage Queue

**User Story:** As a developer, I want a report of top OCR parsing misses grouped by failure pattern, so that I can prioritize parser improvements by impact.

#### Acceptance Criteria

1. THE Coverage_Reporter SHALL generate a miss triage report grouping failures by pattern: `no_variant_hint`, `wrong_class`, `ocr_corruption`, `base_only_vs_finished_rw`, `no_property_signature`
2. THE Coverage_Reporter SHALL rank miss groups by total FG value lost (sum of median FG for rows in each group)
3. THE Coverage_Reporter SHALL include up to 5 sample excerpts per miss group for manual review
4. THE Coverage_Reporter SHALL accept `--min-fg` flag to focus on high-value misses

### Requirement 17: Modifier Lexicon Integration for Property Parsing

**User Story:** As a developer, I want the modifier lexicon used to validate and score property token extraction, so that impossible property combos are rejected and parser precision improves.

#### Acceptance Criteria

1. WHEN the Property_Parser extracts properties from an excerpt, THE Property_Parser SHALL validate extracted property names against the modifier lexicon
2. WHEN an extracted property combination is impossible for the detected item category (e.g. FCR on a weapon base), THE Property_Parser SHALL discard the impossible property
3. THE Property_Parser SHALL use modifier lexicon scoring to prefer higher-confidence property interpretations when ambiguous regex matches exist
4. THE Property_Parser SHALL log rejected properties with reason codes for diagnostic review

### Requirement 18: OCR Quality Dashboard by Class and Type

**User Story:** As a developer, I want precision/recall metrics for OCR property parsing broken down by item class and type, so that I can identify which item categories need parser attention.

#### Acceptance Criteria

1. THE Coverage_Reporter SHALL compute precision and recall for property extraction grouped by item class: `runeword`, `torch`, `anni`, `base`, `jewel`, `charm`, `circlet`, `other`
2. THE Coverage_Reporter SHALL include up to 3 mismatch sample excerpts per class for manual review
3. THE Coverage_Reporter SHALL compare extracted Property_Signature against `observed_variant_hint` (when available) as ground truth
4. THE Coverage_Reporter SHALL output results to stdout and optionally to JSON with `--json` flag

### Requirement 19: Saved Filter Presets

**User Story:** As a trader, I want saved filter presets for common trading workflows, so that I can switch between views without re-entering filter criteria each time.

#### Acceptance Criteria

1. THE Property_Table SHALL provide built-in presets: `Commodities`, `Runewords`, `Torches/Annis`, `LLD`, `Bases`, `No source link`, `High FG + low confidence`
2. WHEN a preset is selected, THE Property_Table SHALL apply the corresponding filter combination immediately
3. THE Property_Table SHALL allow users to save custom filter combinations as named presets stored in browser localStorage
4. THE Property_Table SHALL allow users to delete custom presets

### Requirement 20: Multi-Filter Chips for Req/Class/Type

**User Story:** As a trader, I want multi-select filter chips for req level, class, and type, so that I can combine multiple values in a single filter dimension.

#### Acceptance Criteria

1. THE Property_Table SHALL render Req Level, Class, and Type filters as selectable chip groups (multi-select toggle buttons)
2. WHEN multiple chips are selected within a single filter dimension, THE Property_Table SHALL apply them as logical OR within that dimension
3. WHEN chips are selected across different dimensions, THE Property_Table SHALL apply them as logical AND between dimensions
4. THE Property_Table SHALL visually indicate active chips with a distinct background color

### Requirement 21: Last Seen / Freshness Column

**User Story:** As a trader, I want to see when each property row was last observed, so that I can judge whether pricing data is current or stale.

#### Acceptance Criteria

1. THE Property_Table SHALL display a `Last Seen` column showing the most recent observation timestamp for each row
2. THE Property_Table SHALL format the timestamp as relative time (e.g. `"2h ago"`, `"3d ago"`)
3. WHEN a row has not been observed in more than 7 days, THE Property_Table SHALL visually mark the row as stale (muted text color)
4. THE Property_Table SHALL support sorting by the `Last Seen` column

### Requirement 22: Signal Mix Split Columns

**User Story:** As a trader, I want BIN, c/o, ASK, and SOLD prices shown as separate columns, so that I can compare signal types without them being blended into a single median.

#### Acceptance Criteria

1. THE Property_Table SHALL display separate numeric columns for `BIN`, `c/o`, `ASK`, and `SOLD` signal types
2. WHEN a signal type has no observations for a row, THE Property_Table SHALL display an empty cell for that column
3. THE Property_Table SHALL compute per-signal-type median values when multiple observations exist for the same signal type
4. THE Property_Table SHALL support sorting by each individual signal column

### Requirement 23: Suspicious Row Detector

**User Story:** As a developer, I want automatic detection of likely-wrong property table rows, so that I can prioritize parser fixes on the highest-impact data quality issues.

#### Acceptance Criteria

1. THE Suspicious_Row_Detector SHALL flag rows where extracted properties are impossible for the item category (e.g. FCR on a rune listing)
2. THE Suspicious_Row_Detector SHALL flag rows where the median FG deviates by more than 5x from the category median (extreme price anomaly)
3. THE Suspicious_Row_Detector SHALL flag rows where the excerpt text and the assigned Type1 category are contradictory
4. THE Suspicious_Row_Detector SHALL output flagged rows with reason codes and sample excerpts
5. THE Suspicious_Row_Detector SHALL accept `--min-fg` flag to focus on high-value suspicious rows

### Requirement 24: Topic Replay Tool

**User Story:** As a developer, I want to reparse a specific d2jsp topic and see a before/after diff of extracted observations, so that I can iterate on parser changes with targeted feedback.

#### Acceptance Criteria

1. WHEN given a thread_id, THE Topic_Replay_Tool SHALL reparse the topic HTML and extract observations using the current parser
2. THE Topic_Replay_Tool SHALL compare new observations against existing observations in the database
3. THE Topic_Replay_Tool SHALL display a diff showing added, removed, and changed observations with field-level detail
4. THE Topic_Replay_Tool SHALL support `--dry-run` mode that shows the diff without modifying the database

### Requirement 25: Parser Regression Corpus

**User Story:** As a developer, I want a curated corpus of real d2jsp excerpts that previously caused parser errors, so that parser changes can be validated against known bad cases.

#### Acceptance Criteria

1. THE regression corpus SHALL contain at least 30 real d2jsp excerpts covering: runeword kit/finished confusion, OCR-corrupted req levels, torch/anni misclassification, base item misparsing, LLD charm/jewel shorthand failures
2. THE regression corpus SHALL be stored as a pytest fixture file loadable by the test suite
3. WHEN the parser is modified, THE test suite SHALL validate all corpus entries produce expected Property_Signatures
4. THE regression corpus SHALL include the expected Property_Signature and expected extracted properties for each entry
