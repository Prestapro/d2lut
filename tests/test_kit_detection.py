"""Regression tests for runeword kit vs finished detection.

**Validates: Requirements 9.1, 9.2, 9.3, 9.5, 10.2**

Tests cover:
- Kit detection for base + rune recipe sequences
- Multi-line recipe cases where runes are spread across lines
- Finished runeword detection (runeword name + roll stats → NOT kit)
- Signature differentiation: kit prefix ensures separate grouping
- Unmade/kit shorthand hints
"""

import pytest

from scripts.export_property_price_table_html import extract_props, props_signature


class TestKitDetectionBasic:
    """Requirement 9.1: base + rune names without roll stats → kit."""

    def test_enigma_kit_single_line(self):
        p = extract_props("jah ith ber + eth archon plate")
        assert p.kit is True
        assert p.base == "archon_plate"
        assert p.eth is True

    def test_spirit_kit(self):
        p = extract_props("tal thul ort amn + monarch")
        assert p.kit is True
        assert p.base == "monarch"

    def test_infinity_kit(self):
        p = extract_props("ber mal ber ist + eth giant thresher")
        assert p.kit is True
        assert p.base == "giant_thresher"

    def test_grief_kit(self):
        p = extract_props("eth tir lo mal ral + phase blade")
        assert p.kit is True
        assert p.base == "phase_blade"

    def test_insight_kit(self):
        p = extract_props("ral tir tal sol + eth thresher")
        assert p.kit is True
        assert p.base == "thresher"

    def test_unmade_enigma_hint(self):
        p = extract_props("unmade enigma mage plate")
        assert p.kit is True
        assert p.base == "mage_plate"

    def test_hoto_kit_hint(self):
        p = extract_props("hoto kit flail")
        assert p.kit is True


class TestFinishedDetection:
    """Requirement 9.2: runeword name + roll stats → NOT kit (finished)."""

    def test_enigma_finished(self):
        p = extract_props("enigma 775 def mage plate")
        assert p.kit is False
        assert p.base == "mage_plate"
        assert p.defense == 775

    def test_spirit_finished(self):
        p = extract_props("spirit monarch 35fcr")
        assert p.kit is False
        assert p.base == "monarch"
        assert p.fcr == 35

    def test_infinity_finished(self):
        p = extract_props("infinity eth gt -55 res")
        assert p.kit is False
        assert p.base == "giant_thresher"

    def test_grief_finished(self):
        p = extract_props("grief pb 40ias 400dmg")
        assert p.kit is False
        assert p.base == "phase_blade"

    def test_plain_base_not_kit(self):
        """A plain base item without rune recipe is not a kit."""
        p = extract_props("eth 4 os GT")
        assert p.kit is False
        assert p.base == "giant_thresher"


class TestMultiLineRecipeCases:
    """Requirement 9.5: multi-line recipe cases where runes are spread across lines."""

    def test_enigma_kit_newline_separated(self):
        p = extract_props("jah ith ber\neth archon plate")
        assert p.kit is True
        assert p.base == "archon_plate"
        assert p.eth is True

    def test_enigma_kit_base_first(self):
        p = extract_props("eth archon plate\njah ith ber")
        assert p.kit is True
        assert p.base == "archon_plate"

    def test_enigma_kit_runes_split(self):
        p = extract_props("jah ith\nber + eth ap")
        assert p.kit is True
        assert p.base == "archon_plate"

    def test_spirit_kit_three_lines(self):
        p = extract_props("tal thul\nort amn\nmonarch")
        assert p.kit is True
        assert p.base == "monarch"

    def test_infinity_kit_two_lines(self):
        p = extract_props("ber mal ber ist\neth gt")
        assert p.kit is True
        assert p.base == "giant_thresher"

    def test_grief_kit_two_lines(self):
        p = extract_props("eth tir lo mal ral\nphase blade")
        assert p.kit is True
        assert p.base == "phase_blade"

    def test_unmade_enigma_newline(self):
        p = extract_props("unmade enigma\nmage plate")
        assert p.kit is True
        assert p.base == "mage_plate"

    def test_finished_multiline_not_kit(self):
        """Finished runeword across lines should NOT be detected as kit."""
        p = extract_props("enigma\n775 def\nmage plate")
        assert p.kit is False
        assert p.defense == 775


class TestKitSignatureDifferentiation:
    """Requirement 10.2: kit and finished with same runeword → different signatures."""

    def test_enigma_kit_vs_finished_different_sigs(self):
        kit_p = extract_props("jah ith ber + eth archon plate")
        kit_sig = props_signature(kit_p)
        fin_p = extract_props("enigma 775 def archon plate")
        fin_sig = props_signature(fin_p)
        assert kit_sig != fin_sig
        assert kit_sig is not None
        assert fin_sig is not None
        assert kit_sig.startswith("kit")
        assert not fin_sig.startswith("kit")

    def test_spirit_kit_vs_finished_different_sigs(self):
        kit_p = extract_props("tal thul ort amn + monarch")
        kit_sig = props_signature(kit_p)
        fin_p = extract_props("spirit monarch 35fcr")
        fin_sig = props_signature(fin_p)
        assert kit_sig != fin_sig
        assert "kit" in kit_sig
        assert "kit" not in fin_sig

    def test_kit_signature_prefix(self):
        """Requirement 9.3: kit signature starts with 'kit' token."""
        p = extract_props("jah ith ber + eth archon plate")
        sig = props_signature(p)
        assert sig is not None
        parts = sig.split(" + ")
        assert parts[0] == "kit"
