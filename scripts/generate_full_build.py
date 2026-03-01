#!/usr/bin/env python3
"""Generate complete D2R loot filter with FG prices from static configs."""
import json
import yaml
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent

# Rune code to name mapping
RUNE_MAP = {
    "r01": "El", "r02": "Eld", "r03": "Tir", "r04": "Nef", "r05": "Eth", "r06": "Ith",
    "r07": "Tal", "r08": "Ral", "r09": "Ort", "r10": "Thul", "r11": "Amn", "r12": "Sol",
    "r13": "Shael", "r14": "Dol", "r15": "Hel", "r16": "Io", "r17": "Lum", "r18": "Ko",
    "r19": "Fal", "r20": "Lem", "r21": "Pul", "r22": "Um", "r23": "Mal", "r24": "Ist",
    "r25": "Gul", "r26": "Vex", "r27": "Ohm", "r28": "Lo", "r29": "Sur", "r30": "Ber",
    "r31": "Jah", "r32": "Cham", "r33": "Zod"
}

# High value uniques with approximate FG prices
UNIQUE_PRICES = {
    # S-tier uniques
    "Harlequin Crest": 30, "Shako": 30,
    "Arachnid Mesh": 25,
    "Stormshield": 15,
    "Skin of the Vipermagi": 10,
    "Mara's Kaleidoscope": 20,
    "Stone of Jordan": 15,
    "Bul-Kathos' Wedding Band": 15,
    "Raven Frost": 5,
    "Sandstorm Trek": 8,
    "War Traveler": 5,
    "Waterwalk": 3,
    "Silkweave": 2,
    "Magefist": 3,
    "Frostburn": 2,
    "Chance Guards": 3,
    "Laying of Hands": 5,
    "Bloodfist": 1,
    "String of Ears": 5,
    "Thundergod's Vigor": 3,
    "Snowclash": 2,
    "Nosferatu's Coil": 5,
    "Goldwrap": 2,
    "Tal Rasha's Adjudication": 5,
    "Tal Rasha's Horadric Crest": 3,
    "Tal Rasha's Guardianship": 10,
    "Tal Rasha's Fine-spun Cloth": 3,
    "Tal Rasha's Lidless Eye": 2,
    "Immortal King's Will": 3,
    "Immortal King's Stone Crusher": 5,
    "Immortal King's Soul Cage": 3,
    "Immortal King's Detail": 1,
    "Immortal King's Forge": 1,
    "Immortal King's Pillar": 1,
    "Natalya's Totem": 2,
    "Natalya's Mark": 3,
    "Natalya's Shadow": 2,
    "Natalya's Soul": 1,
    "Natalya's Shell": 1,
    "Aldur's Stony Gaze": 2,
    "Aldur's Rhythm": 3,
    "Aldur's Advance": 2,
    "Aldur's Deception": 1,
    "Aldur's Watchtower": 1,
    "Griswold's Heart": 3,
    "Griswold's Valor": 2,
    "Griswold's Redemption": 5,
    "Griswold's Honor": 3,
    "Griswold's Legacy": 2,
    "Trang-Oul's Guise": 2,
    "Trang-Oul's Scales": 2,
    "Trang-Oul's Wing": 5,
    "Trang-Oul's Claws": 1,
    "Trang-Oul's Girth": 1,
    "Trang-Oul's Avatar": 3,
    # Rings/Amulets
    "The Oculus": 5,
    "Wizardspike": 5,
    "Heart of the Oak": 15,
    "Call to Arms": 20,
    "Spirit": 8,
    "Enigma": 50,
    "Chains of Honor": 15,
    "Bramble": 10,
    "Fortitude": 12,
    "Phoenix": 10,
    "Dream": 10,
    "Doom": 8,
    "Breath of the Dying": 30,
    "Last Wish": 25,
    "Grief": 20,
    "Death": 10,
    "Oath": 5,
    "Destruction": 8,
    "Faith": 15,
    "Ice": 10,
    "Brand": 8,
    "Wrath": 5,
    "Fury": 3,
    "Kingslayer": 5,
    "Hand of Justice": 3,
    "Dragon": 8,
    "Prudence": 3,
    "Sanctuary": 3,
    "Stone": 3,
    "Duress": 2,
    "Lionheart": 1,
    "Smoke": 1,
    "Wealth": 1,
    "Treachery": 2,
    "Principle": 1,
    "Peace": 1,
    "Myth": 1,
    "Bone": 3,
    "Rain": 2,
    "Gloom": 2,
    "Enlightenment": 1,
    "Exile": 15,
    "Delirium": 10,
    "Andariel's Visage": 8,
    "Giant's Skull": 3,
    "Crown of Thieves": 3,
    "Vampire Gaze": 5,
    "Stealskull": 2,
    "Tals Mask": 3,
    "Rockstopper": 2,
    "Darksight Helm": 1,
    "Blackhorn's Face": 2,
    "Valkyrie Wing": 2,
    "Veil of Steel": 2,
    "Crown of Ages": 20,
    "Grim Helm": 1,
    "Bone Visage": 2,
    "Spired Helm": 2,
    "Diadem": 5,
    "Tiara": 3,
    "Coronet": 2,
    "Circlet": 1,
    # Weapons
    "Windforce": 15,
    "Eaglehorn": 5,
    "Messerschmidt's Reaver": 3,
    "Cranebeak": 5,
    "Boneslayer Blade": 2,
    "Butcher's Pupil": 1,
    "Bloodletter": 1,
    "Blade of Ali Baba": 3,
    "Gull": 2,
    "Milabrega's Orb": 0.5,
    "Isenhart's Lightbrand": 0.5,
    "Sazabi's Cobalt Redeemer": 3,
    "Bul-Kathos' Sacred Charge": 5,
    "Bul-Kathos' Tribal Guardian": 3,
    "The Grandfather": 10,
    "Doombringer": 5,
    "Lightsabre": 5,
    "Azurewrath": 8,
    "Frostwind": 3,
    "Headstriker": 2,
    "Bloodmoon": 3,
    "The Patriarch": 1,
    "Spellsteel": 2,
    "Demonlimb": 3,
    "Hellrack": 2,
    "Arm of King Leoric": 5,
    "Blackhand Key": 2,
    "Boneshade": 5,
    "Death's Web": 30,
    "Mang Song's Lesson": 5,
    "Eschuta's Temper": 8,
    "Ormus' Robes": 5,
    "The Cranium Basher": 3,
    "Windhammer": 3,
    "Earthshifter": 3,
    "Titan's Revenge": 8,
    "Lycander's Flank": 3,
    "Lycander's Aim": 5,
    "Gargoyle's Bite": 2,
    "Demon's Arch": 2,
    "Wraith Flight": 2,
    "Gimmershred": 2,
    "Stormladder": 1,
    "Shadow Killer": 2,
    "Firelizard's Talons": 5,
    "Jade Talon": 3,
    "Bartuc's Cut-throat": 5,
    "Shadow Dancer": 10,
    "Natalya's Mark": 3,
    "Upheaval": 2,
    "Stone Crusher": 2,
    "Schaefer's Hammer": 5,
    "Horizon's Cyclone": 2,
    "The Atlantean": 2,
    "Sureshrill Frost": 1,
    "Splash of Havoc": 1,
    "Baranar's Star": 5,
    "Lightsabre": 5,
    "Nord's Tenderizer": 3,
    "Darkfall": 2,
    "Spire of Honor": 2,
    "The Gavel of Pike": 1,
    "Heaven's Light": 2,
    "The Meat Scraper": 2,
    "Steelpillar": 2,
    "Spire of Lazarus": 2,
    "Pierre's Ribcage": 1,
    "Heaven's Brethren": 1,
    "Duriel's Shell": 3,
    "Que-Hegan's Wisdom": 2,
    "Crow Caw": 2,
    "Ironpelt": 2,
    "Spiritforge": 2,
    "Gladiator's Bane": 3,
    "Black Hades": 2,
    "Steel Carapace": 3,
    "Leviathan": 8,
    "Tyrael's Might": 30,
    "Templar's Might": 5,
    "Steel Shaft": 2,
    "Skin of the Flayed One": 2,
    "The Spirit Shroud": 2,
    "Twitchthroe": 1,
    "Victor's Silks": 1,
    "Greyform": 1,
    "Sparking Mail": 0.5,
    "Jason's Parrying Sword": 0.5,
    "Swordback Hold": 1,
    "Steelclash": 1,
    "Wall of the Eyeless": 1,
    "Umbral Disk": 1,
    "Stormguild": 1,
    "Tiamat's Rebuke": 2,
    "Mosers Blessed Circle": 2,
    "Lance Guard": 1,
    "Gerke's Sanctuary": 3,
    "Medusa's Gaze": 5,
    "Spirit Ward": 5,
    "Lidless Wall": 3,
    "Head Hunter's Glory": 3,
    "Darkforge Spawn": 2,
    "Troll Nest": 2,
    "Blade Barrier": 1,
    "Heater": 1,
    "Hyperion": 1,
    "Monarch": 5,
    "Aegis": 2,
    "Ward": 1,
    # Misc items
    "Annihilus": 50,
    "Hellfire Torch": 30,
    "Gheed's Fortune": 5,
    "Key of Terror": 0.5,
    "Key of Hate": 0.5,
    "Key of Destruction": 0.5,
    "Token of Absolution": 2,
}

def load_rune_prices():
    """Load rune prices from config."""
    with open(APP_DIR / "config" / "rune_prices.yml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("prices", {})

def clean_existing_price(text):
    """Remove existing FG price tag from text."""
    # Match patterns like " | 5 FG", " | 0.5 FG", " [50 FG]", etc.
    patterns = [
        r'\s*\|\s*\d+(?:\.\d+)?\s*FG\s*$',
        r'\s*\[\d+(?:\.\d+)?\s*FG\]\s*$',
        r'\s*\(\d+(?:\.\d+)?\s*FG\)\s*$',
        r'\s*\d+(?:\.\d+)?\s*FG\s*$',
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text.strip()

def format_fg_price(price):
    """Format FG price for display."""
    if price >= 1:
        return f"{int(price)}"
    else:
        return f"{price:.1f}"

def main():
    print("Loading item names...")
    input_path = APP_DIR / "data" / "templates" / "item-names-full.json"
    if not input_path.exists():
        input_path = APP_DIR / "data" / "templates" / "item-names.json"
    with open(input_path, "r", encoding="utf-8") as f:
        items = json.load(f)
    
    print("Loading rune prices...")
    rune_prices = load_rune_prices()
    
    print("Processing items...")
    items_with_prices = 0
    
    for item in items:
        key = item.get("Key", "")
        enUS = item.get("enUS", "")
        
        # Clean existing price
        clean_name = clean_existing_price(enUS)
        
        price = None
        
        # Check if it's a rune
        if key.startswith("r") and key[1:].isdigit():
            rune_code = key
            rune_name = RUNE_MAP.get(rune_code, "")
            if rune_name and rune_name in rune_prices:
                price = rune_prices[rune_name]
        # Check if it's in unique prices (by name)
        if not price:
            for unique_name, unique_price in UNIQUE_PRICES.items():
                if unique_name.lower() in clean_name.lower():
                    price = unique_price
                    break
        
        # If we found a price, update the item
        if price is not None and price > 0:
            item["enUS"] = f"{clean_name} | {format_fg_price(price)} FG"
            items_with_prices += 1
        else:
            # Keep the cleaned name (or original if no price)
            item["enUS"] = clean_name
    
    print(f"Added prices to {items_with_prices} items")
    
    # Create output directory
    output_dir = APP_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write output
    output_path = output_dir / "item-names.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    
    print(f"Wrote {len(items)} items to {output_path}")
    
    # Generate item-nameaffixes.json for GG affixes
    print("\nGenerating affixes...")
    affixes = []
    
    # GG prefixes
    gg_prefixes = [
        ("Jeweler's", 2000, "4os"),
        ("Artisan's", 500, "3os"),
        ("Cruel", 50, "300ed"),
        ("Fletcher's", 100, "+3 Bow"),
        ("Lancer's", 80, "+3 Jav"),
        ("Rose Branded", 200, "+3 Pala"),
        ("Harpoonist's", 100, "+3 Jav"),
        ("Volcanic", 80, "+3 Fire"),
        ("Powered", 80, "+3 Light"),
        ("Glacial", 80, "+3 Cold"),
        ("Venomous", 100, "+3 PnB"),
        ("Entrapping", 150, "+3 Traps"),
        ("Nature's", 100, "+3 Elem"),
        ("Fungal", 100, "+3 PnB"),
        ("Golemlord's", 50, "+3 Summ"),
    ]
    
    # GG suffixes
    gg_suffixes = [
        ("of Deflecting", 1000, "20fbr"),
        ("of the Magus", 500, "20fcr"),
        ("of Quickness", 500, "40ias"),
        ("of the Titan", 200, "+20str"),
        ("of Vita", 100, "+41-50 life"),
        ("of the Whale", 80, "+81-100 life"),
        ("of Good Luck", 150, "35mf"),
        ("of Fortune", 50, "25mf"),
        ("of Sustenance", 30, "+31-40 life"),
        ("of Alacrity", 80, "20ias"),
        ("of the Apprentice", 50, "15fcr"),
        ("of the Bear", 50, "KB"),
        ("of Simplicity", 30, "-req"),
        ("of the Squid", 25, "+61-80 life"),
    ]
    
    # Add prefixes
    for name, price, note in gg_prefixes:
        affixes.append({
            "id": len(affixes) + 1,
            "Key": name,
            "enUS": f"{name} ÿc1[{format_fg_price(price)} FG]ÿc0 {note}"
        })
    
    # Add suffixes
    for name, price, note in gg_suffixes:
        affixes.append({
            "id": len(affixes) + 1,
            "Key": name,
            "enUS": f"{name} ÿc1[{format_fg_price(price)} FG]ÿc0 {note}"
        })
    
    # Write affixes
    affix_path = output_dir / "item-nameaffixes.json"
    with open(affix_path, "w", encoding="utf-8") as f:
        json.dump(affixes, f, indent=2, ensure_ascii=False)
    
    print(f"Wrote {len(affixes)} affixes to {affix_path}")
    
    # Generate item-runes.json with prices
    print("\nGenerating runes...")
    runes = []
    for i, (code, name) in enumerate(RUNE_MAP.items(), 1):
        price = rune_prices.get(name, 0)
        if price > 0:
            runes.append({
                "id": i,
                "Key": code,
                "enUS": f"{name} Rune ÿc1[{format_fg_price(price)} FG]ÿc0"
            })
    
    runes_path = output_dir / "item-runes.json"
    with open(runes_path, "w", encoding="utf-8") as f:
        json.dump(runes, f, indent=2, ensure_ascii=False)
    
    print(f"Wrote {len(runes)} runes to {runes_path}")
    
    print("\n=== Build complete ===")
    print(f"Output directory: {output_dir}")
    print(f"- item-names.json: {len(items)} items ({items_with_prices} with prices)")
    print(f"- item-nameaffixes.json: {len(affixes)} affixes")
    print(f"- item-runes.json: {len(runes)} runes")

if __name__ == "__main__":
    main()
