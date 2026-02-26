"""Regression tests for req-level parser hardening.

Covers charms, jewels, circlets, and LLD excerpts across all RE_REQ_LVL
pattern variants: standard, rlvl, lv, colon/equals, OCR-noise.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
"""

import pytest

from scripts.export_property_price_table_html import extract_props, props_signature


# ---------------------------------------------------------------------------
# Requirement 6.1 — Standard and extended formats
# ---------------------------------------------------------------------------

class TestReqLevelStandardFormats:
    """RE_REQ_LVL recognises req N, req9, rlvl N, lv N, lvN,
    required lvl N, required level N, lvl req N."""

    @pytest.mark.parametrize("excerpt,expected_req", [
        # Existing formats (must still work)
        ("sc 3/20/20 req 9", 9),
        ("jewel 15ias req lvl 18", 18),
        ("circlet 2/20 lvl req 30", 30),
        ("req9 sc 5fhr", 9),
        # New: rlvl N
        ("rlvl 9 sc 3/20/20", 9),
        ("rlvl 18 jewel 15ias 40ed", 18),
        # New: lv N / lvN
        ("lv9 sc 5fhr 11lr", 9),
        ("lv 30 tiara 2/20", 30),
        ("lv18 jewel 15ias", 18),
        # New: required lvl / required level
        ("required lvl 25 gc 12fhr", 25),
        ("required level 30 circlet 2/20", 30),
    ])
    def test_standard_format(self, excerpt, expected_req):
        p = extract_props(excerpt)
        assert p.req_lvl == expected_req, (
            f"Expected req_lvl={expected_req} for {excerpt!r}, got {p.req_lvl}"
        )


# ---------------------------------------------------------------------------
# Requirement 6.2 — OCR-noise variants
# ---------------------------------------------------------------------------

class TestReqLevelOcrNoise:
    """OCR-corrupted 'lvl' as '1v1' or 'Iv1', and 'rvl' as 'rv1'."""

    @pytest.mark.parametrize("excerpt,expected_req", [
        ("req 1v1 9 jewel 15ias", 9),
        ("req 1v1 18 sc 3/20/20", 18),
        ("rv1 9 gc max/ar/life", 9),
        ("rv1 25 circlet 2/20", 25),
    ])
    def test_ocr_noise_format(self, excerpt, expected_req):
        p = extract_props(excerpt)
        assert p.req_lvl == expected_req, (
            f"Expected req_lvl={expected_req} for {excerpt!r}, got {p.req_lvl}"
        )


# ---------------------------------------------------------------------------
# Requirement 6.3 — Colon and equals variants
# ---------------------------------------------------------------------------

class TestReqLevelColonEquals:
    """req:N, req=N, rlvl:N formats."""

    @pytest.mark.parametrize("excerpt,expected_req", [
        ("req:18 circlet 2/20", 18),
        ("req=9 sc 3/20/20", 9),
        ("rlvl:25 jewel 15ias 40ed", 25),
        ("req:30 tiara 2os", 30),
    ])
    def test_colon_equals_format(self, excerpt, expected_req):
        p = extract_props(excerpt)
        assert p.req_lvl == expected_req, (
            f"Expected req_lvl={expected_req} for {excerpt!r}, got {p.req_lvl}"
        )


# ---------------------------------------------------------------------------
# Requirements 6.4, 6.5 — Range validation (1-99)
# ---------------------------------------------------------------------------

class TestReqLevelRangeValidation:
    """Parsed req_lvl outside 1-99 is discarded (set to None)."""

    @pytest.mark.parametrize("excerpt,expected_req", [
        ("req 1 sc", 1),       # lower bound — valid
        ("req 99 gc", 99),     # upper bound — valid
        ("req 50 jewel", 50),  # mid-range — valid
        ("req 0 sc", None),    # below range — discard
    ])
    def test_range_validation(self, excerpt, expected_req):
        p = extract_props(excerpt)
        assert p.req_lvl == expected_req, (
            f"Expected req_lvl={expected_req} for {excerpt!r}, got {p.req_lvl}"
        )


# ---------------------------------------------------------------------------
# Requirement 6.6 — Item-type coverage: charms, jewels, circlets, LLD
# ---------------------------------------------------------------------------

class TestReqLevelItemTypeCoverage:
    """Req-level parsing works correctly across item types."""

    def test_charm_sc_with_rlvl(self):
        p = extract_props("rlvl 9 sc 3/20/20")
        assert p.req_lvl == 9
        assert p.charm_size == "sc"
        assert p.lld is True

    def test_charm_gc_with_lv(self):
        p = extract_props("lv18 gc 12fhr")
        assert p.req_lvl == 18
        assert p.charm_size == "gc"
        assert p.lld is True

    def test_jewel_with_ocr_noise(self):
        p = extract_props("req 1v1 9 jewel 15ias 40ed")
        assert p.req_lvl == 9
        assert p.jewel is True
        assert p.ias == 15
        assert p.ed == 40
        assert p.lld is True

    def test_circlet_with_colon(self):
        p = extract_props("req:18 circlet 2/20")
        assert p.req_lvl == 18
        assert p.item_form == "circlet"
        assert p.lld is True

    def test_lld_excerpt_with_rv1(self):
        p = extract_props("rv1 9 sc 5fhr 11lr lld")
        assert p.req_lvl == 9
        assert p.charm_size == "sc"
        assert p.lld is True

    def test_existing_req_lvl_format_preserved(self):
        """Existing 'req lvl N' format still works identically."""
        p = extract_props("jewel 15 ias 30 ed req lvl 18")
        assert p.req_lvl == 18
        assert p.jewel is True
        assert p.ias == 15
        assert p.ed == 30
        assert p.lld is True
        sig = props_signature(p)
        assert sig == "jewel + 30%ED + 15IAS + req18 + LLD"


# ---------------------------------------------------------------------------
# Preservation — existing req-level matches produce identical results
# ---------------------------------------------------------------------------

class TestReqLevelPreservation:
    """Existing req-level patterns must produce identical results after expansion."""

    @pytest.mark.parametrize("excerpt,expected_sig", [
        ("jewel 15 ias 30 ed req lvl 18", "jewel + 30%ED + 15IAS + req18 + LLD"),
        ("3/20/20 sc", "SC + 20AR + 3max + 20life + LLD"),
        ("5fhr 11lr sc", "SC + 5FHR + 11LR + LLD"),
    ])
    def test_signature_preserved(self, excerpt, expected_sig):
        p = extract_props(excerpt)
        sig = props_signature(p)
        assert sig == expected_sig, (
            f"Signature changed for {excerpt!r}: expected {expected_sig!r}, got {sig!r}"
        )
