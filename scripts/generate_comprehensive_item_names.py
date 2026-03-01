#!/usr/bin/env python3
"""
Comprehensive item-names.json generator with FG prices.
Combines data from multiple config sources to maximize coverage.
"""

import json
import yaml
import re
from pathlib import Path
from typing import Any

# Item name mappings
RUNE_NAMES = {
    "r01": "El Rune", "r02": "Eld Rune", "r03": "Tir Rune", "r04": "Nef Rune",
    "r05": "Eth Rune", "r06": "Ith Rune", "r07": "Tal Rune", "r08": "Ral Rune",
    "r09": "Ort Rune", "r10": "Thul Rune", "r11": "Amn Rune", "r12": "Sol Rune",
    "r13": "Shael Rune", "r14": "Dol Rune", "r15": "Hel Rune", "r16": "Io Rune",
    "r17": "Lum Rune", "r18": "Ko Rune", "r19": "Fal Rune", "r20": "Lem Rune",
    "r21": "Pul Rune", "r22": "Um Rune", "r23": "Mal Rune", "r24": "Ist Rune",
    "r25": "Gul Rune", "r26": "Vex Rune", "r27": "Ohm Rune", "r28": "Lo Rune",
    "r29": "Sur Rune", "r30": "Ber Rune", "r31": "Jah Rune", "r32": "Cham Rune",
    "r33": "Zod Rune",
}

GEM_NAMES = {
    "gpb": "Perfect Sapphire", "gpg": "Perfect Emerald", "gpr": "Perfect Ruby",
    "gpv": "Perfect Amethyst", "gpw": "Perfect Diamond", "gpy": "Perfect Topaz",
    "skz": "Perfect Skull",
    # Flawed versions (less valuable)
    "glb": "Flawed Sapphire", "glg": "Flawed Emerald", "glr": "Flawed Ruby",
    "glv": "Flawed Amethyst", "glw": "Flawed Diamond", "gly": "Flawed Topaz",
    "skl": "Flawed Skull",
    # Flawless versions
    "gmb": "Flawless Sapphire", "gmg": "Flawless Emerald", "gmr": "Flawless Ruby",
    "gmv": "Flawless Amethyst", "gmw": "Flawless Diamond", "gmy": "Flawless Topaz",
    "skm": "Flawless Skull",
}

KEY_NAMES = {
    "pk1": "Key of Terror", "pk2": "Key of Hate", "pk3": "Key of Destruction",
}

# Unique item name mapping (internal key -> display name)
UNIQUE_DISPLAY_NAMES = {
    # Sorc Helms
    "griffons_eye": "Griffon's Eye",
    "nightwings_veil": "Nightwing's Veil",
    "harlequin_crest": "Harlequin Crest",
    # Pally Shields  
    "herald_of_zakarum": "Herald of Zakarum",
    "alma_negra": "Alma Negra",
    "akaran_targe": "Akaran Targe",
    # Belts
    "arachnid_mesh": "Arachnid Mesh",
    "verdungos_hearty_cord": "Verdungo's Hearty Cord",
    "thundergods_vigor": "Thundergod's Vigor",
    "strings_of_ears": "String of Ears",
    "razortail": "Razortail",
    "tal_rashas_fine_spun_cloth": "Tal Rasha's Fine-Spun Cloth",
    "nosferatus_coil": "Nosferatu's Coil",
    # Boots
    "wartraveler": "War Traveler",
    "sandstorm_trek": "Sandstorm Trek",
    "marrowwalk": "Marrowwalk",
    "waterwalk": "Waterwalk",
    "silkweave": "Silkweave",
    "gore_rider": "Gore Rider",
    "shadow_dancer": "Shadow Dancer",
    # Gloves
    "magefist": "Magefist",
    "frostburn": "Frostburn",
    "chance_guards": "Chance Guards",
    "draculs_grasp": "Dracul's Grasp",
    "steelrend": "Steelrend",
    "laying_of_hands": "Laying of Hands",
    "bloodfist": "Bloodfist",
    # Rings
    "stone_of_jordan": "Stone of Jordan",
    "bul_kathos_wedding_band": "Bul-Kathos' Wedding Band",
    "raven_frost": "Raven Frost",
    "dwarf_star": "Dwarf Star",
    "wisp_projector": "Wisp Projector",
    "natures_peace": "Nature's Peace",
    "carrion_wind": "Carrion Wind",
    "nagelring": "Nagelring",
    "manald_heal": "Manald Heal",
    # Amulets
    "maras_kaleidoscope": "Mara's Kaleidoscope",
    "tal_rashas_adjudication": "Tal Rasha's Adjudication",
    "highlords_wrath": "Highlord's Wrath",
    "cats_eye": "The Cat's Eye",
    "atmas_scarab": "Atma's Scarab",
    "seraphs_hymn": "Seraph's Hymn",
    "metalskin": "The Mahantem",
    "nokozan_relic": "Nokozan Relic",
    "tancreds_crow": "Tancred's Crow",
    # Armor
    "tal_rashas_guardianship": "Tal Rasha's Guardianship",
    "skin_of_the_vipermagi": "Skin of the Vipermagi",
    "shaftstop": "Shaftstop",
    "skullders_ire": "Skullder's Ire",
    "guardian_angel": "Guardian Angel",
    "arkaines_valor": "Arkaine's Valor",
    "tyraels_might": "Tyrael's Might",
    "ormus_robes": "Ormus' Robes",
    "crow_caw": "Crow Caw",
    "twitchthroe": "Twitchthroe",
    "vampire_gaze": "Vampire Gaze",
    "giant_skull": "Giant Skull",
    "andariels_visage": "Andariel's Visage",
    "stealskull": "Stealskull",
    "arreats_face": "Arreat's Face",
    "jalals_mane": "Jalal's Mane",
    "crown_of_ages": "Crown of Ages",
    "kiras_guardian": "Kira's Guardian",
    "valkyrie_wing": "Valkyrie Wing",
    "steelshade": "Steelshade",
    # Weapons - Javelins
    "titans_revenge": "Titan's Revenge",
    "thunderstroke": "Thunderstroke",
    "stygian_pillar": "Stygian Pillar",
    # Weapons - Bows
    "windforce": "Windforce",
    "eaglehorn": "Eaglehorn",
    "witchwild_string": "Witchwild String",
    "buriza_do_kyanon": "Buriza-Do Kyanon",
    "lasher": "Lasher",
    # Weapons - Wands
    "deaths_web": "Death's Web",
    "arm_of_king_leoric": "Arm of King Leoric",
    "boneflame": "Boneflame",
    "homunculus": "Homunculus",
    "darkforge_spawn": "Darkforge Spawn",
    # Weapons - Orbs
    "deaths_fathom": "Death's Fathom",
    "eschutas_temper": "Eschuta's Temper",
    "occulus": "The Oculus",
    # Weapons - Scepters
    "zakarums_hand": "Zakarum's Hand",
    "steelrend_scepter": "Steelrend",
    # Weapons - Swords
    "azurewrath": "Azurewrath",
    "lightsabre": "Lightsabre",
    "doombringer": "Doombringer",
    "bloodmoon": "Bloodmoon",
    # Weapons - Axes
    "death_cleaver": "Death Cleaver",
    # Weapons - Polearms
    "tomb_reaver": "Tomb Reaver",
    "stormspire": "Stormspire",
    # Weapons - Hammers
    "stormlash": "Stormlash",
    "schaefers_hammer": "Schaefer's Hammer",
    "earthshifter": "Earthshifter",
    "horizons_tornado": "Horizon's Tornado",
    # Weapons - Assassin Claws
    "bartucs_cutthroat": "Bartuc's Cut-Throat",
    "jade_talon": "Jade Talon",
    "shadow_killer": "Shadow Killer",
    # Weapons - Barbarian
    "blade_of_barbarian_king": "Blade of the Barbarian King",
    "bul_kathos_sacred_charge": "Bul-Kathos' Sacred Charge",
    "bul_kathos_mythical_sword": "Bul-Kathos' Mythical Sword",
    # Weapons - Misc
    "gimmershred": "Gimmershred",
    "demons_arch": "Demon's Arch",
    "flamebellow": "Flamebellow",
    "demonlimb": "Demonlimb",
}

# Set item name mapping
SET_DISPLAY_NAMES = {
    # Tal Rasha's
    "tal_rashas_lidless_eye": "Tal Rasha's Lidless Eye",
    "tal_rashas_adjudication": "Tal Rasha's Adjudication",
    "tal_rashas_horadric_crest": "Tal Rasha's Horadric Crest",
    "tal_rashas_guardianship": "Tal Rasha's Guardianship",
    "tal_rashas_fine_spun_cloth": "Tal Rasha's Fine-Spun Cloth",
    # Immortal King
    "immortal_king_helm": "Immortal King's Helm",
    "immortal_king_armor": "Immortal King's Armor",
    "immortal_king_gloves": "Immortal King's Gloves",
    "immortal_king_belt": "Immortal King's Belt",
    "immortal_king_pillar": "Immortal King's Pillar",
    "immortal_king_maul": "Immortal King's Maul",
    # Trang-Oul's
    "trang_ouls_wing": "Trang-Oul's Wing",
    "trang_ouls_scale": "Trang-Oul's Scale",
    "trang_ouls_girth": "Trang-Oul's Girth",
    "trang_ouls_claws": "Trang-Oul's Claws",
    # Natalya's
    "natalyas_totem": "Natalya's Totem",
    "natalyas_shell": "Natalya's Shell",
    "natalyas_mark": "Natalya's Mark",
    "natalyas_soul": "Natalya's Soul",
    # Aldur's
    "aldurs_eyes": "Aldur's Eyes",
    "aldurs_advance": "Aldur's Advance",
    "aldurs_deception": "Aldur's Deception",
    "aldurs_royalty": "Aldur's Royalty",
    # Griswold's
    "griswolds_heart": "Griswold's Heart",
    "griswolds_redemption": "Griswold's Redemption",
    "griswolds_valor": "Griswold's Valor",
    "griswolds_honor": "Griswold's Honor",
    # Heaven's Brethren
    "haemosus_adament": "Haemosu's Adament",
    "dangoths_teachings": "Dangoth's Teachings",
    "twylawns_fury": "Twylawn's Fury",
    "saracens_chance": "Saracen's Chance",
    # Angelic
    "angelic_halo": "Angelic Halo",
    "angelic_wings": "Angelic Wings",
    "angelic_mantle": "Angelic Mantle",
    "angelic_sickle": "Angelic Sickle",
    "angelic_trench": "Angelic Trench",
    # Iratha's
    "irathas_collar": "Iratha's Collar",
    "irathas_coil": "Iratha's Coil",
    "irathas_crown": "Iratha's Crown",
    "irathas_cuff": "Iratha's Cuff",
    # Cathan's
    "cathans_ring": "Cathan's Ring",
    "cathans_amulet": "Cathan's Amulet",
    "cathans_mesh": "Cathan's Mesh",
    "cathans_sigil": "Cathan's Sigil",
    # Tancred's
    "tancreds_horn": "Tancred's Horn",
    "tancreds_crow": "Tancred's Crow",
    "tancreds_spine": "Tancred's Spine",
    "tancreds_treads": "Tancred's Treads",
    "tancreds_skull": "Tancred's Skull",
}

# Base item prices (elite bases for runewords)
BASE_PRICES = {
    # Polearms (Infinity/Insight)
    "7pa": 8,    # Cryptic Axe
    "7gd": 30,   # Giant Thresher
    "7vo": 15,   # Thresher (colossus voulge)
    "7wc": 25,   # Giant Thresher
    "7s8": 25,   # Thresher
    "7h7": 10,   # Great Poleaxe
    "pax": 1,    # Poleaxe (normal)
    "scy": 1,    # Scythe (normal)
    # Swords
    "7wa": 15,   # Phase Blade
    "7cr": 8,    # Crystal Sword
    "7bs": 10,   # Balrog Blade
    "7ls": 8,    # Legendary Sword
    "7gd": 10,   # Colossus Blade
    "7gs": 8,    # Colossus Sword
    # Axes
    "7ax": 20,   # Berserker Axe
    "7la": 8,    # Silver Edged Axe
    # Shields (Spirit/Phoenix)
    "uit": 8,    # Monarch
    "pab": 15,   # Sacred Targe
    "pac": 12,   # Sacred Rondache
    "pad": 10,   # Kurast Shield
    "paf": 12,   # Vortex Shield
    "ulg": 5,    # Luna
    "ush": 10,   # Sacred Rondache
    "uws": 8,    # Targe
    # Armor (Enigma/Fortitude)
    "uap": 15,   # Archon Plate
    "upl": 8,    # Balrog Skin
    "ula": 8,    # Wire Fleece
    "uld": 10,   # Great Hauberk
    "utp": 5,    # Sacred Armor
    "xap": 12,   # Dusk Shroud
    "xtp": 8,    # Wyrmhide
    "ung": 20,   # Mage Plate (low str!)
    # Assassin Claws
    "7ar": 15,   # Suwayyah
    "7tw": 15,   # Runic Talons
    "7qr": 12,   # Scissors Suwayyah
    "9tw": 12,   # Greater Talons
    "7lw": 8,    # Feral Claws
    # Scepters (FoH/Hammerdin)
    "7ws": 10,   # Caduceus
    "7sc": 5,    # War Scepter
    "7fl": 3,    # Flail (CTA/HOTO)
    # Wands (White runeword)
    "7bw": 10,   # Lich Wand
    "7gw": 15,   # Unearthed Wand
    # Helms
    "uhm": 10,   # Diadem
    "usk": 5,    # Shako
    "ci3": 8,    # Tiara
    "ci2": 5,    # Coronet
    "ci0": 3,    # Circlet
}


def normalize_name(name: str) -> str:
    """Normalize item name for matching."""
    return re.sub(r'[^a-z0-9]', '', name.lower())


def format_fg(fg: float) -> str:
    """Format FG value for display."""
    if fg >= 1:
        return str(int(fg))
    else:
        return str(fg).rstrip('0').rstrip('.')


def load_all_prices(app_dir: Path) -> dict[str, float]:
    """Load all prices from config files."""
    prices = {}
    
    # Load comprehensive prices first
    comp_path = app_dir / "config" / "comprehensive_prices.yml"
    if comp_path.exists():
        with open(comp_path, 'r') as f:
            data = yaml.safe_load(f)
            if data:
                def extract_prices(obj, prefix=''):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if isinstance(v, (int, float)):
                                key = f"{prefix}{k}" if prefix else k
                                prices[key] = float(v)
                                prices[normalize_name(k)] = float(v)
                            elif isinstance(v, dict):
                                extract_prices(v, f"{prefix}{k}:")
                extract_prices(data)
    
    # Load rune prices
    rune_path = app_dir / "config" / "rune_prices.yml"
    if rune_path.exists():
        with open(rune_path, 'r') as f:
            data = yaml.safe_load(f)
            if data and 'prices' in data:
                for name, price in data['prices'].items():
                    # Map rune name to code
                    for code, rname in RUNE_NAMES.items():
                        if rname.replace(" Rune", "") == name:
                            prices[code] = float(price)
                            break
                    prices[normalize_name(name)] = float(price)
    
    # Load static prices
    static_path = app_dir / "config" / "static_prices.yml"
    if static_path.exists():
        with open(static_path, 'r') as f:
            data = yaml.safe_load(f)
            if data:
                def extract_prices(obj, prefix=''):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if isinstance(v, (int, float)):
                                key = f"{prefix}{k}" if prefix else k
                                prices[key] = float(v)
                                prices[normalize_name(k)] = float(v)
                            elif isinstance(v, dict):
                                extract_prices(v, f"{prefix}{k}:")
                extract_prices(data)
    
    return prices


def match_item_to_price(item: dict, prices: dict[str, float]) -> float | None:
    """Try to match an item to a price."""
    key = item.get("Key", "")
    enus = item.get("enUS", "")
    category = item.get("category", "")
    
    # Direct key match
    if key in prices:
        return prices[key]
    
    # Rune codes
    if key in RUNE_NAMES and key in prices:
        return prices[key]
    
    # Gem codes
    if key in GEM_NAMES:
        if key in prices:
            return prices[key]
        # Perfect gems
        if key.startswith("gp") or key == "skz":
            return 0.5
        # Flawless gems
        if key.startswith("gm") or key == "skm":
            return 0.2
        # Flawed gems
        return 0.1
    
    # Key codes
    if key in KEY_NAMES and key in prices:
        return prices[key]
    
    # Base items
    if category == "base":
        base_key = key.split(":")[-1] if ":" in key else key
        if base_key in BASE_PRICES:
            return BASE_PRICES[base_key]
        # Check by code in key
        for code, price in BASE_PRICES.items():
            if code in key.lower():
                return price
    
    # Unique items
    if category == "unique":
        # Extract name from key
        if ":" in key:
            name_part = key.split(":", 1)[1]
            norm = normalize_name(name_part)
            if norm in prices:
                return prices[norm]
            # Check display name mapping
            for uname, display in UNIQUE_DISPLAY_NAMES.items():
                if normalize_name(uname) == norm:
                    if normalize_name(display) in prices:
                        return prices[normalize_name(display)]
    
    # Set items
    if category == "set":
        if ":" in key:
            name_part = key.split(":", 1)[1]
            norm = normalize_name(name_part)
            if norm in prices:
                return prices[norm]
    
    # Normalize name and try to match
    norm_name = normalize_name(enus)
    if norm_name in prices:
        return prices[norm_name]
    
    # Try matching enUS name directly
    for price_key, price in prices.items():
        if normalize_name(price_key) == norm_name:
            return price
    
    return None


def main():
    app_dir = Path(__file__).resolve().parent.parent
    
    # Paths
    base_path = app_dir / "data" / "templates" / "item-names-full.json"
    output_path = app_dir / "data" / "templates" / "item-names.json"
    
    # Load prices
    prices = load_all_prices(app_dir)
    print(f"Loaded {len(prices)} price entries from configs")
    
    # Load base items
    with open(base_path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    print(f"Loaded {len(items)} base items")
    
    # Build lookup for existing items
    by_key = {}
    for i, item in enumerate(items):
        if item.get("Key"):
            by_key[item["Key"]] = i
    
    # Apply prices to items
    fg_count = 0
    no_price_count = 0
    
    for item in items:
        price = match_item_to_price(item, prices)
        
        if price and price > 0:
            enus = item.get("enUS", "")
            # Don't double-tag
            if "FG" not in enus:
                fg_text = format_fg(price)
                item["enUS"] = f"{enus} | {fg_text} FG"
                fg_count += 1
        else:
            no_price_count += 1
    
    # Add missing runes
    for rune_code, rune_name in RUNE_NAMES.items():
        if rune_code not in by_key:
            # Find price
            price = prices.get(rune_code, 0)
            if not price:
                price = prices.get(normalize_name(rune_name.replace(" Rune", "")), 0)
            if price > 0:
                fg_text = format_fg(price)
                items.append({
                    "id": len(items) + 1,
                    "Key": rune_code,
                    "enUS": f"{rune_name} | {fg_text} FG",
                    "category": "rune",
                    "quality": "normal"
                })
                fg_count += 1
    
    # Add missing gems
    for gem_code, gem_name in GEM_NAMES.items():
        if gem_code not in by_key:
            price = prices.get(gem_code, 0)
            if price > 0:
                fg_text = format_fg(price)
                items.append({
                    "id": len(items) + 1,
                    "Key": gem_code,
                    "enUS": f"{gem_name} | {fg_text} FG",
                    "category": "gem",
                    "quality": "normal"
                })
                fg_count += 1
    
    # Add missing keys
    for key_code, key_name in KEY_NAMES.items():
        if key_code not in by_key:
            price = prices.get(key_code, 0)
            if not price:
                price = 3  # Default key price
            fg_text = format_fg(price)
            items.append({
                "id": len(items) + 1,
                "Key": key_code,
                "enUS": f"{key_name} | {fg_text} FG",
                "category": "key",
                "quality": "normal"
            })
            fg_count += 1
    
    # Add special items
    special_items = [
        ("annihilus", "Annihilus", "charm", 25),
        ("hellfire_torch", "Hellfire Torch", "charm", 15),
        ("gheeds_fortune", "Gheed's Fortune", "charm", 5),
        ("token_of_absolution", "Token of Absolution", "token", 3),
        ("organ_set", "Set of Keys", "keyset", 10),
    ]
    for key, name, cat, price in special_items:
        if key not in by_key:
            fg_text = format_fg(price)
            items.append({
                "id": len(items) + 1,
                "Key": key,
                "enUS": f"{name} | {fg_text} FG",
                "category": cat,
                "quality": "unique"
            })
            fg_count += 1
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== Summary ===")
    print(f"Written {len(items)} items to {output_path}")
    print(f"Items with FG prices: {fg_count}")
    print(f"Items without prices: {no_price_count}")
    
    # Count by category
    categories = {}
    fg_by_cat = {}
    for item in items:
        cat = item.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
        if "FG" in item.get("enUS", ""):
            fg_by_cat[cat] = fg_by_cat.get(cat, 0) + 1
    
    print("\nItems by category:")
    for cat in sorted(categories.keys(), key=lambda x: -categories[x]):
        fg = fg_by_cat.get(cat, 0)
        total = categories[cat]
        pct = (fg / total * 100) if total > 0 else 0
        print(f"  {cat}: {total} total, {fg} with FG ({pct:.0f}%)")


if __name__ == "__main__":
    main()
