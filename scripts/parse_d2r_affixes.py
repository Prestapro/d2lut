#!/usr/bin/env python3
"""Parse D2R MagicPrefix.txt and MagicSuffix.txt into structured YAML.

This script converts the original game data files to a structured format
with FG pricing estimates for d2lut.

Usage:
    python scripts/parse_d2r_affixes.py

Input files (from fabd/diablo2 repo or extracted from D2R CASC):
    - data/d2r_excel/MagicPrefix.txt
    - data/d2r_excel/MagicSuffix.txt

Output:
    - config/affix_database_complete.yml (full database with all affixes)
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


# Item type code mappings (D2R internal -> readable)
ITEM_TYPE_NAMES = {
    "weap": "weapon",
    "mele": "melee weapon",
    "miss": "missile weapon",
    "rang": "ranged weapon",
    "armo": "armor",
    "tors": "torso armor",
    "helm": "helmet",
    "boot": "boots",
    "glov": "gloves",
    "belt": "belt",
    "shld": "shield",
    "ring": "ring",
    "amul": "amulet",
    "circ": "circlet",
    "scep": "scepter",
    "wand": "wand",
    "staf": "staff",
    "rod": "rod (wand/staff/orb)",
    "orb": "sorceress orb",
    "phlm": "pelt (druid helm)",
    "h2h": "assassin claw",
    "scha": "small charm",
    "mcha": "large charm",  # Actually medium charm in code
    "lcha": "grand charm",  # Actually large charm in code
    "jew": "jewel",
}

# Mod code mappings (internal -> readable property)
MOD_PROPERTIES = {
    # Defense
    "ac%": "Enhanced Defense",
    "ac": "Defense",
    
    # Damage
    "dmg%": "Enhanced Damage",
    "dmg-min": "Minimum Damage",
    "dmg-max": "Maximum Damage",
    
    # Attack
    "att": "Attack Rating",
    "dmg-ac": "Target Defense Reduction",
    "ignore-ac": "Ignore Target Defense",
    
    # Speed
    "swing1": "10% IAS",
    "swing2": "20% IAS",
    "swing3": "40% IAS",
    "cast1": "10% FCR",
    "cast2": "?% FCR",
    "cast3": "20% FCR",
    "move1": "10% FRW",
    "move2": "20% FRW",
    "move3": "30% FRW",
    
    # Block
    "block": "Increased Chance of Blocking",
    "block2": "Faster Block Rate",
    
    # Life/Mana
    "hp": "Life",
    "mana": "Mana",
    
    # Resistances
    "res-all": "All Resistances",
    "res-cold": "Cold Resist",
    "res-fire": "Fire Resist",
    "res-ltng": "Lightning Resist",
    "res-pois": "Poison Resist",
    
    # Damage reduction
    "red-dmg": "Damage Reduced",
    "red-mag": "Magic Damage Reduced",
    "dmg-to-mana": "Damage Taken Goes to Mana",
    
    # Leech
    "mana-kill": "Mana After Each Kill",
    "hit-leechnorm": "Life Stolen Per Hit",
    "hit-mana": "Mana Stolen Per Hit",
    
    # Elemental damage
    "cold-min": "Minimum Cold Damage",
    "cold-max": "Maximum Cold Damage",
    "fire-min": "Minimum Fire Damage",
    "fire-max": "Maximum Fire Damage",
    "ltng-min": "Minimum Lightning Damage",
    "ltng-max": "Maximum Lightning Damage",
    "pois-min": "Minimum Poison Damage",
    "pois-max": "Maximum Poison Damage",
    
    # Skills
    "skill": "+Skill",
    "skilltab": "+Skill Tab",
    "skill-rand": "+Random Skill",
    
    # Other
    "mag%": "Magic Find",
    "gold%": "Gold Find",
    "light": "Light Radius",
    "thorns": "Thorns",
    "regen": "Regenerate Mana",
    "regen-stam": "Stamina Regeneration",
    "stam": "Stamina",
    "howl": "Hit Causes Monster to Flee",
    "charged": "Charged Skill",
}

# FG Price estimates for valuable affixes
AFFIX_PRICES = {
    # Prefixes - Skills
    "Arch-Angel's": {"base_price": 400, "notes": "+2 All Skills"},
    "Necromancer's": {"base_price": 300, "notes": "+2 Necro Skills"},
    "Sorceress's": {"base_price": 250, "notes": "+2 Sorc Skills"},
    "Paladin's": {"base_price": 280, "notes": "+2 Paladin Skills"},
    "Druid's": {"base_price": 300, "notes": "+2 Druid Skills"},
    "Assassin's": {"base_price": 200, "notes": "+2 Assassin Skills"},
    "Barbarian's": {"base_price": 150, "notes": "+2 Barb Skills"},
    "Amazon's": {"base_price": 120, "notes": "+2 Amazon Skills"},
    
    # Skill tabs +3
    "Venomous": {"base_price": 800, "notes": "+3 Poison & Bone"},
    "Golemlord's": {"base_price": 400, "notes": "+3 Summoning"},
    "Hexing": {"base_price": 100, "notes": "+3 Curses"},
    "Powered": {"base_price": 400, "notes": "+3 Lightning Skills"},
    "Glacial": {"base_price": 350, "notes": "+3 Cold Skills"},
    "Volcanic": {"base_price": 300, "notes": "+3 Fire Skills"},
    "Gaea's": {"base_price": 500, "notes": "+3 Elemental (Druid)"},
    "Keeper's": {"base_price": 350, "notes": "+3 Summoning (Druid)"},
    "Communal": {"base_price": 200, "notes": "+3 Shapeshifting"},
    "Rose Branded": {"base_price": 500, "notes": "+3 Combat (Paladin)"},
    "Marshal's": {"base_price": 200, "notes": "+3 Offensive Auras"},
    "Guardian's": {"base_price": 150, "notes": "+3 Defensive Auras"},
    "Cunning": {"base_price": 400, "notes": "+3 Traps"},
    "Shadow": {"base_price": 250, "notes": "+3 Shadow Disciplines"},
    "Kenshi's": {"base_price": 150, "notes": "+3 Martial Arts"},
    "Echoing": {"base_price": 400, "notes": "+3 Warcries"},
    "Furious": {"base_price": 150, "notes": "+3 Combat Masteries"},
    "Master's": {"base_price": 250, "notes": "+3 Combat (Barb)"},
    "Archer's": {"base_price": 150, "notes": "+3 Bow/Crossbow"},
    "Athlete's": {"base_price": 80, "notes": "+3 Passive & Magic"},
    "Lancer's": {"base_price": 200, "notes": "+3 Javelin & Spear"},
    
    # Sockets
    "Jeweler's": {"base_price": 500, "notes": "4 Sockets"},
    "Artificer's": {"base_price": 100, "notes": "3 Sockets"},
    
    # ED
    "Cruel": {"base_price": 150, "notes": "201-300% ED"},
    "Ferocious": {"base_price": 120, "notes": "101-200% ED"},
    "Merciless": {"base_price": 90, "notes": "81-100% ED"},
    
    # Resists
    "Chromatic": {"base_price": 150, "notes": "All Res 21-30%"},
    "Prismatic": {"base_price": 100, "notes": "All Res 15-25%"},
    
    # Suffixes (without "of ")
    "the Magus": {"base_price": 300, "notes": "20% FCR"},
    "Speed": {"base_price": 100, "notes": "30% FRW"},
    "Haste": {"base_price": 50, "notes": "20% FRW"},
    "the Whale": {"base_price": 200, "notes": "81-100 Life"},
    "Vita": {"base_price": 150, "notes": "Life suffix"},
    "Deflecting": {"base_price": 400, "notes": "20% Block"},
    "Teleportation": {"base_price": 1000, "notes": "Teleport charges"},
    "the Apprentice": {"base_price": 150, "notes": "10% FCR"},
    "Fortune": {"base_price": 100, "notes": "Magic Find"},
    "Good Luck": {"base_price": 50, "notes": "Magic Find"},
    "the Vampire": {"base_price": 80, "notes": "Mana Leech"},
    "the Leech": {"base_price": 100, "notes": "Life Leech"},
    "Atlas": {"base_price": 80, "notes": "+Strength"},
    "Nirvana": {"base_price": 50, "notes": "+Dexterity"},
    "Freedom": {"base_price": 100, "notes": "-Requirements"},
    "Fervent": {"base_price": 200, "notes": "15% IAS"},
}


@dataclass
class Affix:
    """Represents a D2R affix."""
    name: str
    affix_type: str  # "prefix" or "suffix"
    level: int
    level_req: int
    group: int
    mods: list[dict]
    item_types: list[str]
    excluded_types: list[str]
    spawnable: bool
    rare: bool
    class_specific: Optional[str] = None
    frequency: int = 0
    
    def get_property_desc(self) -> str:
        """Generate human-readable property description."""
        parts = []
        for mod in self.mods:
            code = mod.get("code", "")
            min_val = mod.get("min", 0)
            max_val = mod.get("max", 0)
            
            prop_name = MOD_PROPERTIES.get(code, code)
            
            if min_val == max_val:
                if min_val != 0:
                    parts.append(f"{prop_name} +{min_val}")
            else:
                parts.append(f"{prop_name} {min_val}-{max_val}")
        
        return ", ".join(parts) if parts else "Unknown"
    
    def get_item_types_desc(self) -> str:
        """Get readable item types."""
        return [ITEM_TYPE_NAMES.get(t, t) for t in self.item_types]


def parse_mods(row: dict, prefix: str) -> list[dict]:
    """Parse modifier columns from row."""
    mods = []
    for i in range(1, 4):
        code = row.get(f"{prefix}{i}code", "").strip()
        if code:
            mod = {
                "code": code,
                "param": row.get(f"{prefix}{i}param", "").strip(),
                "min": row.get(f"{prefix}{i}min", "").strip(),
                "max": row.get(f"{prefix}{i}max", "").strip(),
            }
            mods.append(mod)
    return mods


def parse_item_types(row: dict, prefix: str = "itype") -> list[str]:
    """Parse item type columns."""
    types = []
    for i in range(1, 8):
        val = row.get(f"{prefix}{i}", "").strip()
        if val:
            types.append(val)
    return types


def parse_affix_file(filepath: Path, affix_type: str) -> list[Affix]:
    """Parse a MagicPrefix.txt or MagicSuffix.txt file."""
    affixes = []
    
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        # Skip empty lines and get header
        lines = [line for line in f if line.strip()]
        
        if not lines:
            return affixes
        
        # Parse as tab-separated
        reader = csv.DictReader(lines, delimiter="\t")
        
        for row in reader:
            name = row.get("Name", "").strip()
            
            # Skip empty names
            if not name:
                continue
            
            # Parse numeric fields
            try:
                level = int(row.get("level", "0") or "0")
                level_req = int(row.get("levelreq", "0") or "0")
                group = int(row.get("group", "0") or "0")
                frequency = int(row.get("frequency", "0") or "0")
            except ValueError:
                continue
            
            # Parse boolean fields
            spawnable = row.get("spawnable", "0").strip() == "1"
            rare = row.get("rare", "0").strip() == "1"
            
            # Class specific
            class_specific = row.get("classspecific", "").strip() or None
            
            # Parse mods
            mods = parse_mods(row, "mod")
            
            # Parse item types
            item_types = parse_item_types(row, "itype")
            excluded_types = parse_item_types(row, "etype")
            
            affix = Affix(
                name=name,
                affix_type=affix_type,
                level=level,
                level_req=level_req,
                group=group,
                mods=mods,
                item_types=item_types,
                excluded_types=excluded_types,
                spawnable=spawnable,
                rare=rare,
                class_specific=class_specific,
                frequency=frequency,
            )
            affixes.append(affix)
    
    return affixes


def affix_to_yaml_dict(affix: Affix) -> dict:
    """Convert Affix to YAML-friendly dict with pricing."""
    result = {
        "property": affix.get_property_desc(),
        "level": affix.level,
        "level_req": affix.level_req,
        "group": affix.group,
        "item_types": affix.get_item_types_desc(),
        "item_codes": affix.item_types,
    }
    
    if affix.excluded_types:
        result["excluded_types"] = affix.excluded_types
    
    if affix.class_specific:
        result["class_specific"] = affix.class_specific
    
    # Add pricing
    lookup_name = affix.name
    if affix.affix_type == "suffix":
        # Remove "of " for lookup
        lookup_name = affix.name.replace("of ", "")
    
    price_info = AFFIX_PRICES.get(affix.name) or AFFIX_PRICES.get(lookup_name)
    if price_info:
        result["base_price"] = price_info.get("base_price", 0)
        if "notes" in price_info:
            result["notes"] = price_info["notes"]
    else:
        # Default low price for unknown affixes
        result["base_price"] = 1
    
    return result


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Input files
    prefix_file = project_root / "data" / "d2r_excel" / "MagicPrefix.txt"
    suffix_file = project_root / "data" / "d2r_excel" / "MagicSuffix.txt"
    
    # Output file
    output_file = project_root / "config" / "affix_database_complete.yml"
    
    print(f"Parsing {prefix_file}...")
    prefixes = parse_affix_file(prefix_file, "prefix")
    print(f"  Found {len(prefixes)} prefixes")
    
    print(f"Parsing {suffix_file}...")
    suffixes = parse_affix_file(suffix_file, "suffix")
    print(f"  Found {len(suffixes)} suffixes")
    
    # Build YAML structure
    output = {
        "metadata": {
            "source": "D2R MagicPrefix.txt / MagicSuffix.txt",
            "prefix_count": len(prefixes),
            "suffix_count": len(suffixes),
        },
        "prefixes": {},
        "suffixes": {},
    }
    
    # Group prefixes by name (multiple rows may have same name with different levels)
    prefix_groups: dict[str, list[Affix]] = {}
    for p in prefixes:
        if p.name not in prefix_groups:
            prefix_groups[p.name] = []
        prefix_groups[p.name].append(p)
    
    for name, variants in sorted(prefix_groups.items()):
        if len(variants) == 1:
            output["prefixes"][name] = affix_to_yaml_dict(variants[0])
        else:
            # Multiple variants
            output["prefixes"][name] = {
                "variants": [
                    {
                        "property": v.get_property_desc(),
                        "level": v.level,
                        "level_req": v.level_req,
                        "item_codes": v.item_types,
                        "base_price": AFFIX_PRICES.get(name, {}).get("base_price", 1),
                    }
                    for v in variants
                ],
                "notes": f"{len(variants)} variants",
            }
    
    # Same for suffixes
    suffix_groups: dict[str, list[Affix]] = {}
    for s in suffixes:
        if s.name not in suffix_groups:
            suffix_groups[s.name] = []
        suffix_groups[s.name].append(s)
    
    for name, variants in sorted(suffix_groups.items()):
        # Remove "of " prefix for cleaner keys
        key = name
        if len(variants) == 1:
            output["suffixes"][key] = affix_to_yaml_dict(variants[0])
        else:
            output["suffixes"][key] = {
                "variants": [
                    {
                        "property": v.get_property_desc(),
                        "level": v.level,
                        "level_req": v.level_req,
                        "item_codes": v.item_types,
                        "base_price": AFFIX_PRICES.get(name.replace("of ", ""), {}).get("base_price", 1),
                    }
                    for v in variants
                ],
                "notes": f"{len(variants)} variants",
            }
    
    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print(f"\nWrote {output_file}")
    print(f"  Prefixes: {len(output['prefixes'])} unique names")
    print(f"  Suffixes: {len(output['suffixes'])} unique names")
    
    # Print some stats
    valuable_prefixes = [p for p in prefixes if AFFIX_PRICES.get(p.name, {}).get("base_price", 0) >= 100]
    valuable_suffixes = [s for s in suffixes if AFFIX_PRICES.get(s.name.replace("of ", ""), {}).get("base_price", 0) >= 100]
    
    print(f"\nValuable affixes (>= 100 FG base price):")
    print(f"  Prefixes: {len(valuable_prefixes)}")
    print(f"  Suffixes: {len(valuable_suffixes)}")


if __name__ == "__main__":
    main()
