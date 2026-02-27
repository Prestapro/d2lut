from __future__ import annotations

import html
import re
import sqlite3
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin

from .modifier_lexicon import infer_variant_from_noisy_ocr

D2JSP_BASE = "https://forums.d2jsp.org/"

# Global cache for slang aliases (loaded once per process)
_SLANG_CACHE: dict[str, list[dict]] | None = None

_PRICE_RE = re.compile(
    r"(?i)\b(?:(sold|bin|c/?o|offer(?:s)?|asking?)\s*[:@-]?\s*(\d[\d,\.]*)\s*(?:fg)?|(\d[\d,\.]*)\s*fg\s*(sold|bin|c/?o))\b"
)
_PREFIX_PRICE_RE = re.compile(
    r"(?i)\b(sold|bin|c/?o|offer(?:s)?|asking?)\s*[:@-]?\s*(\d[\d,\.]*)\s*(fg)?\b"
)
_SUFFIX_PRICE_RE = re.compile(
    r"(?i)\b(\d[\d,\.]*)\s*(fg)\s*(sold|bin|c/?o)\b"
)
_PLAIN_FG_RE = re.compile(r"(?i)\b(\d[\d,\.]*)\s*fg\b")
_PLAIN_NUM_PRICE_CANDIDATE_RE = re.compile(r"(?i)(?:^|[\s:|~,\-])(\d{2,5})(?=$|[\s:|,\-])")

_BIN_RE = re.compile(r"(?i)\bbin\b")
_SOLD_RE = re.compile(r"(?i)\bsold\b")
_TRADE_FT_RE = re.compile(r"(?i)\b(ft|for trade|offer|o )\b")
_ISO_SERVICE_RE = re.compile(r"(?i)\b(iso|service|rush|grush)\b")
_ISO_RE = re.compile(r"(?i)\biso\b")
_SERVICE_RE = re.compile(r"(?i)\b(service|rush|grush|terrorize)\b")
_PC_RE = re.compile(r"(?i)\b(pc|price check)\b")
_STAT_CONTEXT_RE = re.compile(
    r"(?i)\b(def|ed|res|allres|life|mana|fcr|frw|ias|str|dex|vit|ene|mf|gf|ll|ml|ar|dmg|cold|fire|light|psn)\b|%|\b[3456]os\b|\b\d+/\d+\b"
)
_PRICE_ONLY_REPLY_RE = re.compile(r"(?i)^\s*(?:@|bin|c/?o|offer|offers|sold)?\s*[:@-]?\s*(\d{2,5})(\s*fg)?\s*(?:here|now|ok|nty|/ea|each)?\s*$")

RUNE_NAMES = [
    "zod","cham","jah","ber","sur","lo","ohm","vex","gul","ist","mal","um","pul","lem","fal","ko","lum","io","hel","dol","shael","sol","amn","thul","ort","ral","tal","ith","el"
]

_RUNE_RE = re.compile(r"(?i)\b(" + "|".join(RUNE_NAMES) + r")\b(?!['’]d\b)")
_RUNE_BUNDLE_RE = re.compile(
    r"(?i)\b(?:" + "|".join(RUNE_NAMES) + r")\b(?!['’]d\b)(?:\s*[+/,&]\s*\b(?:" + "|".join(RUNE_NAMES) + r")\b(?!['’]d\b)){1,}"
)
_RUNE_SEQ_SPACED_RE = re.compile(
    r"(?i)\b(?:" + "|".join(RUNE_NAMES) + r")\b(?!['’]d\b)(?:\s+\b(?:" + "|".join(RUNE_NAMES) + r")\b(?!['’]d\b)){1,}"
)
_ENIGMA_RUNE_SEQ_RE = re.compile(
    r"(?i)\bjah\b(?:\s*[+/,&]?\s*)\bith\b(?:\s*[+/,&]?\s*)\bber\b"
)
_KEYSET_RE = re.compile(r"(?i)\bkey\s*set\b|\b3x3\b")
_KEY_RE = re.compile(r"(?i)\b(key of terror|key of hate|key of destruction|terror key|hate key|destruction key)\b")
_TOKEN_RE = re.compile(r"(?i)\btoken(?: of absolution)?\b")
_ESS_RE = re.compile(r"(?i)\b(ess(?:ence)?s?)\b")
_TORCH_RE = re.compile(r"(?i)\btorch(?:es)?\b")
_TORCH_CLASS_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(?:warlock|sorc(?:eress)?|orb(?:er)?)\b"), "sorceress"),
    (re.compile(r"(?i)\b(?:pala?d?i?n?|pally)\b"), "paladin"),
    (re.compile(r"(?i)\b(?:necro(?:mancer)?|bonemancer)\b"), "necromancer"),
    (re.compile(r"(?i)\b(?:ama(?:zon)?|zon|javazon|bowazon)\b"), "amazon"),
    (re.compile(r"(?i)\b(?:barb(?:arian)?)\b"), "barbarian"),
    (re.compile(r"(?i)\b(?:druid|wolf|windy)\b"), "druid"),
    (re.compile(r"(?i)\b(?:sin|assa?ss?in|trapsin)\b"), "assassin"),
]
_ANNI_RE = re.compile(r"(?i)\banni(?:hilus)?\b")
_FACET_RE = re.compile(r"(?i)\bfacet(?:s)?\b")
_SHAKO_RE = re.compile(r"(?i)\b(?:shako|harlequin\s+crest)\b")
_GRIFFON_RE = re.compile(r"(?i)\b(?:griffon'?s?\s+eye|griffons?)\b")
_HOZ_RE = re.compile(r"(?i)\b(?:herald\s+of\s+zakarum|hoz|zaka)\b")
_NIGHTWING_RE = re.compile(r"(?i)\b(?:nightwing'?s?(?:\s+veil)?|nw)\b")

# --- Additional unique/set item patterns for broader market coverage ---
_ARACH_RE = re.compile(r"(?i)\b(?:arach(?:nid)?(?:'?s)?(?:\s+mesh)?)\b")
_MARAS_RE = re.compile(r"(?i)\b(?:mara'?s?(?:\s+kaleidoscope)?)\b")
_HIGHLORD_RE = re.compile(r"(?i)\b(?:highlord'?s?(?:\s+wrath)?)\b")
_WAR_TRAV_RE = re.compile(r"(?i)\b(?:war\s*trav(?:eler)?s?|wt)\b")
_SOJ_RE = re.compile(r"(?i)\b(?:soj|stone\s+of\s+jordan)\b")
_OCULUS_RE = re.compile(r"(?i)\b(?:occ(?:y|ulus)|the\s+oculus)\b")
_SKULLDERS_RE = re.compile(r"(?i)\b(?:skull?ders?(?:'?s)?(?:\s+ire)?)\b")
_GHEEDS_RE = re.compile(r"(?i)\b(?:gheed'?s?(?:\s+fortune)?)\b")
_CHANCE_RE = re.compile(r"(?i)\b(?:chance\s*guards?|chancies?)\b")
_DRACULS_RE = re.compile(r"(?i)\b(?:dracul'?s?(?:\s+grasp)?|drac'?s?)\b")
_GORE_RE = re.compile(r"(?i)\b(?:gore\s*riders?|gores?)\b")
_GUILLAUMES_RE = re.compile(r"(?i)\b(?:guillaume'?s?(?:\s+face)?|gface|gull?y)\b")
_HOMUNCULUS_RE = re.compile(r"(?i)\b(?:homunculus)\b")
_RAVEN_RE = re.compile(r"(?i)\b(?:raven\s*frost|ravenfrost)\b")
_VERDUNGOS_RE = re.compile(r"(?i)\b(?:verdungo'?s?(?:\s+hearty\s+cord)?)\b")
_WIZSPIKE_RE = re.compile(r"(?i)\b(?:wizard\s*spike|wizzy|wizardspike)\b")
_MAGEFIST_RE = re.compile(r"(?i)\b(?:magefist|mage\s*fist)\b")
_NAGEL_RE = re.compile(r"(?i)\b(?:nagel(?:ring)?)\b")
_VIPERMAGI_RE = re.compile(r"(?i)\b(?:viper\s*magi|vmagi|skin\s+of\s+the\s+vipermagi)\b")
_TITANS_RE = re.compile(r"(?i)\b(?:titan'?s?(?:\s+revenge)?)\b")
_ANDARIELS_RE = re.compile(r"(?i)\b(?:andy'?s?(?:\s+visage)?|andariel'?s?(?:\s+visage)?)\b")
_REAPERS_RE = re.compile(r"(?i)\b(?:reaper'?s?\s+toll)\b")
_COA_RE = re.compile(r"(?i)\b(?:coa|crown\s+of\s+ages)\b")
_DFATHOM_RE = re.compile(r"(?i)\b(?:death'?s?\s+fathom|dfathom)\b")
_DWEB_RE = re.compile(r"(?i)\b(?:death'?s?\s+web|dweb)\b")
_TYRAELS_RE = re.compile(r"(?i)\b(?:tyrael'?s?(?:\s+might)?)\b")
_WISP_RE = re.compile(r"(?i)\b(?:wisp\s*projector)\b")
_METALGRID_RE = re.compile(r"(?i)\b(?:metalgrid)\b")
_ONDALS_RE = re.compile(r"(?i)\b(?:ondal'?s?(?:\s+wisdom)?)\b")
_ORMUS_RE = re.compile(r"(?i)\b(?:ormus'?(?:\s+robes?)?)\b")
_THUNDERSTROKE_RE = re.compile(r"(?i)\b(?:thunderstroke|t-?strokes?)\b")
_JALALS_RE = re.compile(r"(?i)\b(?:jalal'?s?(?:\s+mane)?)\b")
_KIRAS_RE = re.compile(r"(?i)\b(?:kira'?s?(?:\s+guardian)?)\b")
_LOH_RE = re.compile(r"(?i)\b(?:laying\s+of\s+hands|loh)\b")
_GOLDWRAP_RE = re.compile(r"(?i)\b(?:goldwrap)\b")
_DWARF_STAR_RE = re.compile(r"(?i)\b(?:dwarf\s*star)\b")
_BK_RING_RE = re.compile(r"(?i)\b(?:bk\s*(?:ring|wedding)|bul[- ]?kathos)\b")
_TGODS_RE = re.compile(r"(?i)\b(?:tgod'?s?|thundergod'?s?(?:\s+vigor)?)\b")
_STORMSHIELD_RE = re.compile(r"(?i)\b(?:stormshield|ss)\b")
_LIDLESS_RE = re.compile(r"(?i)\b(?:lidless(?:\s+wall)?)\b")
_STRING_OF_EARS_RE = re.compile(r"(?i)\b(?:string\s+of\s+ears|soe)\b")
_LEVIATHAN_RE = re.compile(r"(?i)\b(?:leviathan)\b")
_WINDFORCE_RE = re.compile(r"(?i)\b(?:windforce|wf)\b")
_GRANDFATHER_RE = re.compile(r"(?i)\b(?:grandfather|gf)\b")
_ESCHUTA_RE = re.compile(r"(?i)\b(?:eschuta'?s?(?:\s+temper)?)\b")
_RAVENLORE_RE = re.compile(r"(?i)\b(?:ravenlore)\b")
_SANDSTORM_RE = re.compile(r"(?i)\b(?:sandstorm\s*treks?|sandtreks?)\b")
_WATERWALK_RE = re.compile(r"(?i)\b(?:waterwalk)\b")
_NOSFERATU_RE = re.compile(r"(?i)\b(?:nosferatu'?s?(?:\s+coil)?)\b")
_ARREAT_RE = re.compile(r"(?i)\b(?:arreat'?s?(?:\s+face)?)\b")
_STEELREND_RE = re.compile(r"(?i)\b(?:steelrend)\b")

# Additional set items
_IK_ARMOR_RE = re.compile(r"(?i)\b(?:ik\s*armor|immortal\s+king'?s?\s+soul\s+cage)\b")
_IK_MAUL_RE = re.compile(r"(?i)\b(?:ik\s*maul|immortal\s+king'?s?\s+stone\s+crusher)\b")
_TRANG_ARMOR_RE = re.compile(r"(?i)\b(?:trang'?s?\s+armor|trang(?:oul)?'?s?\s+scales)\b")
_NATS_ARMOR_RE = re.compile(r"(?i)\b(?:nat'?s?\s+armor|natalya'?s?\s+shadow)\b")
_NATS_CLAW_RE = re.compile(r"(?i)\b(?:nat'?s?\s+claw|natalya'?s?\s+mark)\b")
_GRISWOLD_ARMOR_RE = re.compile(r"(?i)\b(?:gris(?:wold)?'?s?\s+armor|griswold'?s?\s+heart)\b")
_MAVINA_BOW_RE = re.compile(r"(?i)\b(?:mav(?:ina)?'?s?\s+bow|mavina'?s?\s+caster)\b")
_ALDUR_ARMOR_RE = re.compile(r"(?i)\b(?:aldur'?s?\s+armor|aldur'?s?\s+deception)\b")

# Skiller Grand Charms — class-specific +skill tree GCs
_SKILLER_CLASS_HINTS: list[tuple[re.Pattern[str], str]] = [
    # Sorceress trees
    (re.compile(r"(?i)\b(?:light(?:ning|ning)?\s*skill|light\s*gc|light\s*skiller)\b"), "lightning"),
    (re.compile(r"(?i)\b(?:cold\s*skill|cold\s*gc|cold\s*skiller|blizzard\s*gc)\b"), "cold"),
    (re.compile(r"(?i)\b(?:fire\s*skill|fire\s*gc|fire\s*skiller)\b"), "fire"),
    # Paladin trees
    (re.compile(r"(?i)\b(?:p(?:ala?(?:din)?|aly?)?\s*combat\s*skill|pcomb|p\s*comb)\b"), "paladin_combat"),
    (re.compile(r"(?i)\b(?:off(?:ensive)?\s*aura|off\s*aura)\b"), "offensive_aura"),
    (re.compile(r"(?i)\b(?:def(?:ensive)?\s*aura|def\s*aura)\b"), "defensive_aura"),
    # Necromancer trees
    (re.compile(r"(?i)\b(?:p(?:oison)?\s*(?:and|&|n)\s*b(?:one)?|pnb)\b"), "poison_and_bone"),
    (re.compile(r"(?i)\b(?:necro?\s*summon|summon\s*(?:necro?|gc|skiller))\b"), "necro_summoning"),
    (re.compile(r"(?i)\b(?:curses?\s*(?:gc|skiller))\b"), "curses"),
    # Amazon trees
    (re.compile(r"(?i)\b(?:java?\s*(?:skill|gc|skiller)|jav(?:elin)?\s+(?:and\s+)?spear)\b"), "javelin_and_spear"),
    (re.compile(r"(?i)\b(?:bow\s*(?:skill|gc|skiller)|bow\s+(?:and\s+)?crossbow)\b"), "bow_and_crossbow"),
    (re.compile(r"(?i)\b(?:passive\s*(?:skill|gc|skiller)|passive\s+(?:and\s+)?magic)\b"), "passive_and_magic"),
    # Barbarian trees
    (re.compile(r"(?i)\b(?:warcr(?:y|ies)\s*(?:gc|skiller)?|war\s*cry\s*(?:gc|skiller)?)\b"), "warcries"),
    (re.compile(r"(?i)\b(?:barb\s*combat|combat\s*(?:mastery|masteries))\b"), "combat_masteries"),
    # Druid trees
    (re.compile(r"(?i)\b(?:ele(?:mental)?\s*(?:gc|skiller)|elemental\s*skill)\b"), "elemental"),
    (re.compile(r"(?i)\b(?:shape\s*shift|shape\s*shifting)\b"), "shape_shifting"),
    (re.compile(r"(?i)\b(?:druid\s*summon)\b"), "druid_summoning"),
    # Assassin trees
    (re.compile(r"(?i)\b(?:trap(?:s|sin)?\s*(?:gc|skiller)?|chaos\s*(?:gc|skiller))\b"), "traps"),
    (re.compile(r"(?i)\b(?:ma\s*(?:gc|skiller)|martial\s*arts?\s*(?:gc|skiller)?)\b"), "martial_arts"),
    (re.compile(r"(?i)\b(?:shadow\s*(?:disc|discipline)?\s*(?:gc|skiller)?)\b"), "shadow_disciplines"),
    # Warlock (RotW) trees
    (re.compile(r"(?i)\b(?:eldritch\s*(?:gc|skiller))\b"), "eldritch"),
    (re.compile(r"(?i)\b(?:chaos\s*(?:magic)?\s*(?:gc|skiller))\b"), "chaos"),
]
_SKILLER_RE = re.compile(r"(?i)\b(?:skiller|skill\s*(?:gc|grand\s*charm))\b")

# Sunder Charms (D2R 2.5+)
_SUNDER_RE = re.compile(r"(?i)\b(?:sunder\s*(?:charm)?)\b")
_SUNDER_ELEMENT_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(?:cold|frozen|fathom)\b"), "cold"),
    (re.compile(r"(?i)\b(?:fire|flame|rift)\b"), "fire"),
    (re.compile(r"(?i)\b(?:light(?:ning)?|crack|heaven)\b"), "lightning"),
    (re.compile(r"(?i)\b(?:poison|venom|bane)\b"), "poison"),
    (re.compile(r"(?i)\b(?:magic|arcane)\b"), "magic"),
    (re.compile(r"(?i)\b(?:phys(?:ical)?|bone|break)\b"), "physical"),
]

# More uniques not yet covered
_VAMP_GAZE_RE = re.compile(r"(?i)\b(?:vamp(?:ire)?(?:'?s?)?\s*gaze)\b")
_SNOWCLASH_RE = re.compile(r"(?i)\b(?:snowclash)\b")
_ARKAINES_RE = re.compile(r"(?i)\b(?:arkaine'?s?\s+valor)\b")
_GUARDIAN_ANGEL_RE = re.compile(r"(?i)\b(?:guardian\s+angel)\b")
_SHAFTSTOP_RE = re.compile(r"(?i)\b(?:shaftstop)\b")
_DURIELS_RE = re.compile(r"(?i)\b(?:duriel'?s?\s+shell)\b")
_SKULDERS_ALT_RE = re.compile(r"(?i)\b(?:skullder'?s?\s+ire)\b")
_BURIZA_RE = re.compile(r"(?i)\b(?:buriza|buriza-do\s+kyanon)\b")
_FROSTBURN_RE = re.compile(r"(?i)\b(?:frostburn)\b")

_CTA_RE = re.compile(r"(?i)\b(?:cta|call\s+to\s+arms)\b")
_HOTO_RE = re.compile(r"(?i)\b(?:hoto|heart\s+of\s+the\s+oak)\b")
_BOTD_RE = re.compile(r"(?i)\b(?:e?botd(?:z)?|breath\s+of\s+the\s+dying)\b")
_ENIGMA_RE = re.compile(r"(?i)\benigma\b")
_ENIGMA_KIT_HINT_RE = re.compile(r"(?i)\b(?:unmade|unmaked?)\s+eni(?:gma)?\b|\beni(?:gma)?\s+kit\b")
_UNMADE_RW_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+eni(?:gma)?\b"), "enigma"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+hoto\b"), "heart_of_the_oak"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+cta\b"), "call_to_arms"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+inf(?:inity)?\b"), "infinity"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+grief\b"), "grief"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+insight\b"), "insight"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+spirit\b"), "spirit"),
    (re.compile(r"(?i)\b(?:unmade|unmaked?)\s+botd\b"), "breath_of_the_dying"),
]
_GRIEF_RE = re.compile(r"(?i)\bgrief\b")
_INFINITY_RW_RE = re.compile(r"(?i)\binfinity\b")
_SPIRIT_RW_RE = re.compile(r"(?i)\bspirit\b")
_INSIGHT_RW_RE = re.compile(r"(?i)\binsight\b")
_PGEM_RE = re.compile(r"(?i)\b(?:p(?:erfect)?\s*)?gems?\b|\bpgems?\b")
_PSKULL_RE = re.compile(r"(?i)\b(?:p(?:erfect)?\s*)?skulls?\b|\bpskulls?\b")
_JEWEL_FRAGMENT_RE = re.compile(r"(?i)\bjewel\s*fragments?\b|\bfrags?\b")
_WSS_RE = re.compile(r"(?i)\bworldstone\s*shards?\b|\bwss\b")
_PUZZLEBOX_RE = re.compile(r"(?i)\blarzuk(?:'s)?\s*puzzlebox\b|\bpuzzlebox\b")
_PUZZLEPIECE_RE = re.compile(r"(?i)\blarzuk(?:'s)?\s*puzzlepiece\b|\bpuzzlepiece\b")
_ORGSET_RE = re.compile(r"(?i)\borgan\s*sets?\b|\b(mephisto'?s brain|diablo'?s horn|baal'?s eye)\b")
_SPIRIT_SET_RE = re.compile(r"(?i)\bspirit\s*sets?\b")
_INSIGHT_SET_RE = re.compile(r"(?i)\binsight\s*sets?\b")
_MAP_REROLL_RE = re.compile(r"(?i)\bmap\s*reroll\s*runes?\b")
_COW_MAP_RE = re.compile(r"(?i)\bcow\s*maps?\b")
_CRAFTSET_CASTER_AMMY_RE = re.compile(r"(?i)\b(?:caster\s*amulets?|ral\s*\+\s*p(?:erfect)?\s*amethyst\s*\+\s*jewel)\b")
_CRAFTSET_CASTER_BOOTS_RE = re.compile(r"(?i)\b(?:caster\s*boots?|thul\s*\+\s*p(?:erfect)?\s*amethyst\s*\+\s*jewel)\b")
_CRAFTSET_BLOOD_RING_RE = re.compile(r"(?i)\b(?:blood\s*rings?|sol\s*\+\s*p(?:erfect)?\s*rub(?:y|ies)\s*\+\s*jewel)\b")
_CRAFTSET_BLOOD_GLOVES_RE = re.compile(r"(?i)\b(?:blood\s*gloves?|nef\s*\+\s*p(?:erfect)?\s*rub(?:y|ies)\s*\+\s*jewel)\b")

# Rune pack patterns: "low rune pack", "mid rune pack", "high rune pack", generic "rune pack"
_RUNE_PACK_TIER_RE = re.compile(r"(?i)\b(low|mid|high)\s+rune\s+packs?\b")
_RUNE_PACK_GENERIC_RE = re.compile(r"(?i)\brune\s+packs?\b")

# Quantity patterns: "x5", "5x", "x 5", "5 x" (before or after item names)
_QTY_RE = re.compile(r"(?i)\b(?:(\d{1,4})\s*x|x\s*(\d{1,4}))\b")

_TAL_AMMY_RE = re.compile(r"(?i)\b(?:ta(?:l|ls?)\s*a(?:my|mmy|m(?:u|my)|mulet)|adjudication)\b")
_TAL_BELT_RE = re.compile(r"(?i)\b(?:ta(?:l|ls?)\s*belt|fine[- ]spun cloth)\b")
_TAL_ARMOR_RE = re.compile(r"(?i)\b(?:ta(?:l|ls?)\s*armor|guardianship)\b")
_TAL_MASK_RE = re.compile(r"(?i)\b(?:ta(?:l|ls?)\s*mask|horadric crest)\b")
_TAL_ORB_RE = re.compile(r"(?i)\b(?:ta(?:l|ls?)\s*orb|lidless eye)\b")
_NAJ_ARMOR_RE = re.compile(r"(?i)\bnaj(?:'s)?\s*armor\b")
_BASE_RE = re.compile(
    r"(?i)\b(archon plate|mage plate|monarch|sacred targe|sacred rondache|phase blade|berserker axe|colossus voulge|thresher|giant thresher|cryptic axe|great poleaxe)\b"
)
_RUNEWORD_KIT_BASE_RE = re.compile(
    r"(?i)\b(archon plate|mage plate|dusk shroud|wire fleece|monarch|sacred targe|sacred rondache|phase blade|berserker axe|colossus voulge|thresher|giant thresher|cryptic axe|great poleaxe|flail|crystal sword|broad sword)\b"
)
_BASE_SHORTHAND_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bgt\b"), "giant thresher"),
    (re.compile(r"(?i)\bcv\b"), "colossus voulge"),
    (re.compile(r"(?i)\bgpa\b"), "great poleaxe"),
    (re.compile(r"(?i)\bca\b"), "cryptic axe"),
    (re.compile(r"(?i)\bpb\b"), "phase blade"),
    (re.compile(r"(?i)\bba\b"), "berserker axe"),
    (re.compile(r"(?i)\bap\b"), "archon plate"),
    (re.compile(r"(?i)\bmp\b"), "mage plate"),
    (re.compile(r"(?i)\bmon\b"), "monarch"),
]

# Top runeword recipes for "base + runes" kit detection in d2jsp listings.
_RUNEWORD_KIT_RECIPES: list[tuple[str, list[str]]] = [
    ("enigma", ["jah", "ith", "ber"]),
    ("heart_of_the_oak", ["ko", "vex", "pul", "thul"]),
    ("call_to_arms", ["amn", "ral", "mal", "ist", "ohm"]),
    ("infinity", ["ber", "mal", "ber", "ist"]),
    ("grief", ["eth", "tir", "lo", "mal", "ral"]),
    ("insight", ["ral", "tir", "tal", "sol"]),
    ("spirit", ["tal", "thul", "ort", "amn"]),
    ("breath_of_the_dying", ["vex", "hel", "el", "eld", "zod", "eth"]),
]


def _recipe_seq_re(runes: list[str]) -> re.Pattern[str]:
    # Accept separators or just spaces between rune names.
    sep = r"(?:\s*[+/,&]?\s*)"
    pat = r"(?i)\b" + sep.join(re.escape(r) for r in runes) + r"\b"
    return re.compile(pat)


_RUNEWORD_KIT_RECIPE_RES: list[tuple[str, re.Pattern[str]]] = [
    (rw, _recipe_seq_re(recipe)) for rw, recipe in _RUNEWORD_KIT_RECIPES
]


def _infer_runeword_kit_variant(text_norm: str) -> tuple[str, str] | None:
    """Detect listings that are a runeword kit (base + runes), not a finished runeword."""
    base_match = _RUNEWORD_KIT_BASE_RE.search(text_norm) or _BASE_RE.search(text_norm)
    if not base_match:
        return None
    base = base_match.group(1).lower().replace(" ", "_")

    # Explicit "unmade <rw>" shorthand with base present.
    for rx, rw in _UNMADE_RW_HINTS:
        if rx.search(text_norm):
            return (f"bundle:runeword_kit:{rw}", f"bundle:runeword_kit:{rw}:{base}")

    # Implicit kits by base + exact rune recipe sequence (common d2jsp shorthand).
    for rw, rx in _RUNEWORD_KIT_RECIPE_RES:
        if rx.search(text_norm):
            return (f"bundle:runeword_kit:{rw}", f"bundle:runeword_kit:{rw}:{base}")
    return None


def _norm_term(text: str) -> str:
    """Normalize a term for slang lookup (same as seed_slang_aliases.py)."""
    s = text.lower().replace("&amp;", "and").replace("'", "")
    s = re.sub(r"[^a-z0-9+]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_quantity(text: str) -> int | None:
    """Extract a quantity multiplier from text like 'x5', '5x', 'x 5', '5 x'.

    Returns the integer quantity if found, or None.
    """
    m = _QTY_RE.search(text)
    if m:
        raw = m.group(1) or m.group(2)
        qty = int(raw)
        if qty >= 1:
            return qty
    return None


def _normalize_bundle_variant(canonical: str, variant: str) -> str:
    """Produce a consistent variant key for bundles.

    Sorts rune lists alphabetically within ``bundle:runes`` variants and
    lowercases everything so that both market DB and overlay lookup
    resolve to the same key.

    >>> _normalize_bundle_variant("bundle:runes", "bundle:runes:gul+vex")
    'bundle:runes:gul+vex'
    >>> _normalize_bundle_variant("bundle:rune_pack", "bundle:rune_pack:low")
    'bundle:rune_pack:low'
    """
    variant = variant.lower().strip()
    # Sort rune names inside bundle:runes:X+Y+Z for deterministic keys
    if variant.startswith("bundle:runes:"):
        rune_part = variant[len("bundle:runes:"):]
        runes = sorted(rune_part.split("+"))
        variant = "bundle:runes:" + "+".join(runes)
    return variant


def load_slang_aliases(db_path: str) -> dict[str, list[dict]]:
    """Load enabled slang aliases from the database.
    
    Returns a dict mapping term_norm -> list of alias records.
    Each record contains: term_type, canonical_item_id, replacement_text, confidence.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        aliases: dict[str, list[dict]] = {}
        
        # Load slang aliases
        try:
            cur = conn.execute(
                """
                SELECT term_norm, term_type, canonical_item_id, replacement_text, confidence
                FROM slang_aliases
                WHERE enabled = 1
                ORDER BY confidence DESC, term_norm
                """
            )
            for row in cur:
                term = row["term_norm"]
                if term not in aliases:
                    aliases[term] = []
                aliases[term].append({
                    "term_type": row["term_type"],
                    "canonical_item_id": row["canonical_item_id"],
                    "replacement_text": row["replacement_text"],
                    "confidence": row["confidence"],
                })
        except sqlite3.OperationalError:
            pass

        # Load catalog aliases
        try:
            cur = conn.execute(
                """
                SELECT alias_norm, alias_type, canonical_item_id, priority
                FROM catalog_aliases
                """
            )
            for row in cur:
                term = row["alias_norm"]
                
                # Transform catalog alias into a slang-like alias
                term_type = "item_alias"
                if row["alias_type"] == "code":
                    term_type = "trade_term"
                    
                if term not in aliases:
                    aliases[term] = []
                
                aliases[term].append({
                    "term_type": term_type,
                    "canonical_item_id": row["canonical_item_id"],
                    "replacement_text": "", # catalog_aliases don't have replacement text, they map directly to canonical
                    "confidence": min(0.99, row["priority"] / 100.0),
                })
        except sqlite3.OperationalError:
            pass
            
        conn.close()
        return aliases
    except sqlite3.DatabaseError:
        return {}


def init_slang_cache(db_path: str) -> None:
    """Initialize the global slang cache from the database."""
    global _SLANG_CACHE
    _SLANG_CACHE = load_slang_aliases(db_path)


def apply_slang_normalization(text: str, db_path: str | None = None) -> str:
    """Apply slang alias normalization to text.
    
    Replaces known slang terms with their normalized replacements.
    Uses cached aliases if available, otherwise loads from db_path.
    
    Args:
        text: Input text to normalize
        db_path: Path to database (optional if cache already initialized)
        
    Returns:
        Normalized text with slang terms replaced
    """
    global _SLANG_CACHE
    
    # Initialize cache if needed
    if _SLANG_CACHE is None:
        if db_path is None:
            # No cache and no db_path - return text unchanged
            return text
        init_slang_cache(db_path)
    
    if not _SLANG_CACHE:
        # Empty cache - no aliases available
        return text
    
    # Apply replacements for base_alias and item_alias types
    result = text
    for term_norm, aliases in _SLANG_CACHE.items():
        for alias in aliases:
            # Only apply base_alias and item_alias types that have replacement_text
            if alias["term_type"] in ("base_alias", "item_alias") and alias["replacement_text"]:
                # Create a regex pattern that matches the term as a whole word
                pattern = re.compile(r"\b" + re.escape(term_norm) + r"\b", re.IGNORECASE)
                result = pattern.sub(alias["replacement_text"], result)
    
    return result


def _parse_fg_number(raw: str) -> float | None:
    s = raw.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def extract_fg_signals(text: str) -> list[tuple[str, float]]:
    low = text.lower()
    candidates: list[tuple[int, str, float, bool, tuple[int, int]]] = []

    for m in _PREFIX_PRICE_RE.finditer(text):
        kind = (m.group(1) or "").lower().replace("/", "")
        val = _parse_fg_number(m.group(2) or "")
        has_fg = bool(m.group(3))
        if val is None:
            continue
        if kind.startswith("offer") or kind.startswith("ask"):
            kind = "ask"
        if kind == "co":
            kind = "co"
        candidates.append((m.start(), kind, val, has_fg, m.span()))

    for m in _SUFFIX_PRICE_RE.finditer(text):
        kind = (m.group(3) or "").lower().replace("/", "")
        val = _parse_fg_number(m.group(1) or "")
        has_fg = True
        if val is None:
            continue
        if kind == "co":
            kind = "co"
        candidates.append((m.start(), kind, val, has_fg, m.span()))

    out: list[tuple[str, float]] = []
    seen: set[tuple[str, float, tuple[int, int]]] = set()
    for _pos, kind, val, has_fg, span in sorted(candidates, key=lambda x: x[0]):
        # Reject common quantity/placeholder patterns like "bin 1", "bin 1 lem", "bin 1 tal amu".
        if not has_fg and val < 20:
            continue
        # Reject "best offer 10 min." style non-price minimums.
        tail = low[span[1] : min(len(low), span[1] + 10)]
        if kind in {"ask", "co"} and "min" in tail:
            continue
        # Bare 5-digit offer/c/o values without `fg` are frequently junk/troll bids.
        # Keep explicit `fg` values; those are rarer and more intentional.
        if kind in {"ask", "co"} and not has_fg and val >= 10000:
            continue
        key = (kind, float(val), span)
        if key in seen:
            continue
        seen.add(key)
        out.append((kind, val))
    return out


def extract_title_fg_signals(title: str) -> list[tuple[str, float]]:
    """Title-specific extraction: explicit signals first, then plain `X fg` as weak ask.

    Forum titles often omit `bin` and just embed a number + `fg`. We treat those
    as weak ask signals, mainly for FT threads, while preserving explicit BIN/SOLD.
    """
    explicit = extract_fg_signals(title)
    if explicit:
        return explicit

    low = title.lower()
    # Avoid pricing service titles with incidental fg mentions.
    if _SERVICE_RE.search(low):
        return []

    out: list[tuple[str, float]] = []
    for m in _PLAIN_FG_RE.finditer(title):
        val = _parse_fg_number(m.group(1))
        if val is None:
            continue
        out.append(("ask", val))
    if out:
        return out

    # Conservative fallback: "naked" price in FT titles (e.g. "Gul 185", "Tal Amy - 300")
    # Only consider >=100 to avoid parsing common roll stats like "20 life", "35fcr", "4/4".
    if not _TRADE_FT_RE.search(low) and normalize_item_hint(title) is None:
        return []
    if _STAT_CONTEXT_RE.search(low):
        return []

    nums: list[float] = []
    for m in _PLAIN_NUM_PRICE_CANDIDATE_RE.finditer(title):
        raw = m.group(1)
        if not raw:
            continue
        try:
            n = float(raw)
        except ValueError:
            continue
        if n < 100 or n > 100000:
            continue
        nums.append(n)
    nums = list(dict.fromkeys(nums))
    if len(nums) == 1:
        return [("ask", nums[0])]
    return out


def extract_reply_price_only_signals(text: str) -> list[tuple[str, float]]:
    """Conservative parser for reply-only prices like `300`, `@ 250`, `bin 400`.

    Used only when topic title already gives a normalized item hint.
    """
    explicit = extract_fg_signals(text)
    if explicit:
        return explicit
    low = text.lower().strip()
    if not low or _STAT_CONTEXT_RE.search(low):
        return []
    m = _PRICE_ONLY_REPLY_RE.match(low)
    if not m:
        return []
    val = _parse_fg_number(m.group(1))
    has_fg = bool(m.group(2))
    if val is None or val < 20 or val > 100000:
        return []
    # Bare 5-digit reply numbers (without explicit `fg`) are often noise/troll bids
    # and can badly skew low-confidence fallback observations (e.g. `44444` on torch threads).
    # Explicit `44444 fg` is still handled earlier by `extract_fg_signals()`.
    if val >= 10000 and not has_fg:
        return []
    return [("co", val)]


def classify_thread_trade_type(title: str) -> str:
    low = (title or "").lower()
    if not low:
        return "unknown"
    if _SERVICE_RE.search(low):
        return "service"
    if _PC_RE.search(low):
        return "pc"
    if _ISO_RE.search(low):
        return "iso"
    if _TRADE_FT_RE.search(low):
        return "ft"
    return "unknown"


def normalize_item_hint(text: str) -> tuple[str, str] | None:
    """Normalize item hint from text, applying slang aliases first.
    
    This function now applies slang normalization before the existing
    pattern matching logic to reduce unresolved shorthand noise.
    """
    t = text.lower()
    
    # Apply slang normalization if cache is available
    # Note: db_path is not passed here to avoid coupling to storage layer
    # The cache should be initialized externally via init_slang_cache()
    if _SLANG_CACHE is not None:
        t = apply_slang_normalization(t)
    
    # After slang replacement, try full-text alias lookup
    if _SLANG_CACHE is not None:
        # Sort by length descending to match longest terms first (e.g. "spectral shard" before "shard")
        for term in sorted(_SLANG_CACHE.keys(), key=len, reverse=True):
            if re.search(r"\b" + re.escape(term) + r"\b", t):
                for alias in _SLANG_CACHE[term]:
                    if alias["canonical_item_id"]:
                        return (alias["canonical_item_id"], alias["canonical_item_id"])

    # Apply legacy base shorthand substitutions (kept for backward compatibility)
    for rx, repl in _BASE_SHORTHAND_SUBS:
        t = rx.sub(repl, t)

    # Set-item phrases before rune names ("Tal Amy", "Tal Armor", etc.).
    if _TAL_AMMY_RE.search(t):
        return ("set:tal_rashas_adjudication", "set:tal_rashas_adjudication")
    if _TAL_BELT_RE.search(t):
        return ("set:tal_rashas_fine-spun_cloth", "set:tal_rashas_fine-spun_cloth")
    if _TAL_ARMOR_RE.search(t):
        return ("set:tal_rashas_guardianship", "set:tal_rashas_guardianship")
    if _TAL_MASK_RE.search(t):
        return ("set:tal_rashas_horadric_crest", "set:tal_rashas_horadric_crest")
    if _TAL_ORB_RE.search(t):
        return ("set:tal_rashas_lidless_eye", "set:tal_rashas_lidless_eye")
    if _NAJ_ARMOR_RE.search(t):
        return ("set:najs_light_plate", "set:najs_light_plate")

    # Commodity/bulk/craft-set patterns before rune parsing to avoid false matches on "Ral + PAmethyst + Jewel".
    if _SPIRIT_SET_RE.search(t):
        return ("bundle:spirit_set", "bundle:spirit_set")
    if _INSIGHT_SET_RE.search(t):
        return ("bundle:insight_set", "bundle:insight_set")
    if _ORGSET_RE.search(t):
        return ("bundle:organ_set", "bundle:organ_set")
    if _CRAFTSET_CASTER_AMMY_RE.search(t):
        return ("bundle:craftset:caster_amulet", "bundle:craftset:caster_amulet")
    if _CRAFTSET_CASTER_BOOTS_RE.search(t):
        return ("bundle:craftset:caster_boots", "bundle:craftset:caster_boots")
    if _CRAFTSET_BLOOD_RING_RE.search(t):
        return ("bundle:craftset:blood_ring", "bundle:craftset:blood_ring")
    if _CRAFTSET_BLOOD_GLOVES_RE.search(t):
        return ("bundle:craftset:blood_gloves", "bundle:craftset:blood_gloves")
    # Rune pack tiers: "low rune pack", "mid rune pack", "high rune pack"
    if (m := _RUNE_PACK_TIER_RE.search(t)):
        tier = m.group(1).lower()
        return ("bundle:rune_pack", f"bundle:rune_pack:{tier}")
    if _RUNE_PACK_GENERIC_RE.search(t):
        return ("bundle:rune_pack", "bundle:rune_pack")

    if _MAP_REROLL_RE.search(t):
        return ("bundle:map_reroll_runes", "bundle:map_reroll_runes")
    if _COW_MAP_RE.search(t):
        return ("map:cow", "map:cow")
    if _PUZZLEBOX_RE.search(t):
        return ("consumable:larzuks_puzzlebox", "consumable:larzuks_puzzlebox")
    if _PUZZLEPIECE_RE.search(t):
        return ("consumable:larzuks_puzzlepiece", "consumable:larzuks_puzzlepiece")
    if _WSS_RE.search(t):
        return ("consumable:worldstone_shard", "consumable:worldstone_shard")
    if _JEWEL_FRAGMENT_RE.search(t):
        return ("consumable:jewel_fragments", "consumable:jewel_fragments")
    if _PSKULL_RE.search(t):
        return ("gem:perfect_skull", "gem:perfect_skull")
    if _PGEM_RE.search(t):
        return ("gem:perfect_gems_mixed", "gem:perfect_gems_mixed")
    if (kit := _infer_runeword_kit_variant(t)):
        return kit
    # "Unmade Eni MP" listings are kits (base + runes), not a finished Enigma or just a base.
    if _ENIGMA_KIT_HINT_RE.search(t):
        base_match = _BASE_RE.search(t)
        if base_match:
            base = base_match.group(1).lower().replace(" ", "_")
            return ("bundle:runeword_kit:enigma", f"bundle:runeword_kit:enigma:{base}")
        return ("bundle:runeword_kit:enigma", "bundle:runeword_kit:enigma")
    # Rune-word kits (base + required runes) should not be parsed as a single rune.
    # Example: "MP 15ed 15dura + Jah ith Ber bin 7700" = Enigma kit, not rune:jah.
    if _ENIGMA_RUNE_SEQ_RE.search(t) and not _ENIGMA_RE.search(t):
        base_match = _BASE_RE.search(t)
        if base_match:
            base = base_match.group(1).lower().replace(" ", "_")
            return ("bundle:runeword_kit:enigma", f"bundle:runeword_kit:enigma:{base}")
        return ("bundle:runes", "bundle:runes:ber+ith+jah")
    if _SPIRIT_RW_RE.search(t):
        return ("runeword:spirit", "runeword:spirit")
    if _INSIGHT_RW_RE.search(t):
        return ("runeword:insight", "runeword:insight")
    if _KEYSET_RE.search(t):
        return ("keyset:3x3", "keyset:3x3")
    if (m := _KEY_RE.search(t)):
        k = m.group(1).lower().replace("key of ", "").replace(" key", "")
        return (f"key:{k}", f"key:{k}")
    if _TOKEN_RE.search(t):
        return ("token:absolution", "token:absolution")
    if _ESS_RE.search(t):
        return ("essence:mixed", "essence:mixed")

    # Skiller Grand Charms — must be before torch/unique checks to avoid
    # "chaos skiller" matching as a runeword or "light skiller" as a rune.
    if _SKILLER_RE.search(t):
        for class_re, skill_tree in _SKILLER_CLASS_HINTS:
            if class_re.search(t):
                return ("charm:skiller", f"charm:skiller:{skill_tree}")
        return ("charm:skiller", "charm:skiller")

    # Sunder Charms (D2R 2.5+)
    if _SUNDER_RE.search(t):
        for elem_re, element in _SUNDER_ELEMENT_HINTS:
            if elem_re.search(t):
                return ("charm:sunder", f"charm:sunder:{element}")
        return ("charm:sunder", "charm:sunder")

    if _TORCH_RE.search(t):
        for class_re, torch_class in _TORCH_CLASS_HINTS:
            if class_re.search(t):
                return ("unique:hellfire_torch", f"unique:hellfire_torch:{torch_class}")
        return ("unique:hellfire_torch", "unique:hellfire_torch")
    if _ANNI_RE.search(t):
        return ("unique:annihilus", "unique:annihilus")
    if _FACET_RE.search(t):
        return ("jewel:rainbow_facet", "jewel:rainbow_facet")
    if _SHAKO_RE.search(t):
        return ("unique:harlequin_crest", "unique:harlequin_crest")
    if _GRIFFON_RE.search(t):
        return ("unique:griffons_eye", "unique:griffons_eye")
    if _HOZ_RE.search(t):
        return ("unique:herald_of_zakarum", "unique:herald_of_zakarum")
    if _NIGHTWING_RE.search(t):
        return ("unique:nightwings_veil", "unique:nightwings_veil")

    # --- Additional unique items ---
    if _ARACH_RE.search(t):
        return ("unique:arachnid_mesh", "unique:arachnid_mesh")
    if _MARAS_RE.search(t):
        return ("unique:maras_kaleidoscope", "unique:maras_kaleidoscope")
    if _HIGHLORD_RE.search(t):
        return ("unique:highlords_wrath", "unique:highlords_wrath")
    if _WAR_TRAV_RE.search(t):
        return ("unique:war_traveler", "unique:war_traveler")
    if _SOJ_RE.search(t):
        return ("unique:stone_of_jordan", "unique:stone_of_jordan")
    if _OCULUS_RE.search(t):
        return ("unique:the_oculus", "unique:the_oculus")
    if _SKULLDERS_RE.search(t):
        return ("unique:skulders_ire", "unique:skulders_ire")
    if _GHEEDS_RE.search(t):
        return ("unique:gheeds_fortune", "unique:gheeds_fortune")
    if _CHANCE_RE.search(t):
        return ("unique:chance_guards", "unique:chance_guards")
    if _DRACULS_RE.search(t):
        return ("unique:draculs_grasp", "unique:draculs_grasp")
    if _GORE_RE.search(t):
        return ("unique:gore_rider", "unique:gore_rider")
    if _GUILLAUMES_RE.search(t):
        return ("unique:guillaumes_face", "unique:guillaumes_face")
    if _HOMUNCULUS_RE.search(t):
        return ("unique:homunculus", "unique:homunculus")
    if _RAVEN_RE.search(t):
        return ("unique:raven_frost", "unique:raven_frost")
    if _VERDUNGOS_RE.search(t):
        return ("unique:verdungos_hearty_cord", "unique:verdungos_hearty_cord")
    if _WIZSPIKE_RE.search(t):
        return ("unique:wizardspike", "unique:wizardspike")
    if _MAGEFIST_RE.search(t):
        return ("unique:magefist", "unique:magefist")
    if _NAGEL_RE.search(t):
        return ("unique:nagelring", "unique:nagelring")
    if _VIPERMAGI_RE.search(t):
        return ("unique:skin_of_the_vipermagi", "unique:skin_of_the_vipermagi")
    if _TITANS_RE.search(t):
        return ("unique:titans_revenge", "unique:titans_revenge")
    if _ANDARIELS_RE.search(t):
        return ("unique:andariels_visage", "unique:andariels_visage")
    if _REAPERS_RE.search(t):
        return ("unique:reapers_toll", "unique:reapers_toll")
    if _COA_RE.search(t):
        return ("unique:crown_of_ages", "unique:crown_of_ages")
    if _DFATHOM_RE.search(t):
        return ("unique:deaths_fathom", "unique:deaths_fathom")
    if _DWEB_RE.search(t):
        return ("unique:deaths_web", "unique:deaths_web")
    if _TYRAELS_RE.search(t):
        return ("unique:tyraels_might", "unique:tyraels_might")
    if _WISP_RE.search(t):
        return ("unique:wisp_projector", "unique:wisp_projector")
    if _METALGRID_RE.search(t):
        return ("unique:metalgrid", "unique:metalgrid")
    if _ONDALS_RE.search(t):
        return ("unique:ondals_wisdom", "unique:ondals_wisdom")
    if _ORMUS_RE.search(t):
        return ("unique:ormus_robes", "unique:ormus_robes")
    if _THUNDERSTROKE_RE.search(t):
        return ("unique:thunderstroke", "unique:thunderstroke")
    if _JALALS_RE.search(t):
        return ("unique:jalals_mane", "unique:jalals_mane")
    if _KIRAS_RE.search(t):
        return ("unique:kiras_guardian", "unique:kiras_guardian")
    if _LOH_RE.search(t):
        return ("unique:laying_of_hands", "unique:laying_of_hands")
    if _GOLDWRAP_RE.search(t):
        return ("unique:goldwrap", "unique:goldwrap")
    if _DWARF_STAR_RE.search(t):
        return ("unique:dwarf_star", "unique:dwarf_star")
    if _BK_RING_RE.search(t):
        return ("unique:bul_kathos_wedding_band", "unique:bul_kathos_wedding_band")
    if _TGODS_RE.search(t):
        return ("unique:thundergods_vigor", "unique:thundergods_vigor")
    if _STORMSHIELD_RE.search(t):
        return ("unique:stormshield", "unique:stormshield")
    if _LIDLESS_RE.search(t):
        return ("unique:lidless_wall", "unique:lidless_wall")
    if _STRING_OF_EARS_RE.search(t):
        return ("unique:string_of_ears", "unique:string_of_ears")
    if _LEVIATHAN_RE.search(t):
        return ("unique:leviathan", "unique:leviathan")
    if _WINDFORCE_RE.search(t):
        return ("unique:windforce", "unique:windforce")
    if _GRANDFATHER_RE.search(t):
        return ("unique:the_grandfather", "unique:the_grandfather")
    if _ESCHUTA_RE.search(t):
        return ("unique:eschutas_temper", "unique:eschutas_temper")
    if _RAVENLORE_RE.search(t):
        return ("unique:ravenlore", "unique:ravenlore")
    if _SANDSTORM_RE.search(t):
        return ("unique:sandstorm_trek", "unique:sandstorm_trek")
    if _WATERWALK_RE.search(t):
        return ("unique:waterwalk", "unique:waterwalk")
    if _NOSFERATU_RE.search(t):
        return ("unique:nosferatus_coil", "unique:nosferatus_coil")
    if _ARREAT_RE.search(t):
        return ("unique:arreats_face", "unique:arreats_face")
    if _STEELREND_RE.search(t):
        return ("unique:steelrend", "unique:steelrend")
    if _VAMP_GAZE_RE.search(t):
        return ("unique:vampire_gaze", "unique:vampire_gaze")
    if _SNOWCLASH_RE.search(t):
        return ("unique:snowclash", "unique:snowclash")
    if _ARKAINES_RE.search(t):
        return ("unique:arkaines_valor", "unique:arkaines_valor")
    if _GUARDIAN_ANGEL_RE.search(t):
        return ("unique:guardian_angel", "unique:guardian_angel")
    if _SHAFTSTOP_RE.search(t):
        return ("unique:shaftstop", "unique:shaftstop")
    if _DURIELS_RE.search(t):
        return ("unique:duriels_shell", "unique:duriels_shell")
    if _BURIZA_RE.search(t):
        return ("unique:buriza_do_kyanon", "unique:buriza_do_kyanon")
    if _FROSTBURN_RE.search(t):
        return ("unique:frostburn", "unique:frostburn")

    # --- Additional set items ---
    if _IK_ARMOR_RE.search(t):
        return ("set:immortal_kings_soul_cage", "set:immortal_kings_soul_cage")
    if _IK_MAUL_RE.search(t):
        return ("set:immortal_kings_stone_crusher", "set:immortal_kings_stone_crusher")
    if _TRANG_ARMOR_RE.search(t):
        return ("set:trang_ouls_scales", "set:trang_ouls_scales")
    if _NATS_ARMOR_RE.search(t):
        return ("set:natalyas_shadow", "set:natalyas_shadow")
    if _NATS_CLAW_RE.search(t):
        return ("set:natalyas_mark", "set:natalyas_mark")
    if _GRISWOLD_ARMOR_RE.search(t):
        return ("set:griswolds_heart", "set:griswolds_heart")
    if _MAVINA_BOW_RE.search(t):
        return ("set:mavinas_caster", "set:mavinas_caster")
    if _ALDUR_ARMOR_RE.search(t):
        return ("set:aldurs_deception", "set:aldurs_deception")

    if _CTA_RE.search(t):
        return ("runeword:call_to_arms", "runeword:call_to_arms")
    if _HOTO_RE.search(t):
        return ("runeword:heart_of_the_oak", "runeword:heart_of_the_oak")
    if _BOTD_RE.search(t):
        base_hint = None
        if re.search(r"(?i)\b(?:ebotdz|zerker|berserker axe|ba)\b", t):
            base_hint = "berserker_axe"
        elif re.search(r"(?i)\b(?:phase blade|pb)\b", t):
            base_hint = "phase_blade"
        variant = "runeword:breath_of_the_dying"
        if base_hint:
            variant += f":{base_hint}"
        return ("runeword:breath_of_the_dying", variant)
    if _ENIGMA_RE.search(t):
        return ("runeword:enigma", "runeword:enigma")
    if _GRIEF_RE.search(t):
        return ("runeword:grief", "runeword:grief")
    if _INFINITY_RW_RE.search(t):
        return ("runeword:infinity", "runeword:infinity")

    # Multi-rune bundles like "vex+gul", "jah/ber" should not contaminate single-rune prices.
    if (m := _RUNE_BUNDLE_RE.search(t)):
        bundle_part = m.group(0)
        runes = [x.lower() for x in _RUNE_RE.findall(bundle_part)]
        if len(runes) >= 2:
            return ("bundle:runes", "bundle:runes:" + "+".join(runes))
    if (m := _RUNE_SEQ_SPACED_RE.search(t)):
        rune_part = m.group(0)
        runes = [x.lower() for x in _RUNE_RE.findall(rune_part)]
        if len(runes) >= 2:
            return ("bundle:runes", "bundle:runes:" + "+".join(sorted(set(runes))))

    if (m := _RUNE_RE.search(t)):
        rune = m.group(1).lower()
        return (f"rune:{rune}", f"rune:{rune}")
    if (m := _BASE_RE.search(t)):
        base = m.group(1).lower().replace(" ", "_")
        eth = "eth" if " eth" in f" {t} " or t.startswith("eth ") else "noneth"
        sockets_match = re.search(r"(?i)\b([3456])\s*os\b|\b([3456])\s*soc(?:ket)?s?\b", t)
        sockets = None
        if sockets_match:
            sockets = next(g for g in sockets_match.groups() if g)
        variant = f"base:{base}:{eth}"
        if sockets:
            variant += f":{sockets}os"
        return (f"base:{base}", variant)
    if (variant := infer_variant_from_noisy_ocr(text, text)):
        parts = variant.split(":")
        canonical = f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else variant
        return (canonical, variant)
    return None


def normalize_title_item(title: str) -> tuple[str, str] | None:
    return normalize_item_hint(title)


def _split_title_listing_segments(title: str) -> list[str]:
    """Split mixed-item topic titles conservatively.

    Only split on separators with surrounding whitespace to avoid breaking
    roll notation like `17/15/5`.
    """
    if not title:
        return []
    # Split on:
    # - slash/pipe with surrounding spaces (`foo / bar`, `foo | bar`)
    # - slash immediately before an alpha token (`650fg/thresher`)
    # while preserving roll notation like `17/15/5` and `4/5`.
    parts = [p.strip() for p in re.split(r"\s(?:/|\|)\s|/(?=[A-Za-z])", title) if p.strip()]
    if len(parts) <= 1:
        return [title.strip()]
    return parts


def _title_rows_from_text(
    *,
    title: str,
    market_key: str,
    forum_id: int,
    thread_id: int | None,
    source_url: str | None,
    observed_at: str | None,
    thread_trade_type: str | None = None,
    thread_category_id: int | None = None,
) -> list[dict]:
    """Extract title observations, supporting mixed-item slash-separated titles."""
    rows: list[dict] = []
    segments = _split_title_listing_segments(title)
    used_segment_mode = False
    if len(segments) > 1:
        seg_rows: list[dict] = []
        seg_variants: set[str] = set()
        for seg in segments:
            item = normalize_title_item(seg)
            if not item:
                continue
            signals = extract_title_fg_signals(seg)
            if not signals:
                continue
            used_segment_mode = True
            canonical_item_id, variant_key = item
            seg_variants.add(variant_key)
            for signal_kind, value in signals:
                conf = 0.85 if signal_kind in {"bin", "sold"} else 0.25
                seg_rows.append(
                    {
                        "source": "d2jsp",
                        "market_key": market_key,
                        "forum_id": forum_id,
                        "thread_id": thread_id,
                        "post_id": None,
                        "source_kind": "title",
                        "signal_kind": signal_kind,
                        "thread_category_id": thread_category_id,
                        "thread_trade_type": thread_trade_type or "unknown",
                        "canonical_item_id": canonical_item_id,
                        "variant_key": variant_key,
                        "price_fg": value,
                        "confidence": conf,
                        "observed_at": observed_at,
                        "source_url": source_url,
                        "raw_excerpt": seg[:300],
                    }
                )
        # Only trust segment mode if it actually separated multiple items.
        if len(seg_variants) >= 2 and seg_rows:
            return seg_rows

    # Fallback to legacy whole-title behavior.
    item = normalize_title_item(title)
    if not item:
        return []
    signals = extract_title_fg_signals(title)
    if not signals:
        return []
    canonical_item_id, variant_key = item
    for signal_kind, value in signals:
        conf = 0.85 if signal_kind in {"bin", "sold"} else 0.25
        rows.append(
            {
                "source": "d2jsp",
                "market_key": market_key,
                "forum_id": forum_id,
                "thread_id": thread_id,
                "post_id": None,
                "source_kind": "title",
                "signal_kind": signal_kind,
                "thread_category_id": thread_category_id,
                "thread_trade_type": thread_trade_type or "unknown",
                "canonical_item_id": canonical_item_id,
                "variant_key": variant_key,
                "price_fg": value,
                "confidence": conf,
                "observed_at": observed_at,
                "source_url": source_url,
                "raw_excerpt": title[:300],
            }
        )
    return rows


def observations_from_thread_row(thread: dict, market_key: str) -> list[dict]:
    title = thread["title"]
    trade_type = thread.get("thread_trade_type") or classify_thread_trade_type(title)
    return _title_rows_from_text(
        title=title,
        market_key=market_key,
        forum_id=thread["forum_id"],
        thread_id=thread["thread_id"],
        source_url=thread["url"],
        observed_at=thread.get("created_at"),
        thread_trade_type=trade_type,
        thread_category_id=thread.get("thread_category_id"),
    )


def observations_from_text(
    *,
    text: str,
    market_key: str,
    forum_id: int,
    thread_id: int | None,
    post_id: int | None,
    source_kind: str,
    source_url: str | None,
    observed_at: str | None,
    thread_category_id: int | None = None,
    thread_trade_type: str | None = None,
) -> list[dict]:
    item = normalize_item_hint(text)
    if not item:
        return []
    signals = extract_fg_signals(text)
    if not signals:
        return []

    canonical_item_id, variant_key = item
    rows: list[dict] = []
    tt = thread_trade_type or "unknown"
    for signal_kind, value in signals:
        conf = 0.9 if signal_kind == "sold" else 0.8 if signal_kind == "bin" else 0.35
        rows.append(
            {
                "source": "d2jsp",
                "market_key": market_key,
                "forum_id": forum_id,
                "thread_id": thread_id,
                "post_id": post_id,
                "source_kind": source_kind,
                "signal_kind": signal_kind,
                "thread_category_id": thread_category_id,
                "thread_trade_type": tt,
                "canonical_item_id": canonical_item_id,
                "variant_key": variant_key,
                "price_fg": value,
                "confidence": conf,
                "observed_at": observed_at,
                "source_url": source_url,
                "raw_excerpt": text[:300],
            }
        )
    return rows


@dataclass(slots=True)
class ForumThreadRow:
    forum_id: int
    thread_id: int
    url: str
    title: str
    reply_count: int | None = None


class D2JspForumHTMLParser(HTMLParser):
    """Parses thread links from a saved d2jsp forum page HTML snapshot.

    This parser is intentionally conservative and only extracts thread IDs/titles
    from anchor hrefs like `topic.php?t=<id>`.
    """

    def __init__(self, forum_id: int) -> None:
        super().__init__(convert_charrefs=True)
        self.forum_id = forum_id
        self._current_topic_href: str | None = None
        self._current_topic_tid: int | None = None
        self._capture_text = False
        self._text_parts: list[str] = []
        self.rows: list[ForumThreadRow] = []
        self._seen_tids: set[int] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href") or ""
        title_attr = (attr_map.get("title") or "").strip().lower()
        if "goto last post" in title_attr or re.search(r"(?:^|[?&])v=1\b", href):
            return
        m = re.search(r"(?:^|[?&])t=(\d+)\b", href)
        if not m or "topic.php" not in href:
            return
        tid = int(m.group(1))
        if tid in self._seen_tids:
            return
        self._current_topic_tid = tid
        self._current_topic_href = urljoin(D2JSP_BASE, href.lstrip("/"))
        self._capture_text = True
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_text:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._capture_text:
            return
        title = html.unescape(" ".join(p.strip() for p in self._text_parts)).strip()
        if title and self._current_topic_tid and self._current_topic_href:
            self.rows.append(
                ForumThreadRow(
                    forum_id=self.forum_id,
                    thread_id=self._current_topic_tid,
                    url=self._current_topic_href,
                    title=title,
                )
            )
            self._seen_tids.add(self._current_topic_tid)
        self._capture_text = False
        self._current_topic_tid = None
        self._current_topic_href = None
        self._text_parts = []


def parse_forum_threads_from_html(html_text: str, forum_id: int) -> list[dict]:
    rows: list[dict] = []
    seen_tids: set[int] = set()

    # Prefer row-based parsing because we need reply counts (`<div class="b1">N</div>`).
    for mrow in re.finditer(r"(?is)<tr\b[^>]*>(.*?)</tr>", html_text):
        row_html = mrow.group(1)
        reply_m = re.search(r'(?is)<div\b[^>]*class="[^"]*\bb1\b[^"]*"[^>]*>\s*(\d+)\s*</div>', row_html)
        if not reply_m:
            continue
        reply_count = int(reply_m.group(1))

        anchors = re.findall(r'(?is)<a\b([^>]*)href="([^"]*topic\.php[^"]*)\"([^>]*)>(.*?)</a>', row_html)
        topic_href = None
        topic_tid = None
        topic_title = None
        topic_category_id = None
        for _pre, href, _post, inner in anchors:
            if re.search(r"(?:^|[?&])v=1\b", href):
                continue
            tid_m = re.search(r"(?:^|[?&])t=(\d+)\b", href)
            if not tid_m:
                continue
            text = re.sub(r"(?is)<[^>]+>", "", inner)
            text = html.unescape(re.sub(r"\s+", " ", text)).strip()
            if not text or text == "»":
                continue
            topic_tid = int(tid_m.group(1))
            topic_href = urljoin(D2JSP_BASE, href.lstrip("/"))
            topic_title = text
            # Extract category from URL if present (e.g., c=2, c=3, etc.)
            cat_m = re.search(r"(?:^|[?&])c=(\d+)(?:&|$)", href)
            if cat_m:
                try:
                    topic_category_id = int(cat_m.group(1))
                except ValueError:
                    pass
            break

        if not topic_tid or not topic_href or not topic_title or topic_tid in seen_tids:
            continue
        seen_tids.add(topic_tid)
        row_data = {
            "source": "d2jsp",
            "forum_id": forum_id,
            "thread_id": topic_tid,
            "url": topic_href,
            "title": topic_title,
            "thread_trade_type": classify_thread_trade_type(topic_title),
            "reply_count": reply_count,
        }
        if topic_category_id is not None:
            row_data["thread_category_id"] = topic_category_id
        rows.append(row_data)

    if rows:
        return rows

    # Fallback: anchor-only parser (older fixtures / unexpected markup)
    parser = D2JspForumHTMLParser(forum_id=forum_id)
    parser.feed(html_text)
    for r in parser.rows:
        row_data = {
            "source": "d2jsp",
            "forum_id": r.forum_id,
            "thread_id": r.thread_id,
            "url": r.url,
            "title": r.title,
            "thread_trade_type": classify_thread_trade_type(r.title),
            "reply_count": r.reply_count,
        }
        # Extract category from URL if present
        cat_m = re.search(r"(?:^|[?&])c=(\d+)(?:&|$)", r.url)
        if cat_m:
            try:
                row_data["thread_category_id"] = int(cat_m.group(1))
            except ValueError:
                pass
        rows.append(row_data)
    return rows


def parse_observations_from_threads(threads: Iterable[dict], market_key: str) -> list[dict]:
    out: list[dict] = []
    for th in threads:
        out.extend(observations_from_thread_row(th, market_key=market_key))
    return out


class _TextBlockHTMLParser(HTMLParser):
    """Generic HTML text extractor preserving rough line breaks."""

    BLOCK_TAGS = {
        "p",
        "div",
        "tr",
        "li",
        "br",
        "h1",
        "h2",
        "h3",
        "td",
        "blockquote",
        "span",
    }
    SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self._buf.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self._buf.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data.strip():
            self._buf.append(data)

    def text(self) -> str:
        raw = "".join(self._buf)
        raw = raw.replace("\xa0", " ")
        raw = re.sub(r"\r", "", raw)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def extract_html_text(html_text: str) -> str:
    p = _TextBlockHTMLParser()
    p.feed(html_text)
    return p.text()


def is_bump_only_text(text: str) -> bool:
    """Heuristic: topic body contains only bumps/ups and no meaningful trade content."""
    lines = [re.sub(r"\s+", " ", ln.strip().lower()) for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return True

    trivial = {
        "up",
        "upp",
        "up!",
        "bump",
        "bump!",
        "bumpp",
        "still ft",
        "still iso",
        "update",
    }
    meaningful = 0
    for ln in lines:
        if ln in trivial:
            continue
        if re.fullmatch(r"[\^.\-~ ]{1,12}", ln):
            continue
        if re.fullmatch(r"(up|bump)[!.\s\d]*", ln):
            continue
        # Lines with item/price-like tokens are meaningful.
        if _PRICE_RE.search(ln) or _PLAIN_FG_RE.search(ln) or _RUNE_RE.search(ln):
            meaningful += 1
            continue
        if any(tok in ln for tok in ("torch", "anni", "ring", "amulet", "charm", "facet", "key", "rune", "offer", "bin", "sold")):
            meaningful += 1
            continue
    return meaningful == 0


def parse_topic_meta_from_html(html_text: str) -> dict:
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
    title = ""
    if title_match:
        title = html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip()

    thread_id = None
    for m in re.finditer(r"topic\.php\?(?:[^\"'>]*&)?t=(\d+)", html_text):
        thread_id = int(m.group(1))
        break

    post_ids = [int(x) for x in re.findall(r"(?:id=[\"']p?(\d+)[\"']|(?:^|[?&])p=(\d+)\b)", html_text) for x in (x if isinstance(x, tuple) else (x,)) if x]
    # The regex above can return tuples because of alternation groups; flatten robustly.
    flat_post_ids: list[int] = []
    for x in re.findall(r"id=[\"']p?(\d+)[\"']", html_text):
        try:
            flat_post_ids.append(int(x))
        except ValueError:
            pass
    for x in re.findall(r"(?:^|[?&])p=(\d+)\b", html_text):
        try:
            flat_post_ids.append(int(x))
        except ValueError:
            pass

    return {
        "thread_id": thread_id,
        "title": title,
        "post_ids": sorted(set(flat_post_ids)),
    }


def parse_observations_from_topic_html(
    html_text: str,
    *,
    forum_id: int,
    market_key: str,
    source_url: str | None = None,
    observed_at: str | None = None,
) -> tuple[dict, list[dict], list[dict]]:
    """Return (thread_row, post_rows, observed_price_rows) from topic HTML.

    `post_rows` is currently coarse: one synthetic row carrying extracted topic text.
    This is enough for MVP pricing and can be replaced later with precise post parsing.
    """
    meta = parse_topic_meta_from_html(html_text)
    text = extract_html_text(html_text)
    thread_id = meta.get("thread_id")

    thread_row = {
        "source": "d2jsp",
        "forum_id": forum_id,
        "thread_id": int(thread_id) if thread_id is not None else -1,
        "url": source_url or (f"{D2JSP_BASE}topic.php?t={thread_id}" if thread_id else ""),
        "title": meta.get("title") or "topic",
        "thread_trade_type": classify_thread_trade_type(meta.get("title") or ""),
        "author": None,
        "created_at": observed_at,
    }

    post_rows = [
        {
            "source": "d2jsp",
            "thread_id": int(thread_id) if thread_id is not None else -1,
            "post_id": None,
            "author": None,
            "posted_at": observed_at,
            "body_text": text[:200000],
        }
    ]

    obs_rows: list[dict] = []
    obs_rows.extend(
        _title_rows_from_text(
            title=thread_row["title"],
            market_key=market_key,
            forum_id=forum_id,
            thread_id=thread_row["thread_id"] if thread_row["thread_id"] > 0 else None,
            source_url=thread_row["url"],
            observed_at=observed_at,
            thread_trade_type=thread_row.get("thread_trade_type"),
            thread_category_id=thread_row.get("thread_category_id"),
        )
    )
    title_item = normalize_item_hint(thread_row["title"])
    # Split by lines to avoid mixing multiple items/prices in one huge topic body.
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        line_obs = observations_from_text(
            text=line,
            market_key=market_key,
            forum_id=forum_id,
            thread_id=thread_row["thread_id"] if thread_row["thread_id"] > 0 else None,
            post_id=None,
            source_kind="post",
            source_url=thread_row["url"],
            observed_at=observed_at,
            thread_trade_type=thread_row.get("thread_trade_type"),
        )
        obs_rows.extend(line_obs)
        if line_obs or not title_item:
            continue
        # Fallback for common d2jsp replies that only contain a price/c/o.
        for signal_kind, value in extract_reply_price_only_signals(line):
            canonical_item_id, variant_key = title_item
            obs_rows.append(
                {
                    "source": "d2jsp",
                    "market_key": market_key,
                    "forum_id": forum_id,
                    "thread_id": thread_row["thread_id"] if thread_row["thread_id"] > 0 else None,
                    "post_id": None,
                    "source_kind": "post",
                    "signal_kind": signal_kind,
                    "thread_trade_type": thread_row.get("thread_trade_type") or "unknown",
                    "canonical_item_id": canonical_item_id,
                    "variant_key": variant_key,
                    "price_fg": value,
                    "confidence": 0.2,
                    "observed_at": observed_at,
                    "source_url": thread_row["url"],
                    "raw_excerpt": line[:300],
                }
            )

    # De-duplicate identical observations extracted from repeated UI fragments.
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for row in obs_rows:
        key = (
            row["source_kind"],
            row["signal_kind"],
            row["variant_key"],
            round(float(row["price_fg"]), 4),
            row.get("raw_excerpt", "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return thread_row, post_rows, deduped
