#!/usr/bin/env python3
"""Import D2R affix data from blizzhackers/d2data JSON files.

This script converts the d2data JSON format to the d2lut YAML affix database
with accurate property descriptions and FG pricing.

Usage:
    python scripts/import_d2data_affixes.py

Input:
    data/d2data_json/magicprefix.json
    data/d2data_json/magicsuffix.json
    data/d2data_json/properties.json
    data/d2data_json/itemstatcost.json

Output:
    config/affix_database_d2data.yml
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import yaml


# Property code to description mapping
PROPERTY_DESC = {
    # Stats
    "str": "Strength",
    "dex": "Dexterity",
    "enr": "Energy",
    "vit": "Vitality",

    # Combat stats
    "ac%": "Enhanced Defense",
    "ac": "Defense",
    "dmg%": "Enhanced Damage",
    "dmg-min": "Minimum Damage",
    "dmg-max": "Maximum Damage",
    "att": "Attack Rating",
    "ar%": "Attack Rating %",

    # Speed
    "swing1": "10% IAS",
    "swing2": "20% IAS",
    "swing3": "40% IAS",
    "cast1": "10% FCR",
    "cast2": "15% FCR",
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
    "mana-kill": "Mana After Kill",
    "hit-leechnorm": "Life Leech",
    "hit-mana": "Mana Leech",

    # Elemental damage
    "cold-min": "Min Cold Damage",
    "cold-max": "Max Cold Damage",
    "cold-len": "Cold Length",
    "fire-min": "Min Fire Damage",
    "fire-max": "Max Fire Damage",
    "ltng-min": "Min Lightning Damage",
    "ltng-max": "Max Lightning Damage",
    "pois-min": "Min Poison Damage",
    "pois-max": "Max Poison Damage",
    "dmg-pois": "Poison Damage",

    # Skills
    "skill": "+Skill",
    "skilltab": "+Skill Tab",
    "sor": "+Sorceress Skills",
    "ama": "+Amazon Skills",
    "nec": "+Necromancer Skills",
    "pal": "+Paladin Skills",
    "bar": "+Barbarian Skills",
    "dru": "+Druid Skills",
    "ass": "+Assassin Skills",

    # Other
    "mag%": "Magic Find",
    "gold%": "Gold Find",
    "light": "Light Radius",
    "thorns": "Thorns",
    "regen": "Mana Regeneration",
    "regen-stam": "Stamina Regeneration",
    "stam": "Stamina",
    "howl": "Hit Causes Monster to Flee",
    "charged": "Charged Skill",
    "sock": "Sockets",
    "ignore-ac": "Ignore Target Defense",
    "dmg-ac": "Target Defense Reduction",
    "att-demon": "Attack Rating vs Demons",
    "dmg-demon": "Damage vs Demons",
    "att-undead": "Attack Rating vs Undead",
    "dmg-undead": "Damage vs Undead",
}

# Skill tab parameter to description
SKILL_TABS = {
    # Amazon
    0: "Bow and Crossbow",
    1: "Passive and Magic",
    2: "Javelin and Spear",
    # Sorceress
    8: "Fire Skills",
    9: "Lightning Skills",
    10: "Cold Skills",
    # Necromancer
    16: "Curses",
    17: "Poison and Bone",
    18: "Summoning",
    # Paladin
    24: "Combat",
    25: "Offensive Auras",
    26: "Defensive Auras",
    # Barbarian
    32: "Combat",
    33: "Combat Masteries",
    34: "Warcries",
    # Druid
    40: "Summoning",
    41: "Shapeshifting",
    42: "Elemental",
    # Assassin
    48: "Traps",
    49: "Shadow Disciplines",
    50: "Martial Arts",
}

# Item type codes to readable names
ITEM_TYPES = {
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
    "ashd": "auric shield",
    "ring": "ring",
    "amul": "amulet",
    "circ": "circlet",
    "scep": "scepter",
    "wand": "wand",
    "staf": "staff",
    "rod": "rod",
    "orb": "sorceress orb",
    "phlm": "pelt",
    "h2h": "assassin claw",
    "knif": "knife",
    "tkni": "throwing knife",
    "thro": "throwing weapon",
    "jewl": "jewel",
    "scha": "small charm",
    "mcha": "large charm",
    "lcha": "grand charm",
    "head": "voodoo heads",
}

# FG prices for valuable affixes
AFFIX_PRICES = {
    # +2 Class Skills
    "Arch-Angel's": {"base_price": 400, "notes": "+2 All Skills"},
    "Necromancer's": {"base_price": 300, "notes": "+2 Necro Skills"},
    "Sorceress's": {"base_price": 250, "notes": "+2 Sorc Skills"},
    "Paladin's": {"base_price": 280, "notes": "+2 Paladin Skills"},
    "Druid's": {"base_price": 300, "notes": "+2 Druid Skills"},
    "Assassin's": {"base_price": 200, "notes": "+2 Assassin Skills"},
    "Barbarian's": {"base_price": 150, "notes": "+2 Barbarian Skills"},
    "Amazon's": {"base_price": 120, "notes": "+2 Amazon Skills"},

    # +3 Skill Tabs
    "Venomous": {"base_price": 800, "notes": "+3 Poison & Bone"},
    "Golemlord's": {"base_price": 400, "notes": "+3 Summoning"},
    "Hexing": {"base_price": 100, "notes": "+3 Curses"},
    "Powered": {"base_price": 400, "notes": "+3 Lightning"},
    "Charged": {"base_price": 350, "notes": "+3 Lightning"},
    "Glacial": {"base_price": 350, "notes": "+3 Cold"},
    "Volcanic": {"base_price": 300, "notes": "+3 Fire"},
    "Blazing": {"base_price": 300, "notes": "+3 Fire"},
    "Gaea's": {"base_price": 500, "notes": "+3 Elemental (Druid)"},
    "Keeper's": {"base_price": 350, "notes": "+3 Summoning (Druid)"},
    "Communal": {"base_price": 200, "notes": "+3 Shapeshifting"},
    "Rose Branded": {"base_price": 500, "notes": "+3 Combat (Paladin)"},
    "Commander's": {"base_price": 500, "notes": "+3 Combat (Paladin)"},
    "Marshal's": {"base_price": 200, "notes": "+3 Offensive Auras"},
    "Guardian's": {"base_price": 150, "notes": "+3 Defensive Auras"},
    "Cunning": {"base_price": 400, "notes": "+3 Traps"},
    "Entrapping": {"base_price": 400, "notes": "+3 Traps"},
    "Shadow": {"base_price": 250, "notes": "+3 Shadow Disciplines"},
    "Shadowdweller": {"base_price": 250, "notes": "+3 Shadow Disciplines"},
    "Kenshi's": {"base_price": 150, "notes": "+3 Martial Arts"},
    "Echoing": {"base_price": 400, "notes": "+3 Warcries"},
    "Furious": {"base_price": 150, "notes": "+3 Combat Masteries"},
    "Master's": {"base_price": 250, "notes": "+3 Combat (Barb)"},
    "Archer's": {"base_price": 150, "notes": "+3 Bow/Crossbow"},
    "Bowyer's": {"base_price": 150, "notes": "+3 Bow/Crossbow"},
    "Athlete's": {"base_price": 80, "notes": "+3 Passive & Magic"},
    "Acrobat's": {"base_price": 80, "notes": "+3 Passive & Magic"},
    "Lancer's": {"base_price": 200, "notes": "+3 Javelin & Spear"},
    "Harpoonist's": {"base_price": 200, "notes": "+3 Javelin & Spear"},

    # Sockets
    "Jeweler's": {"base_price": 500, "notes": "4 Sockets"},
    "Artificer's": {"base_price": 100, "notes": "3 Sockets"},

    # Enhanced Damage
    "Cruel": {"base_price": 150, "notes": "201-300% ED"},
    "Ferocious": {"base_price": 120, "notes": "101-200% ED"},
    "Merciless": {"base_price": 90, "notes": "81-100% ED"},
    "Savage": {"base_price": 70, "notes": "66-80% ED"},

    # Resistances
    "Chromatic": {"base_price": 150, "notes": "All Res 21-30%"},
    "Prismatic": {"base_price": 100, "notes": "All Res 15-25%"},
    "Scintillating": {"base_price": 80, "notes": "All Res 11-15%"},

    # Suffixes (with "of " prefix)
    "of the Magus": {"base_price": 300, "notes": "20% FCR"},
    "of the Apprentice": {"base_price": 150, "notes": "10% FCR"},
    "of Speed": {"base_price": 100, "notes": "30% FRW"},
    "of Haste": {"base_price": 50, "notes": "20% FRW"},
    "of the Whale": {"base_price": 200, "notes": "81-100 Life"},
    "of Vita": {"base_price": 150, "notes": "Life suffix"},
    "of Life": {"base_price": 100, "notes": "Life suffix"},
    "of Deflecting": {"base_price": 400, "notes": "20% Block"},
    "of Blocking": {"base_price": 100, "notes": "10% Block"},
    "of Teleportation": {"base_price": 1000, "notes": "Teleport charges"},
    "of Fortune": {"base_price": 100, "notes": "Magic Find"},
    "of Good Luck": {"base_price": 50, "notes": "Magic Find"},
    "of the Vampire": {"base_price": 80, "notes": "Mana Leech"},
    "of the Leech": {"base_price": 100, "notes": "Life Leech"},
    "of the Locust": {"base_price": 80, "notes": "Life Leech"},
    "of Atlas": {"base_price": 80, "notes": "+Strength"},
    "of Titans": {"base_price": 80, "notes": "+Strength"},
    "of Nirvana": {"base_price": 50, "notes": "+Dexterity"},
    "of Freedom": {"base_price": 100, "notes": "-Requirements"},
    "of Ease": {"base_price": 50, "notes": "-Requirements"},
    "of Fervent": {"base_price": 200, "notes": "15% IAS"},
    "of Alacrity": {"base_price": 80, "notes": "20% IAS"},
    "of Readiness": {"base_price": 20, "notes": "10% IAS"},
    "of Quickness": {"base_price": 150, "notes": "40% IAS"},
    "of Swiftness": {"base_price": 60, "notes": "30% IAS"},
}


def load_json(path: Path) -> dict:
    """Load JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_property_desc(mod_code: str, mod_param: int | None, mod_min: int, mod_max: int) -> str:
    """Generate human-readable property description."""
    base_desc = PROPERTY_DESC.get(mod_code, mod_code)

    # Handle skill tabs
    if mod_code == "skilltab" and mod_param is not None:
        tab_name = SKILL_TABS.get(mod_param, f"Tab {mod_param}")
        if mod_min == mod_max:
            return f"+{mod_min} {tab_name}"
        return f"+{mod_min}-{mod_max} {tab_name}"

    # Handle class skills
    if mod_code in ("sor", "ama", "nec", "pal", "bar", "dru", "ass"):
        class_names = {
            "sor": "Sorceress", "ama": "Amazon", "nec": "Necromancer",
            "pal": "Paladin", "bar": "Barbarian", "dru": "Druid", "ass": "Assassin"
        }
        class_name = class_names.get(mod_code, mod_code)
        if mod_min == mod_max:
            return f"+{mod_min} {class_name} Skills"
        return f"+{mod_min}-{mod_max} {class_name} Skills"

    # Handle charged skills
    if mod_code == "charged":
        return f"Charged Skill ({mod_param})"

    # Handle sockets
    if mod_code == "sock":
        return f"{mod_param} Sockets"

    # Standard properties
    if mod_min == mod_max:
        return f"{base_desc} +{mod_min}"
    return f"{base_desc} {mod_min}-{mod_max}"


def get_item_types(data: dict) -> list[str]:
    """Extract item types from affix data."""
    types = []
    for i in range(1, 8):
        key = f"itype{i}" if f"itype{i}" in data else f"iType{i}"
        if key in data and data[key]:
            code = data[key]
            types.append(ITEM_TYPES.get(code, code))
    return types


def get_item_codes(data: dict) -> list[str]:
    """Extract item type codes from affix data."""
    codes = []
    for i in range(1, 8):
        key = f"itype{i}" if f"itype{i}" in data else f"iType{i}"
        if key in data and data[key]:
            codes.append(data[key])
    return codes


def parse_affix(data: dict) -> dict:
    """Parse a single affix entry."""
    result = {
        "level": data.get("level", 0),
        "level_req": data.get("levelreq", 0),
        "group": data.get("group", 0),
        "spawnable": data.get("spawnable", 0) == 1,
        "rare": data.get("rare", 0) == 1,
        "item_types": get_item_types(data),
        "item_codes": get_item_codes(data),
    }

    # Parse mods
    mods = []
    for i in range(1, 4):
        code = data.get(f"mod{i}code", "")
        if code:
            mods.append({
                "code": code,
                "param": data.get(f"mod{i}param"),
                "min": data.get(f"mod{i}min", 0),
                "max": data.get(f"mod{i}max", 0),
            })

    # Generate property description
    if mods:
        prop_parts = []
        for mod in mods:
            prop_parts.append(get_property_desc(
                mod["code"], mod.get("param"), mod["min"], mod["max"]
            ))
        result["property"] = ", ".join(prop_parts)
    else:
        result["property"] = "Unknown"

    # Class specific
    if data.get("classspecific"):
        result["class_specific"] = data["classspecific"]

    # Add pricing
    name = data.get("Name", "")
    price_info = AFFIX_PRICES.get(name)
    if price_info:
        result["base_price"] = price_info.get("base_price", 1)
        if "notes" in price_info:
            result["notes"] = price_info["notes"]
    else:
        result["base_price"] = 1

    return result


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Input paths
    d2data_dir = project_root / "data" / "d2data_json"
    prefix_file = d2data_dir / "magicprefix.json"
    suffix_file = d2data_dir / "magicsuffix.json"

    # Output path
    output_file = project_root / "config" / "affix_database_d2data.yml"

    print(f"Loading {prefix_file}...")
    prefixes_raw = load_json(prefix_file)
    print(f"  {len(prefixes_raw)} prefix entries")

    print(f"Loading {suffix_file}...")
    suffixes_raw = load_json(suffix_file)
    print(f"  {len(suffixes_raw)} suffix entries")

    # Group by name
    prefix_groups: dict[str, list[dict]] = {}
    for idx, data in prefixes_raw.items():
        name = data.get("Name", "")
        if not name:
            continue
        if name not in prefix_groups:
            prefix_groups[name] = []
        prefix_groups[name].append(parse_affix(data))

    suffix_groups: dict[str, list[dict]] = {}
    for idx, data in suffixes_raw.items():
        name = data.get("Name", "")
        if not name:
            continue
        if name not in suffix_groups:
            suffix_groups[name] = []
        suffix_groups[name].append(parse_affix(data))

    # Build output
    output = {
        "metadata": {
            "source": "blizzhackers/d2data JSON files",
            "prefix_count": len(prefixes_raw),
            "suffix_count": len(suffixes_raw),
            "unique_prefixes": len(prefix_groups),
            "unique_suffixes": len(suffix_groups),
        },
        "prefixes": {},
        "suffixes": {},
    }

    # Process prefixes
    for name, variants in sorted(prefix_groups.items()):
        if len(variants) == 1:
            output["prefixes"][name] = variants[0]
        else:
            # Multiple variants - keep all with simplified structure
            output["prefixes"][name] = {
                "variants": [
                    {
                        "property": v["property"],
                        "level": v["level"],
                        "level_req": v["level_req"],
                        "item_codes": v["item_codes"],
                        "base_price": v["base_price"],
                    }
                    for v in variants
                ],
                "notes": f"{len(variants)} variants",
            }

    # Process suffixes
    for name, variants in sorted(suffix_groups.items()):
        if len(variants) == 1:
            output["suffixes"][name] = variants[0]
        else:
            output["suffixes"][name] = {
                "variants": [
                    {
                        "property": v["property"],
                        "level": v["level"],
                        "level_req": v["level_req"],
                        "item_codes": v["item_codes"],
                        "base_price": v["base_price"],
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

    # Stats
    valuable = [name for name, data in output["prefixes"].items()
                if isinstance(data, dict) and data.get("base_price", 1) >= 100]
    print(f"\nValuable prefixes (>=100 FG): {len(valuable)}")
    for name in sorted(valuable)[:20]:
        print(f"  {name}")


if __name__ == "__main__":
    main()
