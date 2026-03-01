#!/usr/bin/env python3
"""
Create a full D2R item-names.json with FG prices and base hints.
This file replaces the game's localization strings to show prices.
"""
import json
from pathlib import Path

# Base item codes and names
BASE_ITEMS = {
    # Elite shields
    "uit": "Monarch",
    "ulg": "Luna", 
    "ush": "Hyperion",
    "uws": "Ward",
    "uap": "Shako",
    
    # Elite armor
    "utp": "Archon Plate",
    "uhn": "Hellforge Plate",
    "urs": "Sacred Armor",
    "ula": "Wire Fleece",
    "uld": "Scarab Husk",
    "ung": "Wyrmhide",
    "uhw": "Great Hauberk",
    "uhn": "Boneweave",
    "ulg": "Kraken Shell",
    "umc": "Mage Plate",
    "upl": "Plate Mail",
    
    # Circlets
    "ci0": "Circlet",
    "ci1": "Coronet",
    "ci2": "Tiara",
    "ci3": "Diadem",
    
    # Misc
    "amu": "Amulet",
    "rin": "Ring",
    "jew": "Jewel",
    "cm3": "Grand Charm",
    "cm1": "Small Charm",
    
    # Keys
    "pk1": "Key of Terror",
    "pk2": "Key of Hate",
    "pk3": "Key of Destruction",
    "toa": "Token of Absolution",
    
    # Essences
    "eyz": "Essence of Suffering",
    "ebl": "Essence of Hatred",
    "egt": "Essence of Terror",
    "edt": "Essence of Destruction",
}

# Runes
RUNES = {f"r{i:02d}": name for i, name in enumerate([
    "El", "Eld", "Tir", "Nef", "Eth", "Ith", "Tal", "Ral", "Ort", "Thul",
    "Amn", "Sol", "Shael", "Dol", "Hel", "Io", "Lum", "Ko", "Fal", "Lem",
    "Pul", "Um", "Mal", "Ist", "Gul", "Vex", "Ohm", "Lo", "Sur", "Ber",
    "Jah", "Cham", "Zod"
], 1)}

# GG Uniques with prices
GG_UNIQUES = {
    "Harlequin Crest": ("ÿc;ÿcO[141def] ", "400 FG"),
    "Arachnid Mesh": ("ÿc;ÿcO[120ed] ", "700 FG"),
    "Griffons Eye": ("ÿc;ÿcO[-20/+15] ", "900 FG"),
    "Nightwings Veil": ("ÿc;ÿcO[15ed] ", "400 FG"),
    "War Traveler": ("ÿc;ÿcO[50mf] ", "400 FG"),
    "Gore Rider": ("ÿc8ÿcO[200ed] ", "140 FG"),
    "Herald Of Zakarum": ("ÿc8ÿcO[200ed] ", "125 FG"),
    "Skin Of The Vipermagi": ("ÿc8ÿcO[35allres] ", "100 FG"),
    "Vampire Gaze": ("ÿc;ÿcO[20dr/8ll] ", "500 FG"),
    "Stormshield": ("ÿc;ÿcO[35dr] ", "150 FG"),
    "Hellfire Torch": ("ÿc;ÿcO[20/20/20] ", "300 FG"),
    "Annihilus": ("ÿc1ÿcO[20/20/20] ", "2700 FG"),
    "Stone of Jordan": ("ÿc;", "850 FG"),
    "Maras Kaleidoscope": ("ÿc;ÿcO[30allres] ", "800 FG"),
    "Highlords Wrath": ("ÿc;", "275 FG"),
    "Andariels Visage": ("ÿc;ÿcO[15str] ", "200 FG"),
    "The Oculus": ("ÿc8ÿcO[30allres] ", "150 FG"),
    "Leviathan": ("ÿc8ÿcO[50dr] ", "115 FG"),
    "Ondals Wisdom": ("ÿc8ÿcO[3allskills] ", "100 FG"),
    "Gheed's Fortune": ("ÿc;ÿcO[40mf] ", "650 FG"),
}

# GG Set items
GG_SETS = {
    "Tal Rasha's Adjudication": ("ÿc;ÿcO[2skill/15res] ", "300 FG"),
    "Tal Rasha's Guardianship": ("ÿc;ÿcO[1skill/65life] ", "450 FG"),
    "Tal Rasha's Horadric Crest": ("ÿc;ÿcO[15dr] ", "200 FG"),
}

# Rune prices
RUNE_PRICES = {
    "r33": ("ÿc;", "1700 FG"),  # Zod
    "r31": ("ÿc1", "4200 FG"),  # Jah
    "r30": ("ÿc1", "2400 FG"),  # Ber
    "r32": ("ÿc;", "800 FG"),   # Cham
    "r29": ("ÿc1", "1100 FG"),  # Sur
    "r28": ("ÿc;", "800 FG"),   # Lo
    "r27": ("ÿc;", "600 FG"),   # Ohm
    "r26": ("ÿc;", "390 FG"),   # Vex
    "r25": ("ÿc;", "180 FG"),   # Gul
    "r24": ("ÿc;", "220 FG"),   # Ist
    "r23": ("ÿc8", "85 FG"),    # Mal
    "r22": ("ÿc8", "60 FG"),    # Um
    "r21": ("ÿc8", "40 FG"),    # Pul
    "r20": ("ÿc8", "30 FG"),    # Lem
    "r19": ("ÿc0", "15 FG"),    # Fal
    "r18": ("ÿc0", "25 FG"),    # Ko
    "r17": ("ÿc0", "15 FG"),    # Lum
    "r16": ("ÿc0", "10 FG"),    # Io
    "r15": ("ÿc0", "15 FG"),    # Hel
    "r14": ("ÿc5", "5 FG"),     # Dol
    "r13": ("ÿc5", "5 FG"),     # Shael
    "r12": ("ÿc5", "5 FG"),     # Sol
    "r11": ("ÿc5", "5 FG"),     # Amn
    "r10": ("ÿc5", "3 FG"),     # Thul
    "r09": ("ÿc5", "3 FG"),     # Ort
    "r08": ("ÿc0", "10 FG"),    # Ral
    "r07": ("ÿc5", "3 FG"),     # Tal
    "r06": ("ÿc5", "2 FG"),     # Ith
    "r05": ("ÿc5", "2 FG"),     # Eth
    "r04": ("ÿc5", "2 FG"),     # Nef
    "r03": ("ÿc5", "2 FG"),     # Tir
    "r02": ("ÿc5", "2 FG"),     # Eld
    "r01": ("ÿc8", "30 FG"),    # El
}

# Base item hints
BASE_HINTS = {
    "uit": "[Stormshield | Spirit: 4os | Phoenix: 4os | ★ GG magic]",
    "uap": "[Enigma: 3os | 524def | Fortitude: 4os]",
    "utp": "[Enigma: 3os | Fortitude: 4os | Chains: 4os]",
    "ci0": "[★ GG magic: 2skill/20fcr]",
    "ci3": "[Diadem: ilvl=99 always]",
    "amu": "[★ GG magic: 2skill/20fcr]",
    "rin": "[SoJ | BK | Wisp | Raven | Dwarf | Nagel | ★ GG magic]",
}

def main():
    output = []
    item_id = 1
    
    # Add runes
    for code, name in sorted(RUNES.items(), key=lambda x: int(x[0][1:])):
        color, price = RUNE_PRICES.get(code, ("ÿc5", "1 FG"))
        hint = BASE_HINTS.get(code, "")
        enus = f"{name} Rune {color}{price}ÿc0"
        output.append({"id": item_id, "Key": code, "enUS": enus})
        item_id += 1
    
    # Add base items with hints
    for code, name in sorted(BASE_ITEMS.items()):
        hint = BASE_HINTS.get(code, "")
        if hint:
            enus = f"{name} ÿc0{hint}"
        else:
            enus = name
        output.append({"id": item_id, "Key": code, "enUS": enus})
        item_id += 1
    
    # Add uniques
    for name, (prefix, price) in sorted(GG_UNIQUES.items()):
        enus = f"{name} {prefix}[{price}]ÿc0"
        output.append({"id": item_id, "Key": name, "enUS": enus})
        item_id += 1
    
    # Add set items
    for name, (prefix, price) in sorted(GG_SETS.items()):
        enus = f"{name} {prefix}[{price}]ÿc0"
        output.append({"id": item_id, "Key": name, "enUS": enus})
        item_id += 1
    
    # Add magic affixes from gg_affixes.yml
    output.append({"id": item_id, "Key": "Jeweler's", "enUS": "ÿc1[$$$] Jeweler'sÿc0"})
    item_id += 1
    output.append({"id": item_id, "Key": "of Deflecting", "enUS": "ÿc9of Deflecting ÿc1[$$$]ÿc0"})
    item_id += 1
    output.append({"id": item_id, "Key": "of the Magus", "enUS": "ÿc9of the Magus ÿc1[$$$]ÿc0"})
    item_id += 1
    output.append({"id": item_id, "Key": "of Teleportation", "enUS": "ÿc9of Teleportation ÿc1[$$$]ÿc0"})
    item_id += 1
    
    # Save
    Path("output").mkdir(exist_ok=True)
    with open("output/item-names.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Created {len(output)} items")
    print(f"Runes: {len(RUNES)}")
    print(f"Base items: {len(BASE_ITEMS)}")
    print(f"Uniques: {len(GG_UNIQUES)}")
    print(f"Sets: {len(GG_SETS)}")

if __name__ == "__main__":
    main()
