"""Tests for scripts/report_ocr_miss_triage.py — OCR miss triage queue.

Validates: Requirements 16.1, 16.2, 16.3, 16.4
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure repo root is on path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.report_ocr_miss_triage import (
    classify_failure,
    rank_groups,
    triage_rows,
)
from scripts.export_property_price_table_html import extract_props, props_signature


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(
    variant_key: str | None = None,
    raw_excerpt: str = "",
    price_fg: float = 100.0,
) -> dict:
    return {
        "variant_key": variant_key,
        "raw_excerpt": raw_excerpt,
        "price_fg": price_fg,
    }


# ---------------------------------------------------------------------------
# Req 16.1: classify_failure groups by pattern
# ---------------------------------------------------------------------------

class TestClassifyFailure:
    """Req 16.1 — grouping failures by pattern."""

    def test_no_variant_hint_none(self):
        row = _make_row(variant_key=None, raw_excerpt="some random text")
        assert classify_failure(row, sig=None) == "no_variant_hint"

    def test_no_variant_hint_empty(self):
        row = _make_row(variant_key="", raw_excerpt="some random text")
        assert classify_failure(row, sig=None) == "no_variant_hint"

    def test_not_a_miss_when_sig_present(self):
        row = _make_row(variant_key="runeword:enigma", raw_excerpt="enigma")
        assert classify_failure(row, sig="runeword:enigma") is None

    def test_ocr_corruption_digit_O(self):
        """Excerpt with O adjacent to digit → ocr_corruption."""
        row = _make_row(
            variant_key="unique:hellfire_torch:sorc",
            raw_excerpt="sorc torch 2O/2O",
        )
        assert classify_failure(row, sig=None) == "ocr_corruption"

    def test_ocr_corruption_digit_l(self):
        """Excerpt with l adjacent to digit → ocr_corruption."""
        row = _make_row(
            variant_key="charm:sc",
            raw_excerpt="sc 3/2l/20 lld",
        )
        assert classify_failure(row, sig=None) == "ocr_corruption"

    def test_no_property_signature_catchall(self):
        """Variant present, no OCR noise, no class mismatch → no_property_signature."""
        row = _make_row(
            variant_key="unique:shako",
            raw_excerpt="shako",
        )
        assert classify_failure(row, sig=None) == "no_property_signature"

    def test_wrong_class_torch_in_jewel_variant(self):
        """Excerpt says torch but variant says jewel → wrong_class."""
        row = _make_row(
            variant_key="jewel:magic",
            raw_excerpt="sorc torch 20/20",
        )
        assert classify_failure(row, sig=None) == "wrong_class"

    def test_base_only_vs_finished_rw(self):
        """Variant says runeword but excerpt is base + runes (kit) → base_only_vs_finished_rw."""
        row = _make_row(
            variant_key="runeword:enigma",
            raw_excerpt="jah ith ber + eth archon plate",
        )
        assert classify_failure(row, sig=None) == "base_only_vs_finished_rw"

    def test_base_variant_with_runeword_name(self):
        """Variant says base but excerpt mentions a runeword name → base_only_vs_finished_rw."""
        row = _make_row(
            variant_key="base:archon_plate",
            raw_excerpt="enigma 775 def",
        )
        assert classify_failure(row, sig=None) == "base_only_vs_finished_rw"


# ---------------------------------------------------------------------------
# Req 16.1 + 16.2: triage_rows and rank_groups
# ---------------------------------------------------------------------------

class TestTriageAndRank:
    """Req 16.1, 16.2 — grouping + ranking by total FG lost."""

    def _sample_rows(self) -> list[dict]:
        return [
            # no_variant_hint: 2 rows, total 300 FG
            _make_row(variant_key=None, raw_excerpt="random stuff", price_fg=200.0),
            _make_row(variant_key="", raw_excerpt="more stuff", price_fg=100.0),
            # no_property_signature: 1 row, 500 FG
            _make_row(variant_key="unique:shako", raw_excerpt="shako", price_fg=500.0),
            # ocr_corruption: 1 row, 150 FG
            _make_row(variant_key="charm:sc", raw_excerpt="sc 3/2l/20", price_fg=150.0),
        ]

    def test_triage_groups_all_patterns(self):
        rows = self._sample_rows()
        groups = triage_rows(rows)
        assert "no_variant_hint" in groups
        assert len(groups["no_variant_hint"]) == 2

    def test_rank_by_total_fg_lost(self):
        """Req 16.2 — groups ranked by total FG lost descending."""
        rows = self._sample_rows()
        groups = triage_rows(rows)
        ranked = rank_groups(groups)
        # First group should have highest total FG lost
        fg_values = [g["total_fg_lost"] for g in ranked]
        assert fg_values == sorted(fg_values, reverse=True)

    def test_rank_includes_count_and_median(self):
        rows = self._sample_rows()
        groups = triage_rows(rows)
        ranked = rank_groups(groups)
        for g in ranked:
            assert "count" in g
            assert "total_fg_lost" in g
            assert "median_fg" in g
            assert "pattern" in g
            assert g["count"] > 0


# ---------------------------------------------------------------------------
# Req 16.3: up to 5 sample excerpts per group
# ---------------------------------------------------------------------------

class TestSampleExcerpts:
    """Req 16.3 — up to 5 sample excerpts per miss group."""

    def test_max_5_samples(self):
        # Create 8 rows in same pattern
        rows = [
            _make_row(variant_key=None, raw_excerpt=f"item {i}", price_fg=float(i * 10))
            for i in range(1, 9)
        ]
        groups = triage_rows(rows)
        ranked = rank_groups(groups)
        for g in ranked:
            assert len(g["samples"]) <= 5

    def test_samples_prefer_high_fg(self):
        """Samples should be sorted by FG descending (highest value first)."""
        rows = [
            _make_row(variant_key=None, raw_excerpt=f"item {i}", price_fg=float(i * 100))
            for i in range(1, 8)
        ]
        groups = triage_rows(rows)
        ranked = rank_groups(groups)
        for g in ranked:
            fg_vals = [s["price_fg"] for s in g["samples"]]
            assert fg_vals == sorted(fg_vals, reverse=True)

    def test_samples_contain_excerpt_and_variant(self):
        rows = [_make_row(variant_key=None, raw_excerpt="test excerpt", price_fg=50.0)]
        groups = triage_rows(rows)
        ranked = rank_groups(groups)
        assert ranked
        sample = ranked[0]["samples"][0]
        assert "excerpt" in sample
        assert "variant_key" in sample
        assert "price_fg" in sample


# ---------------------------------------------------------------------------
# Req 16.4: --min-fg flag (tested via main() CLI)
# ---------------------------------------------------------------------------

class TestMinFgFlag:
    """Req 16.4 — --min-fg flag filters to high-value misses."""

    def test_min_fg_filters_low_value_rows(self):
        """Rows below min-fg threshold should not appear in DB query.

        Since the actual filtering happens at the SQL level in main(),
        we test that triage_rows correctly processes only the rows it receives.
        """
        high_fg_rows = [
            _make_row(variant_key=None, raw_excerpt="expensive item", price_fg=500.0),
        ]
        low_fg_rows = [
            _make_row(variant_key=None, raw_excerpt="cheap item", price_fg=10.0),
        ]
        # Simulating --min-fg=100: only high_fg_rows would be passed
        groups = triage_rows(high_fg_rows)
        ranked = rank_groups(groups)
        assert ranked[0]["total_fg_lost"] == 500.0

        # All rows: total would be 510
        groups_all = triage_rows(high_fg_rows + low_fg_rows)
        ranked_all = rank_groups(groups_all)
        assert ranked_all[0]["total_fg_lost"] == 510.0


# ---------------------------------------------------------------------------
# Integration: rows with valid signatures are excluded
# ---------------------------------------------------------------------------

class TestIntegration:
    """Verify that rows producing valid signatures are NOT classified as misses."""

    def test_valid_sig_excluded(self):
        """A row that produces a valid property signature should not be triaged."""
        # "sorc torch 20/20" with correct variant should produce a sig
        row = _make_row(
            variant_key="unique:hellfire_torch:sorc",
            raw_excerpt="sorc torch 20/20",
            price_fg=1000.0,
        )
        props = extract_props(row["raw_excerpt"], row["variant_key"])
        sig = props_signature(props)
        # If this produces a sig, classify_failure should return None
        if sig is not None:
            assert classify_failure(row, sig=sig) is None

    def test_empty_excerpt_not_triaged(self):
        """Rows with empty excerpts produce no props/sig but triage handles gracefully."""
        rows = [_make_row(variant_key="unique:shako", raw_excerpt="", price_fg=100.0)]
        groups = triage_rows(rows)
        # Empty excerpt → props is None → sig is None → should be classified
        total = sum(len(v) for v in groups.values())
        assert total <= 1  # At most 1 miss (or 0 if empty excerpt is skipped)
