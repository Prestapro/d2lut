"""Bug condition exploration tests — Property 1: Fault Condition.

**Validates: Requirements 1.1, 1.2, 6.1, 6.2, 6.3, 8.1, 8.2, 9.1, 9.2, 12.1, 12.2, 13.1, 13.2, 14.2, 14.3, 15.1, 15.4**

These tests encode the EXPECTED (correct) behavior for known parser gaps and
presenter regressions.  On unfixed code they are expected to FAIL — failure
confirms the bugs exist.  After the fixes land, these same tests validate
correctness.

DO NOT fix the code to make these pass during the exploration phase.
"""

import pytest

from scripts.export_property_price_table_html import (
    extract_props,
    props_signature,
)


# ---------------------------------------------------------------------------
# Req-level parser gaps  (Requirements 6.1, 6.2, 6.3)
# ---------------------------------------------------------------------------

class TestReqLevelParserGaps:
    """RE_REQ_LVL currently only handles 'req N', 'req lvl N', 'lvl req N'.
    These tests exercise common d2jsp and OCR-corrupted formats that are NOT
    matched today."""

    def test_rlvl_format(self):
        """'rlvl 9' is a common shorthand — should parse req_lvl=9."""
        p = extract_props("rlvl 9 sc 3/20/20")
        assert p.req_lvl == 9, f"Expected req_lvl=9, got {p.req_lvl}"

    def test_ocr_corrupted_lvl(self):
        """OCR often renders 'lvl' as '1v1' — should still parse req_lvl=9."""
        p = extract_props("req 1v1 9")
        assert p.req_lvl == 9, f"Expected req_lvl=9, got {p.req_lvl}"


# ---------------------------------------------------------------------------
# Runeword kit vs finished detection  (Requirements 9.1, 9.2)
# ---------------------------------------------------------------------------

class TestRunewordKitDetection:
    """extract_props() has no 'kit' field today.  Kit listings (base + runes)
    should be distinguished from finished runewords."""

    def test_kit_field_exists_and_true_for_kit_listing(self):
        """'jah ith ber + eth archon plate' is a kit — expect kit=True."""
        p = extract_props("jah ith ber + eth archon plate")
        # The field may not exist yet; accessing it should not crash.
        kit_val = getattr(p, "kit", None)
        assert kit_val is True, (
            f"Expected kit=True for kit listing, got kit={kit_val}"
        )


# ---------------------------------------------------------------------------
# Roll-aware runeword extraction  (Requirements 12.1, 12.2)
# ---------------------------------------------------------------------------

class TestRollAwareRuneword:
    """CTA with '+6 BO' should produce a roll-qualified signature."""

    def test_cta_bo_in_signature(self):
        """'CTA +6 BO / +1 BC' → signature should contain BO level detail."""
        p = extract_props("CTA +6 BO / +1 BC")
        sig = props_signature(p)
        assert sig is not None, "Signature should not be None for CTA listing"
        # Expect something like 'runeword:cta + +6BO' or at least '+6BO' in sig
        assert "+6BO" in (sig or "").upper() or "6BO" in (sig or "").upper(), (
            f"Expected roll-qualified BO in signature, got: {sig}"
        )


# ---------------------------------------------------------------------------
# Torch/anni OCR noise  (Requirements 13.1, 13.2)
# ---------------------------------------------------------------------------

class TestTorchAnniOcrNoise:
    """OCR commonly substitutes 'O' for '0' in digit contexts."""

    def test_anni_ocr_o_for_zero(self):
        """'anni 20/2O/1O' — 'O' is OCR for '0', expect anni_attrs=20."""
        p = extract_props("anni 20/2O/1O")
        assert p.anni_attrs == 20, (
            f"Expected anni_attrs=20 (OCR O→0), got {p.anni_attrs}"
        )
        assert p.anni_res == 20, (
            f"Expected anni_res=20 (OCR O→0), got {p.anni_res}"
        )
        assert p.anni_xp == 10, (
            f"Expected anni_xp=10 (OCR O→0), got {p.anni_xp}"
        )

    def test_torch_class_from_prefix(self):
        """'sorc torch 20/20' — class parsed from prefix position.

        NOTE (exploration): This PASSES on unfixed code — RE_TORCH_CLASS
        already handles 'sorc torch' via alternation.  Retained as a
        preservation / regression guard.
        """
        p = extract_props("sorc torch 20/20")
        assert p.torch_class == "sorceress", (
            f"Expected torch_class='sorceress', got {p.torch_class}"
        )
        assert p.torch_attrs == 20
        assert p.torch_res == 20


# ---------------------------------------------------------------------------
# Base item parser gaps  (Requirements 14.2, 14.3)
# ---------------------------------------------------------------------------

class TestBaseItemParserGaps:
    """'eth 4 os GT' should produce a signature with giant_thresher + eth + 4os.

    NOTE (exploration): This PASSES on unfixed code — BASE_PATTERNS already
    matches \\bgt\\b and RE_SOCKETS handles '4 os'.  Retained as a
    preservation / regression guard.
    """

    def test_eth_4os_gt_signature(self):
        p = extract_props("eth 4 os GT")
        sig = props_signature(p)
        assert sig is not None, "Signature should not be None for 'eth 4 os GT'"
        assert p.base == "giant_thresher", f"Expected base='giant_thresher', got {p.base}"
        assert p.eth is True
        assert p.os == 4, f"Expected os=4, got {p.os}"
        assert "giant_thresher" in (sig or "")
        assert "eth" in (sig or "")
        assert "4os" in (sig or "")


# ---------------------------------------------------------------------------
# Jewel combo parsing  (Requirements 15.1, 15.4)
# ---------------------------------------------------------------------------

class TestJewelComboParsing:
    """'15ias/40ed jewel' — slash-separated shorthand should be parsed.

    NOTE (exploration): This PASSES on unfixed code — RE_IAS and RE_ED
    already parse '15ias' and '40ed' even with '/' separator.  Retained
    as a preservation / regression guard.
    """

    def test_ias_ed_jewel_shorthand(self):
        p = extract_props("15ias/40ed jewel")
        sig = props_signature(p)
        assert p.jewel is True
        assert p.ias == 15, f"Expected ias=15, got {p.ias}"
        assert p.ed == 40, f"Expected ed=40, got {p.ed}"
        assert sig is not None
        assert "15IAS" in (sig or "")
        assert "40%ED" in (sig or "")


# ---------------------------------------------------------------------------
# LLD bucket assignment  (Requirements 8.1, 8.2)
# ---------------------------------------------------------------------------

class TestLldBucketAssignment:
    """req_lvl should map to an lld_bucket label.  The field does not exist yet."""

    @pytest.mark.parametrize("req_lvl_input,expected_bucket", [
        (9, "LLD9"),
        (18, "LLD18"),
        (25, "LLD30"),
    ])
    def test_lld_bucket_from_req_lvl(self, req_lvl_input, expected_bucket):
        """Bucket assignment: req_lvl → LLD9/LLD18/LLD30."""
        p = extract_props(f"sc 3/20/20 req {req_lvl_input}")
        bucket = getattr(p, "lld_bucket", None)
        assert bucket == expected_bucket, (
            f"Expected lld_bucket='{expected_bucket}' for req_lvl={req_lvl_input}, "
            f"got lld_bucket={bucket}"
        )
