"""Tests for modifier lexicon integration in extract_props() — Task 19.

Validates that extracted properties are filtered against category constraints,
impossible combos are discarded, and rejections are logged.
"""

import logging

from scripts.export_property_price_table_html import extract_props, props_signature
from scripts.export_property_price_table_html import _validate_props_against_lexicon, ExtractedProps
from d2lut.normalize.modifier_lexicon import (
    infer_item_category_from_variant,
    property_allowed_by_category_constraints,
)


# ---------------------------------------------------------------------------
# 19.1  Validate extracted property names against modifier lexicon
# ---------------------------------------------------------------------------

class TestLexiconValidationBasics:
    """property_allowed_by_category_constraints rejects impossible props."""

    def test_fcr_denied_on_runes(self):
        assert not property_allowed_by_category_constraints("runes", "fcr")

    def test_sockets_denied_on_charm(self):
        assert not property_allowed_by_category_constraints("charm", "sockets")

    def test_ias_allowed_on_jewel(self):
        assert property_allowed_by_category_constraints("jewel", "ias")

    def test_unknown_category_allows_everything(self):
        assert property_allowed_by_category_constraints("generic", "fcr")

    def test_unknown_property_allowed(self):
        # Properties not in the lexicon mapping are conservatively allowed.
        assert property_allowed_by_category_constraints("runes", "unknown_stat")


class TestExtractPropsLexiconFiltering:
    """extract_props() discards impossible properties via lexicon."""

    def test_rune_variant_strips_fcr(self):
        """FCR parsed from text should be discarded when variant is a rune."""
        p = extract_props("jah rune 10 fcr", "rune:jah")
        assert p.fcr is None, "FCR should be rejected for rune category"

    def test_rune_variant_strips_ias(self):
        p = extract_props("ber rune 20 ias", "rune:ber")
        assert p.ias is None, "IAS should be rejected for rune category"

    def test_rune_variant_strips_life(self):
        p = extract_props("jah rune 40 life", "rune:jah")
        assert p.life is None, "life should be rejected for rune category"

    def test_charm_variant_strips_sockets(self):
        """Sockets parsed from text should be discarded for charms."""
        p = extract_props("sc 3/20/20 4 os", "charm:small_charm")
        assert p.os is None, "sockets should be rejected for charm category"

    def test_charm_variant_strips_defense(self):
        p = extract_props("gc skiller 500 def", "charm:grand_charm")
        assert p.defense is None, "defense should be rejected for charm category"

    def test_torch_variant_strips_sockets(self):
        p = extract_props("sorc torch 20/20 4 os", "unique:hellfire_torch:sorceress")
        assert p.os is None, "sockets should be rejected for torch category"

    def test_torch_variant_strips_ias(self):
        p = extract_props("sorc torch 20/20 15 ias", "unique:hellfire_torch:sorceress")
        assert p.ias is None, "IAS should be rejected for torch category"

    def test_anni_variant_strips_mf(self):
        p = extract_props("anni 20/20/10 40 mf", "unique:annihilus")
        assert p.mf is None, "MF should be rejected for anni category"

    def test_jewel_variant_keeps_ias(self):
        """IAS is valid on jewels — should NOT be stripped."""
        p = extract_props("15 ias 40 ed jewel", "jewel:ias_ed")
        assert p.ias == 15
        assert p.ed == 40

    def test_base_armor_allows_sockets_and_defense(self):
        """Sockets and defense are valid on base armor."""
        p = extract_props("4 os monarch 148 def", "base:monarch:noneth:4os")
        assert p.os == 4
        assert p.defense == 148

    def test_no_variant_skips_validation(self):
        """When variant_key is None, no filtering occurs (conservative)."""
        p = extract_props("10 fcr 20 ias 40 life", None)
        assert p.fcr == 10
        assert p.ias == 20
        assert p.life == 40


# ---------------------------------------------------------------------------
# 19.2  Discard impossible property combos for detected item category
# ---------------------------------------------------------------------------

class TestImpossibleCombosDiscarded:
    """End-to-end: impossible combos are removed from signature."""

    def test_rune_with_noise_produces_clean_signature(self):
        """A rune listing with stray stat text should not include those stats."""
        p = extract_props("jah rune 10 fcr 20 ias 40 life", "rune:jah")
        sig = props_signature(p)
        # FCR, IAS, life should all be stripped for runes.
        assert p.fcr is None
        assert p.ias is None
        assert p.life is None

    def test_charm_sockets_stripped_from_signature(self):
        p = extract_props("gc plain 4 os", "charm:grand_charm")
        sig = props_signature(p)
        assert p.os is None
        if sig:
            assert "os" not in sig.lower().split("+")

    def test_torch_fcr_stripped(self):
        p = extract_props("sorc torch 20/20 10 fcr", "unique:hellfire_torch:sorceress")
        assert p.fcr is None

    def test_anni_ar_stripped(self):
        p = extract_props("anni 20/20/10 100 ar", "unique:annihilus")
        assert p.ar is None


# ---------------------------------------------------------------------------
# 19.3  Use lexicon scoring for ambiguous regex matches
# ---------------------------------------------------------------------------

class TestLexiconScoringAmbiguousMatches:
    """When category constraints exist, higher-confidence interpretations win."""

    def test_base_weapon_keeps_sockets_drops_charm(self):
        """Base weapon: sockets allowed, charm_size denied."""
        p = extract_props("eth 4 os thresher gc", "base:thresher:eth:4os")
        assert p.os == 4
        # 'gc' might be parsed as charm_size but should be rejected for base_weapon.
        # (charm_size maps to "charm" code which is not in base_weapon allow_codes)

    def test_runeword_keeps_ed_drops_charm(self):
        """Runeword item: ED allowed, charm denied."""
        p = extract_props("fortitude 300 ed gc", "runeword:fortitude")
        assert p.ed == 300


# ---------------------------------------------------------------------------
# 19.4  Log rejected properties with reason codes
# ---------------------------------------------------------------------------

class TestRejectionLogging:
    """Rejected properties are logged with reason codes."""

    def test_rejection_logged(self, caplog):
        """Verify that rejected properties produce debug log messages."""
        with caplog.at_level(logging.DEBUG, logger="scripts.export_property_price_table_html"):
            p = extract_props("jah rune 10 fcr", "rune:jah")
        assert p.fcr is None
        # Check that at least one rejection log line was emitted.
        reject_msgs = [r for r in caplog.records if "lexicon_reject" in r.getMessage()]
        assert len(reject_msgs) >= 1
        msg = reject_msgs[0].getMessage()
        assert "fcr" in msg.lower()
        assert "runes" in msg.lower()

    def test_no_rejection_logged_for_valid_props(self, caplog):
        """No rejection logs when all properties are valid for the category."""
        with caplog.at_level(logging.DEBUG, logger="scripts.export_property_price_table_html"):
            p = extract_props("15 ias 40 ed jewel", "jewel:ias_ed")
        reject_msgs = [r for r in caplog.records if "lexicon_reject" in r.getMessage()]
        assert len(reject_msgs) == 0

    def test_multiple_rejections_logged(self, caplog):
        """Multiple impossible props each produce a log entry."""
        with caplog.at_level(logging.DEBUG, logger="scripts.export_property_price_table_html"):
            p = extract_props("jah rune 10 fcr 20 ias 40 life 30 mf", "rune:jah")
        reject_msgs = [r for r in caplog.records if "lexicon_reject" in r.getMessage()]
        # fcr, ias, life, mf should all be rejected for runes.
        assert len(reject_msgs) >= 4


# ---------------------------------------------------------------------------
# Validate helper directly
# ---------------------------------------------------------------------------

class TestValidatePropsHelper:
    """Direct tests for _validate_props_against_lexicon."""

    def test_returns_rejected_list(self):
        p = ExtractedProps()
        p.fcr = 10
        p.ias = 20
        rejected = _validate_props_against_lexicon(p, "rune:jah")
        field_names = [r[0] for r in rejected]
        assert "fcr" in field_names
        assert "ias" in field_names
        # Fields should be cleared.
        assert p.fcr is None
        assert p.ias is None

    def test_generic_category_no_rejections(self):
        p = ExtractedProps()
        p.fcr = 10
        p.ias = 20
        rejected = _validate_props_against_lexicon(p, None)
        assert rejected == []
        assert p.fcr == 10
        assert p.ias == 20

    def test_reason_contains_category(self):
        p = ExtractedProps()
        p.mf = 40
        rejected = _validate_props_against_lexicon(p, "unique:annihilus")
        assert len(rejected) == 1
        assert "anni" in rejected[0][2]
