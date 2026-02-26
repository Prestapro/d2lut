from __future__ import annotations

from d2lut.normalize.d2jsp_market import normalize_item_hint


def test_keyset_3x3_parsing():
    assert normalize_item_hint("FT 3x3 key set 120 fg") == ("keyset:3x3", "keyset:3x3")


def test_spirit_set_parsing():
    assert normalize_item_hint("10x spirit sets ft") == ("bundle:spirit_set", "bundle:spirit_set")


def test_insight_set_parsing():
    assert normalize_item_hint("Insight set x20") == ("bundle:insight_set", "bundle:insight_set")


def test_organ_set_parsing():
    assert normalize_item_hint("organ set / mephisto's brain + diablo horn + baal eye") == (
        "bundle:organ_set",
        "bundle:organ_set",
    )


def test_crafting_sets_parsing():
    assert normalize_item_hint("50x caster amulets set ral + p amethyst + jewel") == (
        "bundle:craftset:caster_amulet",
        "bundle:craftset:caster_amulet",
    )
    assert normalize_item_hint("blood gloves set nef + p ruby + jewel") == (
        "bundle:craftset:blood_gloves",
        "bundle:craftset:blood_gloves",
    )


def test_bulk_commodity_parsing():
    assert normalize_item_hint("40 pgems ft") == ("gem:perfect_gems_mixed", "gem:perfect_gems_mixed")
    assert normalize_item_hint("50 p skulls") == ("gem:perfect_skull", "gem:perfect_skull")
    assert normalize_item_hint("50 jewel fragments") == ("consumable:jewel_fragments", "consumable:jewel_fragments")


def test_spaced_rune_sequence_is_bundle_not_single_rune():
    assert normalize_item_hint("Jah ith Ber") == ("bundle:runes", "bundle:runes:ber+ith+jah")


def test_enigma_kit_base_plus_runes_is_bundle_kit():
    assert normalize_item_hint("Mp 15ed 15dura + Jah ith Ber Bin 7700") == (
        "bundle:runeword_kit:enigma",
        "bundle:runeword_kit:enigma:mage_plate",
    )


def test_hoto_kit_base_plus_runes_is_bundle_kit():
    assert normalize_item_hint("Unmade Hoto flail ko vex pul thul 600") == (
        "bundle:runeword_kit:heart_of_the_oak",
        "bundle:runeword_kit:heart_of_the_oak:flail",
    )


def test_cta_kit_base_plus_runes_is_bundle_kit():
    assert normalize_item_hint("CTA crystal sword amn ral mal ist ohm") == (
        "bundle:runeword_kit:call_to_arms",
        "bundle:runeword_kit:call_to_arms:crystal_sword",
    )
