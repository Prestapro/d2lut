"""Tests for property combo extraction (including full skiller coverage v1/v2)."""

from scripts.export_property_price_table_html import (
    _maxroll_magic_seed_tags,
    _potential_tags,
    extract_props,
    props_signature,
)


def test_extract_base_and_eth_os_ed_combo():
    p = extract_props("ETH CV Insight - 16 / 251 ED - 500fg bin", "base:colossus_voulge:eth")
    sig = props_signature(p)
    assert p.base == "colossus_voulge"
    assert p.eth is True
    assert p.ed == 251
    assert "colossus_voulge" in sig
    assert "eth" in sig
    assert "251%ED" in sig


def test_extract_monarch_fcr():
    p = extract_props("35 fcr Spirit Monarch / bin 290fg", "base:monarch:noneth")
    sig = props_signature(p)
    assert p.base == "monarch"
    assert p.fcr == 35
    assert "monarch" in sig
    assert "35FCR" in sig


def test_min_regex_does_not_match_offer_min_phrase():
    p = extract_props("best offer 10 min", None)
    sig = props_signature(p) or ""
    assert p.min_dmg is None
    assert "10min" not in sig.lower()


def test_skiller_sorc_cold_with_life_gc():
    p = extract_props("Cold skiller gc 40 life", None)
    sig = props_signature(p)
    assert p.skiller == "sorc_cold_skiller"
    assert p.grand_charm is True
    assert p.life == 40
    assert "sorc_cold_skiller" in sig
    assert "GC" in sig
    assert "40life" in sig


def test_skiller_sorc_lightning_alias():
    p = extract_props("lite skiller 32 life", None)
    assert p.skiller == "sorc_lightning_skiller"
    assert p.life == 32


def test_skiller_paladin_variants():
    assert extract_props("pcomb skiller", None).skiller == "pala_combat_skiller"
    assert extract_props("offensive auras skiller", None).skiller == "pala_off_aura_skiller"
    assert extract_props("def auras skiller", None).skiller == "pala_def_aura_skiller"


def test_skiller_amazon_variants():
    assert extract_props("jav skiller gc", None).skiller == "ama_javelin_skiller"
    assert extract_props("bow skiller 12 fhr", None).skiller == "ama_bow_skiller"
    assert extract_props("passive and magic skiller", None).skiller == "ama_passive_magic_skiller"


def test_skiller_barb_variants():
    assert extract_props("wc skiller 33 life", None).skiller == "barb_warcries_skiller"
    assert extract_props("bcomb skiller", None).skiller == "barb_combat_skiller"
    assert extract_props("masteries skiller", None).skiller == "barb_masteries_skiller"


def test_skiller_druid_variants():
    assert extract_props("ele skiller gc", None).skiller == "druid_elemental_skiller"
    assert extract_props("shape skiller", None).skiller == "druid_shapeshift_skiller"
    assert extract_props("druid summon skiller", None).skiller == "druid_summon_skiller"


def test_skiller_necro_variants():
    assert extract_props("pnb skiller", None).skiller == "necro_pnb_skiller"
    assert extract_props("necro summon skiller", None).skiller == "necro_summon_skiller"
    assert extract_props("curses skiller", None).skiller == "necro_curses_skiller"


def test_skiller_assassin_variants():
    p = extract_props("trap skiller gc 12 fhr", None)
    sig = props_signature(p)
    assert p.skiller == "assa_traps_skiller"
    assert p.fhr == 12
    assert "12FHR" in sig
    assert extract_props("shadow skiller", None).skiller == "assa_shadow_skiller"
    assert extract_props("ma skiller", None).skiller == "assa_martial_skiller"


def test_plain_gc_skiller_combo():
    p = extract_props("pcomb gc plain", None)
    sig = props_signature(p)
    assert p.skiller == "pala_combat_skiller"
    assert p.grand_charm is True
    assert p.plain is True
    assert "plain" in sig


def test_lld_small_charm_triple_shorthand():
    p = extract_props("3/20/20 sc", None)
    sig = props_signature(p)
    assert p.charm_size == "sc"
    assert p.max_dmg == 3
    assert p.ar == 20
    assert p.life == 20
    assert p.lld is True
    assert "SC" in sig
    assert "3max" in sig
    assert "20AR" in sig
    assert "20life" in sig


def test_lld_small_charm_single_res_and_fhr():
    p = extract_props("5fhr 11lr sc", None)
    sig = props_signature(p)
    assert p.charm_size == "sc"
    assert p.fhr == 5
    assert p.light_res == 11
    assert p.lld is True
    assert "5FHR" in sig
    assert "11LR" in sig


def test_small_charm_all_res_and_lld_tag():
    p = extract_props("5@ sc", None)
    sig = props_signature(p)
    assert p.charm_size == "sc"
    assert p.all_res == 5
    assert p.lld is True
    assert "@5" in sig


def test_jewel_ias_ed_and_req_lvl():
    p = extract_props("jewel 15 ias 30 ed req lvl 18", None)
    sig = props_signature(p)
    assert p.jewel is True
    assert p.ias == 15
    assert p.ed == 30
    assert p.req_lvl == 18
    assert p.lld is True
    assert "jewel" in sig
    assert "15IAS" in sig
    assert "30%ED" in sig
    assert "req18" in sig


def test_jewel_max_ar_life_combo():
    p = extract_props("jewel 9 max 76 ar 30 life", None)
    sig = props_signature(p)
    assert p.jewel is True
    assert p.max_dmg == 9
    assert p.ar == 76
    assert p.life == 30
    assert "jewel" in sig
    assert "9max" in sig
    assert "76AR" in sig
    assert "30life" in sig


def test_amulet_two_twenty_shorthand_with_stats():
    p = extract_props("2/20 pally ammy 15@ 20str", None)
    sig = props_signature(p)
    assert p.item_form == "amulet"
    assert p.class_skills == "paladin"
    assert p.skills == 2
    assert p.fcr == 20
    assert p.all_res == 15
    assert p.strength == 20
    assert "amulet" in sig
    assert "paladin_skills" in sig
    assert "+2skills" in sig
    assert "20FCR" in sig
    assert "@15" in sig
    assert "20str" in sig


def test_circlet_two_skills_fcr_frw_sockets():
    p = extract_props("2 nec 20 fcr circlet 30frw 2os", None)
    sig = props_signature(p)
    assert p.item_form == "circlet"
    assert p.class_skills == "necromancer"
    assert p.skills == 2
    assert p.fcr == 20
    assert p.frw == 30
    assert p.os == 2
    assert "circlet" in sig
    assert "necromancer_skills" in sig
    assert "30FRW" in sig
    assert "2os" in sig


def test_ring_fcr_stats_ar_res_combo():
    p = extract_props("10fcr ring 20str 70ar 15fr", None)
    sig = props_signature(p)
    assert p.item_form == "ring"
    assert p.fcr == 10
    assert p.strength == 20
    assert p.ar == 70
    assert p.fire_res == 15
    assert "ring" in sig
    assert "10FCR" in sig
    assert "20str" in sig
    assert "70AR" in sig
    assert "15FR" in sig


def test_torch_class_and_roll_shorthand():
    p = extract_props("necro torch 17/16", None)
    sig = props_signature(p)
    assert p.item_form == "torch"
    assert p.torch_class == "necromancer"
    assert p.torch_attrs == 17
    assert p.torch_res == 16
    assert "torch" in sig
    assert "necromancer_torch" in sig
    assert "17attr" in sig
    assert "16res" in sig


def test_anni_triple_roll():
    p = extract_props("anni 20/20/10", None)
    sig = props_signature(p)
    assert p.item_form == "anni"
    assert p.anni_attrs == 20
    assert p.anni_res == 20
    assert p.anni_xp == 10
    assert "anni" in sig
    assert "20anni_attr" in sig
    assert "20anni_res" in sig
    assert "10xp" in sig


def test_facet_element_and_roll():
    p = extract_props("5/5 fire facet", None)
    sig = props_signature(p)
    assert p.item_form == "facet"
    assert p.facet_element == "fire"
    assert p.facet_dmg == 5
    assert p.facet_enemy_res == 5
    assert "facet" in sig
    assert "fire_facet" in sig
    assert "+5facet_dmg" in sig
    assert "-5facet_res" in sig


def test_gheeds_triple_roll():
    p = extract_props("gheeds 160/15/40", None)
    sig = props_signature(p)
    assert p.item_form == "gheed"
    assert p.gheed_mf == 160
    assert p.gheed_vendor == 15
    assert p.gheed_gold == 40
    assert "gheed" in sig
    assert "160MF_gheed" in sig
    assert "15vendor" in sig
    assert "40gold" in sig


def test_maxroll_magic_seed_tags_for_jmod():
    tags = _maxroll_magic_seed_tags(["Jeweler's Monarch of Deflecting"])
    assert "maxroll_jmod" in tags
    assert "magic_shield_seed" in tags


def test_maxroll_magic_seed_tags_for_skill_gc_names():
    tags = _maxroll_magic_seed_tags(["Lion Branded Grand Charm of Vita 45 life"])
    assert "maxroll_skill_gc_name" in tags
    assert "magic_gc_seed" in tags


def test_maxroll_magic_seed_tags_for_jewel_and_gloves():
    jewel_tags = _maxroll_magic_seed_tags(["Ruby Jewel of Fervor 38ed"])
    glove_tags = _maxroll_magic_seed_tags(["Lancer's Sharkskin Gloves of Alacrity"])
    assert "magic_jewel_seed" in jewel_tags
    assert "maxroll_magic_gloves" in glove_tags


def test_potential_tags_skiller_plus_and_rw_base():
    sk = extract_props("lite skiller gc 40 life", None)
    sk_tags = _potential_tags(sk, max_fg=120, obs_count=1)
    assert "skiller" in sk_tags
    assert "skiller_plus" in sk_tags

    base = extract_props("eth gt 4os", "base:giant_thresher:eth:4os")
    base_tags = _potential_tags(base, max_fg=80, obs_count=1)
    assert "rw_base" in base_tags
