#!/usr/bin/env python3
"""
Generate item-nameaffixes.json with FG prices for magic items.

Output format:
- Single affixes: "Jeweler's | 500 FG"
- GG Combinations: "Jeweler's Monarch of Deflecting | 2000-8000 FG | 4os/20fbr"

The GG combinations are shown as FULL item names with:
- Price range (base to perfect)
- Perfect roll stats
"""

import json
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class GGCombo:
    """GG Magic item combination."""
    prefix: str
    base_items: list[str]  # e.g., ["Monarch", "Luna", "Hyperion", "Ward"]
    base_codes: list[str]  # e.g., ["uit", "ulg", "ush", "uws"]
    suffix: str
    base_price: int
    perfect_price: int
    perfect_rolls: str  # e.g., "4os/20fbr"
    notes: str


# GG Magic Item Combinations with perfect roll info
GG_COMBINATIONS = [
    # JMOD - Jeweler's of Deflecting
    GGCombo(
        prefix="Jeweler's",
        base_items=["Monarch", "Luna", "Hyperion", "Ward"],
        base_codes=["uit", "ulg", "ush", "uws"],
        suffix="of Deflecting",
        base_price=2000,
        perfect_price=8000,
        perfect_rolls="4os/20fbr",
        notes="JMOD - GG for Spirit/Phoenix"
    ),
    
    # Venomous of the Magus (Poison Necro)
    GGCombo(
        prefix="Venomous",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=4000,
        perfect_price=20000,
        perfect_rolls="+3PnB/20fcr",
        notes="GG Poison Necro circlet"
    ),
    
    # Necromancer's of the Magus
    GGCombo(
        prefix="Necromancer's",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem", "Amulet"],
        base_codes=["ci0", "ci1", "ci2", "ci3", "amu"],
        suffix="of the Magus",
        base_price=3000,
        perfect_price=15000,
        perfect_rolls="+2Nec/20fcr",
        notes="GG Necro circlet/amulet"
    ),
    
    # Berserker's of Teleportation (PvP Barb)
    GGCombo(
        prefix="Berserker's",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of Teleportation",
        base_price=5000,
        perfect_price=15000,
        perfect_rolls="+3War/Tele",
        notes="GG PvP Barb Teleport circlet"
    ),
    
    # Necromancer's of Teleportation
    GGCombo(
        prefix="Necromancer's",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of Teleportation",
        base_price=4000,
        perfect_price=12000,
        perfect_rolls="+2Nec/Tele",
        notes="GG PvP Necro Teleport"
    ),
    
    # Druid's of the Magus
    GGCombo(
        prefix="Druid's",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem", "Amulet"],
        base_codes=["ci0", "ci1", "ci2", "ci3", "amu"],
        suffix="of the Magus",
        base_price=2500,
        perfect_price=10000,
        perfect_rolls="+2Dru/20fcr",
        notes="GG Windy Druid circlet"
    ),
    
    # Hierophant's of the Magus (Hammerdin)
    GGCombo(
        prefix="Hierophant's",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=2500,
        perfect_price=10000,
        perfect_rolls="+3Com/20fcr",
        notes="GG Hammerdin circlet"
    ),
    
    # Arch-Angel's of the Magus
    GGCombo(
        prefix="Arch-Angel's",
        base_items=["Amulet"],
        base_codes=["amu"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=5000,
        perfect_rolls="+2all/20fcr",
        notes="GG caster amulet"
    ),
    
    # Paladin's of the Magus
    GGCombo(
        prefix="Paladin's",
        base_items=["Amulet"],
        base_codes=["amu"],
        suffix="of the Magus",
        base_price=1800,
        perfect_price=7000,
        perfect_rolls="+2Pal/20fcr",
        notes="GG Hammerdin amulet"
    ),
    
    # Powered of the Magus (Lightning Sorc)
    GGCombo(
        prefix="Powered",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=2000,
        perfect_price=8000,
        perfect_rolls="+3Lit/20fcr",
        notes="GG Lightning Sorc circlet"
    ),
    
    # Charged of the Magus
    GGCombo(
        prefix="Charged",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1800,
        perfect_price=7000,
        perfect_rolls="+3Lit/20fcr",
        notes="GG Lightning Sorc (alt)"
    ),
    
    # Keeper's of the Magus (Summon Druid)
    GGCombo(
        prefix="Keeper's",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=2000,
        perfect_price=8000,
        perfect_rolls="+3Sum/20fcr",
        notes="GG Summon Druid circlet"
    ),
    
    # Echoing of the Magus (Warcry Barb)
    GGCombo(
        prefix="Echoing",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=2000,
        perfect_price=8000,
        perfect_rolls="+3War/20fcr",
        notes="GG Warcry Barb circlet"
    ),
    
    # Cunning of the Magus (Trapsin)
    GGCombo(
        prefix="Cunning",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Trap/20fcr",
        notes="GG Trapsin circlet"
    ),
    
    # Golemlord's of the Magus (Summon Necro)
    GGCombo(
        prefix="Golemlord's",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Sum/20fcr",
        notes="GG Summon Necro circlet"
    ),
    
    # Shimmering GC of Vita (Skiller)
    GGCombo(
        prefix="Shimmering",
        base_items=["Grand Charm"],
        base_codes=["cm3"],
        suffix="of Vita",
        base_price=800,
        perfect_price=2500,
        perfect_rolls="+1sk/45life",
        notes="GG Skiller GC"
    ),
    
    # Crimson Jewel of Fervent (40/15)
    GGCombo(
        prefix="Crimson",
        base_items=["Jewel"],
        base_codes=["jew"],
        suffix="of Fervent",
        base_price=1500,
        perfect_price=5000,
        perfect_rolls="40ed/15ias",
        notes="GG 40/15 Jewel"
    ),
    
    # Fervent Jewel of Freedom (15/-15)
    GGCombo(
        prefix="Fervent",
        base_items=["Jewel"],
        base_codes=["jew"],
        suffix="of Freedom",
        base_price=600,
        perfect_price=2000,
        perfect_rolls="15ias/-15req",
        notes="GG LLD Jewel"
    ),
    
    # Lion Branded of the Magus
    GGCombo(
        prefix="Lion Branded",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Com/20fcr",
        notes="GG Pally Combat circlet"
    ),
    
    # Shadow of the Magus
    GGCombo(
        prefix="Shadow",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3SD/20fcr",
        notes="GG Shadow Dancer circlet"
    ),
    
    # Freezing of the Magus
    GGCombo(
        prefix="Freezing",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Cold/20fcr",
        notes="GG Cold Sorc circlet"
    ),
    
    # Grim of the Magus
    GGCombo(
        prefix="Grim",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1200,
        perfect_price=5000,
        perfect_rolls="+3Fire/20fcr",
        notes="GG Fire Sorc circlet"
    ),
    
    # Witch-hunter's of Teleportation
    GGCombo(
        prefix="Witch-hunter's",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of Teleportation",
        base_price=3000,
        perfect_price=10000,
        perfect_rolls="+2Assa/Tele",
        notes="GG PvP Trapsin Teleport"
    ),
    
    # Assassin's of the Magus
    GGCombo(
        prefix="Assassin's",
        base_items=["Amulet"],
        base_codes=["amu"],
        suffix="of the Magus",
        base_price=1200,
        perfect_price=4500,
        perfect_rolls="+2Assa/20fcr",
        notes="GG Trapsin amulet"
    ),
    
    # Sorceress's of the Magus
    GGCombo(
        prefix="Sorceress's",
        base_items=["Amulet"],
        base_codes=["amu"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+2Sorc/20fcr",
        notes="GG Sorc amulet"
    ),
    
    # Amazon's of the Magus
    GGCombo(
        prefix="Amazon's",
        base_items=["Amulet"],
        base_codes=["amu"],
        suffix="of the Magus",
        base_price=1000,
        perfect_price=3500,
        perfect_rolls="+2Zon/20fcr",
        notes="GG Zon amulet"
    ),
    
    # Barbarian's of the Magus
    GGCombo(
        prefix="Barbarian's",
        base_items=["Amulet"],
        base_codes=["amu"],
        suffix="of the Magus",
        base_price=800,
        perfect_price=2500,
        perfect_rolls="+2Barb/20fcr",
        notes="GG Warcry Barb amulet"
    ),
    
    # Glacial of the Magus
    GGCombo(
        prefix="Glacial",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Cold/20fcr",
        notes="GG Cold Druid circlet"
    ),
    
    # Volcanic of the Magus
    GGCombo(
        prefix="Volcanic",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Fire/20fcr",
        notes="GG Fire Druid circlet"
    ),
    
    # Blazing of the Magus
    GGCombo(
        prefix="Blazing",
        base_items=["Circlet", "Coronet", "Tiara", "Diadem"],
        base_codes=["ci0", "ci1", "ci2", "ci3"],
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Fire/20fcr",
        notes="GG Fire Sorc circlet"
    ),
    
    # Jeweler's of the Whale
    GGCombo(
        prefix="Jeweler's",
        base_items=["Monarch", "Luna", "Hyperion", "Ward"],
        base_codes=["uit", "ulg", "ush", "uws"],
        suffix="of the Whale",
        base_price=800,
        perfect_price=2500,
        perfect_rolls="4os/100life",
        notes="High value shield"
    ),
    
    # Jeweler's of the Titan
    GGCombo(
        prefix="Jeweler's",
        base_items=["Monarch", "Luna", "Hyperion", "Ward"],
        base_codes=["uit", "ulg", "ush", "uws"],
        suffix="of the Titan",
        base_price=600,
        perfect_price=1500,
        perfect_rolls="4os/30str",
        notes="Spirit shield variant"
    ),
    
    # Artisan's of Deflecting
    GGCombo(
        prefix="Artisan's",
        base_items=["Monarch", "Luna", "Hyperion", "Ward"],
        base_codes=["uit", "ulg", "ush", "uws"],
        suffix="of Deflecting",
        base_price=1500,
        perfect_price=5000,
        perfect_rolls="3os/20fbr",
        notes="3os JMOD variant"
    ),
]


def format_fg(fg: float) -> str:
    """Format FG for display."""
    if fg >= 1:
        return str(int(fg))
    return str(fg).rstrip('0').rstrip('.')


def main():
    script_dir = Path(__file__).resolve().parent
    app_dir = script_dir.parent
    
    # Load configs
    with open(app_dir / "config" / "magic_affix_prices.yml") as f:
        prices = yaml.safe_load(f) or {}
    
    with open(app_dir / "config" / "affix_database_complete.yml") as f:
        db = yaml.safe_load(f) or {}
    
    with open(app_dir / "config" / "gg_affixes.yml") as f:
        gg = yaml.safe_load(f) or {}
    
    # Build single affix price lookup
    prefix_prices = {}
    suffix_prices = {}
    
    # From single_affix_values
    for name, info in prices.get("single_affix_values", {}).items():
        if isinstance(info, dict):
            fg = info.get("base_price", 0)
        else:
            fg = float(info) if info else 0
        
        if fg > 0:
            if name.startswith("of "):
                suffix_prices[name] = fg
            else:
                prefix_prices[name] = fg
    
    # From affix database
    for prefix_name, prefix_data in db.get("prefixes", {}).items():
        if prefix_name in prefix_prices:
            continue
        if isinstance(prefix_data, dict):
            if "variants" in prefix_data:
                max_price = max(v.get("base_price", 0) for v in prefix_data["variants"])
                if max_price > 0:
                    prefix_prices[prefix_name] = max_price
            elif "base_price" in prefix_data:
                prefix_prices[prefix_name] = prefix_data["base_price"]
    
    for suffix_name, suffix_data in db.get("suffixes", {}).items():
        if suffix_name in suffix_prices:
            continue
        if isinstance(suffix_data, dict):
            if "variants" in suffix_data:
                max_price = max(v.get("base_price", 0) for v in suffix_data["variants"])
                if max_price > 0:
                    suffix_prices[suffix_name] = max_price
            elif "base_price" in suffix_data:
                suffix_prices[suffix_name] = suffix_data["base_price"]
    
    # Build output
    output = []
    item_id = 1
    seen_keys = set()
    
    # 1. Add GG Combinations FIRST (highest priority)
    for combo in GG_COMBINATIONS:
        for base_item, base_code in zip(combo.base_items, combo.base_codes):
            key = f"{combo.prefix} {base_item} {combo.suffix}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            # Format: "Jeweler's Monarch of Deflecting | 2000-8000 FG | 4os/20fbr"
            enUS = f"{combo.prefix} {base_item} {combo.suffix} | {combo.base_price}-{combo.perfect_price} FG | {combo.perfect_rolls}"
            
            output.append({
                "id": item_id,
                "Key": key,
                "enUS": enUS,
                "category": "magic_combo",
                "quality": "magic",
                "base_code": base_code,
                "base_price": combo.base_price,
                "perfect_price": combo.perfect_price,
                "perfect_rolls": combo.perfect_rolls,
                "notes": combo.notes
            })
            item_id += 1
    
    # 2. Add single prefixes
    for name in sorted(prefix_prices.keys()):
        if name in seen_keys:
            continue
        
        fg = prefix_prices[name]
        if fg > 0:
            fg_text = format_fg(fg)
            output.append({
                "id": item_id,
                "Key": name,
                "enUS": f"{name} | {fg_text} FG",
                "category": "prefix",
                "quality": "magic"
            })
        else:
            output.append({
                "id": item_id,
                "Key": name,
                "enUS": name,
                "category": "prefix",
                "quality": "magic"
            })
        item_id += 1
    
    # 3. Add single suffixes
    for name in sorted(suffix_prices.keys()):
        if name in seen_keys:
            continue
        
        fg = suffix_prices[name]
        if fg > 0:
            fg_text = format_fg(fg)
            output.append({
                "id": item_id,
                "Key": name,
                "enUS": f"{name} | {fg_text} FG",
                "category": "suffix",
                "quality": "magic"
            })
        else:
            output.append({
                "id": item_id,
                "Key": name,
                "enUS": name,
                "category": "suffix",
                "quality": "magic"
            })
        item_id += 1
    
    # Sort: GG combos first, then prefixes, then suffixes
    def sort_key(item):
        cat = item.get("category", "")
        if cat == "magic_combo":
            return (0, item.get("perfect_price", 0), item.get("Key", ""))
        elif cat == "prefix":
            return (1, item.get("Key", ""))
        else:
            return (2, item.get("Key", ""))
    
    output.sort(key=sort_key)
    
    # Reassign IDs
    for i, item in enumerate(output, 1):
        item["id"] = i
    
    # Write output
    output_path = app_dir / "data" / "templates" / "item-nameaffixes.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Stats
    combos = sum(1 for item in output if item.get("category") == "magic_combo")
    prefixes = sum(1 for item in output if item.get("category") == "prefix")
    suffixes = sum(1 for item in output if item.get("category") == "suffix")
    
    print(f"Generated {len(output)} magic affix entries")
    print(f"  GG Combinations: {combos}")
    print(f"  Prefixes: {prefixes}")
    print(f"  Suffixes: {suffixes}")
    print(f"Output: {output_path}")
    
    # Show top GG combos
    print("\n=== TOP GG COMBINATIONS ===")
    gg_items = [item for item in output if item.get("category") == "magic_combo"]
    gg_items.sort(key=lambda x: -x.get("perfect_price", 0))
    for item in gg_items[:10]:
        print(f"  {item['enUS']}")


if __name__ == "__main__":
    main()
