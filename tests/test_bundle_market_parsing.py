"""Tests for market-side bundle parsing: rune packs, quantity handling, variant normalization."""
from __future__ import annotations

from d2lut.normalize.d2jsp_market import (
    extract_quantity,
    normalize_item_hint,
    _normalize_bundle_variant,
)


# --- Rune pack tier parsing ---

def test_low_rune_pack():
    assert normalize_item_hint("FT low rune pack 50fg") == (
        "bundle:rune_pack",
        "bundle:rune_pack:low",
    )


def test_mid_rune_pack():
    assert normalize_item_hint("selling mid rune pack") == (
        "bundle:rune_pack",
        "bundle:rune_pack:mid",
    )


def test_high_rune_pack():
    assert normalize_item_hint("high rune pack x2") == (
        "bundle:rune_pack",
        "bundle:rune_pack:high",
    )


def test_rune_packs_plural():
    assert normalize_item_hint("3x low rune packs") == (
        "bundle:rune_pack",
        "bundle:rune_pack:low",
    )


def test_generic_rune_pack():
    assert normalize_item_hint("rune pack ft 100fg") == (
        "bundle:rune_pack",
        "bundle:rune_pack",
    )


def test_generic_rune_packs_plural():
    assert normalize_item_hint("selling rune packs") == (
        "bundle:rune_pack",
        "bundle:rune_pack",
    )


# --- Quantity extraction ---

def test_quantity_prefix():
    assert extract_quantity("5x Ber") == 5


def test_quantity_suffix():
    assert extract_quantity("Ber x5") == 5


def test_quantity_spaced_prefix():
    assert extract_quantity("5 x Ber") == 5


def test_quantity_spaced_suffix():
    assert extract_quantity("Ber x 10") == 10


def test_quantity_none_when_absent():
    assert extract_quantity("Ber rune ft") is None


def test_quantity_from_title():
    assert extract_quantity("FT 10x spirit sets") == 10


def test_quantity_single():
    assert extract_quantity("x1 torch") == 1


# --- Bundle variant normalization ---

def test_normalize_rune_bundle_sorts():
    result = _normalize_bundle_variant("bundle:runes", "bundle:runes:vex+gul")
    assert result == "bundle:runes:gul+vex"


def test_normalize_rune_bundle_already_sorted():
    result = _normalize_bundle_variant("bundle:runes", "bundle:runes:ber+jah")
    assert result == "bundle:runes:ber+jah"


def test_normalize_rune_pack_passthrough():
    result = _normalize_bundle_variant("bundle:rune_pack", "bundle:rune_pack:low")
    assert result == "bundle:rune_pack:low"


def test_normalize_generic_bundle_passthrough():
    result = _normalize_bundle_variant("bundle:spirit_set", "bundle:spirit_set")
    assert result == "bundle:spirit_set"


def test_normalize_lowercases():
    result = _normalize_bundle_variant("bundle:runes", "BUNDLE:RUNES:VEX+GUL")
    assert result == "bundle:runes:gul+vex"


def test_normalize_strips_whitespace():
    result = _normalize_bundle_variant("bundle:rune_pack", "  bundle:rune_pack:high  ")
    assert result == "bundle:rune_pack:high"


# --- Rune pack does not interfere with existing patterns ---

def test_rune_pack_takes_priority_over_single_rune():
    """'low rune pack' should match as a pack, not as individual rune."""
    result = normalize_item_hint("low rune pack")
    assert result is not None
    assert result[0] == "bundle:rune_pack"


def test_existing_rune_bundle_still_works():
    """Existing vex+gul style bundles should still parse correctly."""
    result = normalize_item_hint("vex+gul ft")
    assert result is not None
    assert result[0] == "bundle:runes"
    assert "vex" in result[1]
    assert "gul" in result[1]


def test_existing_spirit_set_still_works():
    result = normalize_item_hint("spirit set ft")
    assert result == ("bundle:spirit_set", "bundle:spirit_set")
