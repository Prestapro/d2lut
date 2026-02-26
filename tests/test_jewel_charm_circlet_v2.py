"""Jewel, charm, and circlet parser v2 — regression tests.

**Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5**

≥5 real d2jsp LLD excerpts per item type (jewel, SC, LC, GC, circlet).
"""

from __future__ import annotations

import pytest

from scripts.export_property_price_table_html import extract_props, props_signature


# ──────────────────────────────────────────────────────────────────
# Jewel excerpts (≥5)  — Requirement 15.1
# ──────────────────────────────────────────────────────────────────

JEWEL_CASES = [
    (
        "15/40 jewel req 9",
        {"jewel": True, "ias": 15, "ed": 40, "req_lvl": 9, "lld": True},
        "jewel + 40%ED + 15IAS + req9 + LLD",
    ),
    (
        "jewel 9max 76ar 30life req 9",
        {"jewel": True, "max_dmg": 9, "ar": 76, "life": 30, "req_lvl": 9, "lld": True},
        "jewel + 76AR + 9max + 30life + req9 + LLD",
    ),
    (
        "15ias/40ed jewel",
        {"jewel": True, "ias": 15, "ed": 40},
        "jewel + 40%ED + 15IAS",
    ),
    (
        "7fhr jewel req 9",
        {"jewel": True, "fhr": 7, "req_lvl": 9, "lld": True},
        "jewel + 7FHR + req9 + LLD",
    ),
    (
        "30ed/9max jewel",
        {"jewel": True, "ed": 30, "max_dmg": 9},
        "jewel + 30%ED + 9max",
    ),
]


# ──────────────────────────────────────────────────────────────────
# Small Charm (SC) excerpts (≥5)  — Requirement 15.2
# ──────────────────────────────────────────────────────────────────

SC_CASES = [
    (
        "3/20/20 sc lld",
        {"charm_size": "sc", "max_dmg": 3, "ar": 20, "life": 20, "lld": True},
        "SC + 20AR + 3max + 20life + LLD",
    ),
    (
        "5fhr/11lr sc",
        {"charm_size": "sc", "fhr": 5, "light_res": 11, "lld": True},
        "SC + 5FHR + 11LR + LLD",
    ),
    (
        "20life/5@ sc",
        {"charm_size": "sc", "all_res": 5, "life": 20, "lld": True},
        "SC + @5 + 20life + LLD",
    ),
    (
        "5fhr sc req 9",
        {"charm_size": "sc", "fhr": 5, "req_lvl": 9, "lld": True},
        "SC + 5FHR + req9 + LLD",
    ),
    (
        "3/20/20 sc req 9",
        {"charm_size": "sc", "max_dmg": 3, "ar": 20, "life": 20, "req_lvl": 9, "lld": True},
        "SC + 20AR + 3max + 20life + req9 + LLD",
    ),
    (
        "7mf/11lr sc",
        {"charm_size": "sc", "mf": 7, "light_res": 11, "lld": True},
        "SC + 7MF + 11LR + LLD",
    ),
]


# ──────────────────────────────────────────────────────────────────
# Large Charm (LC) excerpts (≥5)  — Requirement 15.2
# ──────────────────────────────────────────────────────────────────

LC_CASES = [
    (
        "lc 5fhr 22life",
        {"charm_size": "lc", "fhr": 5, "life": 22},
        "LC + 5FHR + 22life",
    ),
    (
        "lc 5@ 22life",
        {"charm_size": "lc", "all_res": 5, "life": 22},
        "LC + @5 + 22life",
    ),
    (
        "lc 5fhr 5@ lld",
        {"charm_size": "lc", "fhr": 5, "all_res": 5, "lld": True},
        "LC + @5 + 5FHR + LLD",
    ),
    (
        "lc 22life 11lr",
        {"charm_size": "lc", "life": 22, "light_res": 11},
        "LC + 22life + 11LR",
    ),
    (
        "lc 5fhr 11cr",
        {"charm_size": "lc", "fhr": 5, "cold_res": 11},
        "LC + 5FHR + 11CR",
    ),
]


# ──────────────────────────────────────────────────────────────────
# Grand Charm (GC) excerpts (≥5)  — Requirement 15.2
# ──────────────────────────────────────────────────────────────────

GC_CASES = [
    (
        "gc 12fhr max/ar/life",
        {"charm_size": "gc", "grand_charm": True, "fhr": 12},
        "GC + 12FHR",
    ),
    (
        "gc 12fhr lld",
        {"charm_size": "gc", "grand_charm": True, "fhr": 12, "lld": True},
        "GC + 12FHR + LLD",
    ),
    (
        "pcomb gc 45life",
        {"charm_size": "gc", "grand_charm": True, "skiller": "pala_combat_skiller", "life": 45},
        "pala_combat_skiller + GC + 45life",
    ),
    (
        "cold skiller gc 45life",
        {"charm_size": "gc", "grand_charm": True, "skiller": "sorc_cold_skiller", "life": 45},
        "sorc_cold_skiller + GC + 45life",
    ),
    (
        "gc 3/20/20 lld",
        {"charm_size": "gc", "grand_charm": True, "max_dmg": 3, "ar": 20, "life": 20, "lld": True},
        "GC + 20AR + 3max + 20life + LLD",
    ),
]


# ──────────────────────────────────────────────────────────────────
# Circlet excerpts (≥5)  — Requirement 15.3
# ──────────────────────────────────────────────────────────────────

CIRCLET_CASES = [
    (
        "2/20 circlet 2os",
        {"item_form": "circlet", "skills": 2, "fcr": 20, "os": 2},
        "circlet + 2os + 20FCR + +2skills",
    ),
    (
        "circlet 2sorc 20fcr 2os frw",
        {"item_form": "circlet", "class_skills": "sorceress", "skills": 2, "fcr": 20, "os": 2},
        "circlet + sorceress_skills + 2os + 20FCR + +2skills",
    ),
    (
        "tiara 2/20 30frw",
        {"item_form": "tiara", "skills": 2, "fcr": 20, "frw": 30},
        "tiara + 20FCR + 30FRW + +2skills",
    ),
    (
        "diadem 2/20 2os",
        {"item_form": "diadem", "skills": 2, "fcr": 20, "os": 2},
        "diadem + 2os + 20FCR + +2skills",
    ),
    (
        "coronet 2pal 20fcr",
        {"item_form": "coronet", "class_skills": "paladin", "skills": 2, "fcr": 20},
        "coronet + paladin_skills + 20FCR + +2skills",
    ),
]


# ──────────────────────────────────────────────────────────────────
# Parametrized test runner
# ──────────────────────────────────────────────────────────────────

ALL_CASES = (
    [("jewel", *c) for c in JEWEL_CASES]
    + [("sc", *c) for c in SC_CASES]
    + [("lc", *c) for c in LC_CASES]
    + [("gc", *c) for c in GC_CASES]
    + [("circlet", *c) for c in CIRCLET_CASES]
)


@pytest.mark.parametrize(
    "item_type,excerpt,expected_fields,expected_sig",
    ALL_CASES,
    ids=[f"{c[0]}::{c[1][:40]}" for c in ALL_CASES],
)
def test_jewel_charm_circlet_v2(item_type, excerpt, expected_fields, expected_sig):
    """Each real d2jsp LLD excerpt produces the expected fields and signature."""
    props = extract_props(excerpt)
    sig = props_signature(props)

    # Check signature
    assert sig == expected_sig, (
        f"[{item_type}] Signature mismatch for {excerpt!r}:\n"
        f"  expected: {expected_sig!r}\n"
        f"  got:      {sig!r}"
    )

    # Check expected fields
    for field, expected_val in expected_fields.items():
        actual_val = getattr(props, field)
        assert actual_val == expected_val, (
            f"[{item_type}] Field {field!r} mismatch for {excerpt!r}:\n"
            f"  expected: {expected_val!r}\n"
            f"  got:      {actual_val!r}"
        )


# ──────────────────────────────────────────────────────────────────
# Slash-separated shorthand tests — Requirement 15.4
# ──────────────────────────────────────────────────────────────────

class TestSlashShorthand:
    """Bare slash-separated numbers are interpreted based on item context."""

    def test_jewel_ias_ed_shorthand(self):
        """15/40 on jewel → ias=15, ed=40."""
        p = extract_props("15/40 jewel")
        assert p.ias == 15
        assert p.ed == 40

    def test_jewel_triple_max_ar_life(self):
        """9/76/30 on jewel → max_dmg=9, ar=76, life=30."""
        p = extract_props("9/76/30 jewel")
        assert p.max_dmg == 9
        assert p.ar == 76
        assert p.life == 30

    def test_charm_triple(self):
        """3/20/20 on sc → max_dmg=3, ar=20, life=20."""
        p = extract_props("3/20/20 sc")
        assert p.max_dmg == 3
        assert p.ar == 20
        assert p.life == 20

    def test_circlet_two_twenty(self):
        """2/20 on circlet → skills=2, fcr=20."""
        p = extract_props("2/20 circlet")
        assert p.skills == 2
        assert p.fcr == 20

    def test_circlet_triple(self):
        """3/20/20 on circlet → skills=3, fcr=20, frw=20."""
        p = extract_props("circlet 3/20/20")
        assert p.skills == 3
        assert p.fcr == 20
        assert p.frw == 20


# ──────────────────────────────────────────────────────────────────
# GC dedup regression — no duplicate GC in signature
# ──────────────────────────────────────────────────────────────────

class TestGCDedup:
    """charm_size=gc and grand_charm=True should not produce duplicate GC."""

    def test_gc_skiller_no_dup(self):
        sig = props_signature(extract_props("pcomb gc 45life"))
        assert sig is not None
        assert sig.count("GC") == 1

    def test_gc_plain_no_dup(self):
        sig = props_signature(extract_props("pcomb gc plain"))
        assert sig is not None
        assert sig.count("GC") == 1

    def test_gc_fhr_no_dup(self):
        sig = props_signature(extract_props("gc 12fhr lld"))
        assert sig is not None
        assert sig.count("GC") == 1
