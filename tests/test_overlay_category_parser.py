"""Unit tests for overlay-side category-aware parsing."""

from d2lut.overlay.category_aware_parser import CategoryAwareParser
from d2lut.overlay.ocr_parser import ParsedItem


def test_category_parser_infers_rune_type_from_explicit_text():
    parser = CategoryAwareParser()
    parsed = ParsedItem(raw_text="Jah Rune", item_name="Jah Rune", confidence=0.95)

    enriched = parser.parse_with_category(parsed)

    assert enriched.item_type == "rune"
    assert enriched.diagnostic.get("category_hint_applied") == "runes"
    assert enriched.diagnostic.get("category_inferred_item_type") == "rune"


def test_category_parser_infers_set_quality_for_tal_rasha_item():
    parser = CategoryAwareParser()
    parsed = ParsedItem(raw_text="Tal Rasha's Adjudication Amulet", item_name="Tal Rasha's Adjudication", confidence=0.9)

    enriched = parser.parse_with_category(parsed)

    assert enriched.quality == "set"
    assert enriched.item_type == "amulet"
    assert enriched.diagnostic.get("category_inferred_quality") == "set"


def test_category_parser_preserves_existing_fields_and_adds_lld_context():
    parser = CategoryAwareParser()
    parsed = ParsedItem(
        raw_text="LLD ring with life",
        item_name="Rare Ring",
        item_type="ring",
        quality="rare",
        confidence=0.85,
        diagnostic={"preexisting": True},
    )

    enriched = parser.parse_with_category(parsed, category_hint="lld")

    assert enriched.item_type == "ring"
    assert enriched.quality == "rare"
    assert enriched.diagnostic["preexisting"] is True
    assert enriched.diagnostic.get("category_hint_applied") == "lld"
    assert enriched.diagnostic.get("lld_context") is True
