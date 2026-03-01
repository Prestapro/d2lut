from __future__ import annotations

from d2lut.normalize.d2jsp_market import normalize_item_hint, observations_from_thread_row


def test_unique_aliases_from_trade_guide():
    assert normalize_item_hint("selling 1x hoz 100 fg")[0] == "unique:herald_of_zakarum"
    assert normalize_item_hint("zaka 200ed socketed") == (
        "unique:herald_of_zakarum",
        "unique:herald_of_zakarum",
    )
    assert normalize_item_hint("15% NW + gul rune need enigma")[0] == "unique:nightwings_veil"


def test_runeword_aliases_from_trade_guide():
    assert normalize_item_hint("cta 3/3/3") == ("runeword:call_to_arms", "runeword:call_to_arms")
    assert normalize_item_hint("hoto 40 res") == ("runeword:heart_of_the_oak", "runeword:heart_of_the_oak")
    assert normalize_item_hint("need any enigma") == ("runeword:enigma", "runeword:enigma")


def test_botd_shorthand_variants():
    assert normalize_item_hint("Ebotdz ft") == (
        "runeword:breath_of_the_dying",
        "runeword:breath_of_the_dying:berserker_axe",
    )
    assert normalize_item_hint("eth botd ba") == (
        "runeword:breath_of_the_dying",
        "runeword:breath_of_the_dying:berserker_axe",
    )


def test_class_specific_torch_variant_from_warlock_alias():
    assert normalize_item_hint("4000 For Warlock Torch") == (
        "unique:hellfire_torch",
        "unique:hellfire_torch:sorceress",
    )


def test_mixed_title_segment_prices_do_not_bleed_across_items():
    rows = observations_from_thread_row(
        {
            "forum_id": 271,
            "thread_id": 123,
            "url": "https://forums.d2jsp.org/topic.php?t=123&f=271",
            "title": "Key 3x3 650fg/thresher/guardian Angel/Thresher 4 os 50fg",
            "created_at": None,
            "thread_trade_type": "ft",
            "thread_category_id": 4,
        },
        market_key="test",
    )
    by_variant = {(r["variant_key"], r["price_fg"]) for r in rows}
    assert ("keyset:3x3", 650.0) in by_variant
    assert ("base:thresher:noneth:4os", 50.0) in by_variant
    assert ("base:thresher:noneth:4os", 650.0) not in by_variant
