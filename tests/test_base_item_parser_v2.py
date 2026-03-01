"""Regression tests for base item parser v2 — OCR-corrupted base excerpts.

Covers:
- Superior prefix detection (Req 14.1)
- Defense with colon format (Req 14.2)
- Socketed (N) format (Req 14.3)
- New abbreviations: zerker, ds, wf, st, sr (Req 14.5)
- Trade-relevant bases with various stat combinations (Req 14.6)

Requirements: 14.1, 14.2, 14.3, 14.5, 14.6
"""

from __future__ import annotations

import pytest

from scripts.export_property_price_table_html import extract_props, props_signature


# ---------------------------------------------------------------------------
# Superior prefix detection (Req 14.1)
# ---------------------------------------------------------------------------

class TestSuperiorDetection:
    def test_sup_prefix(self):
        p = extract_props("sup mp 15ed")
        assert p.superior is True
        assert p.base == "mage_plate"
        assert p.ed == 15

    def test_superior_prefix(self):
        p = extract_props("superior archon plate 15ed")
        assert p.superior is True
        assert p.base == "archon_plate"
        assert p.ed == 15

    def test_sup_in_signature(self):
        sig = props_signature(extract_props("sup monarch 4os"))
        assert sig is not None
        assert "sup" in sig
        assert "monarch" in sig

    def test_no_superior_when_absent(self):
        p = extract_props("eth monarch 4os")
        assert p.superior is False

    def test_sup_eth_combo(self):
        p = extract_props("sup eth mage plate 15ed")
        assert p.superior is True
        assert p.eth is True
        assert p.base == "mage_plate"


# ---------------------------------------------------------------------------
# Defense parsing — colon format (Req 14.2)
# ---------------------------------------------------------------------------

class TestDefenseParsing:
    def test_defense_colon_format(self):
        p = extract_props("archon plate defense: 524")
        assert p.defense == 524
        assert p.base == "archon_plate"

    def test_defense_colon_no_space(self):
        p = extract_props("monarch defense:148")
        assert p.defense == 148

    def test_Ndef_format(self):
        p = extract_props("775def mp")
        assert p.defense == 775
        assert p.base == "mage_plate"

    def test_def_N_format(self):
        p = extract_props("def 500 archon plate")
        assert p.defense == 500

    def test_defense_N_format(self):
        p = extract_props("defense 420 monarch")
        assert p.defense == 420


# ---------------------------------------------------------------------------
# Socket parsing — socketed (N) format (Req 14.3)
# ---------------------------------------------------------------------------

class TestSocketParsing:
    def test_socketed_parens(self):
        p = extract_props("monarch socketed (4)")
        assert p.os == 4

    def test_socketed_no_parens(self):
        p = extract_props("thresher socketed 4")
        assert p.os == 4

    def test_Nos_no_space(self):
        p = extract_props("eth gt 4os")
        assert p.os == 4

    def test_N_os_with_space(self):
        p = extract_props("eth cv 4 os")
        assert p.os == 4

    def test_N_socket(self):
        p = extract_props("monarch 4 socket")
        assert p.os == 4

    def test_N_soc(self):
        p = extract_props("pb 5 soc")
        assert p.os == 5


# ---------------------------------------------------------------------------
# New abbreviations (Req 14.5)
# ---------------------------------------------------------------------------

class TestNewBaseAbbreviations:
    def test_zerker(self):
        p = extract_props("eth zerker 6os")
        assert p.base == "berserker_axe"
        assert p.eth is True
        assert p.os == 6

    def test_ds_dusk_shroud(self):
        p = extract_props("ds 4os 15ed")
        assert p.base == "dusk_shroud"
        assert p.os == 4
        assert p.ed == 15

    def test_wf_wire_fleece(self):
        p = extract_props("sup wf 15ed")
        assert p.base == "wire_fleece"
        assert p.superior is True

    def test_st_sacred_targe(self):
        p = extract_props("eth st 4os")
        assert p.base == "sacred_targe"
        assert p.eth is True

    def test_sr_sacred_rondache(self):
        p = extract_props("sr 4os 45@ sup")
        assert p.base == "sacred_rondache"
        assert p.os == 4
        assert p.all_res == 45
        assert p.superior is True

    def test_full_name_sacred_targe(self):
        p = extract_props("sacred targe 4os eth")
        assert p.base == "sacred_targe"

    def test_full_name_sacred_rondache(self):
        p = extract_props("sacred rondache 4os")
        assert p.base == "sacred_rondache"

    def test_full_name_dusk_shroud(self):
        p = extract_props("dusk shroud 4os")
        assert p.base == "dusk_shroud"

    def test_full_name_wire_fleece(self):
        p = extract_props("wire fleece 15ed sup")
        assert p.base == "wire_fleece"


# ---------------------------------------------------------------------------
# Trade-relevant bases with stat combos + signatures (Req 14.6)
# ---------------------------------------------------------------------------

class TestTradeRelevantBaseCombos:
    def test_eth_gt_4os_signature(self):
        sig = props_signature(extract_props("eth 4 os GT"))
        assert sig == "giant_thresher + eth + 4os"

    def test_sup_mp_15ed_signature(self):
        sig = props_signature(extract_props("sup mp 15ed"))
        assert sig == "mage_plate + sup + 15%ED"

    def test_eth_cv_4os_signature(self):
        sig = props_signature(extract_props("eth cv 4 os"))
        assert sig == "colossus_voulge + eth + 4os"

    def test_eth_zerker_6os_signature(self):
        sig = props_signature(extract_props("eth zerker 6os"))
        assert sig == "berserker_axe + eth + 6os"

    def test_eth_thresher_4os_signature(self):
        sig = props_signature(extract_props("eth thresher 4os"))
        assert sig == "thresher + eth + 4os"

    def test_monarch_4os_signature(self):
        sig = props_signature(extract_props("monarch 4os"))
        assert sig == "monarch + 4os"

    def test_sup_ap_defense_colon_signature(self):
        sig = props_signature(extract_props("sup archon plate defense: 524 15ed"))
        assert sig == "archon_plate + sup + 15%ED + 524def"

    def test_eth_gpa_4os_signature(self):
        sig = props_signature(extract_props("eth gpa 4os"))
        assert sig == "great_poleaxe + eth + 4os"

    def test_pb_5os_signature(self):
        sig = props_signature(extract_props("phase blade 5os"))
        assert sig == "phase_blade + 5os"

    def test_ds_4os_signature(self):
        sig = props_signature(extract_props("ds 4os"))
        assert sig == "dusk_shroud + 4os"

    def test_eth_ca_socketed_4_signature(self):
        sig = props_signature(extract_props("eth cryptic axe socketed (4)"))
        assert sig == "cryptic_axe + eth + 4os"

    def test_sup_wf_15ed_signature(self):
        sig = props_signature(extract_props("sup wire fleece 15ed"))
        assert sig == "wire_fleece + sup + 15%ED"

    def test_st_4os_45res_signature(self):
        sig = props_signature(extract_props("sacred targe 4os 45@"))
        assert sig == "sacred_targe + 4os + @45"
