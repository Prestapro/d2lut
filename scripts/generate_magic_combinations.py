#!/usr/bin/env python3
"""
Generate magic item combinations with full pricing for D2R loot filter.

Output format examples:
- Jeweler's Monarch of Deflecting | 2000-8000 FG | 4os/20fbr
- Venomous Circlet of the Magus | 4000-20000 FG | +3PnB/20fcr
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class MagicCombo:
    """Magic item combination with full pricing."""
    prefix: str
    base_item: str
    base_code: str
    suffix: str
    base_price: int
    perfect_price: int
    perfect_rolls: str  # e.g., "4os/20fbr"
    notes: str
    item_types: list[str]
    min_ilvl: int

# GG Magic Item Combinations with perfect roll info
GG_COMBINATIONS = [
    # JMOD - Jeweler's Monarch of Deflecting
    MagicCombo(
        prefix="Jeweler's",
        base_item="Monarch",
        base_code="uit",
        suffix="of Deflecting",
        base_price=2000,
        perfect_price=8000,
        perfect_rolls="4os/20fbr",
        notes="JMOD - GG for Spirit/Phoenix",
        item_types=["uit", "ulg", "ush", "uws"],
        min_ilvl=50
    ),
    
    # Venomous Circlet of the Magus (Poison Necro)
    MagicCombo(
        prefix="Venomous",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=4000,
        perfect_price=20000,
        perfect_rolls="+3PnB/20fcr",
        notes="GG Poison Necro circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Necromancer's Circlet of the Magus
    MagicCombo(
        prefix="Necromancer's",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=3000,
        perfect_price=15000,
        perfect_rolls="+2Nec/20fcr",
        notes="GG Necro circlet/amulet",
        item_types=["ci0", "ci2", "ci3", "amu"],
        min_ilvl=90
    ),
    
    # Berserker's Circlet of Teleportation (PvP Barb)
    MagicCombo(
        prefix="Berserker's",
        base_item="Circlet",
        base_code="ci0",
        suffix="of Teleportation",
        base_price=5000,
        perfect_price=15000,
        perfect_rolls="+3War/Tele",
        notes="GG PvP Barb Teleport circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Necromancer's Circlet of Teleportation
    MagicCombo(
        prefix="Necromancer's",
        base_item="Circlet",
        base_code="ci0",
        suffix="of Teleportation",
        base_price=4000,
        perfect_price=12000,
        perfect_rolls="+2Nec/Tele",
        notes="GG PvP Necro Teleport",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Druid's Circlet of the Magus
    MagicCombo(
        prefix="Druid's",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=2500,
        perfect_price=10000,
        perfect_rolls="+2Dru/20fcr",
        notes="GG Windy Druid circlet",
        item_types=["ci0", "ci2", "ci3", "amu"],
        min_ilvl=90
    ),
    
    # Hierophant's Circlet of the Magus (Hammerdin)
    MagicCombo(
        prefix="Hierophant's",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=2500,
        perfect_price=10000,
        perfect_rolls="+3Com/20fcr",
        notes="GG Hammerdin circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Arch-Angel's Amulet of the Magus
    MagicCombo(
        prefix="Arch-Angel's",
        base_item="Amulet",
        base_code="amu",
        suffix="of the Magus",
        base_price=1500,
        perfect_price=5000,
        perfect_rolls="+2all/20fcr",
        notes="GG caster amulet",
        item_types=["amu"],
        min_ilvl=90
    ),
    
    # Paladin's Amulet of the Magus
    MagicCombo(
        prefix="Paladin's",
        base_item="Amulet",
        base_code="amu",
        suffix="of the Magus",
        base_price=1800,
        perfect_price=7000,
        perfect_rolls="+2Pal/20fcr",
        notes="GG Hammerdin amulet",
        item_types=["amu"],
        min_ilvl=90
    ),
    
    # Powered Circlet of the Magus (Lightning Sorc)
    MagicCombo(
        prefix="Powered",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=2000,
        perfect_price=8000,
        perfect_rolls="+3Lit/20fcr",
        notes="GG Lightning Sorc circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Charged Circlet of the Magus
    MagicCombo(
        prefix="Charged",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=1800,
        perfect_price=7000,
        perfect_rolls="+3Lit/20fcr",
        notes="GG Lightning Sorc (alt)",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Keeper's Circlet of the Magus (Summon Druid)
    MagicCombo(
        prefix="Keeper's",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=2000,
        perfect_price=8000,
        perfect_rolls="+3Sum/20fcr",
        notes="GG Summon Druid circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Echoing Circlet of the Magus (Warcry Barb)
    MagicCombo(
        prefix="Echoing",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=2000,
        perfect_price=8000,
        perfect_rolls="+3War/20fcr",
        notes="GG Warcry Barb circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Cunning Circlet of the Magus (Trapsin)
    MagicCombo(
        prefix="Cunning",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Trap/20fcr",
        notes="GG Trapsin circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Golemlord's Circlet of the Magus (Summon Necro)
    MagicCombo(
        prefix="Golemlord's",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Sum/20fcr",
        notes="GG Summon Necro circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Shimmering Grand Charm of Vita (Skiller)
    MagicCombo(
        prefix="Shimmering",
        base_item="Grand Charm",
        base_code="cm3",
        suffix="of Vita",
        base_price=800,
        perfect_price=2500,
        perfect_rolls="+1sk/45life",
        notes="GG Skiller GC",
        item_types=["cm3"],
        min_ilvl=50
    ),
    
    # Crimson Jewel of Fervent (40/15)
    MagicCombo(
        prefix="Crimson",
        base_item="Jewel",
        base_code="jew",
        suffix="of Fervent",
        base_price=1500,
        perfect_price=5000,
        perfect_rolls="40ed/15ias",
        notes="GG 40/15 Jewel",
        item_types=["jew"],
        min_ilvl=0
    ),
    
    # Fervent Jewel of Freedom (15/-15)
    MagicCombo(
        prefix="Fervent",
        base_item="Jewel",
        base_code="jew",
        suffix="of Freedom",
        base_price=600,
        perfect_price=2000,
        perfect_rolls="15ias/-15req",
        notes="GG LLD Jewel",
        item_types=["jew"],
        min_ilvl=0
    ),
    
    # Lion Branded Circlet of the Magus
    MagicCombo(
        prefix="Lion Branded",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Com/20fcr",
        notes="GG Pally Combat circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Shadow Circlet of the Magus
    MagicCombo(
        prefix="Shadow",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3SD/20fcr",
        notes="GG Shadow Dancer circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Freezing Circlet of the Magus
    MagicCombo(
        prefix="Freezing",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+3Cold/20fcr",
        notes="GG Cold Sorc circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Grim Circlet of the Magus
    MagicCombo(
        prefix="Grim",
        base_item="Circlet",
        base_code="ci0",
        suffix="of the Magus",
        base_price=1200,
        perfect_price=5000,
        perfect_rolls="+3Fire/20fcr",
        notes="GG Fire Sorc circlet",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Witch-hunter's Circlet of Teleportation
    MagicCombo(
        prefix="Witch-hunter's",
        base_item="Circlet",
        base_code="ci0",
        suffix="of Teleportation",
        base_price=3000,
        perfect_price=10000,
        perfect_rolls="+2Assa/Tele",
        notes="GG PvP Trapsin Teleport",
        item_types=["ci0", "ci2", "ci3"],
        min_ilvl=90
    ),
    
    # Assassin's Amulet of the Magus
    MagicCombo(
        prefix="Assassin's",
        base_item="Amulet",
        base_code="amu",
        suffix="of the Magus",
        base_price=1200,
        perfect_price=4500,
        perfect_rolls="+2Assa/20fcr",
        notes="GG Trapsin amulet",
        item_types=["amu"],
        min_ilvl=90
    ),
    
    # Sorceress's Amulet of the Magus
    MagicCombo(
        prefix="Sorceress's",
        base_item="Amulet",
        base_code="amu",
        suffix="of the Magus",
        base_price=1500,
        perfect_price=6000,
        perfect_rolls="+2Sorc/20fcr",
        notes="GG Sorc amulet",
        item_types=["amu"],
        min_ilvl=90
    ),
]

# Base item code to name mapping
BASE_NAMES = {
    "uit": "Monarch",
    "ulg": "Luna", 
    "ush": "Hyperion",
    "uws": "Ward",
    "ci0": "Circlet",
    "ci1": "Coronet",
    "ci2": "Tiara",
    "ci3": "Diadem",
    "amu": "Amulet",
    "rin": "Ring",
    "cm3": "Grand Charm",
    "cm1": "Small Charm",
    "jew": "Jewel",
}


def generate_magic_combo_entries() -> list[dict]:
    """Generate loot filter entries for magic item combinations."""
    entries = []
    entry_id = 10000  # Start at high ID to avoid conflicts
    
    for combo in GG_COMBINATIONS:
        # Generate entry for each item type
        for item_code in combo.item_types:
            base_name = BASE_NAMES.get(item_code, combo.base_item)
            
            # Format: "Jeweler's Monarch of Deflecting | 2000-8000 FG | 4os/20fbr"
            full_name = f"{combo.prefix} {base_name} {combo.suffix}"
            price_range = f"{combo.base_price}-{combo.perfect_price} FG"
            
            enUS = f"{full_name} | {price_range} | {combo.perfect_rolls}"
            
            entry = {
                "id": entry_id,
                "Key": f"magic:{item_code}:{combo.prefix}:{combo.suffix}",
                "enUS": enUS,
                "category": "magic",
                "quality": "magic",
                "base_price": combo.base_price,
                "perfect_price": combo.perfect_price,
                "perfect_rolls": combo.perfect_rolls,
                "notes": combo.notes,
                "min_ilvl": combo.min_ilvl
            }
            entries.append(entry)
            entry_id += 1
    
    return entries


def generate_affix_hints() -> list[dict]:
    """Generate hints for individual affixes showing GG combo potential."""
    entries = []
    entry_id = 20000
    
    # Map affixes to their combo potentials
    combo_hints = {}
    
    for combo in GG_COMBINATIONS:
        # Prefix hints
        if combo.prefix not in combo_hints:
            combo_hints[combo.prefix] = {
                "combos": [],
                "max_price": 0
            }
        combo_hints[combo.prefix]["combos"].append(f"+ {combo.suffix}")
        combo_hints[combo.prefix]["max_price"] = max(
            combo_hints[combo.prefix]["max_price"], 
            combo.perfect_price
        )
        
        # Suffix hints
        if combo.suffix not in combo_hints:
            combo_hints[combo.suffix] = {
                "combos": [],
                "max_price": 0
            }
        combo_hints[combo.suffix]["combos"].append(f"+ {combo.prefix}")
        combo_hints[combo.suffix]["max_price"] = max(
            combo_hints[combo.suffix]["max_price"],
            combo.perfect_price
        )
    
    # Generate affix entries with combo hints
    for affix_name, hint_data in combo_hints.items():
        if hint_data["max_price"] >= 5000:
            tier = "GG"
            color = "ÿc1"  # Red
        elif hint_data["max_price"] >= 2000:
            tier = "HIGH"
            color = "ÿc;"  # Purple
        else:
            tier = "MID"
            color = "ÿc8"  # Orange
        
        combo_list = sorted(set(hint_data["combos"]))[:3]  # Top 3 combos
        combo_str = " | ".join(combo_list)
        
        enUS = f"{affix_name} | Max: {hint_data['max_price']} FG | {combo_str}"
        
        entries.append({
            "id": entry_id,
            "Key": affix_name,
            "enUS": enUS,
            "tier": tier,
            "max_combo_price": hint_data["max_price"]
        })
        entry_id += 1
    
    return entries


def main():
    """Generate magic combination files."""
    script_dir = Path(__file__).parent
    output_dir = script_dir.parent / "data" / "templates"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate magic combinations
    combo_entries = generate_magic_combo_entries()
    combo_output = output_dir / "item-magic-combos.json"
    with open(combo_output, "w", encoding="utf-8") as f:
        json.dump(combo_entries, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(combo_entries)} magic combination entries to {combo_output}")
    
    # Generate affix hints
    affix_hints = generate_affix_hints()
    affix_output = output_dir / "item-affix-hints.json"
    with open(affix_output, "w", encoding="utf-8") as f:
        json.dump(affix_hints, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(affix_hints)} affix hint entries to {affix_output}")
    
    # Print summary
    print("\n=== GG Magic Combinations ===")
    for combo in sorted(GG_COMBINATIONS, key=lambda x: -x.perfect_price)[:10]:
        print(f"  {combo.prefix} {combo.base_item} {combo.suffix}")
        print(f"    Price: {combo.base_price}-{combo.perfect_price} FG")
        print(f"    Perfect: {combo.perfect_rolls}")
        print()


if __name__ == "__main__":
    main()
