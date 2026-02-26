"""Unit tests for LLD bucket assignment logic.

Validates: Requirements 8.1, 8.2
"""

from scripts.export_property_price_table_html import (
    _assign_lld_bucket,
    extract_props,
)


# ---------------------------------------------------------------------------
# Direct _assign_lld_bucket tests (Requirement 8.1)
# ---------------------------------------------------------------------------

class TestAssignLldBucket:
    """Exhaustive boundary tests for the bucket mapping function."""

    def test_req_lvl_1_is_lld9(self):
        assert _assign_lld_bucket(1, False) == "LLD9"

    def test_req_lvl_9_is_lld9(self):
        assert _assign_lld_bucket(9, False) == "LLD9"

    def test_req_lvl_10_is_lld18(self):
        assert _assign_lld_bucket(10, False) == "LLD18"

    def test_req_lvl_18_is_lld18(self):
        assert _assign_lld_bucket(18, False) == "LLD18"

    def test_req_lvl_19_is_lld30(self):
        assert _assign_lld_bucket(19, False) == "LLD30"

    def test_req_lvl_30_is_lld30(self):
        assert _assign_lld_bucket(30, False) == "LLD30"

    def test_req_lvl_31_is_mld(self):
        assert _assign_lld_bucket(31, False) == "MLD"

    def test_req_lvl_49_is_mld(self):
        assert _assign_lld_bucket(49, False) == "MLD"

    def test_req_lvl_50_is_hld(self):
        assert _assign_lld_bucket(50, False) == "HLD"

    def test_req_lvl_99_is_hld(self):
        assert _assign_lld_bucket(99, False) == "HLD"

    def test_none_no_lld_is_unknown(self):
        assert _assign_lld_bucket(None, False) == "unknown"

    def test_none_with_lld_true_is_lld30(self):
        """Requirement 8.2: lld heuristic flag defaults to LLD30."""
        assert _assign_lld_bucket(None, True) == "LLD30"

    def test_req_lvl_overrides_lld_flag(self):
        """When req_lvl is present, bucket is based on req_lvl regardless of lld flag."""
        assert _assign_lld_bucket(9, True) == "LLD9"
        assert _assign_lld_bucket(50, True) == "HLD"


# ---------------------------------------------------------------------------
# Integration: extract_props sets lld_bucket correctly
# ---------------------------------------------------------------------------

class TestExtractPropsLldBucket:
    """Verify lld_bucket is assigned at the end of extract_props()."""

    def test_explicit_req_lvl_9(self):
        p = extract_props("jewel 15 ias req 9", None)
        assert p.req_lvl == 9
        assert p.lld_bucket == "LLD9"

    def test_explicit_req_lvl_18(self):
        p = extract_props("jewel 15 ias 30 ed req lvl 18", None)
        assert p.req_lvl == 18
        assert p.lld_bucket == "LLD18"

    def test_explicit_req_lvl_30(self):
        p = extract_props("3/20/20 sc req 25", None)
        assert p.req_lvl == 25
        assert p.lld_bucket == "LLD30"

    def test_explicit_req_lvl_mld(self):
        p = extract_props("ring 10fcr req 42", None)
        assert p.req_lvl == 42
        assert p.lld_bucket == "MLD"

    def test_explicit_req_lvl_hld(self):
        p = extract_props("amulet 2/20 req 67", None)
        assert p.req_lvl == 67
        assert p.lld_bucket == "HLD"

    def test_lld_keyword_no_req_defaults_lld30(self):
        """Requirement 8.2: lld keyword + no req_lvl → LLD30."""
        p = extract_props("lld sc 3/20/20", None)
        assert p.lld is True
        assert p.req_lvl is None
        assert p.lld_bucket == "LLD30"

    def test_no_lld_no_req_is_unknown(self):
        p = extract_props("some random text", None)
        assert p.lld_bucket == "unknown"

    def test_sc_with_stats_infers_lld_and_bucket(self):
        """SC with pvp stats infers lld=True; no req_lvl → LLD30."""
        p = extract_props("5fhr 11lr sc", None)
        assert p.lld is True
        assert p.lld_bucket == "LLD30"
