"""Preservation property tests — Property 2: Existing Signature Stability & UI Behavior.

**Validates: Requirements 1.3, 3.5, 4.4**

These tests capture the CURRENT (unfixed) behavior of extract_props() and
props_signature() as a baseline.  They must PASS on unfixed code and continue
to pass after any fix — ensuring no regressions in existing signatures.

Observation-first methodology: baselines were recorded by running the parser
on all existing test fixtures before writing these tests.
"""

from __future__ import annotations

import re
from dataclasses import asdict

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from scripts.export_property_price_table_html import (
    ExtractedProps,
    _maxroll_magic_seed_tags,
    _ocr_low_quality_signature,
    _potential_tags,
    extract_props,
    props_signature,
)


# ---------------------------------------------------------------------------
# Observed baselines — recorded from UNFIXED code on existing test fixtures.
# Each entry: (excerpt, variant_key, expected_signature)
# ---------------------------------------------------------------------------

FIXTURE_BASELINES: list[tuple[str, str | None, str | None]] = [
    # NOTE: Two fixtures produce sig=None on unfixed code (known bugs).
    ("ETH CV Insight - 16 / 251 ED - 500fg bin", "base:colossus_voulge:eth", "runeword:insight + colossus_voulge + eth + 251%ED"),
    ("35 fcr Spirit Monarch / bin 290fg", "base:monarch:noneth", "runeword:spirit + monarch + 35FCR"),
    ("best offer 10 min", None, None),
    ("Cold skiller gc 40 life", None, "sorc_cold_skiller + GC + 40life"),
    ("lite skiller 32 life", None, "sorc_lightning_skiller + GC + 32life"),
    ("pcomb skiller", None, "pala_combat_skiller + GC"),
    ("offensive auras skiller", None, "pala_off_aura_skiller + GC"),
    ("def auras skiller", None, "pala_def_aura_skiller + GC"),
    ("jav skiller gc", None, "ama_javelin_skiller + GC"),
    ("bow skiller 12 fhr", None, "ama_bow_skiller + GC + 12FHR"),
    ("passive and magic skiller", None, "ama_passive_magic_skiller + GC"),
    ("wc skiller 33 life", None, "barb_warcries_skiller + GC + 33life"),
    ("bcomb skiller", None, "barb_combat_skiller + GC"),
    ("masteries skiller", None, "barb_masteries_skiller + GC"),
    ("ele skiller gc", None, "druid_elemental_skiller + GC"),
    ("shape skiller", None, "druid_shapeshift_skiller + GC"),
    ("druid summon skiller", None, "druid_summon_skiller + druid_skills + GC"),
    ("pnb skiller", None, "necro_pnb_skiller + GC"),
    ("necro summon skiller", None, "necro_summon_skiller + necromancer_skills + GC"),
    ("curses skiller", None, "necro_curses_skiller + GC"),
    ("trap skiller gc 12 fhr", None, "assa_traps_skiller + GC + 12FHR"),
    ("shadow skiller", None, "assa_shadow_skiller + GC"),
    ("ma skiller", None, "assa_martial_skiller + GC"),
    ("pcomb gc plain", None, "pala_combat_skiller + GC + plain"),
    ("3/20/20 sc", None, "SC + 20AR + 3max + 20life + LLD"),
    ("5fhr 11lr sc", None, "SC + 5FHR + 11LR + LLD"),
    ("5@ sc", None, "SC + @5 + LLD"),
    ("jewel 15 ias 30 ed req lvl 18", None, "jewel + 30%ED + 15IAS + req18 + LLD"),
    ("jewel 9 max 76 ar 30 life", None, "jewel + 76AR + 9max + 30life"),
    ("2/20 pally ammy 15@ 20str", None, "amulet + paladin_skills + @15 + 20FCR + 20str + +2skills"),
    ("2 nec 20 fcr circlet 30frw 2os", None, "circlet + necromancer_skills + 2os + 20FCR + 30FRW + +2skills"),
    # Ring sig now correctly produced after adding ring to informative_prefixes
    ("10fcr ring 20str 70ar 15fr", None, "ring + 10FCR + 20str + 70AR + 15FR"),
    ("necro torch 17/16", None, "torch + necromancer_torch + necromancer_skills + 17attr + 16res"),
    ("anni 20/20/10", None, "anni + 20anni_attr + 20anni_res + 10xp"),
    ("5/5 fire facet", None, "facet + fire_facet + +5facet_dmg + -5facet_res"),
    ("gheeds 160/15/40", None, "gheed + 160MF_gheed + 15vendor + 40gold"),
]


# ---------------------------------------------------------------------------
# Sub-task 5: Fixture signature preservation
# ---------------------------------------------------------------------------

class TestFixtureSignaturePreservation:
    """For all excerpts in existing test fixtures, extract_props and
    props_signature produce the same output as the recorded baseline."""

    @pytest.mark.parametrize(
        "excerpt,variant_key,expected_sig",
        FIXTURE_BASELINES,
        ids=[f[0][:40] for f in FIXTURE_BASELINES],
    )
    def test_signature_matches_baseline(self, excerpt, variant_key, expected_sig):
        """**Validates: Requirements 1.3**"""
        props = extract_props(excerpt, variant_key)
        sig = props_signature(props)
        assert sig == expected_sig, (
            f"Signature changed for {excerpt!r}: expected {expected_sig!r}, got {sig!r}"
        )


# ---------------------------------------------------------------------------
# Sub-task 6: Random excerpts — extract_props never crashes, req_lvl in range
# ---------------------------------------------------------------------------

# Strategy: generate random strings that do NOT match known bug condition
# patterns (rlvl, 1v1, kit rune combos, OCR O-for-0 in anni/torch).
# These represent the "normal" input space that must remain stable.

_SAFE_EXCERPT_ALPHABET = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyz 0123456789/+-%@")
)

_SAFE_EXCERPT = st.text(_SAFE_EXCERPT_ALPHABET, min_size=0, max_size=80)


class TestExtractPropsNeverCrashes:
    """For random excerpt strings, extract_props() never crashes and
    req_lvl is always in range 1-99 or None."""

    @given(excerpt=_SAFE_EXCERPT)
    @settings(max_examples=200, deadline=2000)
    def test_extract_props_no_crash_and_req_lvl_range(self, excerpt):
        """**Validates: Requirements 1.3, 3.5**"""
        props = extract_props(excerpt, None)
        # Must not crash — reaching here is success.
        # req_lvl must be None or in 1-99.
        if props.req_lvl is not None:
            assert 1 <= props.req_lvl <= 99, (
                f"req_lvl={props.req_lvl} out of range for excerpt={excerpt!r}"
            )


# ---------------------------------------------------------------------------
# Sub-task 7: props_signature determinism
# ---------------------------------------------------------------------------

# Strategy for random ExtractedProps: generate plausible field values.
_OPT_INT = st.one_of(st.none(), st.integers(min_value=1, max_value=200))
_OPT_SMALL_INT = st.one_of(st.none(), st.integers(min_value=1, max_value=99))
_OPT_BASE = st.one_of(
    st.none(),
    st.sampled_from([
        "monarch", "archon_plate", "mage_plate", "thresher",
        "giant_thresher", "cryptic_axe", "colossus_voulge",
        "phase_blade", "berserker_axe",
    ]),
)
_OPT_ITEM_FORM = st.one_of(
    st.none(),
    st.sampled_from(["torch", "anni", "gheed", "facet", "amulet", "circlet", "ring"]),
)
_OPT_SKILLER = st.one_of(
    st.none(),
    st.sampled_from([
        "sorc_cold_skiller", "sorc_lightning_skiller", "sorc_fire_skiller",
        "pala_combat_skiller", "ama_javelin_skiller", "barb_warcries_skiller",
        "necro_pnb_skiller", "druid_elemental_skiller", "assa_traps_skiller",
    ]),
)
_OPT_CHARM = st.one_of(st.none(), st.sampled_from(["sc", "lc", "gc"]))
_OPT_CLASS = st.one_of(
    st.none(),
    st.sampled_from(["paladin", "sorceress", "necromancer", "amazon", "barbarian", "druid", "assassin"]),
)
_OPT_TORCH_CLASS = st.one_of(
    st.none(),
    st.sampled_from(["sorceress", "paladin", "necromancer", "amazon", "barbarian", "druid", "assassin"]),
)
_OPT_FACET_ELEM = st.one_of(st.none(), st.sampled_from(["fire", "cold", "lightning", "poison"]))


@st.composite
def random_extracted_props(draw):
    """Generate a random ExtractedProps with plausible field values."""
    return ExtractedProps(
        base=draw(_OPT_BASE),
        eth=draw(st.booleans()),
        os=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=6))),
        ed=draw(_OPT_INT),
        all_res=draw(st.one_of(st.none(), st.integers(min_value=3, max_value=200))),
        defense=draw(_OPT_INT),
        ias=draw(_OPT_SMALL_INT),
        fcr=draw(_OPT_SMALL_INT),
        frw=draw(_OPT_SMALL_INT),
        fhr=draw(_OPT_SMALL_INT),
        strength=draw(_OPT_INT),
        dexterity=draw(_OPT_INT),
        ar=draw(_OPT_INT),
        max_dmg=draw(_OPT_SMALL_INT),
        min_dmg=draw(_OPT_SMALL_INT),
        life=draw(_OPT_INT),
        mf=draw(_OPT_INT),
        skills=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=3))),
        enemy_res=draw(_OPT_SMALL_INT),
        skiller=draw(_OPT_SKILLER),
        item_form=draw(_OPT_ITEM_FORM),
        class_skills=draw(_OPT_CLASS),
        all_skills=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=3))),
        charm_size=draw(_OPT_CHARM),
        jewel=draw(st.booleans()),
        req_lvl=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=99))),
        fire_res=draw(_OPT_SMALL_INT),
        light_res=draw(_OPT_SMALL_INT),
        cold_res=draw(_OPT_SMALL_INT),
        poison_res=draw(_OPT_SMALL_INT),
        grand_charm=draw(st.booleans()),
        plain=draw(st.booleans()),
        lld=draw(st.booleans()),
        torch_class=draw(_OPT_TORCH_CLASS),
        torch_attrs=draw(st.one_of(st.none(), st.integers(min_value=10, max_value=20))),
        torch_res=draw(st.one_of(st.none(), st.integers(min_value=10, max_value=20))),
        anni_attrs=draw(st.one_of(st.none(), st.integers(min_value=10, max_value=20))),
        anni_res=draw(st.one_of(st.none(), st.integers(min_value=10, max_value=20))),
        anni_xp=draw(st.one_of(st.none(), st.integers(min_value=5, max_value=10))),
        gheed_mf=draw(st.one_of(st.none(), st.integers(min_value=20, max_value=160))),
        gheed_vendor=draw(st.one_of(st.none(), st.integers(min_value=5, max_value=15))),
        gheed_gold=draw(st.one_of(st.none(), st.integers(min_value=20, max_value=200))),
        facet_element=draw(_OPT_FACET_ELEM),
        facet_dmg=draw(st.one_of(st.none(), st.integers(min_value=3, max_value=5))),
        facet_enemy_res=draw(st.one_of(st.none(), st.integers(min_value=3, max_value=5))),
    )


class TestPropsSignatureDeterminism:
    """For random ExtractedProps instances, props_signature() is deterministic
    (same input → same output)."""

    @given(props=random_extracted_props())
    @settings(max_examples=300, deadline=2000)
    def test_same_input_same_output(self, props):
        """**Validates: Requirements 4.4**"""
        sig1 = props_signature(props)
        sig2 = props_signature(props)
        assert sig1 == sig2, (
            f"Non-deterministic signature: {sig1!r} != {sig2!r}"
        )


# ---------------------------------------------------------------------------
# Sub-task 8: _ocr_low_quality_signature filtering preservation
# ---------------------------------------------------------------------------

class TestOcrLowQualitySignatureFiltering:
    """_ocr_low_quality_signature() continues to reject genuinely noisy
    signatures and accept good ones."""

    @pytest.mark.parametrize("parts,expected", [
        # Noisy — should be rejected (True)
        ([], True),
        (["@499"], True),
        (["eth", "@3", "req55"], True),
        (["@10"], True),
        (["req30"], True),
        (["eth", "req20"], True),
        # Good — should be kept (False)
        (["torch", "necromancer_torch", "17attr", "16res"], False),
        (["anni", "20anni_attr", "20anni_res", "10xp"], False),
        (["jewel", "30%ED", "15IAS", "req18", "LLD"], False),
        (["sorc_cold_skiller", "GC", "40life"], False),
        (["SC", "20AR", "3max", "20life", "LLD"], False),
        (["facet", "fire_facet", "+5facet_dmg", "-5facet_res"], False),
        (["monarch", "35FCR"], False),
        (["gheed", "160MF_gheed", "15vendor", "40gold"], False),
    ])
    def test_filtering_baseline(self, parts, expected):
        """**Validates: Requirements 1.3**"""
        result = _ocr_low_quality_signature(parts)
        assert result is expected, (
            f"_ocr_low_quality_signature({parts!r}) = {result}, expected {expected}"
        )


# ---------------------------------------------------------------------------
# Sub-task 9: _potential_tags and _maxroll_magic_seed_tags preservation
# ---------------------------------------------------------------------------

class TestPotentialTagsPreservation:
    """_potential_tags() scoring unchanged for existing inputs."""

    def test_skiller_plus_tags(self):
        """**Validates: Requirements 1.3**"""
        sk = extract_props("lite skiller gc 40 life", None)
        tags = _potential_tags(sk, max_fg=120, obs_count=1)
        assert "skiller" in tags
        assert "skiller_plus" in tags

    def test_rw_base_tags(self):
        """**Validates: Requirements 1.3**"""
        base = extract_props("eth gt 4os", "base:giant_thresher:eth:4os")
        tags = _potential_tags(base, max_fg=80, obs_count=1)
        assert "rw_base" in tags
        assert "elite_base" in tags

    def test_torch_market_tags(self):
        """**Validates: Requirements 1.3**"""
        torch = extract_props("necro torch 17/16", None)
        tags = _potential_tags(torch, max_fg=500, obs_count=3)
        assert "market" in tags
        assert "torch" in tags

    def test_anni_perfect_tags(self):
        """**Validates: Requirements 1.3**"""
        anni = extract_props("anni 20/20/10", None)
        tags = _potential_tags(anni, max_fg=1000, obs_count=5)
        assert "market" in tags
        assert "anni" in tags
        assert "perfect" in tags

    def test_facet_perfect_tags(self):
        """**Validates: Requirements 1.3**"""
        facet = extract_props("5/5 fire facet", None)
        tags = _potential_tags(facet, max_fg=200, obs_count=2)
        assert "facet" in tags
        assert "perfect" in tags

    def test_lld_sc_tags(self):
        """**Validates: Requirements 1.3**"""
        sc = extract_props("3/20/20 sc", None)
        tags = _potential_tags(sc, max_fg=50, obs_count=1)
        assert "lld" in tags
        assert "pvp_combo" in tags


class TestMaxrollMagicSeedTagsPreservation:
    """_maxroll_magic_seed_tags() scoring unchanged for existing inputs."""

    def test_jmod_tags(self):
        """**Validates: Requirements 1.3**"""
        tags = _maxroll_magic_seed_tags(["Jeweler's Monarch of Deflecting"])
        assert "maxroll_jmod" in tags
        assert "magic_shield_seed" in tags

    def test_skill_gc_name_tags(self):
        """**Validates: Requirements 1.3**"""
        tags = _maxroll_magic_seed_tags(["Lion Branded Grand Charm of Vita 45 life"])
        assert "maxroll_skill_gc_name" in tags
        assert "magic_gc_seed" in tags

    def test_jewel_tags(self):
        """**Validates: Requirements 1.3**"""
        tags = _maxroll_magic_seed_tags(["Ruby Jewel of Fervor 38ed"])
        assert "maxroll_jewel_fervor" in tags
        assert "magic_jewel_seed" in tags

    def test_gloves_tags(self):
        """**Validates: Requirements 1.3**"""
        tags = _maxroll_magic_seed_tags(["Lancer's Sharkskin Gloves of Alacrity"])
        assert "maxroll_magic_gloves" in tags
        assert "maxroll_alacrity" in tags
