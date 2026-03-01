"""Regression tests for roll-aware runeword property extraction.

**Validates: Requirements 12.1, 12.2, 12.3, 12.4**

Tests cover:
- Runeword name detection for all 8 target runewords
- Roll-specific extraction (CTA BO, Insight meditation, etc.)
- Signature format with runeword: prefix and roll detail
- Generic (unrolled) runeword signatures
- Kit listings do NOT get rw_name set
"""

import pytest

from scripts.export_property_price_table_html import extract_props, props_signature


# ---------------------------------------------------------------------------
# Requirement 12.1: Extract roll-specific properties for each target runeword
# ---------------------------------------------------------------------------

class TestCTARollExtraction:
    """CTA: Battle Orders level."""

    def test_cta_with_bo_level(self):
        p = extract_props("CTA +6 BO / +1 BC")
        assert p.rw_name == "cta"
        assert p.rw_bo_lvl == 6

    def test_cta_battle_orders_verbose(self):
        p = extract_props("call to arms +6 battle orders")
        assert p.rw_name == "cta"
        assert p.rw_bo_lvl == 6

    def test_cta_no_roll(self):
        p = extract_props("CTA")
        assert p.rw_name == "cta"
        assert p.rw_bo_lvl is None

    def test_cta_kit_no_rw_name(self):
        """Kit listing should NOT set rw_name."""
        p = extract_props("cta kit flail")
        assert p.kit is True
        assert p.rw_name is None


class TestHOTORollExtraction:
    """HOTO: All res (reuses existing all_res field)."""

    def test_hoto_with_all_res_at(self):
        p = extract_props("HOTO 40@")
        assert p.rw_name == "hoto"
        assert p.all_res == 40

    def test_hoto_with_all_res_explicit(self):
        p = extract_props("heart of the oak 38 all res")
        assert p.rw_name == "hoto"
        assert p.all_res == 38

    def test_hoto_no_roll(self):
        p = extract_props("hoto flail")
        assert p.rw_name == "hoto"
        assert p.all_res is None


class TestGriefRollExtraction:
    """Grief: IAS + damage (reuses existing ias field)."""

    def test_grief_with_ias(self):
        p = extract_props("grief pb 40ias")
        assert p.rw_name == "grief"
        assert p.base == "phase_blade"
        assert p.ias == 40

    def test_grief_no_roll(self):
        p = extract_props("grief phase blade")
        assert p.rw_name == "grief"
        assert p.base == "phase_blade"
        assert p.ias is None


class TestInfinityRollExtraction:
    """Infinity: -enemy res (reuses existing enemy_res field)."""

    def test_infinity_with_enemy_res(self):
        p = extract_props("infinity eth gt -55 res")
        assert p.rw_name == "infinity"
        assert p.base == "giant_thresher"
        assert p.enemy_res == 55

    def test_infi_shorthand(self):
        p = extract_props("infi eth thresher -50 enemy res")
        assert p.rw_name == "infinity"
        assert p.enemy_res == 50

    def test_infinity_no_roll(self):
        p = extract_props("infinity eth gt")
        assert p.rw_name == "infinity"
        assert p.enemy_res is None


class TestInsightRollExtraction:
    """Insight: Meditation level."""

    def test_insight_with_med_level(self):
        p = extract_props("insight eth thresher 17 med")
        assert p.rw_name == "insight"
        assert p.rw_med_lvl == 17

    def test_insight_meditation_verbose(self):
        p = extract_props("insight eth cv +17 meditation")
        assert p.rw_name == "insight"
        assert p.rw_med_lvl == 17

    def test_insight_no_roll(self):
        p = extract_props("insight eth thresher")
        assert p.rw_name == "insight"
        assert p.rw_med_lvl is None


class TestSpiritRollExtraction:
    """Spirit: FCR + all res (reuses existing fcr/all_res fields)."""

    def test_spirit_with_fcr(self):
        p = extract_props("spirit monarch 35fcr")
        assert p.rw_name == "spirit"
        assert p.base == "monarch"
        assert p.fcr == 35

    def test_spirit_with_fcr_and_all_res(self):
        p = extract_props("spirit monarch 35fcr 112 all res")
        assert p.rw_name == "spirit"
        assert p.fcr == 35
        assert p.all_res == 112

    def test_spirit_no_roll(self):
        p = extract_props("spirit monarch")
        assert p.rw_name == "spirit"
        assert p.fcr is None


class TestFortitudeRollExtraction:
    """Fortitude: ED (reuses existing ed field)."""

    def test_fort_with_ed(self):
        p = extract_props("fort archon plate 30ed")
        assert p.rw_name == "fortitude"
        assert p.base == "archon_plate"
        assert p.ed == 30

    def test_fortitude_full_name(self):
        p = extract_props("fortitude ap 300% ed")
        assert p.rw_name == "fortitude"
        assert p.ed == 300

    def test_fort_no_roll(self):
        p = extract_props("fort ap")
        assert p.rw_name == "fortitude"
        assert p.ed is None


class TestBOTDRollExtraction:
    """BOTD: ED (reuses existing ed field)."""

    def test_botd_with_ed(self):
        p = extract_props("botd eth cv 400ed")
        assert p.rw_name == "botd"
        assert p.base == "colossus_voulge"
        assert p.ed == 400

    def test_breath_of_the_dying_full_name(self):
        p = extract_props("breath of the dying eth ba 395 ed")
        assert p.rw_name == "botd"
        assert p.base == "berserker_axe"
        assert p.ed == 395

    def test_botd_no_roll(self):
        p = extract_props("botd eth cv")
        assert p.rw_name == "botd"
        assert p.ed is None


# ---------------------------------------------------------------------------
# Requirement 12.2, 12.3: Signature format with/without roll detail
# ---------------------------------------------------------------------------

class TestRunewordSignatureFormat:
    """Signatures should start with runeword:{name} and include roll fields."""

    def test_cta_rolled_signature(self):
        sig = props_signature(extract_props("CTA +6 BO / +1 BC"))
        assert sig == "runeword:cta + +6BO"

    def test_cta_generic_signature(self):
        sig = props_signature(extract_props("CTA"))
        assert sig == "runeword:cta"

    def test_hoto_rolled_signature(self):
        sig = props_signature(extract_props("HOTO 40@"))
        assert sig == "runeword:hoto + @40"

    def test_grief_rolled_signature(self):
        sig = props_signature(extract_props("grief pb 40ias"))
        assert sig == "runeword:grief + phase_blade + 40IAS"

    def test_infinity_rolled_signature(self):
        sig = props_signature(extract_props("infinity eth gt -55 res"))
        assert sig == "runeword:infinity + giant_thresher + eth + -55enemy_res"

    def test_insight_rolled_signature(self):
        sig = props_signature(extract_props("insight eth thresher 17 med"))
        assert sig == "runeword:insight + thresher + eth + med17"

    def test_spirit_rolled_signature(self):
        sig = props_signature(extract_props("spirit monarch 35fcr"))
        assert sig == "runeword:spirit + monarch + 35FCR"

    def test_fortitude_rolled_signature(self):
        sig = props_signature(extract_props("fort archon plate 300ed"))
        assert sig == "runeword:fortitude + archon_plate + 300%ED"

    def test_botd_rolled_signature(self):
        sig = props_signature(extract_props("botd eth cv 400ed"))
        assert sig == "runeword:botd + colossus_voulge + eth + 400%ED"


# ---------------------------------------------------------------------------
# Requirement 12.4 / 9.1: Kit listings must NOT get runeword prefix
# ---------------------------------------------------------------------------

class TestKitDoesNotGetRunewordPrefix:
    """Kit detection takes priority — kit listings should not set rw_name."""

    def test_spirit_kit_no_rw_name(self):
        p = extract_props("tal thul ort amn + monarch")
        assert p.kit is True
        assert p.rw_name is None
        sig = props_signature(p)
        assert sig is not None
        assert sig.startswith("kit")
        assert "runeword:" not in sig

    def test_infinity_kit_no_rw_name(self):
        p = extract_props("ber mal ber ist + eth giant thresher")
        assert p.kit is True
        assert p.rw_name is None

    def test_grief_kit_no_rw_name(self):
        p = extract_props("eth tir lo mal ral + phase blade")
        assert p.kit is True
        assert p.rw_name is None

    def test_insight_kit_no_rw_name(self):
        p = extract_props("ral tir tal sol + eth thresher")
        assert p.kit is True
        assert p.rw_name is None
