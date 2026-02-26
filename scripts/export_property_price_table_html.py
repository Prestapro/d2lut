#!/usr/bin/env python3
"""Export a searchable HTML table of expensive property combinations from observed listings.

v1 focuses on robust textual extraction from d2jsp excerpts:
- ED (% enhanced damage)
- all res / @res
- sockets (os)
- eth
- defense
- ias / fcr
- life / mf (simple)

This is intentionally heuristic and source-agnostic. Today it will mostly use d2jsp
(`observed_prices.raw_excerpt`), but the output includes source fields for future expansion.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import median

from d2lut.normalize.modifier_lexicon import (
    infer_item_category_from_variant,
    property_allowed_by_category_constraints,
)

logger = logging.getLogger(__name__)


RE_ED = [
    re.compile(r"\b(\d{2,3})\s*%\s*ed\b", re.I),
    re.compile(r"\b(\d{2,3})\s*ed\b", re.I),
]
RE_ALL_RES_EXPLICIT = [
    re.compile(r"\b(\d{1,3})\s*(?:all\s*res(?:ist(?:ance)?)?)\b", re.I),
    re.compile(r"\b(?:all\s*res(?:ist(?:ance)?)?)\s*(\d{1,3})\b", re.I),
]
RE_ALL_RES_SHORTHAND = [
    re.compile(r"\b@\s*(\d{1,3})\b", re.I),
    re.compile(r"\b(\d{1,3})\s*@(?=\s|$)", re.I),
]
RE_SOCKETS = [
    re.compile(r"\b([1-6])\s*os\b", re.I),
    re.compile(r"\b([1-6])\s*soc(?:ket)?s?\b", re.I),
    re.compile(r"\bsocketed\s*\(?([1-6])\)?", re.I),
]
RE_DEF = [
    re.compile(r"\b(\d{2,4})\s*def\b", re.I),
    re.compile(r"\bdef(?:ense)?\s*:\s*(\d{2,4})\b", re.I),
    re.compile(r"\bdef(?:ense)?\s+(\d{2,4})\b", re.I),
]
RE_IAS = [re.compile(r"\b(\d{1,2})\s*ias\b", re.I)]
RE_FCR = [re.compile(r"\b(\d{1,2})\s*fcr\b", re.I)]
RE_FRW = [re.compile(r"\b(\d{1,2})\s*frw\b", re.I)]
RE_FHR = [re.compile(r"\b(\d{1,2})\s*fhr\b", re.I)]
RE_STR = [re.compile(r"\b(\d{1,3})\s*str\b", re.I), re.compile(r"\bstr(?:ength)?\s*(\d{1,3})\b", re.I)]
RE_DEX = [re.compile(r"\b(\d{1,3})\s*dex\b", re.I), re.compile(r"\bdex(?:terity)?\s*(\d{1,3})\b", re.I)]
RE_AR = [re.compile(r"\b(\d{1,4})\s*ar\b", re.I), re.compile(r"\battack rating\s*(\d{1,4})\b", re.I)]
RE_MAXDMG = [
    re.compile(r"\b(\d{1,2})\s*max(?:\s*dmg)?\b", re.I),
    re.compile(r"\bmax\s*dmg\s*(\d{1,2})\b", re.I),
]
RE_MINDMG = [
    re.compile(r"\b(\d{1,2})\s*min\s*dmg\b", re.I),
    re.compile(r"\bmin\s*dmg\s*(\d{1,2})\b", re.I),
]
RE_LIFE = [
    re.compile(r"\b(\d{1,3})\s*life\b", re.I),
    re.compile(r"\blife\s*(\d{1,3})\b", re.I),
]
RE_MF = [re.compile(r"\b(\d{1,3})\s*mf\b", re.I)]
RE_SKILLS = [
    re.compile(r"\+?(\d)\s+all skills\b", re.I),
    re.compile(r"\+?(\d)\s+to [a-z][a-z '\-]+ skills\b", re.I),
]
RE_ENEMY_RES = [
    re.compile(r"-\s*(\d{1,2})\s*(?:enemy )?(?:[a-z]+\s+)?res", re.I),
]
RE_REQ_LVL = [
    # Existing: req N, req lvl N, req level N, required lvl N, req:N (colon variant)
    re.compile(r"\breq(?:uired)?\s*(?:lvl|level)?\s*[:=]?\s*(\d{1,2})\b", re.I),
    # Existing: lvl req N, lvl req:N
    re.compile(r"\blvl\s*req\s*[:=]?\s*(\d{1,2})\b", re.I),
    # rlvl N, rlvl:N, rlvl=N
    re.compile(r"\brlvl\s*[:=]?\s*(\d{1,2})\b", re.I),
    # lv N, lvN (e.g. lv9, lv 30)
    re.compile(r"\blv\s*(\d{1,2})\b", re.I),
    # OCR-noise: 'lvl' misread as '1v1' or 'Iv1' → req 1v1 N
    re.compile(r"\breq\s*[1Il]v[1Il]\s*(\d{1,2})\b", re.I),
    # OCR-noise: 'rvl'/'lvl' misread as 'rv1' → rv1 N
    re.compile(r"\brv[1Il]\s*(\d{1,2})\b", re.I),
]
RE_SINGLE_RES = [
    ("fr", re.compile(r"\b(\d{1,2})\s*(?:fire\s*res(?:ist)?|fr)\b", re.I)),
    ("lr", re.compile(r"\b(\d{1,2})\s*(?:light(?:ning)?\s*res(?:ist)?|lr)\b", re.I)),
    ("cr", re.compile(r"\b(\d{1,2})\s*(?:cold\s*res(?:ist)?|cr)\b", re.I)),
    ("pr", re.compile(r"\b(\d{1,2})\s*(?:pois(?:on)?\s*res(?:ist)?|pr)\b", re.I)),
]
RE_TWO_TWENTY = [
    re.compile(r"\b2\s*/\s*20\b"),  # classic shorthand for +2 skills / 20 fcr on amu/circlets
]
RE_CLASS_SKILLS = [
    ("paladin", re.compile(r"\b(?:\+?\s*2\s*)?(?:pal(?:a|adin)?|pally)\b", re.I)),
    ("sorceress", re.compile(r"\b(?:\+?\s*2\s*)?(?:sorc|sorc(?:eress)?)\b", re.I)),
    ("necromancer", re.compile(r"\b(?:\+?\s*2\s*)?(?:nec|necro|necromancer)\b", re.I)),
    ("assassin", re.compile(r"\b(?:\+?\s*2\s*)?(?:sin|assa|assassin)\b", re.I)),
    ("druid", re.compile(r"\b(?:\+?\s*2\s*)?druid\b", re.I)),
    ("amazon", re.compile(r"\b(?:\+?\s*2\s*)?(?:ama|zon|amazon)\b", re.I)),
    ("barbarian", re.compile(r"\b(?:\+?\s*2\s*)?(?:barb|barbarian)\b", re.I)),
]
RE_TORCH_CLASS = [
    ("amazon", re.compile(r"\b(?:ama|amazon|zon)\s+torch\b|\btorch\b.*\b(?:ama|amazon|zon)\b", re.I)),
    ("assassin", re.compile(r"\b(?:sin|assa|assassin)\s+torch\b|\btorch\b.*\b(?:sin|assa|assassin)\b", re.I)),
    ("barbarian", re.compile(r"\b(?:barb|barbarian)\s+torch\b|\btorch\b.*\b(?:barb|barbarian)\b", re.I)),
    ("druid", re.compile(r"\bdruid\s+torch\b|\btorch\b.*\bdruid\b", re.I)),
    ("necromancer", re.compile(r"\b(?:nec|necro|necromancer)\s+torch\b|\btorch\b.*\b(?:nec|necro|necromancer)\b", re.I)),
    ("paladin", re.compile(r"\b(?:pal|pally|paladin)\s+torch\b|\btorch\b.*\b(?:pal|pally|paladin)\b", re.I)),
    ("sorceress", re.compile(r"\b(?:sorc|sorc(?:eress)?)\s+torch\b|\btorch\b.*\b(?:sorc|sorceress)\b", re.I)),
]
RE_TORCH_ROLL = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\b")
RE_ANNI_TRIPLE = re.compile(r"\banni(?:hilus)?\b.*?\b(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})\b|\b(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})\s+anni(?:hilus)?\b", re.I)

# ---------------------------------------------------------------------------
# OCR digit folding — targeted replacement of common OCR digit confusions
# in numeric contexts only (near digits or slash separators).
# Applied to a COPY of text used only for torch/anni regex matching.
# ---------------------------------------------------------------------------
_RE_OCR_DIGIT_FOLD = re.compile(r"(?<=\d)[OoIl](?=\s*/|\s*$|\b)|(?<=[\s/])[OoIl](?=\d)")


def _ocr_fold_digits(text: str) -> str:
    """Replace common OCR digit confusions in numeric contexts.

    O/o → 0, l/I/i → 1.  Only applied within slash-separated numeric
    tokens (e.g. '2O/2O' or 'I8/I9/IO') to avoid corrupting words.
    """
    _FOLD = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "i": "1"})

    def _fold_token(tok: str) -> str:
        """Fold a single token if it looks like an OCR-corrupted number."""
        # A token is foldable if it contains at least one real digit
        # OR consists entirely of OCR-confusable letters (e.g. 'io' → '10').
        if any(c.isdigit() for c in tok) or (tok and all(c in "OoIil" for c in tok)):
            return tok.translate(_FOLD)
        return tok

    # Find slash-separated groups where at least one token has a digit.
    # Pattern: sequences of (alphanum-token / alphanum-token [/ ...])
    def _fold_slash_group(m: re.Match) -> str:
        group = m.group(0)
        tokens = group.split("/")
        # Only fold if at least one token contains a real digit.
        if any(any(c.isdigit() for c in tok.strip()) for tok in tokens):
            return "/".join(_fold_token(tok.strip()) if tok.strip() else tok for tok in tokens)
        return group

    # Match slash-separated groups of short alphanumeric tokens.
    result = re.sub(
        r"[A-Za-z0-9]{1,3}(?:\s*/\s*[A-Za-z0-9]{1,3})+",
        _fold_slash_group,
        text,
    )
    # Also fold isolated digit-adjacent OCR letters not in slash groups
    # (e.g. '2O' standalone, 'l5' standalone).
    prev = result
    for _ in range(2):
        cur = re.sub(r"(\d)[OoIil]", lambda m: m.group(1) + m.group(0)[-1].translate(_FOLD), prev)
        cur = re.sub(r"[OoIil](\d)", lambda m: m.group(0)[0].translate(_FOLD) + m.group(1), cur)
        if cur == prev:
            break
        prev = cur
    return prev


# ---------------------------------------------------------------------------
# Torch / anni tier classification
# ---------------------------------------------------------------------------

def _classify_torch_tier(attrs: int, res: int) -> str:
    """Classify torch roll into a tier based on attrs + res sum (range 20-40)."""
    if attrs == 20 and res == 20:
        return "perfect"
    total = attrs + res
    if total >= 38:
        return "near-perfect"
    if total >= 34:
        return "good"
    if total >= 28:
        return "average"
    return "low"


def _classify_anni_tier(attrs: int, res: int, xp: int) -> str:
    """Classify anni roll into a tier based on attrs + res + xp sum (range 25-50)."""
    if attrs == 20 and res == 20 and xp == 10:
        return "perfect"
    total = attrs + res + xp
    if total >= 48:
        return "near-perfect"
    if total >= 42:
        return "good"
    if total >= 35:
        return "average"
    return "low"
RE_FACET_ELEMENT = [
    ("fire", re.compile(r"\bfire\b.*\bfacet\b|\bfacet\b.*\bfire\b", re.I)),
    ("cold", re.compile(r"\bcold\b.*\bfacet\b|\bfacet\b.*\bcold\b", re.I)),
    ("light", re.compile(r"\b(?:light|lightning)\b.*\bfacet\b|\bfacet\b.*\b(?:light|lightning)\b", re.I)),
    ("poison", re.compile(r"\bpoison\b.*\bfacet\b|\bfacet\b.*\bpoison\b", re.I)),
]
RE_FACET_ROLL = re.compile(r"\b(\d)\s*/\s*(\d)\b")
RE_GHEED_TRIPLE = re.compile(r"\bgheed'?s?\b.*?\b(\d{2,3})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})\b|\b(\d{2,3})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})\b.*\bgheed'?s?\b", re.I)
RE_ITEM_FORMS = [
    ("amulet", re.compile(r"\bamu(?:let)?\b|\bammy\b|\bamy\b", re.I)),
    ("ring", re.compile(r"\bring\b", re.I)),
    ("torch", re.compile(r"\b(?:hellfire\s+)?torch\b", re.I)),
    ("anni", re.compile(r"\banni(?:hilus)?\b", re.I)),
    ("gheed", re.compile(r"\bgheed'?s\b|\bgheeds\b", re.I)),
    ("facet", re.compile(r"\bfacet\b", re.I)),
    ("diadem", re.compile(r"\bdiadem\b", re.I)),
    ("tiara", re.compile(r"\btiara\b", re.I)),
    ("coronet", re.compile(r"\bcoronet\b", re.I)),
    ("circlet", re.compile(r"\bcirc(?:let)?\b", re.I)),
]
RE_CHARM_TRIPLE = [
    # Common SC/LC/GC shorthand like 3/20/20, 20/17 (we only decode 3-part safely)
    re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})\b"),
]

BASE_PATTERNS = [
    (re.compile(r"\bgiant thresher\b|\bgt\b", re.I), "giant_thresher"),
    (re.compile(r"\bthresher\b", re.I), "thresher"),
    (re.compile(r"\bcolossus voulge\b|\bcv\b", re.I), "colossus_voulge"),
    (re.compile(r"\bcryptic axe\b|\bca\b", re.I), "cryptic_axe"),
    (re.compile(r"\bgreat poleaxe\b|\bgpa\b", re.I), "great_poleaxe"),
    (re.compile(r"\barchon plate\b|\bap\b", re.I), "archon_plate"),
    (re.compile(r"\bmage plate\b|\bmp\b", re.I), "mage_plate"),
    (re.compile(r"\bmonarch\b|\bmon\b", re.I), "monarch"),
    (re.compile(r"\bphase blade\b|\bpb\b", re.I), "phase_blade"),
    (re.compile(r"\bberserker axe\b|\bba\b|\bzerker\b", re.I), "berserker_axe"),
    (re.compile(r"\bdusk shroud\b|\bds\b", re.I), "dusk_shroud"),
    (re.compile(r"\bwire fleece\b|\bwf\b", re.I), "wire_fleece"),
    (re.compile(r"\bsacred targe\b|\bst\b", re.I), "sacred_targe"),
    (re.compile(r"\bsacred rondache\b|\bsr\b", re.I), "sacred_rondache"),
]

SKILLER_PATTERNS = [
    # Sorceress
    (re.compile(r"\bcold(?:\s+skills?)?\s+skiller\b|\bcold sk(?:iller)?\b", re.I), "sorc_cold_skiller"),
    (re.compile(r"\blight(?:ning)?(?:\s+skills?)?\s+skiller\b|\blite?\s+sk(?:iller)?\b", re.I), "sorc_lightning_skiller"),
    (re.compile(r"\bfire(?:\s+skills?)?\s+skiller\b|\bfire\s+sk(?:iller)?\b", re.I), "sorc_fire_skiller"),
    # Paladin
    (re.compile(r"\bpcomb\b|\bpal(?:a|adin)?\s+combat(?:\s+skiller)?\b", re.I), "pala_combat_skiller"),
    (re.compile(r"\boff(?:ensive)?\s+auras?(?:\s+skiller)?\b", re.I), "pala_off_aura_skiller"),
    (re.compile(r"\bdef(?:ensive)?\s+auras?(?:\s+skiller)?\b", re.I), "pala_def_aura_skiller"),
    # Amazon
    (re.compile(r"\b(?:java|jav)(?:zon)?(?:\s+skiller)?\b|\bjav(?:elin)?\s*(?:and)?\s*spear(?:\s+skiller)?\b", re.I), "ama_javelin_skiller"),
    (re.compile(r"\bbow(?:a|azon)?(?:\s+skiller)?\b|\bbow\s*and\s*crossbow(?:\s+skiller)?\b", re.I), "ama_bow_skiller"),
    (re.compile(r"\bpassive(?:\s*and)?\s*magic(?:\s+skiller)?\b|\bpnm\b", re.I), "ama_passive_magic_skiller"),
    # Barbarian
    (re.compile(r"\bwc\b|\bwar\s*cr(?:y|ies)(?:\s+skiller)?\b", re.I), "barb_warcries_skiller"),
    (re.compile(r"\bbarb\s*combat(?:\s+skiller)?\b|\bbcomb\b", re.I), "barb_combat_skiller"),
    (re.compile(r"\bmaster(?:y|ies)(?:\s+skiller)?\b", re.I), "barb_masteries_skiller"),
    # Druid
    (re.compile(r"\bele(?:mental)?(?:\s+skiller)?\b", re.I), "druid_elemental_skiller"),
    (re.compile(r"\bshape(?:shifting)?(?:\s+skiller)?\b", re.I), "druid_shapeshift_skiller"),
    (re.compile(r"\bdruid\s*summon(?:ing)?(?:\s+skiller)?\b|\bdsum\b", re.I), "druid_summon_skiller"),
    # Necromancer
    (re.compile(r"\bpnb\b|\bpoison\s*(?:&|and)?\s*bone(?:\s+skiller)?\b", re.I), "necro_pnb_skiller"),
    (re.compile(r"\bnecro\s*summon(?:ing)?(?:\s+skiller)?\b|\bnsum\b", re.I), "necro_summon_skiller"),
    (re.compile(r"\bcurses?(?:\s+skiller)?\b", re.I), "necro_curses_skiller"),
    # Assassin
    (re.compile(r"\btrap(?:s)?(?:\s+skiller)?\b", re.I), "assa_traps_skiller"),
    (re.compile(r"\bshadow(?:\s+disciplines?)?(?:\s+skiller)?\b|\bshadow sk(?:iller)?\b", re.I), "assa_shadow_skiller"),
    (re.compile(r"\bma\b|\bmartial\s*arts?(?:\s+skiller)?\b", re.I), "assa_martial_skiller"),
    # Generic fallback
    (re.compile(r"\bskiller\b", re.I), "skiller"),
]

# Maxroll valuable magic-items page (seed knowledge) encoded as heuristic keyword groups.
# These are not prices; they are "do not ignore" hints for potential-high-value detection.
MAXROLL_MAGIC_SEED_PATTERNS = [
    # Skill GC named prefixes (examples from Maxroll list)
    ("maxroll_skill_gc_name", re.compile(
        r"\b(lion branded|captain'?s|sparking|chilling|burning|sounding|harpoonist'?s|fletcher'?s|fungal|graverobber'?s|entrapping|shogukusha'?s|mentalist'?s|natural|spiritual|trainer'?s)\b",
        re.I,
    )),
    # Jewel archetypes
    ("maxroll_jewel_fervor", re.compile(r"\bjewel\b.*\bof fervor\b|\bof fervor\b.*\bjewel\b", re.I)),
    ("maxroll_jewel_carnage", re.compile(r"\bjewel\b.*\bof carnage\b|\bof carnage\b.*\bjewel\b", re.I)),
    ("maxroll_jewel_ed_prefix", re.compile(r"\b(ruby|realgar|rusty|vermilion|carbuncle)\s+jewel\b", re.I)),
    # Magic amulets (class skill + notable suffixes)
    ("maxroll_magic_amulet", re.compile(
        r"\b(rose branded|powered|glacial|volcanic|echoing|venomous|golemlord'?s|cunning|kenshi'?s|shadow|gaean|communal|keeper'?s|fortuitous|chromatic)\s+amulet\b",
        re.I,
    )),
    # Circlets / coronets / tiaras / diadems
    ("maxroll_magic_circlet", re.compile(
        r"\b(rose branded|priest'?s|volcanic|glacial|powered|berserker'?s|venomous|golemlord'?s|necromancer'?s|cunning|kenshi'?s|shadow|witch-hunter'?s|gaean|keeper'?s|hierophant'?s)\s+(?:circlet|coronet|tiara|diadem)\b",
        re.I,
    )),
    ("maxroll_of_the_magus", re.compile(r"\bof the magus\b", re.I)),
    # Magic shields / armors / JMoD family
    ("maxroll_jewelers_monarch", re.compile(r"\bjeweler'?s\s+monarch\b", re.I)),
    ("maxroll_jmod", re.compile(r"\bjeweler'?s\s+monarch\s+of\s+deflecting\b|\bjmod\b", re.I)),
    ("maxroll_magic_armor", re.compile(r"\b(jeweler'?s|artisan'?s)\s+(?:archon plate|dusk shroud|wire fleece|wyrmhide|light plate)\b", re.I)),
    # Gloves
    ("maxroll_magic_gloves", re.compile(r"\b(lancer'?s|archer'?s|kenshi'?s)\s+.*gloves\b", re.I)),
    ("maxroll_alacrity", re.compile(r"\bof alacrity\b", re.I)),
]

# ---------------------------------------------------------------------------
# Runeword kit detection — base + rune recipe sequence (not a finished rw)
# Mirrors logic from d2jsp_market._infer_runeword_kit_variant().
# ---------------------------------------------------------------------------
_KIT_BASE_RE = re.compile(
    r"(?i)\b(archon plate|mage plate|dusk shroud|wire fleece|monarch|sacred targe|sacred rondache"
    r"|phase blade|berserker axe|colossus voulge|thresher|giant thresher|cryptic axe|great poleaxe"
    r"|flail|crystal sword|broad sword)\b"
)
_KIT_BASE_SHORTHAND_RE = re.compile(
    r"(?i)\b(ap|mp|mon|pb|ba|cv|gt|gpa|ca)\b"
)
_KIT_BASE_SHORTHAND_MAP = {
    "ap": "archon plate", "mp": "mage plate", "mon": "monarch",
    "pb": "phase blade", "ba": "berserker axe", "cv": "colossus voulge",
    "gt": "giant thresher", "gpa": "great poleaxe", "ca": "cryptic axe",
}

_KIT_RECIPES: list[tuple[str, list[str]]] = [
    ("enigma", ["jah", "ith", "ber"]),
    ("heart_of_the_oak", ["ko", "vex", "pul", "thul"]),
    ("call_to_arms", ["amn", "ral", "mal", "ist", "ohm"]),
    ("infinity", ["ber", "mal", "ber", "ist"]),
    ("grief", ["eth", "tir", "lo", "mal", "ral"]),
    ("insight", ["ral", "tir", "tal", "sol"]),
    ("spirit", ["tal", "thul", "ort", "amn"]),
    ("breath_of_the_dying", ["vex", "hel", "el", "eld", "zod", "eth"]),
    ("fortitude", ["el", "sol", "dol", "lo"]),
]

def _kit_recipe_re(runes: list[str]) -> re.Pattern[str]:
    sep = r"(?:\s*[+/,&\n]?\s*)"
    pat = r"(?i)\b" + sep.join(re.escape(r) for r in runes) + r"\b"
    return re.compile(pat)

_KIT_RECIPE_RES: list[tuple[str, re.Pattern[str]]] = [
    (rw, _kit_recipe_re(recipe)) for rw, recipe in _KIT_RECIPES
]

_KIT_UNMADE_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+eni(?:gma)?\b|\beni(?:gma)?\s+kit\b"), "enigma"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+hoto\b|\bhoto\s+kit\b"), "heart_of_the_oak"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+(?:cta|call to arms)\b|\bcta\s+kit\b"), "call_to_arms"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+(?:infinity|infi)\b|\binfi(?:nity)?\s+kit\b"), "infinity"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+grief\b|\bgrief\s+kit\b"), "grief"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+insight\b|\binsight\s+kit\b"), "insight"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+spirit\b|\bspirit\s+kit\b"), "spirit"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+(?:botd|breath of the dying)\b|\bbotd\s+kit\b"), "breath_of_the_dying"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+fort(?:itude)?\b|\bfort(?:itude)?\s+kit\b"), "fortitude"),
]


def _detect_kit(text_lower: str) -> bool:
    """Return True if the excerpt looks like a runeword kit (base + runes), not finished."""
    # Must have a base item present.
    has_base = bool(_KIT_BASE_RE.search(text_lower) or _KIT_BASE_SHORTHAND_RE.search(text_lower))
    if not has_base:
        return False
    # Explicit "unmade <rw>" or "<rw> kit" shorthand.
    for rx, _rw in _KIT_UNMADE_HINTS:
        if rx.search(text_lower):
            return True
    # Implicit: base + rune recipe sequence.
    for _rw, rx in _KIT_RECIPE_RES:
        if rx.search(text_lower):
            return True
    return False


# ---------------------------------------------------------------------------
# Runeword name detection — map excerpt text to canonical runeword name.
# Used for roll-aware property extraction (Task 8).
# ---------------------------------------------------------------------------
_RW_NAME_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cta", re.compile(r"\b(?:cta|call to arms)\b", re.I)),
    ("hoto", re.compile(r"\b(?:hoto|heart of the oak)\b", re.I)),
    ("grief", re.compile(r"\bgrief\b", re.I)),
    ("infinity", re.compile(r"\b(?:infinity|infi)\b", re.I)),
    ("insight", re.compile(r"\binsight\b", re.I)),
    ("spirit", re.compile(r"\bspirit\b", re.I)),
    ("fortitude", re.compile(r"\b(?:fortitude|fort)\b", re.I)),
    ("botd", re.compile(r"\b(?:botd|breath of the dying)\b", re.I)),
]

# CTA-specific: Battle Orders level
RE_BO_LVL = [
    re.compile(r"\+?\s*(\d{1,2})\s*(?:bo|battle orders)\b", re.I),
]
# Insight-specific: Meditation level
RE_MED_LVL = [
    re.compile(r"\+?\s*(\d{1,2})\s*(?:med(?:itation)?)\b", re.I),
    re.compile(r"\bmed(?:itation)?\s*(\d{1,2})\b", re.I),
]


def _detect_rw_name(text_lower: str) -> str | None:
    """Detect a runeword name from excerpt text. Returns canonical name or None."""
    for name, rx in _RW_NAME_PATTERNS:
        if rx.search(text_lower):
            return name
    return None


@dataclass
class ExtractedProps:
    base: str | None = None
    eth: bool = False
    os: int | None = None
    ed: int | None = None
    all_res: int | None = None
    defense: int | None = None
    ias: int | None = None
    fcr: int | None = None
    frw: int | None = None
    fhr: int | None = None
    strength: int | None = None
    dexterity: int | None = None
    ar: int | None = None
    max_dmg: int | None = None
    min_dmg: int | None = None
    life: int | None = None
    mf: int | None = None
    skills: int | None = None
    enemy_res: int | None = None
    skiller: str | None = None
    item_form: str | None = None
    class_skills: str | None = None
    all_skills: int | None = None
    charm_size: str | None = None  # sc|lc|gc
    jewel: bool = False
    req_lvl: int | None = None
    fire_res: int | None = None
    light_res: int | None = None
    cold_res: int | None = None
    poison_res: int | None = None
    grand_charm: bool = False
    plain: bool = False
    superior: bool = False
    lld: bool = False
    kit: bool = False
    torch_class: str | None = None
    torch_attrs: int | None = None
    torch_res: int | None = None
    anni_attrs: int | None = None
    anni_res: int | None = None
    anni_xp: int | None = None
    torch_tier: str | None = None
    anni_tier: str | None = None
    gheed_mf: int | None = None
    gheed_vendor: int | None = None
    gheed_gold: int | None = None
    facet_element: str | None = None
    facet_dmg: int | None = None
    facet_enemy_res: int | None = None
    lld_bucket: str | None = None
    rw_name: str | None = None       # detected runeword name (cta, hoto, grief, etc.)
    rw_bo_lvl: int | None = None     # CTA Battle Orders level
    rw_med_lvl: int | None = None    # Insight Meditation level

    def non_empty_items(self) -> list[tuple[str, object]]:
        out: list[tuple[str, object]] = []
        for k, v in asdict(self).items():
            if isinstance(v, bool):
                if v:
                    out.append((k, v))
            elif v is not None:
                out.append((k, v))
        return out


def _first_int(regexes: list[re.Pattern[str]], text: str) -> int | None:
    for rx in regexes:
        m = rx.search(text)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                continue
    return None


def _ocr_low_quality_signature(parts: list[str]) -> bool:
    """Detect noisy OCR-only signatures like '@499' or 'eth + @3 + req55'."""
    if not parts:
        return True
    informative_prefixes = (
        "torch", "anni", "gheed", "facet", "GC", "SC", "LC",
        "jewel", "monarch", "archon_plate", "mage_plate", "thresher",
        "giant_thresher", "cryptic_axe", "phase_blade", "berserker_axe",
        "colossus_voulge", "great_poleaxe", "dusk_shroud", "wire_fleece",
        "sacred_targe", "sacred_rondache",
        "circlet", "coronet", "tiara", "diadem", "amulet", "ring",
    )
    if any(
        p in {"eth", "LLD"} or p.startswith(("+", "@", "req")) or p.endswith(("def", "IAS", "FCR", "FRW", "FHR", "MF", "life", "AR", "max", "min", "skills"))
        for p in parts
    ):
        # If all parts are generic numeric/noisy fragments and no item/base/form context exists, drop it.
        has_context = any(
            (p in {"jewel", "plain", "kit"} or p.startswith("runeword:") or p.endswith("_torch") or p.endswith("_facet") or p.endswith("_skills")
             or p in {"torch", "anni", "gheed", "facet"} or p in informative_prefixes)
            for p in parts
        )
        if not has_context:
            return True
    # Single-token pure shorthand @N or reqN is almost always OCR noise.
    if len(parts) <= 2 and all(p == "eth" or p.startswith("@") or p.startswith("req") for p in parts):
        return True
    return False


def _extract_base_from_variant(variant_key: str | None) -> str | None:
    v = (variant_key or "").lower()
    if v.startswith("base:"):
        parts = v.split(":")
        if len(parts) >= 2:
            return parts[1]
    return None


def _assign_lld_bucket(req_lvl: int | None, lld: bool) -> str:
    """Map req_lvl to an LLD bracket label."""
    if req_lvl is not None:
        if req_lvl <= 9:
            return "LLD9"
        if req_lvl <= 18:
            return "LLD18"
        if req_lvl <= 30:
            return "LLD30"
        if req_lvl <= 49:
            return "MLD"
        return "HLD"
    # No parsed req_lvl — fall back to LLD30 when heuristic flag is set.
    if lld:
        return "LLD30"
    return "unknown"


# ---------------------------------------------------------------------------
# Modifier lexicon integration — post-extraction validation
# ---------------------------------------------------------------------------

# Maps ExtractedProps field names → modifier lexicon property names used by
# property_allowed_by_category_constraints().
_FIELD_TO_LEXICON_PROP: dict[str, str] = {
    "os": "sockets",
    "ed": "enhanced_damage",
    "defense": "defense",
    "ias": "ias",
    "fcr": "fcr",
    "frw": "frw",
    "fhr": "fhr",
    "life": "life",
    "mf": "magic_find",
    "all_res": "all_resistances",
    "all_skills": "all_skills",
    "max_dmg": "max_damage",
    "min_dmg": "min_damage",
    "ar": "attack_rating",
    "eth": "ethereal",
    "charm_size": "charm_size",
    "fire_res": "fire_resistance",
    "light_res": "lightning_resistance",
    "cold_res": "cold_resistance",
    "poison_res": "poison_resistance",
    "strength": "strength",
    "dexterity": "dexterity",
}

# Fields that are nullable ints — cleared by setting to None.
_NULLABLE_INT_FIELDS = frozenset({
    "os", "ed", "defense", "ias", "fcr", "frw", "fhr", "life", "mf",
    "all_res", "all_skills", "max_dmg", "min_dmg", "ar",
    "fire_res", "light_res", "cold_res", "poison_res",
    "strength", "dexterity",
})

# Fields that are booleans — cleared by setting to False.
_BOOL_FIELDS = frozenset({"eth"})

# Fields that are nullable strings — cleared by setting to None.
_STR_FIELDS = frozenset({"charm_size"})


def _validate_props_against_lexicon(
    props: "ExtractedProps",
    variant_key: str | None,
) -> list[tuple[str, str, str]]:
    """Validate extracted properties against modifier lexicon category constraints.

    Returns a list of (field_name, lexicon_prop, reason) tuples for rejected properties.
    Mutates *props* in-place by clearing disallowed fields.
    """
    # When a runeword name is detected in the excerpt, the effective category
    # is "runeword_item" regardless of the variant_key (which may be a base).
    if props.rw_name:
        category = "runeword_item"
    else:
        category = infer_item_category_from_variant(variant_key)
    if not category or category == "generic":
        return []

    rejected: list[tuple[str, str, str]] = []
    for field_name, lexicon_prop in _FIELD_TO_LEXICON_PROP.items():
        # Check if the field has a value worth validating.
        val = getattr(props, field_name, None)
        if val is None or val is False:
            continue

        if not property_allowed_by_category_constraints(category, lexicon_prop):
            reason = f"category={category} denies {lexicon_prop}"
            rejected.append((field_name, lexicon_prop, reason))
            # Clear the disallowed field.
            if field_name in _NULLABLE_INT_FIELDS:
                setattr(props, field_name, None)
            elif field_name in _BOOL_FIELDS:
                setattr(props, field_name, False)
            elif field_name in _STR_FIELDS:
                setattr(props, field_name, None)

    return rejected


def extract_props(text: str, variant_key: str | None = None) -> ExtractedProps:
    t = (text or "").lower()
    is_image_ocr = "[image-ocr]" in t
    p = ExtractedProps()
    p.base = _extract_base_from_variant(variant_key)
    if not p.base:
        for rx, base_name in BASE_PATTERNS:
            if rx.search(t):
                p.base = base_name
                break
    p.eth = bool(re.search(r"\beth(?:ereal)?\b", t))
    p.superior = bool(re.search(r"\bsup(?:erior)?\b", t))
    for form, rx in RE_ITEM_FORMS:
        if rx.search(t):
            p.item_form = form
            break
    if p.item_form == "torch":
        for cls, rx in RE_TORCH_CLASS:
            if rx.search(t):
                p.torch_class = cls
                break
        # OCR-fold a copy of the text for digit matching only.
        t_folded = _ocr_fold_digits(t)
        m = RE_TORCH_ROLL.search(t_folded)
        if m:
            a, r = int(m.group(1)), int(m.group(2))
            # Torch attrs/res valid game range: 10-20
            if 10 <= a <= 20 and 10 <= r <= 20:
                p.torch_attrs = a
                p.torch_res = r
                p.torch_tier = _classify_torch_tier(a, r)
    if p.item_form == "anni":
        # OCR-fold a copy of the text for digit matching only.
        t_folded = _ocr_fold_digits(t)
        m = RE_ANNI_TRIPLE.search(t_folded)
        if m:
            vals = [g for g in m.groups() if g is not None]
            if len(vals) == 3:
                a, r, xp = (int(v) for v in vals)
                # Anni valid game ranges: attrs 10-20, res 10-20, xp 5-10
                if 10 <= a <= 20 and 10 <= r <= 20 and 5 <= xp <= 10:
                    p.anni_attrs = a
                    p.anni_res = r
                    p.anni_xp = xp
                    p.anni_tier = _classify_anni_tier(a, r, xp)
    if p.item_form == "gheed":
        m = RE_GHEED_TRIPLE.search(t)
        if m:
            vals = [g for g in m.groups() if g is not None]
            if len(vals) == 3:
                mf, vendor, gold = (int(v) for v in vals)
                # Typical Gheed ranges are broad; keep only plausible order.
                if 20 <= mf <= 160 and 5 <= vendor <= 15 and 20 <= gold <= 200:
                    p.gheed_mf = mf
                    p.gheed_vendor = vendor
                    p.gheed_gold = gold
    if p.item_form == "facet":
        for elem, rx in RE_FACET_ELEMENT:
            if rx.search(t):
                p.facet_element = elem
                break
        m = RE_FACET_ROLL.search(t)
        if m:
            dmg, eres = int(m.group(1)), int(m.group(2))
            if 3 <= dmg <= 5 and 3 <= eres <= 5:
                p.facet_dmg = dmg
                p.facet_enemy_res = eres
    p.os = _first_int(RE_SOCKETS, t)
    p.ed = _first_int(RE_ED, t)
    p.all_res = _first_int(RE_ALL_RES_EXPLICIT, t)
    if p.all_res is None and not is_image_ocr:
        p.all_res = _first_int(RE_ALL_RES_SHORTHAND, t)
    if p.all_res is not None and not (3 <= p.all_res <= 200):
        p.all_res = None
    p.defense = _first_int(RE_DEF, t)
    p.ias = _first_int(RE_IAS, t)
    p.fcr = _first_int(RE_FCR, t)
    p.frw = _first_int(RE_FRW, t)
    p.fhr = _first_int(RE_FHR, t)
    p.strength = _first_int(RE_STR, t)
    p.dexterity = _first_int(RE_DEX, t)
    p.ar = _first_int(RE_AR, t)
    p.max_dmg = _first_int(RE_MAXDMG, t)
    p.min_dmg = _first_int(RE_MINDMG, t)
    p.life = _first_int(RE_LIFE, t)
    p.mf = _first_int(RE_MF, t)
    p.skills = _first_int(RE_SKILLS, t)
    p.all_skills = p.skills
    p.enemy_res = _first_int(RE_ENEMY_RES, t)
    p.req_lvl = _first_int(RE_REQ_LVL, t)
    # Range validation: req_lvl must be 1-99 (valid D2R character levels)
    if p.req_lvl is not None and not (1 <= p.req_lvl <= 99):
        p.req_lvl = None
    p.jewel = bool(re.search(r"\bjewel\b", t))
    if re.search(r"\bsmall charm\b|\bsc\b", t):
        p.charm_size = "sc"
    elif re.search(r"\blarge charm\b|\blc\b", t):
        p.charm_size = "lc"
    elif re.search(r"\bgrand charm\b|\bgc\b", t):
        p.charm_size = "gc"
    for key, rx in RE_SINGLE_RES:
        m = rx.search(t)
        if not m:
            continue
        val = int(m.group(1))
        if key == "fr":
            p.fire_res = val
        elif key == "lr":
            p.light_res = val
        elif key == "cr":
            p.cold_res = val
        elif key == "pr":
            p.poison_res = val
    # Common LLD charm/jewel shorthand combo 3/20/20 => max/ar/life
    # Only apply when charm/jewel context is present to avoid corrupting unrelated slash values.
    if (p.charm_size or p.jewel) and p.max_dmg is None and p.ar is None and p.life is None:
        for rx in RE_CHARM_TRIPLE:
            m = rx.search(t)
            if not m:
                continue
            a, b, c = (int(m.group(i)) for i in (1, 2, 3))
            # Conservative mapping for typical pvp charm shorthand.
            if a <= 10 and b >= 10 and c >= 10:
                p.max_dmg = a
                p.ar = b
                p.life = c
                break
    # Jewel ias/ed shorthand: bare "N/N" where jewel context is present.
    # e.g. "15/40 jewel" → ias=15, ed=40.  Only when ias and ed are not already set.
    if p.jewel and p.ias is None and p.ed is None:
        m = re.search(r"\b(\d{1,2})\s*/\s*(\d{1,3})\b", t)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            # Typical ias/ed jewel: ias 15-40, ed 15-40 (or ed/max combos).
            if 15 <= a <= 40 and 15 <= b <= 40:
                p.ias = a
                p.ed = b
    p.grand_charm = bool(re.search(r"\bgrand charm\b|\bgc\b", t))
    p.plain = bool(re.search(r"\bplain\b", t))
    p.lld = bool(re.search(r"\blld\b", t))
    for cls, rx in RE_CLASS_SKILLS:
        if rx.search(t):
            p.class_skills = cls
            break
    # Parse classic 2/20 shorthand on amulets/circlets/circlet-family items.
    if p.item_form in {"amulet", "circlet", "coronet", "tiara", "diadem"}:
        if p.fcr is None and any(rx.search(t) for rx in RE_TWO_TWENTY):
            p.fcr = 20
            if p.skills is None:
                p.skills = 2
                p.all_skills = 2
        # Circlet-family 3/20/20 shorthand: skills/fcr/other (e.g. frw or str).
        # Only when skills and fcr are not already set from 2/20 above.
        if p.skills is None and p.fcr is None:
            for rx in RE_CHARM_TRIPLE:
                m = rx.search(t)
                if m:
                    a, b, c = (int(m.group(i)) for i in (1, 2, 3))
                    # Typical circlet: +2-3 skills / 20 fcr / 20 frw|str|etc.
                    if 2 <= a <= 3 and 10 <= b <= 30 and 10 <= c <= 30:
                        p.skills = a
                        p.all_skills = a
                        p.fcr = b
                        # Third value is ambiguous (frw, str, etc.) — store as frw
                        # if not already set, since frw is the most common third stat.
                        if p.frw is None:
                            p.frw = c
                    break
        # Handle verbose "2 nec 20 fcr ..." or "2sorc", "2pal" style
        # if generic skills parser didn't catch it.
        if p.skills is None and p.class_skills and re.search(r"\b2\s*(?:pal|sorc|nec|necro|sin|assa|druid|ama|zon|barb)\b", t):
            p.skills = 2
            p.all_skills = 2
        if p.skills is None and p.class_skills and re.search(r"\b2\b", t):
            p.skills = 2
            p.all_skills = 2
    for rx, sk in SKILLER_PATTERNS:
        if rx.search(t):
            p.skiller = sk
            break
    # Promote generic skiller language into grand charm context when implied.
    if p.skiller and not p.grand_charm and re.search(r"\bskiller\b", t):
        p.grand_charm = True
    if p.charm_size == "gc":
        p.grand_charm = True
    # Infer LLD when low req or common sc/jewel pvp shorthand
    if p.req_lvl is not None and p.req_lvl <= 30:
        p.lld = True
    if p.charm_size == "sc" and any(v is not None for v in (p.max_dmg, p.ar, p.life, p.fhr, p.all_res, p.fire_res, p.light_res, p.cold_res, p.poison_res)):
        p.lld = p.lld or True
    # Kit detection: base + rune recipe = kit listing (not a finished runeword).
    p.kit = _detect_kit(t)
    # Runeword name detection — only when NOT a kit listing.
    if not p.kit:
        rw = _detect_rw_name(t)
        if rw:
            p.rw_name = rw
            # Extract runeword-specific roll values.
            if rw == "cta":
                p.rw_bo_lvl = _first_int(RE_BO_LVL, t)
            elif rw == "insight":
                p.rw_med_lvl = _first_int(RE_MED_LVL, t)
            # Other runewords reuse existing fields (ed, all_res, ias, fcr, enemy_res).
    # Assign LLD bucket based on req_lvl ranges (must come after req_lvl and lld are set).
    p.lld_bucket = _assign_lld_bucket(p.req_lvl, p.lld)

    # --- Modifier lexicon validation (post-extraction filter) ---
    # Discard properties that are impossible for the detected item category.
    rejected = _validate_props_against_lexicon(p, variant_key)
    for field_name, lexicon_prop, reason in rejected:
        logger.debug("lexicon_reject: field=%s prop=%s reason=%s excerpt=%.80s",
                      field_name, lexicon_prop, reason, text)

    return p


def props_signature(props: ExtractedProps) -> str | None:
    parts: list[str] = []
    # Runeword prefix comes first when detected.
    if props.rw_name:
        parts.append(f"runeword:{props.rw_name}")
    if props.kit:
        parts.append("kit")
    if props.skiller:
        parts.append(props.skiller)
    if props.item_form:
        parts.append(props.item_form)
    if props.torch_class:
        parts.append(f"{props.torch_class}_torch")
    if props.class_skills:
        parts.append(f"{props.class_skills}_skills")
    if props.jewel:
        parts.append("jewel")
    if props.charm_size:
        parts.append(props.charm_size.upper())
    if props.grand_charm and props.charm_size != "gc":
        parts.append("GC")
    if props.plain:
        parts.append("plain")
    if props.base:
        parts.append(props.base)
    if props.superior:
        parts.append("sup")
    if props.eth:
        parts.append("eth")
    if props.os is not None:
        parts.append(f"{props.os}os")
    # Runeword-specific roll fields.
    if props.rw_bo_lvl is not None:
        parts.append(f"+{props.rw_bo_lvl}BO")
    if props.rw_med_lvl is not None:
        parts.append(f"med{props.rw_med_lvl}")
    if props.ed is not None:
        parts.append(f"{props.ed}%ED")
    if props.all_res is not None:
        parts.append(f"@{props.all_res}")
    if props.defense is not None:
        parts.append(f"{props.defense}def")
    if props.ias is not None:
        parts.append(f"{props.ias}IAS")
    if props.fcr is not None:
        parts.append(f"{props.fcr}FCR")
    if props.frw is not None:
        parts.append(f"{props.frw}FRW")
    if props.fhr is not None:
        parts.append(f"{props.fhr}FHR")
    if props.strength is not None:
        parts.append(f"{props.strength}str")
    if props.dexterity is not None:
        parts.append(f"{props.dexterity}dex")
    if props.ar is not None:
        parts.append(f"{props.ar}AR")
    if props.max_dmg is not None:
        parts.append(f"{props.max_dmg}max")
    if props.min_dmg is not None:
        parts.append(f"{props.min_dmg}min")
    if props.life is not None:
        parts.append(f"{props.life}life")
    if props.mf is not None:
        parts.append(f"{props.mf}MF")
    if props.skills is not None:
        parts.append(f"+{props.skills}skills")
    if props.torch_attrs is not None:
        parts.append(f"{props.torch_attrs}attr")
    if props.torch_res is not None:
        parts.append(f"{props.torch_res}res")
    if props.anni_attrs is not None:
        parts.append(f"{props.anni_attrs}anni_attr")
    if props.anni_res is not None:
        parts.append(f"{props.anni_res}anni_res")
    if props.anni_xp is not None:
        parts.append(f"{props.anni_xp}xp")
    if props.gheed_mf is not None:
        parts.append(f"{props.gheed_mf}MF_gheed")
    if props.gheed_vendor is not None:
        parts.append(f"{props.gheed_vendor}vendor")
    if props.gheed_gold is not None:
        parts.append(f"{props.gheed_gold}gold")
    if props.facet_element:
        parts.append(f"{props.facet_element}_facet")
    if props.facet_dmg is not None:
        parts.append(f"+{props.facet_dmg}facet_dmg")
    if props.facet_enemy_res is not None:
        parts.append(f"-{props.facet_enemy_res}facet_res")
    if props.enemy_res is not None:
        parts.append(f"-{props.enemy_res}enemy_res")
    if props.fire_res is not None:
        parts.append(f"{props.fire_res}FR")
    if props.light_res is not None:
        parts.append(f"{props.light_res}LR")
    if props.cold_res is not None:
        parts.append(f"{props.cold_res}CR")
    if props.poison_res is not None:
        parts.append(f"{props.poison_res}PR")
    if props.req_lvl is not None:
        parts.append(f"req{props.req_lvl}")
    if props.lld:
        parts.append("LLD")
    if _ocr_low_quality_signature(parts):
        return None
    return " + ".join(parts) if parts else None


def _build_html(market_key: str, rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>d2lut property price table - {market_key}</title>
  <style>
            :root {{
                --bg: #0a1117;
                --panel: #101922;
                --line: #223041;
                --text: #dce7f4;
                --muted: #92a6be;
                --green: #86efac;
                --yellow: #fde68a;
                --red: #fca5a5;
                --blue: #93c5fd;
            }}

            body {{
                margin: 0;
                padding: 16px;
                background: radial-gradient(circle at 10% -10%, #172230, var(--bg));
                color: var(--text);
                font: 14px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            }}

            .wrap {{
                max-width: none;
                width: 100%;
                margin: 0 auto;
                position: static;
            }}

            .bar {{
                display: grid;
                gap: 8px;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                background: rgba(16,25,34,.9);
                border: 1px solid var(--line);
                border-radius: 12px;
                padding: 10px;
                position: sticky;
                top: 0;
                z-index: 5;
            }}

            input, select {{
                background: #0c141c;
                color: var(--text);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 8px 10px;
            }}

            .meta {{
                color: var(--muted);
                margin: 8px 2px 10px;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 12px;
                position: static;
            }}

            thead th {{
                position: sticky;
                top: 55px;
                background: #586573;
                border-bottom: 1px solid var(--line);
                color: var(--muted);
                text-align: left;
                padding: 10px;
                cursor: pointer;
            }}

            tbody td {{
                padding: 8px 10px;
                border-bottom: 1px solid rgba(34,48,65,.55);
                vertical-align: top;
            }}

            tbody tr:hover {{
                background: rgba(147,197,253,.06);
            }}

            .num {{
                text-align: right;
                white-space: nowrap;
            }}

            .pill {{
                display: inline-block;
                padding: 2px 7px;
                border: 1px solid var(--line);
                border-radius: 999px;
                font-size: 12px;
            }}

            .conf-high {{
                color: var(--green);
            }}

            .conf-medium {{
                color: var(--yellow);
            }}

            .conf-low {{
                color: var(--red);
            }}

            .pill-kit {{
                display: inline-block;
                padding: 2px 7px;
                border: 1px solid #f59e0b;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 700;
                color: #f59e0b;
                background: rgba(245,158,11,.12);
                margin-left: 4px;
            }}

            .pill-bucket {{
                display: inline-block;
                padding: 2px 7px;
                border: 1px solid #8b5cf6;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 700;
                color: #8b5cf6;
                background: rgba(139,92,246,.12);
                margin-left: 4px;
            }}

            .muted {{
                color: var(--muted);
            }}

            .sig {{
                color: var(--blue);
                font-weight: 600;
            }}

            .stale-row td {{
                opacity: 0.5;
            }}

            .stack > div {{
                margin: 0 0 2px 0;
            }}

            .empty {{
                color: var(--muted);
                padding: 18px 10px;
            }}

            a {{
                color: var(--blue);
                text-decoration: none;
            }}

            a:hover {{
                text-decoration: underline;
            }}

            .preset-group {{
                display: flex;
                gap: 6px;
                align-items: center;
                grid-column: 1 / -1;
            }}

            .preset-group select {{
                flex: 1;
                min-width: 160px;
            }}

            .preset-group button {{
                background: #0c141c;
                color: var(--text);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 8px 12px;
                cursor: pointer;
                white-space: nowrap;
                font: inherit;
            }}

            .preset-group button:hover {{
                background: rgba(147,197,253,.12);
            }}

            .preset-group button.danger {{
                border-color: #ef4444;
                color: #fca5a5;
            }}

            .preset-group button.danger:hover {{
                background: rgba(239,68,68,.15);
            }}

            @media (max-width: 980px) {{
                .bar {{
                    grid-template-columns: 1fr 1fr;
                }}

                thead th:nth-child(10), tbody td:nth-child(10), thead th:nth-child(16), tbody td:nth-child(16), thead th:nth-child(17), tbody td:nth-child(17), thead th:nth-child(18), tbody td:nth-child(18), thead th:nth-child(19), tbody td:nth-child(19), thead th:nth-child(20), tbody td:nth-child(20), thead th:nth-child(21), tbody td:nth-child(21) {{
                    display: none;
                }}

                thead th {{
                    top: 108px;
                }}
            }}
        </style>
</head>
<body>
  <div class="wrap">
    <div class="bar">
      <input id="q" type="search" placeholder="Search properties/items (e.g. 300%ED, @45, eth 4os, thresher)">
      <input id="minFg" type="number" min="0" step="1" placeholder="Min median fg">
      <select id="charClass">
        <option value="">All classes</option>
        <option value="warlock">Warlock (Sorc)</option>
        <option value="sorceress">Sorceress</option>
        <option value="paladin">Paladin</option>
        <option value="barbarian">Barbarian</option>
        <option value="amazon">Amazon</option>
        <option value="assassin">Assassin</option>
        <option value="necromancer">Necromancer</option>
        <option value="druid">Druid</option>
      </select>
      <select id="lldLevel">
        <option value="">All req levels</option>
        <option value="9">LLD <= 9</option>
        <option value="18">LLD <= 18</option>
        <option value="30">LLD <= 30</option>
      </select>
      <select id="lldBucket">
        <option value="">All LLD buckets</option>
        <option value="LLD9">LLD9 (≤9)</option>
        <option value="LLD18">LLD18 (10-18)</option>
        <option value="LLD30">LLD30 (19-30)</option>
        <option value="MLD">MLD (31-49)</option>
        <option value="HLD">HLD (≥50)</option>
        <option value="unknown">Unknown</option>
      </select>
      <select id="lldMode">
        <option value="exact">LLD exact req</option>
        <option value="both" selected>LLD exact + heuristic</option>
        <option value="heuristic">LLD heuristic only</option>
      </select>
      <select id="rowKind">
        <option value="">All row kinds</option>
        <option value="property">Property</option>
        <option value="variant_fallback">Fallback</option>
        <option value="variant_market_gap">Market-gap</option>
      </select>
      <select id="type1Filter">
        <option value="">All Type1</option>
      </select>
      <select id="kitFilter">
        <option value="">Kit/Finished: All</option>
        <option value="kit">Kit only</option>
        <option value="finished">Finished only</option>
      </select>
      <select id="unidMode">
        <option value="">All id states</option>
        <option value="unid">Unid only</option>
        <option value="id">Identified only</option>
      </select>
      <select id="linkMode">
        <option value="">All links</option>
        <option value="with">With source link</option>
        <option value="without">No source link</option>
      </select>
      <select id="potential">
        <option value="">All potential</option>
        <option value="high">High potential only</option>
      </select>
      <select id="sort">
        <option value="median_desc">Sort: median FG high → low</option>
        <option value="max_desc">Sort: max FG high → low</option>
        <option value="count_desc">Sort: observations high → low</option>
        <option value="samples_desc">Sort: unique items high → low</option>
        <option value="potential_desc">Sort: potential high → low</option>
        <option value="sig_asc">Sort: signature A → Z</option>
      </select>
      <select id="displayMode">
        <option value="grouped">View: Grouped</option>
        <option value="expanded_by_variant">View: Expanded by variant</option>
        <option value="expanded_by_listing">View: Expanded by listing</option>
      </select>
      <select id="conf">
        <option value="">All confidence</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <a href="d2planner_all_items_table.html" class="pill" title="Open full Maxroll D2 Planner item variants + market overlay">All Items</a>
      <div class="preset-group">
        <select id="presetSelect">
          <option value="">— Presets —</option>
          <optgroup label="Built-in" id="builtinPresetGroup"></optgroup>
          <optgroup label="Custom" id="customPresetGroup"></optgroup>
        </select>
        <button id="presetSave" title="Save current filters as a custom preset">Save</button>
        <button id="presetDelete" class="danger" title="Delete selected custom preset">Delete</button>
      </div>
    </div>
    <div class="meta" id="meta"></div>
    <table>
      <thead>
        <tr>
          <th data-key="name_display">Name</th>
          <th data-key="type_l1">Type1</th>
          <th data-key="type_l2">Type2</th>
          <th data-key="type_l3">Type3</th>
          <th data-key="class_tags">Class</th>
          <th data-key="signature">Stats</th>
          <th data-key="req_lvl_min" class="num">Req</th>
          <th data-key="median_fg" class="num">Median FG</th>
          <th data-key="max_fg" class="num">Max FG</th>
          <th data-key="obs_count" class="num">Obs</th>
          <th data-key="variant_count" class="num">Items</th>
          <th data-key="perfect_tier">Perfect</th>
          <th data-key="potential_score" class="num">Potential</th>
          <th data-key="iso_sell">ISO/Sell</th>
          <th data-key="signals">Signals</th>
          <th data-key="bin_fg" class="num">BIN</th>
          <th data-key="co_fg" class="num">c/o</th>
          <th data-key="ask_fg" class="num">ASK</th>
          <th data-key="sold_fg" class="num">SOLD</th>
          <th data-key="example_excerpt">Example</th>
          <th data-key="last_seen" class="num">Last Seen</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <script>
    const DATA = {payload};
    const state = {{ q:"", minFg:null, charClass:"", lldLevel:"", lldMode:"both", lldBucket:"", rowKind:"", type1Filter:"", kitFilter:"", unidMode:"", linkMode:"", conf:"", potential:"", sort:"median_desc", displayMode:"grouped" }};
    const $ = (id) => document.getElementById(id);
    const tbody = $("rows"), meta = $("meta");
    function esc(s) {{
      return String(s ?? "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
    }}
    function n(v) {{ return Math.round(Number(v || 0)); }}
    function escRe(s) {{
      return String(s).replace(/[.*+?^${{}}()|[\\]\\\\]/g, "\\\\$&");
    }}
    function relativeTime(isoStr) {{
      if (!isoStr) return "";
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return "";
      const sec = Math.floor((Date.now() - d.getTime()) / 1000);
      if (sec < 60) return "just now";
      const min = Math.floor(sec / 60);
      if (min < 60) return min + "m ago";
      const hr = Math.floor(min / 60);
      if (hr < 24) return hr + "h ago";
      const day = Math.floor(hr / 24);
      if (day < 7) return day + "d ago";
      const wk = Math.floor(day / 7);
      if (wk < 5) return wk + "w ago";
      const mo = Math.floor(day / 30);
      if (mo < 12) return mo + "mo ago";
      return Math.floor(day / 365) + "y ago";
    }}
    function isStale(isoStr) {{
      if (!isoStr) return false;
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return false;
      return (Date.now() - d.getTime()) > 7 * 24 * 60 * 60 * 1000;
    }}
    function hasToken(hay, alias) {{
      return new RegExp(`(?<![a-z])${{escRe(alias.toLowerCase())}}(?![a-z])`, "i").test(hay);
    }}
    function rowIsUnid(r) {{
      const t3 = String(r.type_l3 || "").toLowerCase();
      if (t3.split("\\n").includes("unid")) return true;
      const txt = `${{r.example_excerpt || ""}} ${{r.signature || ""}}`.toLowerCase();
      return txt.includes("unid") || txt.includes("unidentified");
    }}
    function inferReqHeuristic(r) {{
      const text = [
        r.signature || "",
        r.example_excerpt || "",
        ...(Array.isArray(r.top_variants) ? r.top_variants : []),
        r.name_display || "",
      ].join(" ").toLowerCase();
      const exactPatterns = [
        /(?:req(?:uired)?\\s*(?:lvl|level)?\\s*[:= ]\\s*)(\\d{{1,2}})\\b/i,
        /\\brlvl\\s*[:= ]?\\s*(\\d{{1,2}})\\b/i,
        /\\breq\\s*(\\d{{1,2}})\\b/i,
        /\\blvl\\s*(\\d{{1,2}})\\b/i,
        /\\blevel\\s*(\\d{{1,2}})\\b/i,
      ];
      for (const rx of exactPatterns) {{
        const m = text.match(rx);
        if (m) {{
          const v = Number(m[1]);
          if (Number.isFinite(v)) return v;
        }}
      }}
      // Heuristic LLD markers when exact req isn't present in grouped excerpts.
      const lldKeyword = /\\blld\\b/.test(text);
      const pvpCharmLike =
        (/(small charm|grand charm|large charm|\\bsc\\b|\\bgc\\b|\\blc\\b|jewel|circlet|tiara|coronet|diadem|amulet|ring)/.test(text) &&
         (/\\bfhr\\b|\\bfrw\\b|\\bar\\b|\\bmax\\b|\\blife\\b|\\b2\\/20\\b|\\b3\\/20\\/20\\b/.test(text)));
      if (lldKeyword || pvpCharmLike) return 30;
      return null;
    }}
    function filterRows(rows) {{
      const q = state.q.trim().toLowerCase();
      return rows.filter(r => {{
        if (state.minFg != null && Number(r.median_fg) < state.minFg) return false;
        if (state.rowKind && String(r.row_kind || "") !== state.rowKind) return false;
        if (state.type1Filter && String(r.type_l1 || "") !== state.type1Filter) return false;
        if (state.kitFilter === "kit" && !r.kit) return false;
        if (state.kitFilter === "finished" && r.kit) return false;
        if (state.linkMode === "with" && !String(r.last_source_url || "").trim()) return false;
        if (state.linkMode === "without" && String(r.last_source_url || "").trim()) return false;
        if (state.unidMode === "unid" && !rowIsUnid(r)) return false;
        if (state.unidMode === "id" && rowIsUnid(r)) return false;
        if (state.lldLevel) {{
          const lim = Number(state.lldLevel);
          const req = (r.req_lvl_min == null || r.req_lvl_min === "") ? null : Number(r.req_lvl_min);
          const hreq = inferReqHeuristic(r);
          const mode = String(state.lldMode || "both");
          let ok = false;
          if ((mode === "exact" || mode === "both") && req != null && Number.isFinite(req) && req <= lim) ok = true;
          if ((mode === "heuristic" || mode === "both") && hreq != null && Number.isFinite(hreq) && hreq <= lim) ok = true;
          if (!ok) return false;
        }}
        if (state.lldBucket && String(r.lld_bucket || "unknown") !== state.lldBucket) return false;
        if (state.charClass) {{
          const cls = String(state.charClass || "");
          const hayClass = [
            r.name_display || "",
            r.type_l1 || "",
            r.type_l2 || "",
            r.type_l3 || "",
            r.class_tags || "",
            r.signature || "",
            r.row_kind || "",
            ...(Array.isArray(r.top_variants) ? r.top_variants : []),
            r.example_excerpt || "",
          ].join(" ").toLowerCase();
          const classAliases = {{
            warlock: ["warlock", "sorc", "sorceress"],
            sorceress: ["sorceress", "sorc", "warlock"],
            paladin: ["paladin", "pally", "pal"],
            barbarian: ["barbarian", "barb"],
            amazon: ["amazon", "ama", "zon", "javazon", "bowazon"],
            assassin: ["assassin", "sin", "assa"],
            necromancer: ["necromancer", "necro", "nec"],
            druid: ["druid"],
          }};
          const aliases = classAliases[cls] || [cls];
          if (!aliases.some(a => hasToken(hayClass, a))) return false;
        }}
        if (state.conf && (r.confidence || "") !== state.conf) return false;
        if (state.potential && Number(r.potential_score || 0) <= 0) return false;
        if (!q) return true;
        const hay = [r.name_display || "", r.type_l1 || "", r.type_l2 || "", r.type_l3 || "", r.class_tags || "", r.signature, String(r.req_lvl_min ?? ""), r.row_kind || "", r.top_variants.join(" "), r.example_excerpt, r.signals, r.iso_sell || "", r.perfect_tier || "", (r.potential_tags || []).join(" ")].join(" ").toLowerCase();
        return hay.includes(q);
      }});
    }}
    function sortRows(rows) {{
      return rows.sort((a,b) => {{
        switch (state.sort) {{
          case "req_asc": return Number(a.req_lvl_min ?? 999)-Number(b.req_lvl_min ?? 999) || Number(a.max_fg)-Number(b.max_fg);
          case "req_desc": return Number(b.req_lvl_min ?? -1)-Number(a.req_lvl_min ?? -1) || Number(b.max_fg)-Number(a.max_fg);
          case "median_asc": return Number(a.median_fg)-Number(b.median_fg) || Number(a.max_fg)-Number(b.max_fg);
          case "max_desc": return Number(b.max_fg)-Number(a.max_fg) || Number(b.obs_count)-Number(a.obs_count);
          case "max_asc": return Number(a.max_fg)-Number(b.max_fg) || Number(a.obs_count)-Number(b.obs_count);
          case "count_desc": return Number(b.obs_count)-Number(a.obs_count) || Number(b.median_fg)-Number(a.median_fg);
          case "count_asc": return Number(a.obs_count)-Number(b.obs_count) || Number(a.median_fg)-Number(b.median_fg);
          case "samples_desc": return Number(b.variant_count)-Number(a.variant_count) || Number(b.median_fg)-Number(a.median_fg);
          case "samples_asc": return Number(a.variant_count)-Number(b.variant_count) || Number(a.median_fg)-Number(b.median_fg);
          case "potential_desc": return Number(b.potential_score)-Number(a.potential_score) || Number(b.max_fg)-Number(a.max_fg) || Number(b.median_fg)-Number(a.median_fg);
          case "potential_asc": return Number(a.potential_score)-Number(b.potential_score) || Number(a.max_fg)-Number(b.max_fg) || Number(a.median_fg)-Number(b.median_fg);
          case "sig_asc": return String(a.signature).localeCompare(String(b.signature));
          case "sig_desc": return String(b.signature).localeCompare(String(a.signature));
          case "name_asc": return String(a.name_display || "").localeCompare(String(b.name_display || ""));
          case "name_desc": return String(b.name_display || "").localeCompare(String(a.name_display || ""));
          case "type1_asc": return String(a.type_l1 || "").localeCompare(String(b.type_l1 || "")) || String(a.name_display || "").localeCompare(String(b.name_display || ""));
          case "type1_desc": return String(b.type_l1 || "").localeCompare(String(a.type_l1 || "")) || String(b.name_display || "").localeCompare(String(a.name_display || ""));
          case "type2_asc": return String(a.type_l2 || "").localeCompare(String(b.type_l2 || "")) || String(a.name_display || "").localeCompare(String(b.name_display || ""));
          case "type2_desc": return String(b.type_l2 || "").localeCompare(String(a.type_l2 || "")) || String(b.name_display || "").localeCompare(String(a.name_display || ""));
          case "type3_asc": return String(a.type_l3 || "").localeCompare(String(b.type_l3 || "")) || String(a.name_display || "").localeCompare(String(b.name_display || ""));
          case "type3_desc": return String(b.type_l3 || "").localeCompare(String(a.type_l3 || "")) || String(b.name_display || "").localeCompare(String(a.name_display || ""));
          case "class_asc": return String(a.class_tags || "").localeCompare(String(b.class_tags || "")) || String(a.name_display || "").localeCompare(String(b.name_display || ""));
          case "class_desc": return String(b.class_tags || "").localeCompare(String(a.class_tags || "")) || String(b.name_display || "").localeCompare(String(a.name_display || ""));
          case "perfect_asc": return String(a.perfect_tier || "").localeCompare(String(b.perfect_tier || "")) || Number(a.max_fg)-Number(b.max_fg);
          case "perfect_desc": return String(b.perfect_tier || "").localeCompare(String(a.perfect_tier || "")) || Number(b.max_fg)-Number(a.max_fg);
          case "iso_sell_asc": return String(a.iso_sell || "").localeCompare(String(b.iso_sell || "")) || Number(a.max_fg)-Number(b.max_fg);
          case "iso_sell_desc": return String(b.iso_sell || "").localeCompare(String(a.iso_sell || "")) || Number(b.max_fg)-Number(a.max_fg);
          case "signals_asc": return String(a.signals || "").localeCompare(String(b.signals || "")) || Number(a.max_fg)-Number(b.max_fg);
          case "signals_desc": return String(b.signals || "").localeCompare(String(a.signals || "")) || Number(b.max_fg)-Number(a.max_fg);
          case "bin_fg_desc": return (Number(b.bin_fg ?? -1))-(Number(a.bin_fg ?? -1)) || Number(b.max_fg)-Number(a.max_fg);
          case "bin_fg_asc": return (Number(a.bin_fg ?? Infinity))-(Number(b.bin_fg ?? Infinity)) || Number(a.max_fg)-Number(b.max_fg);
          case "co_fg_desc": return (Number(b.co_fg ?? -1))-(Number(a.co_fg ?? -1)) || Number(b.max_fg)-Number(a.max_fg);
          case "co_fg_asc": return (Number(a.co_fg ?? Infinity))-(Number(b.co_fg ?? Infinity)) || Number(a.max_fg)-Number(b.max_fg);
          case "ask_fg_desc": return (Number(b.ask_fg ?? -1))-(Number(a.ask_fg ?? -1)) || Number(b.max_fg)-Number(a.max_fg);
          case "ask_fg_asc": return (Number(a.ask_fg ?? Infinity))-(Number(b.ask_fg ?? Infinity)) || Number(a.max_fg)-Number(b.max_fg);
          case "sold_fg_desc": return (Number(b.sold_fg ?? -1))-(Number(a.sold_fg ?? -1)) || Number(b.max_fg)-Number(a.max_fg);
          case "sold_fg_asc": return (Number(a.sold_fg ?? Infinity))-(Number(b.sold_fg ?? Infinity)) || Number(a.max_fg)-Number(b.max_fg);
          case "example_asc": return String(a.example_excerpt || "").localeCompare(String(b.example_excerpt || "")) || Number(a.max_fg)-Number(b.max_fg);
          case "example_desc": return String(b.example_excerpt || "").localeCompare(String(a.example_excerpt || "")) || Number(b.max_fg)-Number(a.max_fg);
          case "last_seen_desc": return String(b.last_seen || "").localeCompare(String(a.last_seen || "")) || Number(b.max_fg)-Number(a.max_fg);
          case "last_seen_asc": return String(a.last_seen || "").localeCompare(String(b.last_seen || "")) || Number(a.max_fg)-Number(b.max_fg);
          case "median_desc":
          default: return Number(b.median_fg)-Number(a.median_fg) || Number(b.max_fg)-Number(a.max_fg);
        }}
      }});
    }}
    function headerSortKey(dataKey) {{
      switch (dataKey) {{
        case "name_display": return "name";
        case "type_l1": return "type1";
        case "type_l2": return "type2";
        case "type_l3": return "type3";
        case "class_tags": return "class";
        case "signature": return "sig";
        case "req_lvl_min": return "req";
        case "median_fg": return "median";
        case "max_fg": return "max";
        case "obs_count": return "count";
        case "variant_count": return "samples";
        case "perfect_tier": return "perfect";
        case "potential_score": return "potential";
        case "iso_sell": return "iso_sell";
        case "signals": return "signals";
        case "bin_fg": return "bin_fg";
        case "co_fg": return "co_fg";
        case "ask_fg": return "ask_fg";
        case "sold_fg": return "sold_fg";
        case "example_excerpt": return "example";
        case "last_seen": return "last_seen";
        default: return "";
      }}
    }}
    function toggleHeaderSort(dataKey) {{
      const base = headerSortKey(dataKey);
      if (!base) return;
      const current = String(state.sort || "");
      if (current === `${{base}}_desc`) state.sort = `${{base}}_asc`;
      else if (current === `${{base}}_asc`) state.sort = `${{base}}_desc`;
      else {{
        // default first click: desc for numeric-ish columns, asc for text columns
        const textKeys = new Set(["name","type1","type2","type3","class","sig","perfect","iso_sell","signals","example"]);
        state.sort = `${{base}}_${{textKeys.has(base) ? "asc" : "desc"}}`;
      }}
      const sortEl = $("sort");
      if (sortEl && [...sortEl.options].some(o => o.value === state.sort)) {{
        sortEl.value = state.sort;
      }}
      render();
    }}
    function expandRows(rows) {{
      const mode = state.displayMode;
      if (mode === "grouped") return rows;
      const result = [];
      for (const r of rows) {{
        const obs = r.observations || [];
        if (!obs.length) {{ result.push(r); continue; }}
        if (mode === "expanded_by_variant") {{
          const byVariant = {{}};
          for (const o of obs) {{
            const vk = o.variant_key || "(unknown)";
            if (!byVariant[vk]) byVariant[vk] = [];
            byVariant[vk].push(o);
          }}
          for (const [vk, vobs] of Object.entries(byVariant)) {{
            const prices = vobs.map(o => o.price_fg).filter(p => p > 0);
            prices.sort((a,b) => a - b);
            const med = prices.length ? prices[Math.floor(prices.length / 2)] : 0;
            result.push(Object.assign({{}}, r, {{
              name_display: vk.split(":").pop() || r.name_display,
              median_fg: med,
              max_fg: prices.length ? Math.max(...prices) : 0,
              obs_count: vobs.length,
              variant_count: 1,
              example_excerpt: (vobs[0].raw_excerpt || "").slice(0, 180),
              last_source_url: vobs[0].source_url || "",
              signals: vobs.map(o => o.signal_kind).filter(Boolean).join(", "),
              last_seen: vobs.reduce((mx, o) => {{ const t = o.observed_at || ""; return t > mx ? t : mx; }}, ""),
              _expanded: true,
            }}));
          }}
        }} else if (mode === "expanded_by_listing") {{
          for (const o of obs) {{
            result.push(Object.assign({{}}, r, {{
              median_fg: o.price_fg,
              max_fg: o.price_fg,
              obs_count: 1,
              variant_count: 1,
              example_excerpt: (o.raw_excerpt || "").slice(0, 180),
              last_source_url: o.source_url || "",
              signals: o.signal_kind || "",
              last_seen: o.observed_at || "",
              _observed_at: o.observed_at || "",
              _expanded: true,
            }}));
          }}
        }}
      }}
      return result;
    }}
    function render() {{
      const rows = sortRows(expandRows(filterRows(DATA)));
      const fallbackN = DATA.filter(r => (r.row_kind || "") === "variant_fallback").length;
      const gapN = DATA.filter(r => (r.row_kind || "") === "variant_market_gap").length;
      meta.textContent = `Market: {market_key} | ${{state.displayMode !== "grouped" ? state.displayMode + " | " : ""}}rows: ${{rows.length}} / ${{DATA.length}} (property + fallback) | fallback: ${{fallbackN}} | gap: ${{gapN}}`;
      if (!rows.length) {{
        tbody.innerHTML = `<tr><td class="empty" colspan="22">No rows match filters.</td></tr>`;
        return;
      }}
      tbody.innerHTML = rows.map(r => {{
        const conf = (r.confidence || "low").toLowerCase();
        const src = r.last_source_url ? `<a href="${{esc(r.last_source_url)}}" target="_blank" rel="noopener">open</a>` : "";
        const names = String(r.name_display || "").split(",").map(s => s.trim()).filter(Boolean);
        const namesHtml = `<div class="stack">${{names.length ? names.map(v => `<div>${{esc(v)}}</div>`).join("") : `<div class="muted">-</div>`}}</div>`;
        const t1 = (r.type_l1 || "").split("\\n").filter(Boolean);
        const t2 = (r.type_l2 || "").split("\\n").filter(Boolean);
        const t3 = (r.type_l3 || "").split("\\n").filter(Boolean);
        const ct = (r.class_tags || "").split("\\n").filter(Boolean);
        const stackHtml = (vals) => `<div class="stack">${{vals.length ? vals.map(v => `<div>${{esc(v)}}</div>`).join("") : `<div class="muted">-</div>`}}</div>`;
        const stale = isStale(r.last_seen);
        return `<tr${{stale ? ' class="stale-row"' : ''}}>
          <td>${{namesHtml}}</td>
          <td class="muted">${{stackHtml(t1)}}</td>
          <td class="muted">${{stackHtml(t2)}}</td>
          <td class="muted">${{stackHtml(t3)}}</td>
          <td class="muted">${{stackHtml(ct)}}</td>
          <td class="sig">${{esc(r.signature)}}${{r.kit ? ' <span class="pill-kit">KIT</span>' : ''}}${{r.lld_bucket && r.lld_bucket !== 'unknown' ? ' <span class="pill-bucket">' + esc(r.lld_bucket) + '</span>' : ''}}${{(r.row_kind||'')==='variant_fallback' ? ' <span class="pill">fallback</span>' : ''}}${{(r.row_kind||'')==='variant_market_gap' ? ' <span class="pill">gap</span>' : ''}}</td>
          <td class="num">${{(r.req_lvl_min == null || r.req_lvl_min === "") ? "-" : n(r.req_lvl_min)}}</td>
          <td class="num">${{n(r.median_fg)}} fg</td>
          <td class="num">${{n(r.max_fg)}} fg</td>
          <td class="num">${{n(r.obs_count)}}</td>
          <td class="num">${{n(r.variant_count)}}</td>
          <td class="muted">${{esc(r.perfect_tier || "")}}</td>
          <td class="num">${{n(r.potential_score)}} <span class="muted">${{esc((r.potential_tags||[]).join(","))}}</span></td>
          <td class="muted">${{esc(r.iso_sell || "")}}</td>
          <td class="muted"><span class="pill conf-${{conf}}">${{esc(r.confidence)}}</span> ${{esc(r.signals)}}</td>
          <td class="num">${{r.bin_fg != null ? n(r.bin_fg) + ' fg' : ''}}</td>
          <td class="num">${{r.co_fg != null ? n(r.co_fg) + ' fg' : ''}}</td>
          <td class="num">${{r.ask_fg != null ? n(r.ask_fg) + ' fg' : ''}}</td>
          <td class="num">${{r.sold_fg != null ? n(r.sold_fg) + ' fg' : ''}}</td>
          <td class="muted">${{esc(r.example_excerpt || "")}}${{r._observed_at ? ' <span class="pill">' + esc(r._observed_at) + '</span>' : ''}}</td>
          <td class="num${{stale ? ' stale-row' : ''}}">${{relativeTime(r.last_seen)}}</td>
          <td>${{src}}</td>
        </tr>`;
      }}).join("");
    }}
    $("q").addEventListener("input", e => {{ state.q = e.target.value; render(); }});
    $("minFg").addEventListener("input", e => {{ const v = e.target.value.trim(); state.minFg = v ? Number(v) : null; render(); }});
    $("charClass").addEventListener("change", e => {{ state.charClass = e.target.value; render(); }});
    $("lldLevel").addEventListener("change", e => {{ state.lldLevel = e.target.value; render(); }});
    $("lldBucket").addEventListener("change", e => {{ state.lldBucket = e.target.value; render(); }});
    $("lldMode").addEventListener("change", e => {{ state.lldMode = e.target.value; render(); }});
    $("rowKind").addEventListener("change", e => {{ state.rowKind = e.target.value; render(); }});
    $("type1Filter").addEventListener("change", e => {{ state.type1Filter = e.target.value; render(); }});
    $("kitFilter").addEventListener("change", e => {{ state.kitFilter = e.target.value; render(); }});
    $("unidMode").addEventListener("change", e => {{ state.unidMode = e.target.value; render(); }});
    $("linkMode").addEventListener("change", e => {{ state.linkMode = e.target.value; render(); }});
    $("potential").addEventListener("change", e => {{ state.potential = e.target.value; render(); }});
    $("sort").addEventListener("change", e => {{ state.sort = e.target.value; render(); }});
    $("conf").addEventListener("change", e => {{ state.conf = e.target.value; render(); }});
    $("displayMode").addEventListener("change", e => {{ state.displayMode = e.target.value; render(); }});
    document.querySelectorAll("thead th[data-key]").forEach(th => {{
      th.addEventListener("click", () => toggleHeaderSort(th.dataset.key || ""));
    }});
    (function initType1Options() {{
      const sel = $("type1Filter");
      if (!sel) return;
      const vals = [...new Set(DATA.map(r => String(r.type_l1 || "").trim()).filter(Boolean))].sort((a,b) => a.localeCompare(b));
      for (const v of vals) {{
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v;
        sel.appendChild(opt);
      }}
    }})();
    // ---- Preset system ----
    const BUILTIN_PRESETS = {{
      "Commodities": {{ type1Filter: "bundle", rowKind: "" }},
      "Runewords": {{ type1Filter: "runeword", kitFilter: "" }},
      "Torches/Annis": {{ q: "torch anni", type1Filter: "unique" }},
      "LLD": {{ lldLevel: "30", lldMode: "both", lldBucket: "" }},
      "Bases": {{ type1Filter: "base" }},
      "No source link": {{ linkMode: "without" }},
      "High FG + low confidence": {{ minFg: 500, conf: "low" }},
    }};
    const CUSTOM_PRESET_KEY = "d2lut_custom_presets";
    function _loadCustomPresets() {{
      try {{
        const raw = localStorage.getItem(CUSTOM_PRESET_KEY);
        return raw ? JSON.parse(raw) : {{}};
      }} catch(e) {{ return {{}}; }}
    }}
    function _saveCustomPresets(obj) {{
      try {{ localStorage.setItem(CUSTOM_PRESET_KEY, JSON.stringify(obj)); }} catch(e) {{}}
    }}
    function _currentFilterState() {{
      const snap = {{}};
      for (const k of Object.keys(state)) snap[k] = state[k];
      return snap;
    }}
    function _applyPreset(preset) {{
      // Reset all filter state to defaults first
      const defaults = {{ q:"", minFg:null, charClass:"", lldLevel:"", lldMode:"both", lldBucket:"", rowKind:"", type1Filter:"", kitFilter:"", unidMode:"", linkMode:"", conf:"", potential:"", sort:"median_desc", displayMode:"grouped" }};
      Object.assign(state, defaults);
      // Apply preset overrides
      for (const [k, v] of Object.entries(preset)) {{
        if (k in state) state[k] = v;
      }}
      // Sync UI controls to new state
      const syncMap = {{ q:"q", charClass:"charClass", lldLevel:"lldLevel", lldMode:"lldMode", lldBucket:"lldBucket", rowKind:"rowKind", type1Filter:"type1Filter", kitFilter:"kitFilter", unidMode:"unidMode", linkMode:"linkMode", conf:"conf", potential:"potential", sort:"sort", displayMode:"displayMode" }};
      for (const [stateKey, elId] of Object.entries(syncMap)) {{
        const el = $(elId);
        if (el) el.value = state[stateKey] ?? "";
      }}
      const minFgEl = $("minFg");
      if (minFgEl) minFgEl.value = state.minFg != null ? String(state.minFg) : "";
      render();
    }}
    function _populatePresetOptions() {{
      const builtinGroup = $("builtinPresetGroup");
      const customGroup = $("customPresetGroup");
      if (!builtinGroup || !customGroup) return;
      builtinGroup.innerHTML = "";
      customGroup.innerHTML = "";
      for (const name of Object.keys(BUILTIN_PRESETS)) {{
        const opt = document.createElement("option");
        opt.value = "builtin:" + name;
        opt.textContent = name;
        builtinGroup.appendChild(opt);
      }}
      const custom = _loadCustomPresets();
      for (const name of Object.keys(custom).sort()) {{
        const opt = document.createElement("option");
        opt.value = "custom:" + name;
        opt.textContent = name;
        customGroup.appendChild(opt);
      }}
    }}
    $("presetSelect").addEventListener("change", function(e) {{
      const val = e.target.value;
      if (!val) return;
      if (val.startsWith("builtin:")) {{
        const name = val.slice(8);
        if (BUILTIN_PRESETS[name]) _applyPreset(BUILTIN_PRESETS[name]);
      }} else if (val.startsWith("custom:")) {{
        const name = val.slice(7);
        const custom = _loadCustomPresets();
        if (custom[name]) _applyPreset(custom[name]);
      }}
    }});
    $("presetSave").addEventListener("click", function() {{
      const name = prompt("Preset name:");
      if (!name || !name.trim()) return;
      const custom = _loadCustomPresets();
      custom[name.trim()] = _currentFilterState();
      _saveCustomPresets(custom);
      _populatePresetOptions();
      $("presetSelect").value = "custom:" + name.trim();
    }});
    $("presetDelete").addEventListener("click", function() {{
      const sel = $("presetSelect");
      const val = sel.value;
      if (!val.startsWith("custom:")) return;
      const name = val.slice(7);
      const custom = _loadCustomPresets();
      delete custom[name];
      _saveCustomPresets(custom);
      _populatePresetOptions();
      sel.value = "";
    }});
    _populatePresetOptions();
    render();
  </script>
</body>
</html>
"""


def _confidence_label(obs_count: int, max_fg: float) -> str:
    if obs_count >= 8 and max_fg >= 300:
        return "high"
    if obs_count >= 3:
        return "medium"
    return "low"


def _signals_mix(rows: list[sqlite3.Row]) -> str:
    counts = defaultdict(int)
    for r in rows:
        counts[r["signal_kind"]] += 1
    return " ".join(f"{k}:{counts[k]}" for k in ("bin", "sold", "co", "ask") if counts[k])


def _signal_medians(rows: list[sqlite3.Row]) -> dict[str, float | None]:
    """Compute per-signal-type median FG.  Returns dict with keys bin_fg, co_fg, ask_fg, sold_fg."""
    buckets: dict[str, list[float]] = {"bin": [], "co": [], "ask": [], "sold": []}
    for r in rows:
        kind = str(r["signal_kind"] or "").lower()
        if kind in buckets:
            buckets[kind].append(float(r["price_fg"] or 0.0))
    result: dict[str, float | None] = {}
    for kind in ("bin", "co", "ask", "sold"):
        vals = buckets[kind]
        if vals:
            result[f"{kind}_fg"] = float(median(vals))
        else:
            result[f"{kind}_fg"] = None
    return result


def _best_source_url(rows: list[sqlite3.Row]) -> str:
    """Pick a source URL from a group, preferring explicit URLs then thread-id fallback."""
    with_url = [r for r in rows if str(r["source_url"] or "").strip()]
    if with_url:
        best = max(with_url, key=lambda r: float(r["price_fg"] or 0.0))
        return str(best["source_url"] or "")
    with_tid = [r for r in rows if r["thread_id"] is not None]
    if with_tid:
        best = max(with_tid, key=lambda r: float(r["price_fg"] or 0.0))
        tid = int(best["thread_id"])
        forum_id = int(best["forum_id"] or 271) if best["forum_id"] is not None else 271
        return f"https://forums.d2jsp.org/topic.php?t={tid}&f={forum_id}"
    return ""

def _max_observed_at(rows: list[sqlite3.Row]) -> str:
    """Return the most recent observed_at ISO timestamp from a group of rows."""
    best = ""
    for r in rows:
        ts = str(r["observed_at"] or "").strip()
        if ts and ts > best:
            best = ts
    return best


def _collect_observations(rows: list[sqlite3.Row]) -> list[dict]:
    """Extract per-observation data for expanded display modes."""
    obs = []
    for r in rows:
        source_url = str(r["source_url"] or "").strip()
        if not source_url:
            tid = r["thread_id"]
            if tid is not None:
                fid = int(r["forum_id"] or 271) if r["forum_id"] is not None else 271
                source_url = f"https://forums.d2jsp.org/topic.php?t={int(tid)}&f={fid}"
        obs.append({
            "source_url": source_url,
            "raw_excerpt": (str(r["raw_excerpt"] or ""))[:300],
            "signal_kind": str(r["signal_kind"] or ""),
            "price_fg": float(r["price_fg"] or 0.0),
            "observed_at": str(r["observed_at"] or ""),
            "variant_key": str(r["variant_key"] or ""),
        })
    return obs



def _variant_parts(vk: str) -> list[str]:
    if not vk:
        return []
    return [p for p in str(vk).split(":") if p]


def _variant_type_columns(top_variants: list[str]) -> tuple[str, str, str]:
    lvl1: list[str] = []
    lvl2: list[str] = []
    lvl3: list[str] = []
    for vk in top_variants:
        parts = _variant_parts(vk)
        if len(parts) >= 1:
            lvl1.append(parts[0])
        if len(parts) >= 2:
            lvl2.append(parts[1])
        if len(parts) >= 3:
            lvl3.append(parts[2])

    def _stack(vals: list[str]) -> str:
        seen: list[str] = []
        for v in vals:
            if v and v not in seen:
                seen.append(v)
        return "\n".join(seen)

    return (_stack(lvl1), _stack(lvl2), _stack(lvl3))


def _variant_name_without_type(vk: str) -> str:
    parts = _variant_parts(vk)
    if len(parts) <= 1:
        return vk
    # bundle:<subtype>:... -> show payload only in Name; subtype already has its own column
    if parts[0] == "bundle" and len(parts) >= 3:
        return ":".join(parts[2:])
    return ":".join(parts[1:])


def _rows_have_unid(rows: list[sqlite3.Row]) -> bool:
    for r in rows:
        txt = str(r["raw_excerpt"] or "")
        low = txt.lower()
        if "unid" in low or "unidentified" in low:
            return True
    return False


def _apply_unid_to_type_cols(type_cols: tuple[str, str, str], *, has_unid: bool) -> tuple[str, str, str]:
    if not has_unid:
        return type_cols
    a, b, c = type_cols
    if not c:
        c = "unid"
    elif "unid" not in c.split("\n"):
        c = f"{c}\nunid"
    return (a, b, c)


_RE_ISO_LIKE = re.compile(r"\b(?:iso|wtb|buy(?:ing)?|paying|need|lf)\b", re.I)
_RE_SELL_LIKE = re.compile(r"\b(?:ft|wts|sell(?:ing)?|bin|obo)\b", re.I)


def _iso_sell_label(rows: list[sqlite3.Row]) -> str:
    iso_n = 0
    sell_n = 0
    for r in rows:
        txt = str(r["raw_excerpt"] or "")
        if not txt:
            continue
        if _RE_ISO_LIKE.search(txt):
            iso_n += 1
        if _RE_SELL_LIKE.search(txt):
            sell_n += 1
    if iso_n == 0 and sell_n == 0:
        return ""
    if iso_n and sell_n:
        return f"ISO:{iso_n} / Sell:{sell_n}"
    if iso_n:
        return f"ISO:{iso_n}"
    return f"Sell:{sell_n}"


CLASS_ALIASES: dict[str, list[str]] = {
    "sorceress": ["sorceress", "sorc", "warlock"],
    "paladin": ["paladin", "pally", "pal"],
    "barbarian": ["barbarian", "barb"],
    "amazon": ["amazon", "ama", "zon", "javazon", "bowazon"],
    "assassin": ["assassin", "sin", "assa"],
    "necromancer": ["necromancer", "necro", "nec"],
    "druid": ["druid"],
}


def _infer_class_tags(top_variants: list[str], signature: str, example_excerpt: str) -> str:
    hay = " ".join([*(top_variants or []), signature or "", example_excerpt or ""]).lower()
    tags: list[str] = []

    # Exact torch variant suffixes are strongest.
    for vk in top_variants or []:
        parts = _variant_parts(vk)
        if len(parts) >= 3 and parts[0] == "unique" and parts[1] == "hellfire_torch":
            cls = parts[2].lower()
            if cls in CLASS_ALIASES and cls not in tags:
                tags.append(cls)

    # Skillers / class strings in signatures and excerpts.
    skiller_map = {
        "sorc_": "sorceress",
        "pala_": "paladin",
        "barb_": "barbarian",
        "ama_": "amazon",
        "assa_": "assassin",
        "necro_": "necromancer",
        "druid_": "druid",
    }
    sig_l = (signature or "").lower()
    for prefix, cls in skiller_map.items():
        if prefix in sig_l and cls not in tags:
            tags.append(cls)

    for cls, aliases in CLASS_ALIASES.items():
        if any(re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", hay) for a in aliases):
            if cls not in tags:
                tags.append(cls)

    return "\n".join(tags)


_REQ_LVL_CACHE: dict[str, int | None] = {}


def _req_lvl_from_excerpt_cached(excerpt: str, variant_key: str | None = None) -> int | None:
    key = f"{variant_key or ''}\n{excerpt or ''}"
    if key in _REQ_LVL_CACHE:
        return _REQ_LVL_CACHE[key]
    try:
        props = extract_props(excerpt or "", variant_key)
        val = props.req_lvl
    except Exception:
        val = None
    _REQ_LVL_CACHE[key] = val
    return val


def _min_req_lvl_for_rows(rows: list[sqlite3.Row], *, preferred: int | None = None) -> int | None:
    vals: list[int] = []
    if preferred is not None:
        vals.append(int(preferred))
    for r in rows:
        excerpt = str(r["raw_excerpt"] or "").strip()
        if not excerpt:
            continue
        req = _req_lvl_from_excerpt_cached(excerpt, str(r["variant_key"] or ""))
        if req is not None:
            vals.append(int(req))
    return min(vals) if vals else None


def _maxroll_magic_seed_tags(texts: list[str]) -> list[str]:
    joined = "\n".join(t for t in texts if t).lower()
    if not joined:
        return []
    tags: list[str] = []
    for tag, rx in MAXROLL_MAGIC_SEED_PATTERNS:
        if rx.search(joined):
            tags.append(tag)
    # Higher-level rollups for browser filtering.
    if any(t.startswith("maxroll_skill_gc") for t in tags) or "maxroll_skill_gc_name" in tags:
        tags.append("magic_gc_seed")
    if any(t.startswith("maxroll_jewel") for t in tags):
        tags.append("magic_jewel_seed")
    if "maxroll_magic_amulet" in tags or "maxroll_magic_circlet" in tags:
        tags.append("magic_jewelry_seed")
    if "maxroll_jmod" in tags or "maxroll_jewelers_monarch" in tags:
        tags.append("magic_shield_seed")
    return tags


def _potential_tags(props: ExtractedProps, *, max_fg: float, obs_count: int) -> list[str]:
    """Heuristic tags for potentially high-value combos, even with low sample counts."""
    tags: list[str] = []

    # Existing confirmed expensive combos should still be highlighted as "market-proven".
    if max_fg >= 500 or (max_fg >= 300 and obs_count >= 2):
        tags.append("market")

    # LLD/PvP charm & jewel shorthand can be very expensive with sparse observations.
    if props.lld and (props.charm_size or props.jewel):
        tags.append("lld")
    if props.max_dmg is not None and props.ar is not None and (props.life is not None or props.charm_size == "sc"):
        tags.append("pvp_combo")

    # Skillers and torch/anni/facets are premium property classes.
    if props.skiller:
        tags.append("skiller")
        if props.life is not None or props.fhr is not None:
            tags.append("skiller_plus")
    if props.item_form == "facet":
        tags.append("facet")
        if (props.facet_dmg, props.facet_enemy_res) == (5, 5):
            tags.append("perfect")
    if props.item_form == "torch":
        tags.append("torch")
        if props.torch_attrs == 20 and props.torch_res == 20:
            tags.append("perfect")
    if props.item_form == "anni":
        tags.append("anni")
        if props.anni_attrs == 20 and props.anni_res == 20 and props.anni_xp == 10:
            tags.append("perfect")
    if props.item_form == "gheed":
        tags.append("gheed")
        if props.gheed_mf is not None and props.gheed_mf >= 150:
            tags.append("high_roll")

    # Jewelry/circlets with premium PvP/caster patterns.
    if props.item_form in {"amulet", "circlet", "coronet", "tiara", "diadem", "ring"}:
        if props.fcr is not None and props.fcr >= 10:
            tags.append("fcr_jewelry")
        if props.item_form != "ring" and props.skills is not None and props.skills >= 2:
            tags.append("2skill")
        if props.item_form in {"circlet", "coronet", "tiara", "diadem"} and ((props.frw or 0) >= 20 or (props.os or 0) >= 2):
            tags.append("circlet_pvp")

    # Craft/runeword bases and elite/socketed eth bases.
    if props.base:
        if props.eth and (props.os or 0) >= 4:
            tags.append("rw_base")
        elif props.eth:
            tags.append("eth_base")
        if props.base in {"monarch", "archon_plate", "mage_plate", "thresher", "giant_thresher", "cryptic_axe", "colossus_voulge", "phase_blade", "berserker_axe"}:
            tags.append("elite_base")

    # Generic strong stat clusters.
    if props.all_res is not None and props.all_res >= 15:
        tags.append("high_res")
    if (props.fhr or 0) >= 12 and (props.charm_size == "gc" or props.skiller):
        tags.append("fhr_breakpoint")

    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _perfect_tier_from_tags(tags: list[str]) -> str:
    tset = set(tags or [])
    if "perfect" in tset:
        return "perfect"
    if "high_roll" in tset:
        return "high-roll"
    if "skiller_plus" in tset or "pvp_combo" in tset:
        return "premium"
    return ""


def main() -> int:
    p = argparse.ArgumentParser(description="Export searchable HTML of expensive property combinations")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--out", default="data/cache/property_price_table.html", help="Output HTML path")
    p.add_argument("--min-fg", type=float, default=100.0, help="Minimum observed price to consider (default: 100)")
    p.add_argument("--limit", type=int, default=5000, help="Max observed rows to scan after min-fg filter")
    p.add_argument(
        "--variant-fallback-min-obs",
        type=int,
        default=3,
        help="Add variant-only fallback rows for variants with no property signatures and at least this many observations (default: 3)",
    )
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT source, forum_id, thread_id, source_url, signal_kind, variant_key, price_fg, confidence,
                   COALESCE(raw_excerpt, '') AS raw_excerpt, observed_at
            FROM observed_prices
            WHERE market_key = ? AND price_fg >= ?
            ORDER BY price_fg DESC, id DESC
            LIMIT ?
            """,
            (args.market_key, args.min_fg, args.limit),
        ).fetchall()
    finally:
        conn.close()

    groups: dict[str, list[sqlite3.Row]] = defaultdict(list)
    group_props: dict[str, ExtractedProps] = {}
    variant_all_rows: dict[str, list[sqlite3.Row]] = defaultdict(list)
    variant_has_sig: set[str] = set()
    variant_sig_max_fg: dict[str, float] = {}
    for r in rows:
        vk = str(r["variant_key"] or "").strip()
        if vk:
            variant_all_rows[vk].append(r)
        excerpt = (r["raw_excerpt"] or "").strip()
        if not excerpt:
            continue
        props = extract_props(excerpt, r["variant_key"])
        sig = props_signature(props)
        if not sig:
            continue
        groups[sig].append(r)
        group_props.setdefault(sig, props)
        if vk:
            variant_has_sig.add(vk)
            cur = variant_sig_max_fg.get(vk, 0.0)
            pf = float(r["price_fg"] or 0.0)
            if pf > cur:
                variant_sig_max_fg[vk] = pf

    out_rows: list[dict] = []
    for sig, grows in groups.items():
        props = group_props[sig]
        prices = [float(r["price_fg"]) for r in grows]
        variant_counter: dict[str, int] = defaultdict(int)
        for r in grows:
            variant_counter[r["variant_key"]] += 1
        top_variants = [k for k, _ in sorted(variant_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
        best = max(grows, key=lambda r: float(r["price_fg"]))
        potential_tags = _potential_tags(props, max_fg=max(prices), obs_count=len(grows))
        seed_tags = _maxroll_magic_seed_tags([str(r["raw_excerpt"] or "") for r in grows])
        for t in seed_tags:
            if t not in potential_tags:
                potential_tags.append(t)
        potential_score = len(potential_tags)
        # Extra score weight for Maxroll seed hits to bubble rare magic items even with few observations.
        potential_score += sum(1 for t in potential_tags if t.startswith("maxroll_"))
        potential_score += sum(1 for t in potential_tags if t.endswith("_seed"))
        type_cols = _apply_unid_to_type_cols(
            _variant_type_columns(top_variants),
            has_unid=_rows_have_unid(grows),
        )
        out_rows.append(
            {
                "row_kind": "property",
                "name_display": ", ".join(_variant_name_without_type(v) for v in top_variants),
                "type_l1": type_cols[0],
                "type_l2": type_cols[1],
                "type_l3": type_cols[2],
                "class_tags": _infer_class_tags(top_variants, sig, (best["raw_excerpt"] or "")[:180]),
                "signature": sig,
                "req_lvl_min": _min_req_lvl_for_rows(grows, preferred=props.req_lvl),
                "median_fg": float(median(prices)),
                "max_fg": max(prices),
                "obs_count": len(grows),
                "variant_count": len(variant_counter),
                "potential_score": potential_score,
                "potential_tags": potential_tags,
                "perfect_tier": _perfect_tier_from_tags(potential_tags),
                "iso_sell": _iso_sell_label(grows),
                "top_variants": top_variants,
                "signals": _signals_mix(grows),
                **_signal_medians(grows),
                "confidence": _confidence_label(len(grows), max(prices)),
                "example_excerpt": (best["raw_excerpt"] or "")[:180],
                "last_source_url": _best_source_url(grows),
                "kit": props.kit,
                "lld_bucket": props.lld_bucket or "unknown",
                "last_seen": _max_observed_at(grows),
                "observations": _collect_observations(grows),
            }
        )

    # Add variant-only fallback rows for variants that have no property signatures at all.
    for vk, vrows in variant_all_rows.items():
        if not vk or vk in variant_has_sig:
            continue
        if len(vrows) < args.variant_fallback_min_obs:
            continue
        prices = [float(r["price_fg"]) for r in vrows]
        best = max(vrows, key=lambda r: float(r["price_fg"]))
        potential_tags = ["variant_only"]
        low_vk = vk.lower()
        if low_vk.startswith(("rune:", "key:", "keyset:", "token:", "essence:")):
            potential_tags.append("commodity")
        if low_vk.startswith("runeword:"):
            potential_tags.append("runeword")
        if low_vk.startswith("unique:hellfire_torch"):
            potential_tags.append("torch")
        type_cols = _apply_unid_to_type_cols(_variant_type_columns([vk]), has_unid=_rows_have_unid(vrows))
        out_rows.append(
            {
                "row_kind": "variant_fallback",
                "name_display": _variant_name_without_type(vk),
                "type_l1": type_cols[0],
                "type_l2": type_cols[1],
                "type_l3": type_cols[2],
                "class_tags": _infer_class_tags([vk], f"[variant] {vk}", (best["raw_excerpt"] or "")[:180]),
                "signature": f"[variant] {vk}",
                "req_lvl_min": _min_req_lvl_for_rows(vrows),
                "median_fg": float(median(prices)),
                "max_fg": max(prices),
                "obs_count": len(vrows),
                "variant_count": 1,
                "potential_score": max(1, len(potential_tags)),
                "potential_tags": potential_tags,
                "perfect_tier": _perfect_tier_from_tags(potential_tags),
                "iso_sell": _iso_sell_label(vrows),
                "top_variants": [vk],
                "signals": _signals_mix(vrows),
                **_signal_medians(vrows),
                "confidence": _confidence_label(len(vrows), max(prices)),
                "example_excerpt": (best["raw_excerpt"] or "")[:180],
                "last_source_url": _best_source_url(vrows),
                "kit": False,
                "lld_bucket": _assign_lld_bucket(_min_req_lvl_for_rows(vrows), False),
                "last_seen": _max_observed_at(vrows),
                "observations": _collect_observations(vrows),
            }
        )

    # Add variant market-gap rows when property parsing exists but misses top market prices.
    # This surfaces real high-end prices (e.g. Enigma/Infinity) instead of only low parsed property rows.
    for vk, vrows in variant_all_rows.items():
        if not vk or vk not in variant_has_sig:
            continue
        prices = [float(r["price_fg"]) for r in vrows]
        obs_max = max(prices) if prices else 0.0
        sig_max = float(variant_sig_max_fg.get(vk, 0.0))
        # Add only meaningful gaps to avoid clutter.
        if obs_max < args.min_fg:
            continue
        if sig_max <= 0:
            continue
        gap_abs = obs_max - sig_max
        gap_ratio = (obs_max / sig_max) if sig_max > 0 else 1.0
        if gap_abs < 250 and gap_ratio < 1.5:
            continue
        best = max(vrows, key=lambda r: float(r["price_fg"]))
        potential_tags = ["variant_market_gap"]
        low_vk = vk.lower()
        if low_vk.startswith(("rune:", "key:", "keyset:", "token:", "essence:")):
            potential_tags.append("commodity")
        if low_vk.startswith("runeword:"):
            potential_tags.append("runeword")
        type_cols = _apply_unid_to_type_cols(_variant_type_columns([vk]), has_unid=_rows_have_unid(vrows))
        out_rows.append(
            {
                "row_kind": "variant_market_gap",
                "name_display": _variant_name_without_type(vk),
                "type_l1": type_cols[0],
                "type_l2": type_cols[1],
                "type_l3": type_cols[2],
                "class_tags": _infer_class_tags([vk], f"[market-gap] {vk}", (best["raw_excerpt"] or "")[:180]),
                "signature": f"[market-gap] {vk}",
                "req_lvl_min": _min_req_lvl_for_rows(vrows),
                "median_fg": float(median(prices)),
                "max_fg": obs_max,
                "obs_count": len(vrows),
                "variant_count": 1,
                "potential_score": max(1, len(potential_tags)),
                "potential_tags": potential_tags,
                "perfect_tier": _perfect_tier_from_tags(potential_tags),
                "iso_sell": _iso_sell_label(vrows),
                "top_variants": [vk],
                "signals": _signals_mix(vrows),
                **_signal_medians(vrows),
                "confidence": _confidence_label(len(vrows), obs_max),
                "example_excerpt": (best["raw_excerpt"] or "")[:180],
                "last_source_url": _best_source_url(vrows),
                "kit": False,
                "lld_bucket": _assign_lld_bucket(_min_req_lvl_for_rows(vrows), False),
                "last_seen": _max_observed_at(vrows),
                "observations": _collect_observations(vrows),
            }
        )

    out_rows.sort(
        key=lambda r: (
            -float(r["median_fg"]),
            -float(r["max_fg"]),
            -int(r.get("potential_score", 0)),
            -int(r["obs_count"]),
            r["signature"],
        )
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_build_html(args.market_key, out_rows), encoding="utf-8")
    print(
        f"exported property_rows={len(out_rows)} from_observations={len(rows)} "
        f"market={args.market_key} out={out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
