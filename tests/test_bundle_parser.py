"""Tests for the overlay bundle parser."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from d2lut.overlay.bundle_parser import (
    BundleDefinition,
    BundleParser,
    BundleResult,
    DetectedBundle,
)


# Helper to get bundle names from a result
def _bundle_names(result: BundleResult) -> list[str]:
    return [b.bundle_name for b in result.bundles]


# ------------------------------------------------------------------
# detect_bundles – rune bundles
# ------------------------------------------------------------------


def test_detect_spirit_rune_bundle():
    parser = BundleParser()
    result = parser.detect_bundles(["Tal", "Thul", "Ort", "Amn"])
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Spirit"
    assert result.bundles[0].bundle_type == "rune"
    assert len(result.remaining_items) == 0


def test_detect_enigma_rune_bundle():
    parser = BundleParser()
    result = parser.detect_bundles(["Jah", "Ith", "Ber"])
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Enigma"


def test_detect_infinity_duplicate_ber():
    """Infinity requires 2× Ber — duplicates must be handled."""
    parser = BundleParser()
    result = parser.detect_bundles(["Ber", "Mal", "Ber", "Ist"])
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Infinity"
    assert len(result.remaining_items) == 0


def test_incomplete_rune_bundle_not_detected():
    parser = BundleParser()
    result = parser.detect_bundles(["Jah", "Ith"])  # missing Ber for Enigma
    assert len(result.bundles) == 0
    assert len(result.remaining_items) == 2


# ------------------------------------------------------------------
# detect_bundles – set bundles
# ------------------------------------------------------------------


def test_detect_key_set():
    parser = BundleParser()
    items = ["Key of Terror", "Key of Hate", "Key of Destruction"]
    result = parser.detect_bundles(items)
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Key Set"
    assert result.bundles[0].bundle_type == "set"


def test_detect_organ_set():
    parser = BundleParser()
    items = ["Mephisto's Brain", "Diablo's Horn", "Baal's Eye"]
    result = parser.detect_bundles(items)
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Organ Set"


# ------------------------------------------------------------------
# detect_bundles – remaining items
# ------------------------------------------------------------------


def test_remaining_items_preserved():
    parser = BundleParser()
    items = ["Tal", "Thul", "Ort", "Amn", "Shako", "Arachnid Mesh"]
    result = parser.detect_bundles(items)
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Spirit"
    assert set(result.remaining_items) == {"Shako", "Arachnid Mesh"}


def test_empty_input():
    parser = BundleParser()
    result = parser.detect_bundles([])
    assert result.bundles == []
    assert result.remaining_items == []


def test_no_bundles_found():
    parser = BundleParser()
    result = parser.detect_bundles(["Shako", "Arachnid Mesh"])
    assert result.bundles == []
    assert len(result.remaining_items) == 2


# ------------------------------------------------------------------
# detect_bundles – priority (larger bundles first)
# ------------------------------------------------------------------


def test_larger_bundle_takes_priority():
    """Last Wish (6 runes incl. 3× Jah) should beat smaller bundles."""
    parser = BundleParser()
    items = ["Jah", "Mal", "Jah", "Sur", "Jah", "Ber"]
    result = parser.detect_bundles(items)
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Last Wish"


# ------------------------------------------------------------------
# detect_bundles – case insensitivity
# ------------------------------------------------------------------


def test_case_insensitive_matching():
    parser = BundleParser()
    result = parser.detect_bundles(["jah", "ITH", "Ber"])
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Enigma"


# ------------------------------------------------------------------
# add_bundle_definition
# ------------------------------------------------------------------


def test_add_custom_bundle_definition():
    parser = BundleParser()
    custom = BundleDefinition("My Bundle", "custom", ("shako", "arachnid mesh"))
    parser.add_bundle_definition(custom)

    result = parser.detect_bundles(["Shako", "Arachnid Mesh"])
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "My Bundle"
    assert result.bundles[0].bundle_type == "custom"


# ------------------------------------------------------------------
# get_bundle_price
# ------------------------------------------------------------------


def test_get_bundle_price_returns_none_without_engine():
    parser = BundleParser()
    bundle = DetectedBundle("Spirit", "rune", ["Tal", "Thul", "Ort", "Amn"])
    assert parser.get_bundle_price(bundle) is None


def test_get_bundle_price_returns_none_with_none_engine():
    parser = BundleParser()
    bundle = DetectedBundle("Spirit", "rune", ["Tal", "Thul", "Ort", "Amn"])
    assert parser.get_bundle_price(bundle, price_engine=None) is None


# ------------------------------------------------------------------
# BundleResult defaults
# ------------------------------------------------------------------


def test_bundle_result_defaults():
    r = BundleResult()
    assert r.bundles == []
    assert r.remaining_items == []
    assert r.total_bundle_value is None


# ------------------------------------------------------------------
# OCR suffix stripping ("Ber Rune" -> "ber")
# ------------------------------------------------------------------


def test_ocr_rune_suffix_stripped():
    """OCR may produce 'Ber Rune' instead of 'Ber'."""
    parser = BundleParser()
    result = parser.detect_bundles(["Jah Rune", "Ith Rune", "Ber Rune"])
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Enigma"


def test_ocr_mixed_suffix_and_plain():
    """Mix of OCR-suffixed and plain names should still match."""
    parser = BundleParser()
    result = parser.detect_bundles(["Tal Rune", "Thul", "Ort rune", "Amn"])
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Spirit"


def test_ocr_suffix_case_insensitive():
    parser = BundleParser()
    result = parser.detect_bundles(["BER RUNE", "MAL RUNE", "BER RUNE", "IST RUNE"])
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Infinity"


# ------------------------------------------------------------------
# Additional set bundles
# ------------------------------------------------------------------


def test_detect_natalya_set():
    parser = BundleParser()
    items = [
        "Natalya's Mark",
        "Natalya's Shadow",
        "Natalya's Totem",
        "Natalya's Soul",
    ]
    result = parser.detect_bundles(items)
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Natalya's Odium"
    assert result.bundles[0].bundle_type == "set"


def test_detect_griswold_set():
    parser = BundleParser()
    items = [
        "Griswold's Heart",
        "Griswold's Honor",
        "Griswold's Redemption",
        "Griswold's Valor",
    ]
    result = parser.detect_bundles(items)
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Griswold's Legacy"


def test_detect_mavina_set():
    parser = BundleParser()
    items = [
        "M'avina's Caster",
        "M'avina's Embrace",
        "M'avina's Icy Clutch",
        "M'avina's Tenet",
        "M'avina's True Sight",
    ]
    result = parser.detect_bundles(items)
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "M'avina's Battle Hymn"


def test_detect_aldur_set():
    parser = BundleParser()
    items = [
        "Aldur's Stony Gaze",
        "Aldur's Deception",
        "Aldur's Gauntlet",
        "Aldur's Advance",
    ]
    result = parser.detect_bundles(items)
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Aldur's Watchtower"


# ------------------------------------------------------------------
# Partial bundle detection
# ------------------------------------------------------------------


def test_partial_spirit_3_of_4():
    """3 of 4 Spirit runes should be a partial match."""
    parser = BundleParser()
    result = parser.detect_bundles(
        ["Tal", "Thul", "Ort"], include_partial=True
    )
    assert len(result.bundles) == 0
    assert len(result.partial_bundles) >= 1
    spirit = [p for p in result.partial_bundles if p.bundle_name == "Spirit"]
    assert len(spirit) == 1
    assert spirit[0].confidence == 0.75


def test_partial_not_returned_by_default():
    """Partial detection is opt-in; default should not include partials."""
    parser = BundleParser()
    result = parser.detect_bundles(["Tal", "Thul", "Ort"])
    assert len(result.bundles) == 0
    assert len(result.partial_bundles) == 0


def test_partial_below_threshold_not_reported():
    """1 of 4 runes (25%) is below the 50% threshold."""
    parser = BundleParser()
    result = parser.detect_bundles(["Tal"], include_partial=True)
    spirit_partials = [
        p for p in result.partial_bundles if p.bundle_name == "Spirit"
    ]
    assert len(spirit_partials) == 0


def test_partial_does_not_duplicate_full():
    """A fully matched bundle should not also appear as partial."""
    parser = BundleParser()
    result = parser.detect_bundles(
        ["Tal", "Thul", "Ort", "Amn"], include_partial=True
    )
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_name == "Spirit"
    spirit_partials = [
        p for p in result.partial_bundles if p.bundle_name == "Spirit"
    ]
    assert len(spirit_partials) == 0


def test_partial_key_set_2_of_3():
    parser = BundleParser()
    result = parser.detect_bundles(
        ["Key of Terror", "Key of Hate"], include_partial=True
    )
    assert len(result.bundles) == 0
    key_partials = [
        p for p in result.partial_bundles if p.bundle_name == "Key Set"
    ]
    assert len(key_partials) == 1
    assert key_partials[0].confidence == 0.67


# ------------------------------------------------------------------
# add_bundle_definition edge cases
# ------------------------------------------------------------------


def test_custom_bundle_with_ocr_suffix():
    """Custom bundles should also benefit from OCR suffix stripping."""
    parser = BundleParser()
    custom = BundleDefinition("Test Rune Pack", "custom", ("ber", "jah"))
    parser.add_bundle_definition(custom)
    result = parser.detect_bundles(["Ber Rune", "Jah Rune"])
    # Should match either Enigma (missing ith) or the custom pack
    # Custom pack is smaller so Enigma won't match (only 2 items, needs 3)
    custom_matches = [b for b in result.bundles if b.bundle_name == "Test Rune Pack"]
    assert len(custom_matches) == 1
