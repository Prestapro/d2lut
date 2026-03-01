from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


def norm_text(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("'", "").replace("`", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ocr_fold_text(s: str) -> str:
    s = (s or "").lower()
    fold_map = str.maketrans(
        {
            "@": "o",
            "®": "o",
            "0": "o",
            "1": "l",
            "i": "l",
            "|": " ",
            "!": "l",
            "5": "s",
            "$": "s",
            "8": "b",
            "q": "g",  # OCR often flips g/q in D2 fonts
            "©": "c",  # OCR misread of 'c'
            "¢": "c",
            "€": "e",
        }
    )
    s = s.translate(fold_map)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _contains_all(hay: str, *parts: str) -> bool:
    return all(p in hay for p in parts if p)


MANUAL_ITEM_OCR_ALIASES: list[tuple[str, str]] = [
    # --- Runewords ---
    ("runeword:heart_of_the_oak", "heart of the oak"),
    ("runeword:heart_of_the_oak", "hoto"),
    ("runeword:heart_of_the_oak", "h0t0"),  # OCR 0/O
    ("runeword:call_to_arms", "call to arms"),
    ("runeword:call_to_arms", "cta"),
    ("runeword:infinity", "infinity"),
    ("runeword:infinity", "infanity"),  # common OCR corruption
    ("runeword:infinity", "lnfinity"),  # OCR I/l
    ("runeword:infinity", "inf"),  # d2jsp shorthand
    ("runeword:enigma", "enigma"),
    ("runeword:enigma", "enig"),  # d2jsp shorthand
    ("runeword:breath_of_the_dying", "breath of the dying"),
    ("runeword:breath_of_the_dying", "botd"),
    ("runeword:breath_of_the_dying", "ebotd"),  # eth BOTD
    ("runeword:breath_of_the_dying", "ebotdz"),  # eth BOTD zerker
    ("runeword:grief", "grief"),
    ("runeword:grief", "grlef"),  # OCR i/l
    ("runeword:insight", "insight"),
    ("runeword:insight", "lnsight"),  # OCR I/l
    ("runeword:chains_of_honor", "chains of honor"),
    ("runeword:chains_of_honor", "coh"),
    ("runeword:last_wish", "last wish"),
    ("runeword:last_wish", "lw"),
    ("runeword:fortitude", "fortitude"),
    ("runeword:fortitude", "fort"),
    ("runeword:spirit", "spirit"),
    ("runeword:spirit", "spirlt"),  # OCR i/l
    ("runeword:phoenix", "phoenix"),
    ("runeword:dream", "dream"),
    ("runeword:faith", "faith"),
    ("runeword:pride", "pride"),
    ("runeword:doom", "doom"),
    ("runeword:beast", "beast"),
    ("runeword:exile", "exile"),
    ("runeword:death", "death"),
    ("runeword:destruction", "destruction"),
    ("runeword:hand_of_justice", "hand of justice"),
    ("runeword:hand_of_justice", "hoj"),
    ("runeword:bramble", "bramble"),
    ("runeword:treachery", "treachery"),
    ("runeword:treachery", "trech"),  # d2jsp shorthand
    ("runeword:duress", "duress"),
    ("runeword:stone", "stone"),
    ("runeword:smoke", "smoke"),
    ("runeword:stealth", "stealth"),
    ("runeword:lore", "lore"),
    ("runeword:rhyme", "rhyme"),
    ("runeword:white", "white"),
    ("runeword:oath", "oath"),
    ("runeword:obedience", "obedience"),
    # --- Uniques ---
    ("unique:hellfire_torch", "hellfire torch"),
    ("unique:hellfire_torch", "htorch"),  # d2jsp shorthand
    ("unique:annihilus", "annihilus"),
    ("unique:annihilus", "anni"),  # d2jsp shorthand
    ("unique:annihilus", "annl"),  # OCR i/l
    ("unique:harlequin_crest", "harlequin crest"),
    ("unique:harlequin_crest", "shako"),
    ("unique:harlequin_crest", "shak0"),  # OCR o/0
    ("unique:the_stone_of_jordan", "stone of jordan"),
    ("unique:the_stone_of_jordan", "soj"),
    ("unique:arachnid_mesh", "arachnid mesh"),
    ("unique:arachnid_mesh", "arach"),
    ("unique:mara_kaleidoscope", "mara's kaleidoscope"),
    ("unique:mara_kaleidoscope", "maras"),
    ("unique:war_traveler", "war traveler"),
    ("unique:war_traveler", "war trav"),
    ("unique:war_traveler", "wtrav"),
    ("unique:skullder_ire", "skullder's ire"),
    ("unique:skullder_ire", "skullders"),
    ("unique:tal_rasha_guardianship", "tal rasha's guardianship"),
    ("unique:tal_rasha_guardianship", "tal armor"),
    ("unique:tal_rasha_adjudication", "tal rasha's adjudication"),
    ("unique:tal_rasha_adjudication", "tal ammy"),
    ("unique:griffon_eye", "griffon's eye"),
    ("unique:griffon_eye", "griff"),
    ("unique:griffon_eye", "griffons"),
    ("unique:crown_of_ages", "crown of ages"),
    ("unique:crown_of_ages", "coa"),
    ("unique:deaths_fathom", "death's fathom"),
    ("unique:deaths_fathom", "dfathom"),
    ("unique:deaths_web", "death's web"),
    ("unique:deaths_web", "dweb"),
    ("unique:nightwing_veil", "nightwing's veil"),
    ("unique:nightwing_veil", "nw"),
    ("unique:verdungo_hearty_cord", "verdungo's hearty cord"),
    ("unique:verdungo_hearty_cord", "dungos"),
    ("unique:stormshield", "stormshield"),
    ("unique:stormshield", "ss"),
    ("unique:windforce", "windforce"),
    ("unique:windforce", "wf"),
    ("unique:highlords_wrath", "highlord's wrath"),
    ("unique:highlords_wrath", "highlords"),
    ("unique:chance_guards", "chance guards"),
    ("unique:chance_guards", "chancies"),
    ("unique:goldwrap", "goldwrap"),
    ("unique:oculus", "the oculus"),
    ("unique:oculus", "occy"),
    ("unique:herald_of_zakarum", "herald of zakarum"),
    ("unique:herald_of_zakarum", "hoz"),
    ("unique:herald_of_zakarum", "zaka"),
]


# Coarse category constraints for modifier/stat shorthand parsing and OCR post-processing.
# Each entry maps a category key to allow/deny sets of modifier code prefixes.
# Unknown categories or unknown property codes are allowed (conservative default).
DEFAULT_CATEGORY_CONSTRAINTS: dict[str, dict[str, set[str]]] = {
    # --- item-type categories ---
    "runes": {
        "allow_codes": {"quantity"},
        "deny_codes": {"sock", "ac%", "dmg%", "fcr", "ias", "allres", "life", "mana", "mf", "ar", "fhr", "frw"},
    },
    "torch": {
        "allow_codes": {"allskills", "attributes", "allres", "light_radius", "experience"},
        "deny_codes": {"sock", "fcr", "ias", "dmg", "ac", "ar", "mf"},
    },
    "anni": {
        "allow_codes": {"allskills", "attributes", "allres", "experience"},
        "deny_codes": {"sock", "fcr", "ias", "dmg", "ac", "ar", "mf"},
    },
    "jewel": {
        "deny_codes": {"sock", "charm", "quantity"},
    },
    "charm": {
        "deny_codes": {"sock", "ac", "ethereal", "base", "quantity"},
    },
    "amulet": {
        "deny_codes": {"sock", "ac", "dmg%", "ethereal", "base", "charm", "quantity"},
    },
    "ring": {
        "deny_codes": {"sock", "ac", "dmg%", "ethereal", "base", "charm", "quantity"},
    },
    "circlet": {
        "deny_codes": {"dmg%", "charm", "quantity"},
    },
    "gloves": {
        "deny_codes": {"charm", "quantity", "allskills"},
    },
    "boots": {
        "deny_codes": {"sock", "ias", "fcr", "charm", "quantity", "allskills"},
    },
    "belt": {
        "deny_codes": {"sock", "ias", "charm", "quantity", "allskills"},
    },
    "shield": {
        "deny_codes": {"dmg%", "ias", "charm", "quantity"},
    },
    "helm": {
        "deny_codes": {"dmg%", "ias", "charm", "quantity"},
    },
    "body_armor": {
        "deny_codes": {"dmg%", "ias", "charm", "quantity"},
    },
    # --- base categories (white/grey items for runewords) ---
    "base_armor": {
        "allow_codes": {"sock", "ac", "dur", "ethereal", "base"},
    },
    "base_weapon": {
        "allow_codes": {"sock", "dmg", "ias", "ethereal", "base"},
    },
    # --- quality-class categories (broad deny for impossible combos) ---
    "set_item": {
        "deny_codes": {"sock", "charm", "quantity"},
    },
    "unique_item": {
        "deny_codes": {"charm", "quantity"},
    },
    "runeword_item": {
        "deny_codes": {"charm", "quantity"},
    },
    "magic_item": {
        "deny_codes": {"charm", "quantity"},
    },
    "rare_item": {
        "deny_codes": {"sock", "charm", "quantity"},
    },
}

# Coarse mapping from extracted property names to modifier code prefixes used by constraints.
PROPERTY_NAME_CODE_PREFIXES: dict[str, set[str]] = {
    "sockets": {"sock"},
    "enhanced_damage": {"dmg"},
    "defense": {"ac"},
    "ias": {"ias"},
    "fcr": {"fcr"},
    "frw": {"frw"},
    "fhr": {"fhr"},
    "mana": {"mana"},
    "magic_find": {"mf"},
    "life": {"life"},
    "all_resistances": {"allres"},
    "fire_resistance": {"res"},
    "cold_resistance": {"res"},
    "lightning_resistance": {"res"},
    "poison_resistance": {"res"},
    "all_skills": {"allskills"},
    "max_damage": {"dmg"},
    "min_damage": {"dmg"},
    "attack_rating": {"ar"},
    "ethereal": {"ethereal"},
    "charm_size": {"charm"},
    "rune_name": {"quantity"},
    "base_type": {"base"},
    "durability": {"dur"},
    "strength": {"attributes"},
    "dexterity": {"attributes"},
    "vitality": {"attributes"},
    "energy": {"attributes"},
    "experience": {"experience"},
    "light_radius": {"light_radius"},
}


def property_allowed_by_category_constraints(category_key: str | None, property_name: str | None) -> bool:
    """Coarse constraint gate for extracted properties.

    Uses ``DEFAULT_CATEGORY_CONSTRAINTS`` and property->code-prefix mapping.
    Unknown property names are allowed (conservative default).
    """
    cat = (category_key or "").strip().lower()
    prop = (property_name or "").strip().lower()
    if not cat or not prop:
        return True
    rules = DEFAULT_CATEGORY_CONSTRAINTS.get(cat)
    if not rules:
        return True
    prop_codes = PROPERTY_NAME_CODE_PREFIXES.get(prop)
    if not prop_codes:
        return True

    deny = set(rules.get("deny_codes", set()))
    if any(any(code.startswith(d) for d in deny) for code in prop_codes):
        return False
    allow = set(rules.get("allow_codes", set()))
    if allow and not any(any(code.startswith(a) for a in allow) for code in prop_codes):
        return False
    return True


_RW_INF_RE = re.compile(r"\b(?:infinity|infanity|lnfinity|lnfanlty)\b", re.I)
_RW_HOTO_RE = re.compile(r"\b(?:hoto|h0t0|heart\W*of\W*the\W*oak)\b", re.I)
_RW_CTA_RE = re.compile(r"\b(?:cta|call\W*t[o0]\W*arms)\b", re.I)
_RW_ENIGMA_RE = re.compile(r"\b(?:enigma|enig)\b", re.I)
_RW_BOTD_RE = re.compile(r"\b(?:e?botd(?:z)?|breath\W*of\W*the\W*dying)\b", re.I)
_RW_INSIGHT_RE = re.compile(r"\b(?:insight|lnsight|lnslght)\b", re.I)
_RW_GRIEF_RE = re.compile(r"\b(?:grief|grlef)\b", re.I)
_RW_COH_RE = re.compile(r"\b(?:coh|chains\W*of\W*honor)\b", re.I)
_RW_FORT_RE = re.compile(r"\b(?:fortitude|fort)\b", re.I)
_RW_SPIRIT_RE = re.compile(r"\b(?:spirit|spirlt)\b", re.I)
_RW_FAITH_RE = re.compile(r"\bfaith\b", re.I)
_RW_LAST_WISH_RE = re.compile(r"\b(?:last\W*wish|lw)\b", re.I)
_TORCH_RE = re.compile(r"\bhellfire\W*torch\b|\blarge\W*char\w+\b.*\bkeep\W*invent\w+", re.I)
_TORCH_CLASS_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:warlock|sorc(?:eress)?|orber?)\b", re.I), "sorceress"),
    (re.compile(r"\b(?:pala(?:din)?|smiter|hammer(?:din)?)\b", re.I), "paladin"),
    (re.compile(r"\b(?:zon|ama(?:zon)?)\b", re.I), "amazon"),
    (re.compile(r"\b(?:barb(?:arian)?)\b", re.I), "barbarian"),
    (re.compile(r"\b(?:druid|ele druid|wind druid)\b", re.I), "druid"),
    (re.compile(r"\b(?:sin|assa(?:ssin)?|trapsin)\b", re.I), "assassin"),
    (re.compile(r"\b(?:necro|nec(?:romancer)?)\b", re.I), "necromancer"),
]
_ANNI_RE = re.compile(r"\bannihilus\b|\bsmall\W*charm\b.*\bkeep\W*invent\w+", re.I)
_SHAKO_RE = re.compile(r"\bharlequin\W*crest\b|\bshako\b", re.I)
_SOCKETS_RE = re.compile(r"\b([2-6])\s*(?:os|socket(?:ed)?s?)\b", re.I)
_SOCKETS_PAREN_AFTER_WORD_RE = re.compile(r"\bsocket(?:ed)?s?\s*\(?\s*([2-6])\s*\)?", re.I)
_SOCKETS_OCR_WORD_RE = re.compile(r"\bs[oe]ck\w*\s*\(?\s*([2-6])\s*\)?", re.I)
_ETH_RE = re.compile(r"\beth(?:ereal)?\b", re.I)

_BASE_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("base:mage_plate", re.compile(r"\bmage\W*plate\b", re.I), "base:mage_plate"),
    ("base:archon_plate", re.compile(r"\barchon\W*plate\b", re.I), "base:archon_plate"),
    ("base:sacred_armor", re.compile(r"\bsacred\W*armor\b", re.I), "base:sacred_armor"),
    ("base:thresher", re.compile(r"\bthresher\b", re.I), "base:thresher"),
    ("base:giant_thresher", re.compile(r"\bgiant\W*thresher\b", re.I), "base:giant_thresher"),
    ("base:cryptic_axe", re.compile(r"\bcryptic\W*axe\b", re.I), "base:cryptic_axe"),
    ("base:monarch", re.compile(r"\bmonarch\b", re.I), "base:monarch"),
    ("base:crystal_sword", re.compile(r"\bcrystal\W*sword\b", re.I), "base:crystal_sword"),
    ("base:flail", re.compile(r"\bflail\b", re.I), "base:flail"),
    ("base:thunder_maul", re.compile(r"\bthun[qd]er\W*maul\b", re.I), "base:thunder_maul"),
]


def infer_variant_from_noisy_ocr(item_name: str | None, raw_text: str | None) -> str | None:
    text = " ".join([item_name or "", raw_text or ""]).strip()
    if not text:
        return None
    low = text.lower()
    folded = ocr_fold_text(text)
    if not folded:
        return None

    # Classify distinctive runewords/items first.
    if _RW_HOTO_RE.search(low) or _RW_HOTO_RE.search(folded) or _contains_all(folded, "ko", "vex", "pul", "thul", "flail"):
        return "runeword:heart_of_the_oak"
    if _RW_INF_RE.search(low) or _RW_INF_RE.search(folded) or _contains_all(folded, "ber", "mal", "ber", "ist", "scythe"):
        return "runeword:infinity"
    if _RW_CTA_RE.search(folded) or (_contains_all(folded, "battle", "command") and "order" in folded):
        return "runeword:call_to_arms"
    if _RW_ENIGMA_RE.search(folded) or _contains_all(folded, "jah", "ith", "ber"):
        return "runeword:enigma"
    if _RW_BOTD_RE.search(folded) or _contains_all(folded, "vex", "hel", "el", "eld", "zod", "eth"):
        return "runeword:breath_of_the_dying"
    if _RW_INSIGHT_RE.search(folded) or _contains_all(folded, "ral", "tir", "tal", "sol"):
        return "runeword:insight"
    if _RW_GRIEF_RE.search(low) or _RW_GRIEF_RE.search(folded):
        return "runeword:grief"
    if _RW_COH_RE.search(low) or _RW_COH_RE.search(folded):
        return "runeword:chains_of_honor"
    if _RW_FORT_RE.search(low) or _RW_FORT_RE.search(folded):
        return "runeword:fortitude"
    if _RW_LAST_WISH_RE.search(low) or _RW_LAST_WISH_RE.search(folded):
        return "runeword:last_wish"
    if _RW_FAITH_RE.search(low) or _RW_FAITH_RE.search(folded):
        return "runeword:faith"
    if _RW_SPIRIT_RE.search(low) or _RW_SPIRIT_RE.search(folded):
        return "runeword:spirit"
    is_unid = ("unidentified" in low) or ("unid" in low) or ("unldent" in folded) or ("unld" in folded)
    if (_TORCH_RE.search(low) or _TORCH_RE.search(folded)) and is_unid:
        return "unique:hellfire_torch"
    if _TORCH_RE.search(low) or _TORCH_RE.search(folded):
        for class_re, torch_class in _TORCH_CLASS_HINTS:
            if class_re.search(low) or class_re.search(folded):
                return f"unique:hellfire_torch:{torch_class}"
        return "unique:hellfire_torch"
    if (_ANNI_RE.search(low) or _ANNI_RE.search(folded)) and ("annihilus" in low or "annihilus" in folded):
        return "unique:annihilus"
    if "annihilus" in folded:
        return "unique:annihilus"
    if _SHAKO_RE.search(folded):
        return "unique:harlequin_crest"

    # Base-only fallback for screenshot listings with little text.
    for _family, pat, base in _BASE_PATTERNS:
        if pat.search(low) or pat.search(folded):
            eth = "eth" if _ETH_RE.search(folded) else "noneth"
            m = _SOCKETS_RE.search(folded) or _SOCKETS_PAREN_AFTER_WORD_RE.search(folded) or _SOCKETS_OCR_WORD_RE.search(folded)
            sockets = m.group(1) if m else None
            variant = f"{base}:{eth}"
            if sockets:
                variant += f":{sockets}os"
            return variant
    if "magee plate" in folded:
        m = _SOCKETS_RE.search(folded) or _SOCKETS_PAREN_AFTER_WORD_RE.search(folded) or _SOCKETS_OCR_WORD_RE.search(folded)
        sockets = m.group(1) if m else None
        variant = "base:mage_plate:noneth"
        if sockets:
            variant += f":{sockets}os"
        return variant
    return None


def infer_item_category_from_variant(variant_key: str | None) -> str:
    v = (variant_key or "").lower()
    if v.startswith("rune:"):
        return "runes"
    if v.startswith("unique:hellfire_torch"):
        return "torch"
    if v.startswith("unique:annihilus"):
        return "anni"
    if v.startswith("jewel:"):
        return "jewel"
    if v.startswith("charm:") or "charm" in v:
        return "charm"
    if v.startswith("runeword:"):
        return "runeword_item"
    if v.startswith("set:"):
        return "set_item"
    if v.startswith("unique:"):
        return "unique_item"
    if v.startswith("base:"):
        if any(x in v for x in (":archon_plate", ":mage_plate", ":sacred_armor", ":monarch")):
            return "base_armor"
        return "base_weapon"
    return "generic"


@dataclass
class ModifierAliasMatch:
    canonical_key: str
    alias_text: str
    source: str
    confidence: float


class ModifierLexiconMatcher:
    """Lightweight SQLite-backed matcher for modifier aliases/shorthand."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def search(self, query: str, *, limit: int = 25, ocr: bool = True) -> list[ModifierAliasMatch]:
        if not self.db_path.exists():
            return []
        key = ocr_fold_text(query) if ocr else norm_text(query)
        if not key:
            return []
        col = "ocr_norm_key" if ocr else "norm_key"
        out: list[ModifierAliasMatch] = []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            try:
                rows = conn.execute(
                    f"""
                    SELECT canonical_key, alias_text, source_domain, confidence
                    FROM modifier_alias_lexicon
                    WHERE {col} = ? OR {col} LIKE ?
                    ORDER BY CASE WHEN {col} = ? THEN 0 ELSE 1 END, confidence DESC, length(alias_text) DESC
                    LIMIT ?
                    """,
                    (key, f"%{key}%", key, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                return out
            for r in rows:
                out.append(
                    ModifierAliasMatch(
                        canonical_key=str(r["canonical_key"]),
                        alias_text=str(r["alias_text"]),
                        source=str(r["source_domain"]),
                        confidence=float(r["confidence"] or 0.0),
                    )
                )
        finally:
            conn.close()
        return out
