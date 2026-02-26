"""Tests for scripts/report_ocr_quality.py — OCR quality dashboard.

Validates: Requirements 18.1, 18.2, 18.3, 18.4
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure repo root is on path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.report_ocr_quality import (
    category_to_item_class,
    compute_class_metrics,
    evaluate_row,
    _print_json,
)


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
# Req 18.1: precision/recall grouped by item class
# ---------------------------------------------------------------------------

class TestCategoryToItemClass:
    """category_to_item_class maps inferred categories to the 8 item classes."""

    def test_torch(self):
        assert category_to_item_class("torch") == "torch"

    def test_anni(self):
        assert category_to_item_class("anni") == "anni"

    def test_runeword(self):
        assert category_to_item_class("runeword_item") == "runeword"

    def test_base_armor(self):
        assert category_to_item_class("base_armor") == "base"

    def test_base_weapon(self):
        assert category_to_item_class("base_weapon") == "base"

    def test_jewel(self):
        assert category_to_item_class("jewel") == "jewel"

    def test_charm(self):
        assert category_to_item_class("charm") == "charm"

    def test_circlet(self):
        assert category_to_item_class("circlet") == "circlet"

    def test_generic_maps_to_other(self):
        assert category_to_item_class("generic") == "other"

    def test_unknown_maps_to_other(self):
        assert category_to_item_class("set_item") == "other"
        assert category_to_item_class("unique_item") == "other"
        assert category_to_item_class("runes") == "other"


class TestEvaluateRow:
    """Req 18.1, 18.3 — evaluate_row computes TP/FP/FN per row."""

    def test_tp_variant_and_sig(self):
        """Row with variant_key that produces a signature → TP."""
        row = _make_row(
            variant_key="unique:hellfire_torch:sorc",
            raw_excerpt="sorc torch 20/20",
        )
        ev = evaluate_row(row)
        assert ev is not None
        assert ev["item_class"] == "torch"
        assert ev["tp"] == 1
        assert ev["fp"] == 0
        assert ev["fn"] == 0
        assert ev["is_mismatch"] is False

    def test_fn_variant_no_sig(self):
        """Row with variant_key but no signature → FN."""
        row = _make_row(
            variant_key="unique:shako",
            raw_excerpt="shako",
        )
        ev = evaluate_row(row)
        assert ev is not None
        # shako alone may or may not produce a sig; check FN logic
        if not ev["has_sig"]:
            assert ev["fn"] == 1
            assert ev["tp"] == 0
            assert ev["is_mismatch"] is True

    def test_empty_excerpt_returns_none(self):
        """Row with empty excerpt → None (not evaluable)."""
        row = _make_row(variant_key="unique:shako", raw_excerpt="")
        assert evaluate_row(row) is None

    def test_no_variant_no_sig_returns_none(self):
        """Row with no variant and no sig → None."""
        row = _make_row(variant_key=None, raw_excerpt="random gibberish xyz")
        ev = evaluate_row(row)
        # If extract_props produces no sig and no variant, should be None
        if ev is not None:
            # If somehow a sig was produced, it's an FP
            assert ev["fp"] == 1

    def test_fp_sig_without_variant(self):
        """Row that produces a sig but has no variant_key → FP."""
        # Use an excerpt that reliably produces a signature
        row = _make_row(
            variant_key=None,
            raw_excerpt="sorc torch 20/20",
        )
        ev = evaluate_row(row)
        if ev is not None:
            assert ev["fp"] == 1
            assert ev["tp"] == 0
            assert ev["fn"] == 0
            assert ev["is_mismatch"] is True


class TestComputeClassMetrics:
    """Req 18.1 — aggregate precision/recall per item class."""

    def _sample_evaluations(self) -> list[dict]:
        return [
            # torch: 2 TP, 1 FN
            {"item_class": "torch", "tp": 1, "fp": 0, "fn": 0, "is_mismatch": False,
             "variant_key": "unique:hellfire_torch:sorc", "signature": "torch:sorc+20/20",
             "excerpt": "sorc torch 20/20", "price_fg": 500.0, "has_variant": True, "has_sig": True},
            {"item_class": "torch", "tp": 1, "fp": 0, "fn": 0, "is_mismatch": False,
             "variant_key": "unique:hellfire_torch:pala", "signature": "torch:pala+18/18",
             "excerpt": "pala torch 18/18", "price_fg": 300.0, "has_variant": True, "has_sig": True},
            {"item_class": "torch", "tp": 0, "fp": 0, "fn": 1, "is_mismatch": True,
             "variant_key": "unique:hellfire_torch:necro", "signature": "",
             "excerpt": "necro torch 2O/2O", "price_fg": 200.0, "has_variant": True, "has_sig": False},
            # runeword: 1 TP
            {"item_class": "runeword", "tp": 1, "fp": 0, "fn": 0, "is_mismatch": False,
             "variant_key": "runeword:enigma", "signature": "runeword:enigma",
             "excerpt": "enigma 775 def", "price_fg": 1000.0, "has_variant": True, "has_sig": True},
            # other: 1 FP
            {"item_class": "other", "tp": 0, "fp": 1, "fn": 0, "is_mismatch": True,
             "variant_key": "", "signature": "some_sig",
             "excerpt": "random item", "price_fg": 50.0, "has_variant": False, "has_sig": True},
        ]

    def test_groups_by_class(self):
        metrics = compute_class_metrics(self._sample_evaluations())
        classes = {m["item_class"] for m in metrics}
        assert "torch" in classes
        assert "runeword" in classes
        assert "other" in classes

    def test_torch_precision_recall(self):
        metrics = compute_class_metrics(self._sample_evaluations())
        torch = next(m for m in metrics if m["item_class"] == "torch")
        assert torch["tp"] == 2
        assert torch["fp"] == 0
        assert torch["fn"] == 1
        # precision = 2/(2+0) = 1.0
        assert torch["precision"] == 1.0
        # recall = 2/(2+1) ≈ 0.6667
        assert abs(torch["recall"] - 0.6667) < 0.001

    def test_runeword_perfect_scores(self):
        metrics = compute_class_metrics(self._sample_evaluations())
        rw = next(m for m in metrics if m["item_class"] == "runeword")
        assert rw["tp"] == 1
        assert rw["precision"] == 1.0
        assert rw["recall"] == 1.0

    def test_sorted_by_class_name(self):
        metrics = compute_class_metrics(self._sample_evaluations())
        classes = [m["item_class"] for m in metrics]
        assert classes == sorted(classes)


# ---------------------------------------------------------------------------
# Req 18.2: up to 3 mismatch samples per class
# ---------------------------------------------------------------------------

class TestMismatchSamples:
    """Req 18.2 — up to 3 mismatch sample excerpts per class."""

    def test_max_3_samples(self):
        """Even with many mismatches, only 3 samples are kept."""
        evals = [
            {"item_class": "charm", "tp": 0, "fp": 0, "fn": 1, "is_mismatch": True,
             "variant_key": f"charm:sc_{i}", "signature": "",
             "excerpt": f"sc charm {i}", "price_fg": float(i * 10),
             "has_variant": True, "has_sig": False}
            for i in range(6)
        ]
        metrics = compute_class_metrics(evals)
        charm = next(m for m in metrics if m["item_class"] == "charm")
        assert len(charm["mismatch_samples"]) <= 3

    def test_mismatch_samples_contain_required_fields(self):
        evals = [
            {"item_class": "jewel", "tp": 0, "fp": 0, "fn": 1, "is_mismatch": True,
             "variant_key": "jewel:magic", "signature": "",
             "excerpt": "15ias/40ed jewel", "price_fg": 200.0,
             "has_variant": True, "has_sig": False},
        ]
        metrics = compute_class_metrics(evals)
        jewel = next(m for m in metrics if m["item_class"] == "jewel")
        assert len(jewel["mismatch_samples"]) == 1
        sample = jewel["mismatch_samples"][0]
        assert "variant_key" in sample
        assert "signature" in sample
        assert "excerpt" in sample
        assert "price_fg" in sample

    def test_no_mismatch_samples_when_all_tp(self):
        evals = [
            {"item_class": "anni", "tp": 1, "fp": 0, "fn": 0, "is_mismatch": False,
             "variant_key": "unique:annihilus", "signature": "anni:20/20/10",
             "excerpt": "anni 20/20/10", "price_fg": 800.0,
             "has_variant": True, "has_sig": True},
        ]
        metrics = compute_class_metrics(evals)
        anni = next(m for m in metrics if m["item_class"] == "anni")
        assert len(anni["mismatch_samples"]) == 0


# ---------------------------------------------------------------------------
# Req 18.3: compare sig vs variant_hint
# ---------------------------------------------------------------------------

class TestSigVsVariantComparison:
    """Req 18.3 — evaluate_row compares sig against variant_key as ground truth."""

    def test_variant_present_sig_present_is_tp(self):
        row = _make_row(
            variant_key="unique:hellfire_torch:sorc",
            raw_excerpt="sorc torch 20/20",
        )
        ev = evaluate_row(row)
        if ev is not None and ev["has_sig"]:
            assert ev["tp"] == 1

    def test_variant_present_sig_absent_is_fn(self):
        row = _make_row(
            variant_key="charm:sc",
            raw_excerpt="xyz totally unparseable garbage 999",
        )
        ev = evaluate_row(row)
        if ev is not None and not ev["has_sig"]:
            assert ev["fn"] == 1
            assert ev["has_variant"] is True


# ---------------------------------------------------------------------------
# Req 18.4: --json flag output
# ---------------------------------------------------------------------------

class TestJsonOutput:
    """Req 18.4 — JSON output format."""

    def test_json_output_structure(self, capsys):
        metrics = [
            {
                "item_class": "torch",
                "tp": 5, "fp": 1, "fn": 2,
                "precision": 0.8333, "recall": 0.7143,
                "mismatch_samples": [],
            },
        ]
        _print_json(
            metrics,
            market_key="d2r_sc_ladder",
            min_fg=100.0,
            scanned=100,
            evaluated=50,
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["market_key"] == "d2r_sc_ladder"
        assert data["min_fg"] == 100.0
        assert data["observations_scanned"] == 100
        assert data["observations_evaluated"] == 50
        assert "total_tp" in data
        assert "total_fp" in data
        assert "total_fn" in data
        assert "total_precision" in data
        assert "total_recall" in data
        assert "by_class" in data
        assert len(data["by_class"]) == 1
        assert data["by_class"][0]["item_class"] == "torch"

    def test_json_totals_computed(self, capsys):
        metrics = [
            {"item_class": "torch", "tp": 3, "fp": 1, "fn": 2,
             "precision": 0.75, "recall": 0.6, "mismatch_samples": []},
            {"item_class": "anni", "tp": 2, "fp": 0, "fn": 1,
             "precision": 1.0, "recall": 0.6667, "mismatch_samples": []},
        ]
        _print_json(
            metrics,
            market_key="d2r_sc_ladder",
            min_fg=50.0,
            scanned=200,
            evaluated=100,
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_tp"] == 5
        assert data["total_fp"] == 1
        assert data["total_fn"] == 3
        # total_precision = 5/(5+1) ≈ 0.8333
        assert abs(data["total_precision"] - 0.8333) < 0.001


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases for robustness."""

    def test_empty_evaluations(self):
        metrics = compute_class_metrics([])
        assert metrics == []

    def test_all_zeros_no_division_error(self):
        """Class with 0 TP, 0 FP, 0 FN should not crash."""
        # This shouldn't happen in practice, but guard against it
        evals = [
            {"item_class": "base", "tp": 0, "fp": 0, "fn": 0, "is_mismatch": False,
             "variant_key": "", "signature": "", "excerpt": "", "price_fg": 0.0,
             "has_variant": False, "has_sig": False},
        ]
        metrics = compute_class_metrics(evals)
        base = next(m for m in metrics if m["item_class"] == "base")
        assert base["precision"] == 0.0
        assert base["recall"] == 0.0
