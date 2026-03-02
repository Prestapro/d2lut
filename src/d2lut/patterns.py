"""Shared patterns and constants for price extraction.

This module contains all regex patterns and constants used by both
the forum parser and the live collector, ensuring DRY compliance.
"""

from __future__ import annotations

import re
from typing import Final

# =============================================================================
# Signal Types and Confidence
# =============================================================================

# Signal kinds for price observations
SIGNAL_SOLD: Final = "sold"
SIGNAL_BIN: Final = "bin"
SIGNAL_ASK: Final = "ask"
SIGNAL_CO: Final = "co"

# Confidence levels for each signal type
SIGNAL_CONFIDENCE: Final[dict[str, float]] = {
    SIGNAL_SOLD: 0.9,  # Completed transaction - highest confidence
    SIGNAL_BIN: 0.8,   # Buy-it-now price
    SIGNAL_ASK: 0.7,   # Asking price
    SIGNAL_CO: 0.6,    # Current offer
    "fg": 0.7,         # Generic FG mention
}


def get_signal_confidence(signal_kind: str) -> float:
    """Get confidence level for a signal kind.

    Args:
        signal_kind: The type of price signal

    Returns:
        Confidence score (0.0-1.0)
    """
    return SIGNAL_CONFIDENCE.get(signal_kind, 0.5)


# =============================================================================
# Price Patterns
# =============================================================================

# Price patterns with associated signal kinds
# Each tuple: (pattern, signal_kind)
PRICE_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (re.compile(r"sold\s*:?\s*(\d+)", re.I), SIGNAL_SOLD),
    (re.compile(r"bin\s*:?\s*(\d+)", re.I), SIGNAL_BIN),
    (re.compile(r"co\s*:?\s*(\d+)", re.I), SIGNAL_CO),
    (re.compile(r"ask(?:ing)?\s*:?\s*(\d+)", re.I), SIGNAL_ASK),
    (re.compile(r"(\d+(?:\.\d+)?)\s*fg\b", re.I), "fg"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*forum\s*gold\b", re.I), "fg"),
]


# =============================================================================
# Item Identification Patterns
# =============================================================================

# Item patterns for identification
# Keys are variant_key (e.g., "rune:jah", "unique:shako")
# Values are compiled regex patterns
_ITEM_PATTERN_DEFS: Final[dict[str, str]] = {
    # High runes
    "rune:jah": r"\bjah\b",
    "rune:ber": r"\bber\b",
    "rune:zod": r"\bzod\b",
    "rune:cham": r"\bcham\b",
    "rune:sur": r"\bsur\b",
    "rune:lo": r"\blo\s*(?:rune)?\b",
    "rune:ohm": r"\bohm\b",
    "rune:vex": r"\bvex\b",
    "rune:gul": r"\bgul\b",
    "rune:ist": r"\bist\b",
    "rune:mal": r"\bmal\s*(?:rune)?\b",
    "rune:um": r"\bum\s*(?:rune)?\b",
    "rune:ko": r"\bko\s*(?:rune)?\b",
    "rune:lem": r"\blem\b",
    "rune:pul": r"\bpul\b",
    "rune:hel": r"\bhel\b",

    # Uniques - Helms
    "unique:shako": r"\bshako\b|\bharlequin\s*crest\b",
    "unique:griffon": r"\bgriffon'?s?\s*eye\b|\bgriffon\b",
    "unique:nightraider": r"\bnightraider\b",
    "unique:andariel": r"\bandariel'?s?\s*visage\b|\bandy'?s?\b",
    "unique:giantthresh": r"\bgiant\s*thresh\b",
    "unique:crownofages": r"\bcrown\s*of\s*ages\b|\bcoa\b",
    "unique:kira": r"\bkira'?s?\s*guardian\b|\bkira\b",
    "unique:rockstopper": r"\brockstopper\b",
    "unique:stealskull": r"\bstealskull\b",

    # Uniques - Armor
    "unique:tyraels": r"\btyrael'?s?\s*might\b",
    "unique:arkaine": r"\barkaine'?s?\s*valor\b|\barkaine\b",
    "unique:skullder": r"\bskullder'?s?\s*ire\b|\bskullder\b",
    "unique:shaftstop": r"\bshaftstop\b",
    "unique:guardianangel": r"\bguardian\s*angel\b",
    "unique:duriel": r"\bduriel'?s?\s*shell\b",
    "unique:gladiator": r"\bgladiator'?s?\s*bane\b",
    "unique:corpsemourn": r"\bcorpsemourn\b",
    "unique:ironpelt": r"\biron\s*pelt\b",
    "unique:skinofvipermagi": r"\bskin\s*of\s*(?:the\s*)?viper\s*magi\b|\bviper\b|\bskin\b",
    "unique:que-hagan": r"\bque-hagan'?s?\s*wisdom\b|\bque\s*hagan\b",
    "unique:spiralhauberk": r"\bspiral\s*hauberk\b",
    "unique:blackhadeforge": r"\bblack\s*hade\s*forge\b",
    "unique:heavensbreach": r"\bheaven'?s?\s*breach\b",

    # Uniques - Belts
    "unique:arachnid": r"\barachnid\s*mesh\b|\barachnid\b|\bspider\s*web\s*belt\b",
    "unique:tgods": r"\bthundergod'?s?\s*vigor\b|\btgods?\b|\bthundergod\b",
    "unique:verdungo": r"\bverdungo'?s?\s*hearty\s*cord\b|\bverdungo\b|\bdungo\b",
    "unique:razortail": r"\brazortail\b",
    "unique:snowclash": r"\bsnowclash\b",
    "unique:stringofears": r"\bstring\s*of\s*ears\b|\bsoe\b",
    "unique:nosferatu": r"\bnosferatu'?s?\s*coil\b|\bnosferatu\b",

    # Uniques - Boots
    "unique:wartraveler": r"\bwar\s*traveler\b|\bwt\b|\bwartrav\b",
    "unique:sandstorm": r"\bsandstorm\s*trek\b|\bsandstorm\b|\bsst\b",
    "unique:waterwalk": r"\bwaterwalk\b",
    "unique:gorefoot": r"\bgorefoot\b",
    "unique:goredriver": r"\bgore\s*rider\b|\bgoredriver\b|\bgore\b",
    "unique:shadowdancer": r"\bshadow\s*dancer\b",
    "unique:marrowwalk": r"\bmarrowwalk\b",
    "unique:impshank": r"\bimpshank\b",
    "unique:soulspur": r"\bsoul\s*spur\b",
    "unique:trek": r"\btrek\b",

    # Uniques - Gloves
    "unique:dracul": r"\bdracul'?s?\s*grasp\b|\bdracul\b|\bdracs?\b",
    "unique:soul drain": r"\bsoul\s*drain\b",
    "unique:gravepalm": r"\bgrave\s*palm\b|\bgravepalm\b",
    "unique:bloodfist": r"\bblood\s*fist\b|\bbloodfist\b",
    "unique:steelrend": r"\bsteelrend\b",
    "unique:lavagout": r"\blava\s*gout\b|\blavagout\b",
    "unique:hellmouth": r"\bhellmouth\b",
    "unique:chanceguards": r"\bchance\s*guards?\b|\bchancy\b|\bmf\s*gloves\b",
    "unique:magefist": r"\bmagefist\b",
    "unique:frostburn": r"\bfrostburn\b",
    "unique:venomgrip": r"\bvenom\s*grip\b|\bvenomgrip\b",

    # Uniques - Shields
    "unique:stormshield": r"\bstorm\s*shield\b|\bss\b|\bstorm\b",
    "unique:hommunculus": r"\bhommunculus\b|\bhomu\b",
    "unique:boneflame": r"\bbone\s*flame\b|\bboneflame\b",
    "unique:medusa": r"\bmedusa'?s?\s*gaze\b|\bmedusa\b",
    "unique:tiamat": r"\btiamat'?s?\s*rebuke\b|\btiamat\b",
    "unique:blackoak": r"\bblack\s*oak\s*shield\b|\bblackoak\b",
    "unique:moser": r"\bmoser'?s?\s*blessed\s*circle\b|\bmoser\b",
    "unique:gerke": r"\bgerke'?s?\s*sanctuary\b|\bgerke\b",
    "unique:whistan": r"\bwhistan'?s?\s*guard\b|\bwhistan\b",
    "unique:radament": r"\bradament'?s?\s*sphere\b|\bradament\b",
    "unique:spiritward": r"\bspirit\s*ward\b",
    "unique:demonlimb": r"\bdemon\s*limb\b|\bdemonlimb\b",

    # Uniques - Weapons (Melee)
    "unique:botd": r"\bbreath\s*of\s*the\s*dying\b|\bbotd\b",
    "unique:etherealdeath": r"\bethereal\s*death\b",
    "unique:deathcleaver": r"\bdeath\s*cleaver\b",
    "unique:lightsabre": r"\blight\s*sabre?\b|\blightsabre\b|\bls\b",
    "unique:doombringer": r"\bdoombringer\b",
    "unique:grandfather": r"\bgrandfather\b|\bgf\b",
    "unique:azurewrath": r"\bazure\s*wrath\b|\bazurewrath\b",
    "unique:horizon": r"\bhorizon'?s?\s*tornado\b|\bhorizon\b",
    "unique:hellslayer": r"\bhell\s*slayer\b",
    "unique:executioner": r"\bexecutioner'?s?\s*justice\b",

    # Uniques - Weapons (Ranged)
    "unique:windforce": r"\bwind\s*force\b|\bwf\b|\bwindforce\b",
    "unique:eaglehorn": r"\beagle\s*horn\b",
    "unique:wizendraw": r"\bwizendraw\b",
    "unique:goldstrike": r"\bgoldstrike\s*arch\b|\bgoldstrike\b",
    "unique:hellrack": r"\bhellrack\b",
    "unique:buriza": r"\bburiza\b|\bballista\b",

    # Uniques - Weapons (Caster)
    "unique:occulus": r"\bocculus\b|\boccy\b|\boccu\b",
    "unique:wizardspike": r"\bwizardspike\b|\bwizzy\b|\bwiz\b",
    "unique:eschuta": r"\beschuta'?s?\s*temper\b|\beschuta\b",
    "unique:death": r"\bdeath'?s?\s*fathom\b|\bfathom\b",
    "unique:leoric": r"\barm\s*of\s*king\s*leoric\b|\bleoric\b|\baokl\b",
    "unique:blackhand": r"\bblack\s*hand\s*key\b|\bblackhand\b",
    "unique:dim": r"\bdim\s*oak\b",
    "unique:spire": r"\bspire\s*of\s*lazarus\b",
    "unique:stiletto": r"\bstiletto\b",
    "unique:peasant": r"\bpeasant\s*crown\b",

    # Uniques - Jewelry
    "unique:mara": r"\bmara'?s?\s*kaleidoscope\b|\bmara'?s?\b|\bmara\b",
    "unique:highlord": r"\bhighlord'?s?\s*wrath\b|\bhighlord\b|\bhlw\b",
    "unique:catseye": r"\bcat'?s?\s*eye\b|\bcatseye\b",
    "unique:saracen": r"\bsaracen'?s?\s*chance\b|\bsaracen\b",
    "unique:atma": r"\batma'?s?\s*scarab\b|\batma\b",
    "unique:crescentmoon": r"\bcrescent\s*moon\b",
    "unique:rising": r"\bthe\s*rising\s*sun\b|\brising\s*sun\b",
    "unique:nokozan": r"\bnokozan\s*relic\b|\bnokozan\b",
    "unique:metalgrid": r"\bmetalgrid\b",
    "unique:seraph": r"\bseraph'?s?\s*hymn\b|\bseraph\b",
    "unique:angelic": r"\bangelic\s*(?:wings|halo|mantle)\b|\bangelic\b",

    # Uniques - Rings
    "unique:soj": r"\bstone\s*of\s*jordan\b|\bsoj\b",
    "unique:bk": r"\bbul[-\s]*kathos'?s?\s*(?:wedding\s*band|ring)\b|\bbk(?:\s*ring)?\b",
    "unique:raven": r"\braven\s*frost\b|\braven\b|\brf\b",
    "unique:dwarf": r"\bdwarf\s*star\b|\bdwarf\b",
    "unique:nagel": r"\bnagelring\b|\bnagel\b",
    "unique:manald": r"\bmanald\s*heal\b|\bmanald\b",
    "unique:wisp": r"\bwisp\s*projector\b|\bwisp\b",
    "unique:nature": r"\bnature'?s?\s*peace\b|\bnature\b",
    "unique:carp": r"\bccaroh\s*webb'?s?\s*fang\b|\bcarp\b",
    "unique:fcr": r"\bfcr\s*ring\b|\b10\s*fcr\b",
    "unique:str": r"\bstr\s*ring\b|\bstrength\s*ring\b",

    # Uniques - Charms
    "unique:anni": r"\banni(?:hilus)?\s*(?:charm)?\b|\banni\b",
    "unique:torch": r"\bhellfire\s*torch\b|\btorch\b",
    "unique:gheed": r"\bgheed'?s?\s*fortune\b|\bgheed\b",

    # Runewords - Armor
    "runeword:enigma": r"\benigma\b|\benig\b",
    "runeword:fortitude": r"\bfortitude\b|\bforti?\b",
    "runeword:coh": r"\bchains\s*of\s*honor\b|\bcoh\b",
    "runeword:duress": r"\bduress\b",
    "runeword:bramble": r"\bbramble\b",
    "runeword:stone": r"\bstone\b",
    "runeword:durielshell": r"\bduriel'?s?\s*shell\s*runeword\b",
    "runeword:prudence": r"\bprudence\b",
    "runeword:lionheart": r"\blionheart\b",
    "runeword:smoke": r"\bsmoke\b",
    "runeword:treachery": r"\btreachery\b",
    "runeword:glory": r"\bglory\b",
    "runeword:wealth": r"\bwealth\b",
    "runeword:peace": r"\bpeace\b",

    # Runewords - Weapons
    "runeword:infinity": r"\binfinity\b",
    "runeword:botd": r"\bbreath\s*of\s*the\s*dying\b|\bbotd\b",
    "runeword:grief": r"\bgrief\b",
    "runeword:beast": r"\bbeast\b",
    "runeword:lastwish": r"\blast\s*wish\b|\blastwish\b|\blw\b",
    "runeword:doom": r"\bdoom\b",
    "runeword:death": r"\bdeath\s*runeword\b",
    "runeword:destruction": r"\bdestruction\b",
    "runeword:faith": r"\bfaith\b",
    "runeword:ebotd": r"\be?\s*botd\b|\beth\s*botd\b",
    "runeword:edeath": r"\be?\s*death\b|\beth\s*death\b",
    "runeword:oice": r"\boath\b",
    "runeword:phoenix": r"\bphoenix\b",
    "runeword:handofjustice": r"\bhand\s*of\s*justice\b|\bhoj\b",
    "runeword:wraith": r"\bwraith\b",
    "runeword:wrath": r"\bwrath\b",
    "runeword:fury": r"\bfury\b",
    "runeword:passion": r"\bpassion\b",
    "runeword:kingslayer": r"\bkingslayer\b",

    # Runewords - Shields
    "runeword:spirit": r"\bspirit\s*(?:shield|sword|monarch)?\b|\bfspirit\b|\bsspirit\b",
    "runeword:exile": r"\bexile\b",
    "runeword:Phoenix": r"\bphoenix\s*(?:shield)?\b",
    "runeword:sanctuary": r"\bsanctuary\b",
    "runeword:rhyme": r"\brhyme\b",
    "runeword:splendor": r"\bsplendor\b",
    "runeword:ancient": r"\bancient'?s?\s*pledge\b",

    # Runewords - Weapons (Caster)
    "runeword:cta": r"\bcall\s*to\s*arms\b|\bcta\b|\bhoto\b",
    "runeword:hoto": r"\bheart\s*of\s*the\s*oak\b|\bhoto\b",
    "runeword:insight": r"\binsight\b",
    "runeword:white": r"\bwhite\b",
    "runeword:memory": r"\bmemory\b",
    "runeword:leaf": r"\bleaf\b",
    "runeword:stealth": r"\bstealth\b",

    # Set Items - Tal Rasha
    "set:talrasha": r"\btal\s*rasha\b|\btal'?s?\b",
    "set:talamulet": r"\btal'?s?\s*(?:adjudication|amulet)\b",
    "set:talarmor": r"\btal'?s?\s*(?:guardianship|armor)\b",
    "set:talbelt": r"\btal'?s?\s*(?:fine-spun\s*cloth|belt)\b",
    "set:talhelm": r"\btal'?s?\s*(?:horadric\s*crest|helm)\b",
    "set:talorb": r"\btal'?s?\s*(?:lidless\s*eye|orb)\b",

    # Set Items - Immortal King
    "set:ik": r"\bimmortal\s*king\b|\bik\b",
    "set:ikmaul": r"\bik\s*maul\b|\bstone\s*crusher\b",
    "set:ikarmor": r"\bik\s*armor\b|\bsoul\s*cage\b",
    "set:ikhelm": r"\bik\s*helmet?\b|\bik\s*helm\b",
    "set:ikbelt": r"\bik\s*belt\b",
    "set:ikgloves": r"\bik\s*gloves\b",
    "set:ikboots": r"\bik\s*boots\b",

    # Set Items - Natalya
    "set:nat": r"\bnatalya'?s?\b|\bnat'?s?\b",
    "set:natarmor": r"\bnat'?s?\s*(?:shadow|armor)\b",
    "set:nathelm": r"\bnat'?s?\s*(?:totem|helm)\b",
    "set:natclaw": r"\bnat'?s?\s*mark\b",
    "set:natboots": r"\bnat'?s?\s*(?:soul|boots)\b",

    # Set Items - Aldur
    "set:aldur": r"\baldur'?s?\b",
    "set:aldurarmor": r"\baldur'?s?\s*(?:deception|armor)\b",
    "set:aldurhelm": r"\baldur'?s?\s*(?:stony\s*gaze|helm)\b",
    "set:aldurboots": r"\baldur'?s?\s*(?:advance|boots)\b",
    "set:aldurweapon": r"\baldur'?s?\s*(?:rhythm|weapon)\b",

    # Set Items - Trang-Oul
    "set:trang": r"\btrang[-\s]*oul'?s?\b|\btrang\b",
    "set:trangarmor": r"\btrang'?s?\s*(?:scales|armor)\b",
    "set:tranghelm": r"\btrang'?s?\s*(?:guise|helm)\b",
    "set:trangbelt": r"\btrang'?s?\s*(?:girth|belt)\b",
    "set:tranggloves": r"\btrang'?s?\s*(?:claws|gloves)\b",
    "set:trangshield": r"\btrang'?s?\s*(?:wing|shield)\b",

    # Set Items - Other
    "set:arreat": r"\barreat'?s?\s*face\b|\barreat\b",
    "set:guillaume": r"\bguillaume'?s?\s*face\b|\bguillaume\b",
    "set:laying": r"\blaying\s*of\s*hands\b|\bloh\b",
    "set:lava": r"\blava\s*gout\b",
    "set:disciple": r"\bdisciple\b",

    # Craft Items
    "craft:bloodring": r"\bblood\s*ring\b|\bcraft\s*ring\b",
    "craft:bloodgloves": r"\bblood\s*gloves\b|\bcraft\s*gloves\b",
    "craft:bloodamulet": r"\bblood\s*amulet\b|\bcraft\s*amulet\b",
    "craft:casteramulet": r"\bcaster\s*amulet\b|\b2\s*skill\s*amulet\b|\b2/20\s*amulet\b",
    "craft:casterbelt": r"\bcaster\s*belt\b",
    "craft:casterring": r"\bcaster\s*ring\b",
    "craft:hitgloves": r"\bhit\s*power\s*gloves\b|\bkb\s*gloves\b",
    "craft:safety": r"\bsafety\s*(?:shield|amulet|ring)\b",

    # Magic/Rare Items
    "magic:jewel": r"\bjewel\b|\b15\s*ias\b|\b40\s*ed\b",
    "magic:smallcharm": r"\bsmall\s*charm\b|\bsc\b|\b3/20/20\b|\b20\s*life\s*sc\b|\b5\s*all\s*res\s*sc\b|\b7\s*mf\s*sc\b",
    "magic:grandcharm": r"\bgrand\s*charm\b|\bgc\b|\bskill\s*gc\b|\bpcomb\b|\blife\s*gc\b",
    "magic:largecharm": r"\blarge\s*charm\b|\blc\b",

    # Bases
    "base:monarch": r"\bmonarch\b|\b4\s*os\s*monarch\b|\bmonarch\s*base\b",
    "base:archon": r"\barchon\s*plate\b|\barchon\b|\bap\b",
    "base:dusk": r"\bdusk\s*shroud\b|\bdusk\b|\bds\b",
    "base:greathauberk": r"\bgreat\s*hauberk\b|\bgh\b",
    "base:boneweave": r"\bboneweave\b|\bbw\b",
    "base:sacredarmor": r"\bsacred\s*armor\b|\bsa\b",
    "base:thresher": r"\bthresher\b|\bthresh\b",
    "base:giantthresher": r"\bgiant\s*thresher\b|\bgt\b",
    "base:colossusvoulge": r"\bcolossus\s*voulge\b|\bcv\b",
    "base:berserkeraxe": r"\bberserker\s*axe\b|\bba\b|\bzerek'er\b",
    "base:phaseblade": r"\bphase\s*blade\b|\bpb\b",
    "base:kraken": r"\bkraken\s*shell\b",
    "base:lapidon": r"\blapidon\b",
    "base:trollnest": r"\btroll\s*nest\b",
    "base:bladeshield": r"\bblade\s*shield\b",
    "base:heavyspikedshield": r"\bheavy\s*spiked\s*shield\b",
    "base: elite": r"\belite\s*base\b|\bsup\s*base\b|\beth\s*base\b",

    # Facets
    "facet:fire": r"\bfire\s*facet\b|\b5/5\s*fire\b|\bfire\s*rainbow\b",
    "facet:cold": r"\bcold\s*facet\b|\b5/5\s*cold\b|\bcold\s*rainbow\b",
    "facet:light": r"\blight(?:ning)?\s*facet\b|\b5/5\s*light\b|\blight\s*rainbow\b",
    "facet:poison": r"\bpoison\s*facet\b|\b5/5\s*poison\b|\bpoison\s*rainbow\b",

    # Misc Items
    "misc:token": r"\btoken\s*of\s*absolution\b|\btoken\b|\bretoken\b",
    "misc:essence": r"\bessence\b",
    "misc:key": r"\bkey\s*of\s*(?:terror|hate|destruction)\b|\borgan\s*key\b",
    "misc:organ": r"\borgan\b|\bdiablo'?s?\s*horn\b|\bbaal'?s?\s*eye\b|\bmephisto'?s?\s*brain\b",
}

# Compile all patterns at module load for performance
ITEM_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    key: re.compile(pattern, re.I)
    for key, pattern in _ITEM_PATTERN_DEFS.items()
}


def find_items_in_text(text: str) -> list[str]:
    """Find all items mentioned in text.

    Args:
        text: Text to search for items

    Returns:
        List of variant_keys found in text
    """
    items_found = []
    for variant_key, pattern in ITEM_PATTERNS.items():
        if pattern.search(text):
            items_found.append(variant_key)
    return items_found


def find_best_price_in_text(text: str) -> dict | None:
    """Find the best price signal in text.

    Args:
        text: Text to search for prices

    Returns:
        Dict with price, confidence, and signal_kind, or None if no price found
    """
    best_price: float | None = None
    best_confidence = 0.0
    best_signal_kind = "bin"

    for pattern, signal_kind in PRICE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                price = float(match.group(1))
                confidence = get_signal_confidence(signal_kind)
                if best_price is None or confidence > best_confidence:
                    best_price = price
                    best_confidence = confidence
                    best_signal_kind = signal_kind
            except (ValueError, IndexError):
                continue

    if best_price is None:
        return None

    return {
        "price": best_price,
        "confidence": best_confidence,
        "signal_kind": best_signal_kind,
    }
