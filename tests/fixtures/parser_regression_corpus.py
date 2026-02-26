"""Parser regression corpus — ≥30 real d2jsp excerpts that exercise known parser gaps.

Each entry is a dict with:
  - excerpt:            raw d2jsp text
  - category:           one of the 6 regression categories
  - expected_fields:    dict of ExtractedProps field → expected value (only fields that matter)
  - expected_signature: the Property_Signature the *fixed* parser should produce (or None)
  - xfail:              True when the entry is KNOWN to fail on unfixed code
  - xfail_reason:       short explanation of the parser gap

Requirements: 25.1, 25.2, 25.4
"""

CORPUS = [
    # ──────────────────────────────────────────────────────────────
    # Category 1: Runeword kit / finished confusion  (≥5)
    # ──────────────────────────────────────────────────────────────
    {
        "excerpt": "jah ith ber + eth archon plate",
        "category": "runeword_kit_finished",
        "expected_fields": {
            "base": "archon_plate",
            "eth": True,
            "kit": True,
        },
        "expected_signature": "kit + archon_plate + eth",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "eth thresher + shael + amn + sol + um",
        "category": "runeword_kit_finished",
        "expected_fields": {
            "base": "thresher",
            "eth": True,
        },
        "expected_signature": "thresher + eth",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "hel ko thul eth fal + monarch",
        "category": "runeword_kit_finished",
        "expected_fields": {
            "base": "monarch",
            "eth": True,
        },
        "expected_signature": "monarch + eth",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "enigma 775 def mp",
        "category": "runeword_kit_finished",
        "expected_fields": {
            "base": "mage_plate",
            "defense": 775,
        },
        "expected_signature": "mage_plate + 775def",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "infinity eth gt -55 res",
        "category": "runeword_kit_finished",
        "expected_fields": {
            "base": "giant_thresher",
            "eth": True,
            "enemy_res": 55,
            "rw_name": "infinity",
        },
        "expected_signature": "runeword:infinity + giant_thresher + eth + -55enemy_res",
        "xfail": False,
        "xfail_reason": None,
    },

    # ──────────────────────────────────────────────────────────────
    # Category 2: OCR-corrupted req levels  (≥5)
    # ──────────────────────────────────────────────────────────────
    {
        "excerpt": "rlvl 9 sc 3/20/20",
        "category": "ocr_req_level",
        "expected_fields": {
            "charm_size": "sc",
            "max_dmg": 3,
            "ar": 20,
            "life": 20,
            "req_lvl": 9,
            "lld": True,
        },
        # Parser currently extracts charm triple but misses req_lvl (rlvl not in RE_REQ_LVL)
        "expected_signature": "SC + 20AR + 3max + 20life + req9 + LLD",
        "xfail": True,
        "xfail_reason": "RE_REQ_LVL does not match 'rlvl N' format",
    },
    {
        "excerpt": "req 1v1 9 jewel 15ias",
        "category": "ocr_req_level",
        "expected_fields": {
            "jewel": True,
            "ias": 15,
            "req_lvl": 9,
            "lld": True,
        },
        # Parser misses req_lvl because '1v1' is OCR-corrupted 'lvl'
        "expected_signature": "jewel + 15IAS + req9 + LLD",
        "xfail": True,
        "xfail_reason": "OCR-corrupted 'lvl' as '1v1' not handled by RE_REQ_LVL",
    },
    {
        "excerpt": "lv9 sc 5fhr 11lr",
        "category": "ocr_req_level",
        "expected_fields": {
            "charm_size": "sc",
            "fhr": 5,
            "light_res": 11,
            "req_lvl": 9,
            "lld": True,
        },
        # Parser misses req_lvl ('lv9' not in RE_REQ_LVL)
        "expected_signature": "SC + 5FHR + 11LR + req9 + LLD",
        "xfail": True,
        "xfail_reason": "RE_REQ_LVL does not match 'lvN' format",
    },
    {
        "excerpt": "req:18 circlet 2/20",
        "category": "ocr_req_level",
        "expected_fields": {
            "item_form": "circlet",
            "skills": 2,
            "fcr": 20,
            "req_lvl": 18,
            "lld": True,
        },
        # Parser extracts req_lvl=18 (colon variant works) but signature is None
        # due to _ocr_low_quality_signature filtering
        "expected_signature": "circlet + 20FCR + +2skills + req18 + LLD",
        "xfail": True,
        "xfail_reason": "Signature returns None — _ocr_low_quality_signature rejects it",
    },
    {
        "excerpt": "required level 30 tiara 3/20/20",
        "category": "ocr_req_level",
        "expected_fields": {
            "item_form": "tiara",
            "req_lvl": 30,
            "lld": True,
            "max_dmg": 3,
            "ar": 20,
            "life": 20,
        },
        # Parser gets req_lvl=30 but misses charm triple (no charm_size context on tiara)
        # and signature is None
        "expected_signature": "tiara + 20AR + 3max + 20life + req30 + LLD",
        "xfail": True,
        "xfail_reason": "Charm triple not parsed on tiara; signature returns None",
    },
    {
        "excerpt": "rv1 9 gc max/ar/life",
        "category": "ocr_req_level",
        "expected_fields": {
            "charm_size": "gc",
            "grand_charm": True,
            "req_lvl": 9,
            "lld": True,
        },
        # Parser misses req_lvl ('rv1' is OCR-corrupted 'rvl'/'lvl')
        "expected_signature": "GC + req9 + LLD",
        "xfail": True,
        "xfail_reason": "OCR-corrupted 'rv1' not handled by RE_REQ_LVL",
    },

    # ──────────────────────────────────────────────────────────────
    # Category 3: Torch / anni misclassification  (≥5)
    # ──────────────────────────────────────────────────────────────
    {
        "excerpt": "anni 20/2O/1O",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "anni",
            "anni_attrs": 20,
            "anni_res": 20,
            "anni_xp": 10,
            "anni_tier": "perfect",
        },
        # OCR-fold pre-pass converts '2O' → '20' and '1O' → '10' before regex matching
        "expected_signature": "anni + 20anni_attr + 20anni_res + 10xp",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "torch sorc 20/20",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "torch",
            "torch_class": "sorceress",
            "torch_attrs": 20,
            "torch_res": 20,
            "torch_tier": "perfect",
        },
        # This actually works on current parser
        "expected_signature": "torch + sorceress_torch + sorceress_skills + 20attr + 20res",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "sorc torch 20/20",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "torch",
            "torch_class": "sorceress",
            "torch_attrs": 20,
            "torch_res": 20,
            "torch_tier": "perfect",
        },
        # This actually works on current parser (prefix class handled by RE_TORCH_CLASS)
        "expected_signature": "torch + sorceress_torch + sorceress_skills + 20attr + 20res",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "unid torch",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "torch",
        },
        # Works — produces generic torch signature
        "expected_signature": "torch",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "pala torch 18/19",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "torch",
            "torch_class": "paladin",
            "torch_attrs": 18,
            "torch_res": 19,
            "torch_tier": "near-perfect",
        },
        # Parser misses torch_class for 'pala' prefix — RE_TORCH_CLASS uses 'pal|pally|paladin'
        # but not 'pala'. However class_skills picks up 'paladin' via RE_CLASS_SKILLS.
        "expected_signature": "torch + paladin_skills + 18attr + 19res",
        "xfail": True,
        "xfail_reason": "RE_TORCH_CLASS does not match 'pala' prefix; torch_class is None",
    },
    {
        "excerpt": "anni 15/15/8",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "anni",
            "anni_attrs": 15,
            "anni_res": 15,
            "anni_xp": 8,
            "anni_tier": "average",
        },
        # This works on current parser
        "expected_signature": "anni + 15anni_attr + 15anni_res + 8xp",
        "xfail": False,
        "xfail_reason": None,
    },

    # OCR-corrupted torch/anni excerpts (Task 9.4 regression entries)
    {
        "excerpt": "torch sorc 2O/2O",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "torch",
            "torch_class": "sorceress",
            "torch_attrs": 20,
            "torch_res": 20,
            "torch_tier": "perfect",
        },
        # OCR-fold converts '2O' → '20' before RE_TORCH_ROLL matching
        "expected_signature": "torch + sorceress_torch + sorceress_skills + 20attr + 20res",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "anni 1O/1O/5",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "anni",
            "anni_attrs": 10,
            "anni_res": 10,
            "anni_xp": 5,
            "anni_tier": "low",
        },
        # OCR-fold converts '1O' → '10' before RE_ANNI_TRIPLE matching
        "expected_signature": "anni + 10anni_attr + 10anni_res + 5xp",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "barb torch l5/l8",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "torch",
            "torch_class": "barbarian",
            "torch_attrs": 15,
            "torch_res": 18,
            "torch_tier": "average",
        },
        # OCR-fold converts 'l5' → '15' and 'l8' → '18' (lowercase L → 1)
        "expected_signature": "torch + barbarian_torch + barbarian_skills + 15attr + 18res",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "anni I8/I9/IO",
        "category": "torch_anni_misclass",
        "expected_fields": {
            "item_form": "anni",
            "anni_attrs": 18,
            "anni_res": 19,
            "anni_xp": 10,
            "anni_tier": "good",
        },
        # OCR-fold converts 'I8' → '18', 'I9' → '19', 'IO' → '10' (capital I → 1, O → 0)
        "expected_signature": "anni + 18anni_attr + 19anni_res + 10xp",
        "xfail": False,
        "xfail_reason": None,
    },

    # ──────────────────────────────────────────────────────────────
    # Category 4: Base item misparsing  (≥5)
    # ──────────────────────────────────────────────────────────────
    {
        "excerpt": "eth 4 os GT",
        "category": "base_item_misparsing",
        "expected_fields": {
            "base": "giant_thresher",
            "eth": True,
            "os": 4,
        },
        # Parser extracts fields correctly but signature is None —
        # _ocr_low_quality_signature rejects because 'colossus_voulge' not in informative_prefixes
        # Wait — GT maps to giant_thresher which IS in informative_prefixes.
        # Actually the issue is the has_context check: giant_thresher IS in informative_prefixes
        # but the check looks for exact match in parts. Let me re-check...
        # The probe showed sig='giant_thresher + eth + 4os' — this PASSES.
        "expected_signature": "giant_thresher + eth + 4os",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "sup mp 15ed",
        "category": "base_item_misparsing",
        "expected_fields": {
            "base": "mage_plate",
            "ed": 15,
            "superior": True,
        },
        # Works — mage_plate is in informative_prefixes
        "expected_signature": "mage_plate + sup + 15%ED",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "eth ca 4os",
        "category": "base_item_misparsing",
        "expected_fields": {
            "base": "cryptic_axe",
            "eth": True,
            "os": 4,
        },
        # Works — cryptic_axe is in informative_prefixes
        "expected_signature": "cryptic_axe + eth + 4os",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "sup monarch 15ed 148def",
        "category": "base_item_misparsing",
        "expected_fields": {
            "base": "monarch",
            "ed": 15,
            "defense": 148,
            "superior": True,
        },
        # Works — monarch is in informative_prefixes
        "expected_signature": "monarch + sup + 15%ED + 148def",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "eth cv 4 os",
        "category": "base_item_misparsing",
        "expected_fields": {
            "base": "colossus_voulge",
            "eth": True,
            "os": 4,
        },
        "expected_signature": "colossus_voulge + eth + 4os",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "eth zerker 6os",
        "category": "base_item_misparsing",
        "expected_fields": {
            "base": "berserker_axe",
            "eth": True,
            "os": 6,
        },
        "expected_signature": "berserker_axe + eth + 6os",
        "xfail": False,
        "xfail_reason": None,
    },

    # ──────────────────────────────────────────────────────────────
    # Category 5: LLD charm/jewel shorthand failures  (≥5)
    # ──────────────────────────────────────────────────────────────
    {
        "excerpt": "15ias/40ed jewel req 18",
        "category": "lld_charm_jewel_shorthand",
        "expected_fields": {
            "jewel": True,
            "ias": 15,
            "ed": 40,
            "req_lvl": 18,
            "lld": True,
        },
        # Works on current parser
        "expected_signature": "jewel + 40%ED + 15IAS + req18 + LLD",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "3/20/20 sc lld",
        "category": "lld_charm_jewel_shorthand",
        "expected_fields": {
            "charm_size": "sc",
            "max_dmg": 3,
            "ar": 20,
            "life": 20,
            "lld": True,
        },
        # Works on current parser
        "expected_signature": "SC + 20AR + 3max + 20life + LLD",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "5fhr/11lr sc",
        "category": "lld_charm_jewel_shorthand",
        "expected_fields": {
            "charm_size": "sc",
            "fhr": 5,
            "light_res": 11,
            "lld": True,
        },
        # Works on current parser
        "expected_signature": "SC + 5FHR + 11LR + LLD",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "2/20 circlet 2os frw",
        "category": "lld_charm_jewel_shorthand",
        "expected_fields": {
            "item_form": "circlet",
            "skills": 2,
            "fcr": 20,
            "os": 2,
        },
        # circlet now in informative_prefixes — signature no longer rejected.
        "expected_signature": "circlet + 2os + 20FCR + +2skills",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "gc 12fhr max/ar/life",
        "category": "lld_charm_jewel_shorthand",
        "expected_fields": {
            "charm_size": "gc",
            "grand_charm": True,
            "fhr": 12,
        },
        # Duplicate GC fixed — charm_size=gc and grand_charm=True no longer both emit GC.
        "expected_signature": "GC + 12FHR",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "jewel 9max 76ar 30life req 9",
        "category": "lld_charm_jewel_shorthand",
        "expected_fields": {
            "jewel": True,
            "max_dmg": 9,
            "ar": 76,
            "life": 30,
            "req_lvl": 9,
            "lld": True,
        },
        # Works on current parser
        "expected_signature": "jewel + 76AR + 9max + 30life + req9 + LLD",
        "xfail": False,
        "xfail_reason": None,
    },

    # ──────────────────────────────────────────────────────────────
    # Category 6: Mixed / edge cases  (≥5)
    # ──────────────────────────────────────────────────────────────
    {
        "excerpt": "CTA +6 BO / +1 BC",
        "category": "mixed_edge_cases",
        "expected_fields": {
            "rw_name": "cta",
            "rw_bo_lvl": 6,
        },
        # Parser now extracts runeword name and BO level
        "expected_signature": "runeword:cta + +6BO",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "HOTO 40@",
        "category": "mixed_edge_cases",
        "expected_fields": {
            "all_res": 40,
            "rw_name": "hoto",
        },
        # Parser now extracts runeword name; _ocr_low_quality_signature accepts runeword: prefix
        "expected_signature": "runeword:hoto + @40",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "grief pb 40ias 400dmg",
        "category": "mixed_edge_cases",
        "expected_fields": {
            "base": "phase_blade",
            "ias": 40,
            "rw_name": "grief",
        },
        # Parser gets base + ias + runeword name
        "expected_signature": "runeword:grief + phase_blade + 40IAS",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "spirit monarch 35fcr",
        "category": "mixed_edge_cases",
        "expected_fields": {
            "base": "monarch",
            "fcr": 35,
            "rw_name": "spirit",
        },
        # Works — monarch + fcr + runeword name extracted
        "expected_signature": "runeword:spirit + monarch + 35FCR",
        "xfail": False,
        "xfail_reason": None,
    },
    {
        "excerpt": "5/5 cold facet",
        "category": "mixed_edge_cases",
        "expected_fields": {
            "item_form": "facet",
            "facet_element": "cold",
            "facet_dmg": 5,
            "facet_enemy_res": 5,
        },
        # Works perfectly on current parser
        "expected_signature": "facet + cold_facet + +5facet_dmg + -5facet_res",
        "xfail": False,
        "xfail_reason": None,
    },
]
