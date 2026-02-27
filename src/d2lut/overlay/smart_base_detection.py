"""Smart Base Detection for identifying high-value base items.

Analyzes unidentified base items and estimates their potential value based on:
- Runeword compatibility (Spirit, Enigma, Infinity, etc.)
- Unique drop potential (high-value uniques that can drop from this base)
- GG magic roll potential (JMOD, +2 skills amulets, etc.)
- Ethereal status for specific runewords
- Socket count requirements

This helps players quickly identify which bases are worth picking up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunewordInfo:
    """Information about a runeword that can be made in a base."""
    name: str
    sockets: int
    value_tier: str  # "gg", "high", "medium", "low"
    estimated_fg: float
    notes: str = ""
    requires_ethereal: bool = False
    lld_relevant: bool = False


@dataclass
class UniqueInfo:
    """Information about a unique that can drop from a base."""
    name: str
    value_tier: str  # "gg", "high", "medium", "low"
    estimated_fg: float
    notes: str = ""


@dataclass
class BaseValuation:
    """Complete valuation of an unidentified base item."""
    base_code: str
    base_name: str
    quality: str  # "normal", "exceptional", "elite"
    ethereal: bool
    sockets: int | None
    defense: int | None
    
    # Valuation results
    runeword_potential: list[RunewordInfo] = field(default_factory=list)
    unique_potential: list[UniqueInfo] = field(default_factory=list)
    gg_magic_potential: bool = False
    gg_magic_notes: list[str] = field(default_factory=list)
    
    # Aggregate values
    max_potential_fg: float = 0.0
    overall_tier: str = "low"  # "gg", "high", "medium", "low", "trash"
    recommendation: str = ""  # Human-readable recommendation
    
    # LLD specific
    is_lld_relevant: bool = False
    lld_bucket: str | None = None  # "LLD9", "LLD18", "LLD30"


# ---------------------------------------------------------------------------
# Runeword definitions by base type
# ---------------------------------------------------------------------------

# Shield runewords
SHIELD_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    4: [  # 4os shields
        RunewordInfo("Spirit", 4, "high", 5.0, "FCR, skills, res - caster staple", lld_relevant=True),
        RunewordInfo("Phoenix", 4, "medium", 2.0, "ED%, redemption - phys builds"),
    ],
    2: [  # 2os shields
        RunewordInfo("Rhyme", 2, "low", 0.5, "MF, res - budget option"),
        RunewordInfo("Splendor", 2, "low", 0.3, "MF, +1 skills"),
    ],
    3: [  # 3os shields
        RunewordInfo("Trellis", 3, "low", 0.2, "Defensive option"),
    ],
}

# Paladin shield specific
PALADIN_SHIELD_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    4: [
        RunewordInfo("Spirit", 4, "gg", 15.0, "Pally spirit - highest FCR potential"),
        RunewordInfo("Phoenix", 4, "high", 5.0, "ED%, redemption for smiter"),
        RunewordInfo("Exile", 4, "high", 8.0, "Defiance aura - uber smiter", requires_ethereal=True),
    ],
    2: [
        RunewordInfo("Rhyme", 2, "low", 0.5, "MF, res"),
    ],
}

# Armor runewords (by sockets)
ARMOR_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    4: [
        RunewordInfo("Fortitude", 4, "high", 8.0, "300% ED - phys BiS"),
        RunewordInfo("Chains of Honor", 4, "medium", 4.0, "+2 skills, res - versatile"),
        RunewordInfo("Stone", 4, "low", 1.0, "Defense merc armor"),
    ],
    3: [
        RunewordInfo("Enigma", 3, "gg", 55.0, "Teleport - most valuable armor RW"),
        RunewordInfo("Duress", 3, "medium", 1.0, "CB, OW - budget phys"),
        RunewordInfo("Smoke", 3, "low", 0.2, "Res - budget"),
    ],
    2: [
        RunewordInfo("Smoke", 2, "low", 0.2, "All res"),
        RunewordInfo("Stealth", 2, "low", 0.1, "FCR, FRW - early game"),
    ],
    1: [
        RunewordInfo("Stealth", 1, "low", 0.1, "FCR - early game"),
    ],
}

# Weapon runewords - Polearms (for mercs)
POLEARM_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    4: [
        RunewordInfo("Infinity", 4, "gg", 45.0, "Conviction - caster merc BiS"),
        RunewordInfo("Insight", 4, "medium", 2.0, "Meditation - mana merc staple"),
        RunewordInfo("Obedience", 4, "medium", 1.5, "ED - phys merc"),
    ],
    5: [
        RunewordInfo("Destruction", 5, "low", 1.0, "CB - phys option"),
    ],
    6: [
        RunewordInfo("Breath of the Dying", 6, "high", 15.0, "High ED - phys merc"),
    ],
}

# Weapon runewords - Swords
SWORD_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    4: [
        RunewordInfo("Spirit", 4, "medium", 3.0, "FCR, skills - caster weapon"),
        RunewordInfo("Call to Arms", 4, "gg", 25.0, "BO - essential buff weapon"),
        RunewordInfo("Fury", 4, "low", 1.0, "IAS, CB - phys option"),
    ],
    5: [
        RunewordInfo("Grief", 5, "gg", 30.0, "Flat dmg - smiter/zealer BiS"),
        RunewordInfo("Lawbringer", 5, "medium", 2.0, "Sanctuary - undead/decrepify"),
    ],
    6: [
        RunewordInfo("Breath of the Dying", 6, "high", 12.0, "ED - phys option"),
        RunewordInfo("Last Wish", 6, "high", 18.0, "Might aura, CB"),
    ],
}

# Weapon runewords - Axes
AXE_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    4: [
        RunewordInfo("Oath", 4, "medium", 2.0, "ED, indestructible"),
    ],
    5: [
        RunewordInfo("Grief", 5, "gg", 30.0, "Flat dmg - Barb BiS"),
        RunewordInfo("Beast", 5, "high", 12.0, "Fanaticism - summoner/smiter"),
    ],
    6: [
        RunewordInfo("Breath of the Dying", 6, "high", 12.0, "ED - phys barb"),
        RunewordInfo("Death", 6, "medium", 5.0, "CB, deadly strike"),
    ],
}

# Weapon runewords - Hammers
HAMMER_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    4: [
        RunewordInfo("Heart of the Oak", 4, "gg", 18.0, "+3 skills, FCR - caster BiS"),
    ],
    5: [
        RunewordInfo("Destruction", 5, "low", 1.0, "CB option"),
    ],
}

# Weapon runewords - Bows/Crossbows
BOW_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    4: [
        RunewordInfo("Faith", 4, "gg", 25.0, "Fanaticism - bowazon BiS"),
        RunewordInfo("Ice", 4, "high", 8.0, "Freezing arrow synergy"),
    ],
    3: [
        RunewordInfo("Harmony", 3, "medium", 3.0, "Vigor, valkyrie"),
    ],
    5: [
        RunewordInfo("Brand", 5, "medium", 4.0, "CB, deadly strike"),
    ],
    6: [
        RunewordInfo("Windforce", 6, "low", 2.0, "Knockback - not popular"),
    ],
}

# Weapon runewords - Staves/Orbs (sorceress)
STAFF_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    4: [
        RunewordInfo("Memory", 4, "low", 0.5, "+3 skills - budget"),
        RunewordInfo("Spirit", 4, "medium", 2.0, "FCR - off-hand option"),
    ],
    5: [
        RunewordInfo("Heart of the Oak", 5, "high", 15.0, "+3 skills - but flail better"),
    ],
}

# Helm runewords
HELM_RUNEWORDS: dict[int, list[RunewordInfo]] = {
    2: [
        RunewordInfo("Lore", 2, "low", 0.2, "+1 skills - budget"),
        RunewordInfo("Nadir", 2, "low", 0.1, "Defense - budget"),
    ],
    3: [
        RunewordInfo("Delirium", 3, "medium", 5.0, "Confuse, +2 skills - fun/chaos"),
        RunewordInfo("Dream", 3, "high", 10.0, "Holy shock - dual dream build"),
        RunewordInfo("Radiance", 3, "low", 0.3, "Light radius, res"),
    ],
    4: [
        RunewordInfo("Wisdom", 4, "low", 0.5, "Mana, mana regen"),
    ],
}

# ---------------------------------------------------------------------------
# Unique potential by base
# ---------------------------------------------------------------------------

UNIQUE_POTENTIAL: dict[str, list[UniqueInfo]] = {
    # Rings
    "rin": [
        UniqueInfo("Stone of Jordan", "gg", 40.0, "+1 skills, mana - caster BiS"),
        UniqueInfo("Bul-Kathos Wedding Band", "gg", 25.0, "+1 skills, life - melee BiS"),
        UniqueInfo("Wisp Projector", "high", 15.0, "Level 7 spirit, absorb"),
        UniqueInfo("Raven Frost", "medium", 2.0, "Cannot be frozen, dex"),
        UniqueInfo("Dwarf Star", "low", 0.5, "Fire absorb, life"),
        UniqueInfo("Nagelring", "trash", 0.1, "MF - early game"),
    ],
    # Amulets
    "amu": [
        UniqueInfo("Mara's Kaleidoscope", "gg", 20.0, "+2 skills, res - BiS for many"),
        UniqueInfo("Tal Rasha's Adjudication", "high", 8.0, "+2 sorc, MF - sorc BiS"),
        UniqueInfo("Highlord's Wrath", "high", 10.0, "+1 skills, IAS, deadly strike"),
        UniqueInfo("Arachnid Mesh", "gg", 30.0, "+1 skills, slow - caster belt BiS"),
        UniqueInfo("Cat's Eye", "medium", 3.0, "IAS, dex - zon"),
        UniqueInfo("Atma's Scarab", "medium", 2.0, "Amplify dmg proc"),
        UniqueInfo("Seraph's Hymn", "medium", 4.0, "+2 pally defensive auras"),
        UniqueInfo("Metalgrid", "low", 1.0, "AR, iron golem charges"),
    ],
    # Diadem (griffon)
    "uhm": [
        UniqueInfo("Griffon's Eye", "gg", 50.0, "-ELR, +light dmg - light sorc BiS"),
        UniqueInfo("Nightwing's Veil", "high", 12.0, "+cold dmg - cold sorc"),
    ],
    # Shako
    "usk": [
        UniqueInfo("Harlequin Crest", "gg", 35.0, "+2 skills, DR, life/mana - BiS helm"),
    ],
    # Monarch (stormshield, spirit base)
    "uit": [
        UniqueInfo("Stormshield", "high", 8.0, "DR% - phys tank"),
    ],
    # Dimensional Shard (death's fathom)
    "uzl": [
        UniqueInfo("Death's Fathom", "gg", 45.0, "+cold dmg - cold sorc BiS"),
    ],
    # War Boots (gore rider)
    "xtb": [
        UniqueInfo("Gore Rider", "high", 6.0, "CB, DS, OW - phys BiS"),
    ],
    # Vampirebone Gloves (dracul's)
    "uvg": [
        UniqueInfo("Dracul's Grasp", "high", 6.0, "Life tap, str - phys/smiter"),
    ],
    # Balrog Skin (arkaine's)
    "upl": [
        UniqueInfo("Arkaine's Valor", "medium", 3.0, "+2 skills, life after kill"),
    ],
    # Grim Helm (vampire gaze)
    "xh9": [
        UniqueInfo("Vampire Gaze", "medium", 4.0, "DR, MDR, LL - budget phys"),
    ],
    # Gilded Shield (hoz)
    "xts": [
        UniqueInfo("Herald of Zakarum", "gg", 20.0, "+2 pally, res, block - pally BiS"),
    ],
    # Zombie Head (homunculus)
    "zmb": [
        UniqueInfo("Homunculus", "high", 8.0, "+2 necro, FCR, mana - necro BiS"),
    ],
}

# ---------------------------------------------------------------------------
# GG Magic potential by base
# ---------------------------------------------------------------------------

GG_MAGIC_BASES: dict[str, list[str]] = {
    # Monarch - Jeweler's Monarch of Deflecting (JMOD)
    "uit": ["JMOD (Jeweler's of Deflecting) - 4os + 20% block - 100+ fg"],
    
    # Diadem - +2 skills / 20 fcr
    "uhm": ["+2 skills / 20 FCR amulet - 50+ fg", "+3 skills / 10 FCR - 30+ fg"],
    
    # Tiara/Coronet/Circlet - +2 skills / 20 fcr / FRW
    "ci3": ["+2 skills / 20 FCR / FRW - 30+ fg"],
    "ci2": ["+2 skills / 20 FCR / FRW - 20+ fg"],
    "ci0": ["+2 skills / 20 FCR - 10+ fg"],
    
    # Jewels - ED/IAS, ED/-req, etc
    "jew": ["40/15 ED/IAS - 20+ fg", "15 IAS / -15 req - 15+ fg", "40 ED / -15 req - 10+ fg"],
    
    # Grand Charms - skillers with life
    "cm3": ["Skiller +45 life - 20+ fg", "Skiller +30+ life - 5+ fg"],
    
    # Small Charms - vita, res, fhr
    "cm1": ["20 life / 5 all res - 10+ fg", "3/20/20 - 5+ fg", "5 all res / 5 FHR - 3+ fg"],
    
    # Rings - 10 fcr with stats
    "rin": ["10 FCR / 100+ mana / str/dex - 10+ fg", "10 FCR / 25+ res all - 5+ fg"],
    
    # Amulets - +2 skills / 20 fcr
    "amu": ["+2 skills / 20 FCR / stats - 50+ fg", "+2 skills / 20 FCR / mana - 30+ fg"],
}

# ---------------------------------------------------------------------------
# Base item quality tiers (for armor/weapons)
# ---------------------------------------------------------------------------

BASE_QUALITY_TIERS: dict[str, dict[str, list[str]]] = {
    "armor": {
        "elite": ["uap", "uit", "uhm", "upl", "uzl"],  # Archon, Monarch, Diadem, Balrog, Dimensional
        "exceptional": ["xh9", "xtb", "uvg", "xts"],  # Grim, War, Vamp, Gilded
        "normal": ["hlm", "arm", "shd"],  # Basic helms, armor, shields
    },
    "weapon": {
        "elite": ["7gd", "7wa", "7pa"],  # Giant Thresher, Phase Blade, Cryptic Axe
        "exceptional": ["6gd", "6wa", "6pa"],
        "normal": ["gdm", "wad", "pax"],
    },
}

# LLD relevant bases
LLD_BASES: dict[str, str] = {
    # Bases that are valuable for LLD
    "ci0": "LLD circlets - +2 skills / FRW",
    "ci2": "LLD coronets - +2 skills / FRW",
    "rin": "LLD rings - 10 FCR / stats",
    "amu": "LLD amulets - +2 skills / FCR",
    "jew": "LLD jewels - IAS / ED / -req",
    "cm1": "LLD small charms - max dmg / AR / life",
}

# ---------------------------------------------------------------------------
# Smart Base Detector class
# ---------------------------------------------------------------------------

class SmartBaseDetector:
    """Analyzes base items and provides valuation/recommendations."""
    
    def __init__(self):
        self.runeword_db: dict[str, dict[int, list[RunewordInfo]]] = {
            # Map base codes to their runeword potential
            # Shields
            "uit": SHIELD_RUNEWORDS,  # Monarch
            "ush": SHIELD_RUNEWORDS,  # Sacred Rondache (pally)
            "uws": SHIELD_RUNEWORDS,  # Targe (pally)
            "ulg": SHIELD_RUNEWORDS,  # Luna
            
            # Armor
            "uap": ARMOR_RUNEWORDS,  # Archon Plate
            "upl": ARMOR_RUNEWORDS,  # Balrog Skin
            "ula": ARMOR_RUNEWORDS,  # Wire Fleece
            "uld": ARMOR_RUNEWORDS,  # Great Hauberk
            
            # Polearms (for Insight/Infinity)
            "7pa": POLEARM_RUNEWORDS,  # Cryptic Axe
            "7gd": POLEARM_RUNEWORDS,  # Giant Thresher
            "7vo": POLEARM_RUNEWORDS,  # Thresher
            "7st": POLEARM_RUNEWORDS,  # Stygian Pike
            
            # Swords
            "7wa": SWORD_RUNEWORDS,  # Phase Blade
            "7cr": SWORD_RUNEWORDS,  # Crystal Sword
            "7bs": SWORD_RUNEWORDS,  # Balrog Blade
            
            # Axes
            "7ax": AXE_RUNEWORDS,  # Berserker Axe
            "7ba": AXE_RUNEWORDS,  # Balanced Axe
            
            # Hammers
            "7wh": HAMMER_RUNEWORDS,  # War Hammer -> Flail -> Scourge
            "7fl": HAMMER_RUNEWORDS,  # Flail
            
            # Bows
            "7bw": BOW_RUNEWORDS,  # Great Bow
            "7hb": BOW_RUNEWORDS,  # Hydra Bow
            
            # Helms
            "uhm": HELM_RUNEWORDS,  # Diadem
            "usk": HELM_RUNEWORDS,  # Shako
            "ci3": HELM_RUNEWORDS,  # Tiara
            "ci2": HELM_RUNEWORDS,  # Coronet
            "ci0": HELM_RUNEWORDS,  # Circlet
        }
    
    def analyze_base(
        self,
        base_code: str,
        base_name: str,
        sockets: int | None = None,
        ethereal: bool = False,
        defense: int | None = None,
        quality: str = "normal",
        is_paladin_shield: bool = False,
        req_level: int | None = None,
    ) -> BaseValuation:
        """Analyze a base item and return complete valuation."""
        
        result = BaseValuation(
            base_code=base_code,
            base_name=base_name,
            quality=quality,
            ethereal=ethereal,
            sockets=sockets,
            defense=defense,
        )
        
        # 1. Runeword potential
        rw_db = self.runeword_db.get(base_code, {})
        if is_paladin_shield:
            rw_db = PALADIN_SHIELD_RUNEWORDS
        
        if sockets is not None and sockets in rw_db:
            for rw in rw_db[sockets]:
                # Skip ethereal-required runewords if not ethereal
                if rw.requires_ethereal and not ethereal:
                    continue
                result.runeword_potential.append(rw)
        
        # Also check if base can get more sockets (unsocketed items)
        if sockets is None:
            max_sockets = self._get_max_sockets(base_code)
            for sock_count in range(1, max_sockets + 1):
                if sock_count in rw_db:
                    for rw in rw_db[sock_count]:
                        if not rw.requires_ethereal or ethereal:
                            result.runeword_potential.append(rw)
        
        # 2. Unique potential
        if base_code in UNIQUE_POTENTIAL:
            result.unique_potential = UNIQUE_POTENTIAL[base_code]
        
        # 3. GG Magic potential
        if base_code in GG_MAGIC_BASES:
            result.gg_magic_potential = True
            result.gg_magic_notes = GG_MAGIC_BASES[base_code]
        
        # 4. LLD check
        if base_code in LLD_BASES:
            result.is_lld_relevant = True
            if req_level is not None:
                result.lld_bucket = self._assign_lld_bucket(req_level)
        
        # 5. Calculate aggregate values
        self._calculate_aggregates(result)
        
        return result
    
    def _get_max_sockets(self, base_code: str) -> int:
        """Get maximum socket count for a base."""
        # Monarch = 4, Archon = 4, Phase Blade = 6, etc.
        SOCKET_LIMITS: dict[str, int] = {
            "uit": 4,  # Monarch
            "uap": 4,  # Archon Plate
            "7wa": 6,  # Phase Blade
            "7cr": 6,  # Crystal Sword
            "7ax": 6,  # Berserker Axe
            "7pa": 5,  # Cryptic Axe
            "7gd": 5,  # Giant Thresher
            "uhm": 3,  # Diadem
            "usk": 3,  # Shako
            "ci0": 3, "ci2": 3, "ci3": 3,  # Circlets
        }
        return SOCKET_LIMITS.get(base_code, 4)
    
    def _assign_lld_bucket(self, req_level: int) -> str:
        """Assign LLD bucket based on requirement level."""
        if req_level <= 9:
            return "LLD9"
        if req_level <= 18:
            return "LLD18"
        if req_level <= 30:
            return "LLD30"
        return "MLD" if req_level <= 49 else "HLD"
    
    def _calculate_aggregates(self, result: BaseValuation) -> None:
        """Calculate max potential FG and overall tier."""
        
        # Max potential from runewords
        rw_max = 0.0
        for rw in result.runeword_potential:
            if rw.value_tier == "gg":
                rw_max = max(rw_max, rw.estimated_fg * 1.2)  # Bonus for GG
            else:
                rw_max = max(rw_max, rw.estimated_fg)
        
        # Max potential from uniques
        uniq_max = 0.0
        for u in result.unique_potential:
            uniq_max = max(uniq_max, u.estimated_fg)
        
        # GG magic potential bonus
        magic_bonus = 50.0 if result.gg_magic_potential else 0.0
        
        # Ethereal bonus for specific bases
        eth_bonus = 0.0
        if result.ethereal:
            # Ethereal bases for Exile, Death, etc.
            eth_bonus = 10.0
        
        result.max_potential_fg = max(rw_max, uniq_max, magic_bonus) + eth_bonus
        
        # Determine overall tier
        if result.max_potential_fg >= 30:
            result.overall_tier = "gg"
        elif result.max_potential_fg >= 10:
            result.overall_tier = "high"
        elif result.max_potential_fg >= 3:
            result.overall_tier = "medium"
        elif result.max_potential_fg >= 0.5:
            result.overall_tier = "low"
        else:
            result.overall_tier = "trash"
        
        # Generate recommendation
        result.recommendation = self._generate_recommendation(result)
    
    def _generate_recommendation(self, result: BaseValuation) -> str:
        """Generate human-readable recommendation."""
        parts = []
        
        if result.overall_tier == "gg":
            parts.append("HOT BASE! Pick up immediately.")
        elif result.overall_tier == "high":
            parts.append("Valuable base - worth picking up.")
        elif result.overall_tier == "medium":
            parts.append("Decent base - pick up if you have space.")
        else:
            parts.append("Low value - skip unless needed.")
        
        if result.runeword_potential:
            top_rw = max(result.runeword_potential, key=lambda x: x.estimated_fg)
            parts.append(f"Best RW: {top_rw.name} (~{top_rw.estimated_fg:.0f} fg)")
        
        if result.unique_potential:
            gg_uniques = [u for u in result.unique_potential if u.value_tier == "gg"]
            if gg_uniques:
                parts.append(f"GG unique potential: {', '.join(u.name for u in gg_uniques[:2])}")
        
        if result.gg_magic_potential:
            parts.append("GG magic roll potential!")
        
        if result.is_lld_relevant:
            parts.append(f"LLD relevant ({result.lld_bucket or 'check req'})")
        
        return " | ".join(parts)
    
    def get_base_hint_string(self, base_code: str, sockets: int | None = None) -> str:
        """Get a short hint string for D2R loot filter integration."""
        result = self.analyze_base(base_code, base_code, sockets=sockets)
        
        if result.overall_tier == "trash":
            return ""
        
        hints = []
        
        # Tier indicator
        tier_colors = {
            "gg": "ÿc1",    # Red
            "high": "ÿc;",   # Purple
            "medium": "ÿc8", # Orange
            "low": "ÿc3",    # Blue
        }
        color = tier_colors.get(result.overall_tier, "ÿc0")
        
        # Top runeword
        if result.runeword_potential:
            top_rw = max(result.runeword_potential, key=lambda x: x.estimated_fg)
            hints.append(top_rw.name)
        
        # GG unique count
        gg_count = len([u for u in result.unique_potential if u.value_tier == "gg"])
        if gg_count > 0:
            hints.append(f"{gg_count} GG unique{'s' if gg_count > 1 else ''}")
        
        # GG magic flag
        if result.gg_magic_potential:
            hints.append("★GG magic")
        
        if hints:
            return f" {color}[{'|'.join(hints)}]"
        
        return ""
