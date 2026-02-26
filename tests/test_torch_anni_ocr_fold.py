"""Regression tests for torch/anni OCR digit folding and tier classification.

Validates:
- OCR-fold pre-pass converts common OCR digit confusions (O→0, l→1, I→1)
- Torch tier classification (perfect / near-perfect / good / average / low)
- Anni tier classification (perfect / near-perfect / good / average / low)
- Range validation discards out-of-range values

Requirements: 13.2, 13.3, 13.4, 13.5
"""

from __future__ import annotations

import pytest

from scripts.export_property_price_table_html import (
    ExtractedProps,
    _classify_anni_tier,
    _classify_torch_tier,
    _ocr_fold_digits,
    extract_props,
    props_signature,
)


# ---------------------------------------------------------------------------
# 9.1  OCR digit folding unit tests
# ---------------------------------------------------------------------------

class TestOcrFoldDigits:
    """_ocr_fold_digits replaces OCR-confused letters adjacent to digits."""

    @pytest.mark.parametrize("raw,expected", [
        ("20/2O/1O", "20/20/10"),       # capital O → 0
        ("2o/2o", "20/20"),             # lowercase o → 0
        ("l5/l8", "15/18"),             # lowercase L → 1
        ("I8/I9/IO", "18/19/10"),       # capital I → 1, chained IO → 10
        ("i8/i9/io", "18/19/10"),       # lowercase i (post-.lower()) → 1
        ("15/15/8", "15/15/8"),         # pure digits unchanged
        ("20/20", "20/20"),             # pure digits unchanged
    ])
    def test_fold_numeric_contexts(self, raw: str, expected: str) -> None:
        assert _ocr_fold_digits(raw) == expected

    @pytest.mark.parametrize("text", [
        "torch sorc",
        "cold facet",
        "anni",
        "barb torch",
        "hello world",
    ])
    def test_fold_preserves_words(self, text: str) -> None:
        """Words without digit adjacency should not be corrupted."""
        assert _ocr_fold_digits(text) == text


# ---------------------------------------------------------------------------
# 9.2  Tier classification unit tests
# ---------------------------------------------------------------------------

class TestTorchTierClassification:
    """_classify_torch_tier based on attrs + res sum (range 20-40)."""

    @pytest.mark.parametrize("attrs,res,expected_tier", [
        (20, 20, "perfect"),
        (19, 20, "near-perfect"),    # sum=39 >= 38
        (20, 18, "near-perfect"),    # sum=38 >= 38
        (18, 18, "good"),            # sum=36 >= 34
        (17, 17, "good"),            # sum=34 >= 34
        (16, 16, "average"),         # sum=32 >= 28
        (14, 14, "average"),         # sum=28 >= 28
        (13, 13, "low"),             # sum=26 < 28
        (10, 10, "low"),             # sum=20 < 28
    ])
    def test_torch_tier(self, attrs: int, res: int, expected_tier: str) -> None:
        assert _classify_torch_tier(attrs, res) == expected_tier


class TestAnniTierClassification:
    """_classify_anni_tier based on attrs + res + xp sum (range 25-50)."""

    @pytest.mark.parametrize("attrs,res,xp,expected_tier", [
        (20, 20, 10, "perfect"),
        (20, 20, 9, "near-perfect"),   # sum=49 >= 48
        (19, 20, 10, "near-perfect"),  # sum=49 >= 48
        (20, 18, 10, "near-perfect"),  # sum=48 >= 48
        (18, 18, 10, "good"),          # sum=46 >= 42
        (17, 17, 8, "good"),           # sum=42 >= 42
        (15, 15, 8, "average"),        # sum=38 >= 35
        (15, 15, 5, "average"),        # sum=35 >= 35
        (12, 12, 5, "low"),            # sum=29 < 35
        (10, 10, 5, "low"),            # sum=25 < 35
    ])
    def test_anni_tier(self, attrs: int, res: int, xp: int, expected_tier: str) -> None:
        assert _classify_anni_tier(attrs, res, xp) == expected_tier


# ---------------------------------------------------------------------------
# 9.3  Range validation — out-of-range values discarded
# ---------------------------------------------------------------------------

class TestRangeValidation:
    """Torch 10-20 attrs/res; anni 10-20 attrs/res, 5-10 xp."""

    def test_torch_below_range_discarded(self) -> None:
        """Torch attrs=9 is below valid range 10-20 → discarded."""
        p = extract_props("torch sorc 9/15")
        assert p.torch_attrs is None
        assert p.torch_res is None
        assert p.torch_tier is None

    def test_torch_above_range_discarded(self) -> None:
        """Torch attrs=21 is above valid range 10-20 → discarded."""
        p = extract_props("torch sorc 21/20")
        assert p.torch_attrs is None

    def test_torch_boundary_low_accepted(self) -> None:
        """Torch attrs=10, res=10 is the minimum valid range."""
        p = extract_props("torch sorc 10/10")
        assert p.torch_attrs == 10
        assert p.torch_res == 10
        assert p.torch_tier == "low"

    def test_anni_below_range_discarded(self) -> None:
        """Anni attrs=9 is below valid range 10-20 → discarded."""
        p = extract_props("anni 9/15/8")
        assert p.anni_attrs is None

    def test_anni_xp_above_range_discarded(self) -> None:
        """Anni xp=11 is above valid range 5-10 → discarded."""
        p = extract_props("anni 20/20/11")
        assert p.anni_attrs is None

    def test_anni_boundary_low_accepted(self) -> None:
        """Anni attrs=10, res=10, xp=5 is the minimum valid range."""
        p = extract_props("anni 10/10/5")
        assert p.anni_attrs == 10
        assert p.anni_res == 10
        assert p.anni_xp == 5
        assert p.anni_tier == "low"


# ---------------------------------------------------------------------------
# 9.4  End-to-end OCR-corrupted torch/anni regression tests
# ---------------------------------------------------------------------------

class TestOcrCorruptedTorchAnni:
    """Full extract_props + props_signature for OCR-corrupted excerpts."""

    def test_anni_capital_o_for_zero(self) -> None:
        """'anni 20/2O/1O' — capital O is OCR for 0."""
        p = extract_props("anni 20/2O/1O")
        assert p.anni_attrs == 20
        assert p.anni_res == 20
        assert p.anni_xp == 10
        assert p.anni_tier == "perfect"
        sig = props_signature(p)
        assert sig is not None
        assert "20anni_attr" in sig
        assert "10xp" in sig

    def test_torch_capital_o_for_zero(self) -> None:
        """'torch sorc 2O/2O' — capital O is OCR for 0."""
        p = extract_props("torch sorc 2O/2O")
        assert p.torch_attrs == 20
        assert p.torch_res == 20
        assert p.torch_tier == "perfect"

    def test_anni_lowercase_o_for_zero(self) -> None:
        """'anni 1O/1O/5' — after .lower() becomes '1o/1o/5'."""
        p = extract_props("anni 1O/1O/5")
        assert p.anni_attrs == 10
        assert p.anni_res == 10
        assert p.anni_xp == 5
        assert p.anni_tier == "low"

    def test_torch_lowercase_l_for_one(self) -> None:
        """'barb torch l5/l8' — lowercase L is OCR for 1."""
        p = extract_props("barb torch l5/l8")
        assert p.torch_attrs == 15
        assert p.torch_res == 18
        assert p.torch_tier == "average"

    def test_anni_capital_i_and_o_chained(self) -> None:
        """'anni I8/I9/IO' — capital I→1, O→0, chained IO→10."""
        p = extract_props("anni I8/I9/IO")
        assert p.anni_attrs == 18
        assert p.anni_res == 19
        assert p.anni_xp == 10
        assert p.anni_tier == "good"

    def test_clean_torch_still_works(self) -> None:
        """Clean digits should still parse correctly (preservation)."""
        p = extract_props("sorc torch 20/20")
        assert p.torch_attrs == 20
        assert p.torch_res == 20
        assert p.torch_class == "sorceress"
        assert p.torch_tier == "perfect"

    def test_clean_anni_still_works(self) -> None:
        """Clean digits should still parse correctly (preservation)."""
        p = extract_props("anni 15/15/8")
        assert p.anni_attrs == 15
        assert p.anni_res == 15
        assert p.anni_xp == 8
        assert p.anni_tier == "average"
