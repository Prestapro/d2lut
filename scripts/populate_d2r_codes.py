#!/usr/bin/env python3
"""
Populate D2R codes in the Prisma DB based on item_codes.json and base item names.
"""

import json
import sqlite3
import re
from pathlib import Path

DB_PATH = Path("/Users/alex/Desktop/d2lut/db/custom.db")
CODES_PATH = Path("/Users/alex/Desktop/d2lut/d2lut/data/item_codes.json")

def load_json_codes() -> dict:
    if not CODES_PATH.exists():
        return {}
    with open(CODES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        codes = {}
        for cat, items in data.items():
            if not cat.startswith("_"):
                codes.update(items)
        return codes

def normalize_name(name: str) -> str:
    # Lowercase and remove all non-alphanumeric chars
    return re.sub(r'[^a-z0-9]', '', name.lower())

def main():
    json_codes = load_json_codes()
    print(f"Loaded {len(json_codes)} codes from item_codes.json")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Build base and misc mappings from DB
    # Any base or misc item with a short name (<= 4 chars) is generally its own code
    cursor.execute("""
        SELECT name, displayName FROM D2Item 
        WHERE category IN ('base', 'misc', 'rune') 
          AND LENGTH(name) <= 4 AND name GLOB '[a-z0-9]*'
    """)
    db_base_codes = {}
    for row in cursor.fetchall():
        display_norm = normalize_name(row["displayName"])
        db_base_codes[display_norm] = row["name"]
        
        name_norm = normalize_name(row["name"])
        db_base_codes[name_norm] = row["name"]
        
    print(f"Built internal base/misc map with {len(db_base_codes)} entries")

    # Hardcoded known generic types
    generic_types = {
        "amulet": "amu",
        "ring": "rin",
        "jewel": "jew",
        "charm": "cm1", # generic fallback
        "smallcharm": "cm1",
        "largecharm": "cm2",
        "grandcharm": "cm3",
        "skiller": "cm3",
        "sunder": "cm3",
    }
    db_base_codes.update(generic_types)

    # Custom mapping for named items
    CUSTOM_MAP = {
        # Essences & Keys
        "essence:burning_essence_of_terror": "bet",
        "essence:festering_essence_of_destruction": "fed",
        "essence:twisted_essence_of_suffering": "tes",
        "essence:charged_essense_of_hatred": "ceh",
        "key:destruction": "pk3",
        "key:hate": "pk2",
        "key:terror": "pk1",
        "keyset:3x3": "pk1",  # pseudo, just mapped to key
        
        # Specific Sets
        "set:tal_rashas_adjudication": "amu",
        "set:tal_rashas_fine-spun_cloth": "zmb",
        "set:tal_rashas_guardianship": "uth",
        "set:tal_rashas_horadric_crest": "xsk",
        "set:tal_rashas_lidless_eye": "oba",
        
        # Specific Uniques (including long variants)
        "unique:arachnid_mesh": "umc",
        "unique:arkaines_valor": "upl",
        "unique:bul_kathos_wedding_band": "rin",
        "unique:buriza_do_kyanon": "8bx",
        "unique:duriels_shell": "xla",
        "unique:dwarf_star": "rin",
        "unique:annihilus": "cm3",
        "unique:guardian_angel": "xtp",
        "unique:highlords_wrath": "amu",
        "unique:leviathan": "uld",
        "unique:maras_kaleidoscope": "amu",
        "unique:nagelring": "rin",
        "unique:nosferatus_coil": "uvc",
        "unique:ormus_robes": "uui",
        "unique:raven_frost": "rin",
        "unique:ravenlore": "uba",
        "unique:stone_of_jordan": "rin",
        "unique:the_grandfather": "gcb",
        "unique:the_oculus": "oba",
        "unique:thundergods_vigor": "zhb",
        "unique:tyraels_might": "uar",
        "unique:vampire_gaze": "xh9",
        "unique:wisp_projector": "rin",
        
        # Missing common ones that were unmatched
        "unique:occulus": "obf",
        "unique:shako": "uui",
        "unique:griffon": "uap",
        "unique:andariel": "uhm",
        "unique:soj": "rin",
        "unique:mara": "amu",
        "unique:herald_of_zakarum": "pa9",
        "unique:catseye": "amu",
        
        # Specific Misc
        "misc:0sc": "tsc",
        "misc:amu": "amu",
        "misc:aqv": "aqv",
        "misc:cqv": "cqv",
        "misc:box": "box",
        "misc:cs2": "cm3", 
        "misc:ear": "ear",
        "jewel:cjw": "jew",
    }

    # 2. Iterate all items without a D2R Code and try to assign
    cursor.execute("""
        SELECT id, category, name, displayName, variantKey, d2rCode
        FROM D2Item
        WHERE d2rCode IS NULL OR d2rCode = ''
    """)
    missing_items = cursor.fetchall()

    updates = []
    unmatched = []

    for item in missing_items:
        cat = item["category"]
        vkey = item["variantKey"]
        name = item["name"]
        display = item["displayName"]
        
        # Skip categories that can't have codes
        if cat in ('runeword', 'bundle', 'market_only'):
            continue
            
        new_code = None

        # Try JSON first
        if vkey in json_codes:
            new_code = json_codes[vkey]
        elif name in json_codes:
            new_code = json_codes[name]
            
        # Try Custom Map
        if not new_code and vkey in CUSTOM_MAP:
            new_code = CUSTOM_MAP[vkey]
        if not new_code and name in CUSTOM_MAP:
            new_code = CUSTOM_MAP[name]
            
        # Try generic logic
        if not new_code:
            if cat == 'rune':
                if name.startswith('r') and len(name) == 3 and name[1:].isdigit():
                    new_code = name
                else: 
                    # Try to find 'rXX' for named runes (e.g. 'jah' -> 'r31')
                    # Actually runes are already in JSON mostly, but if missing:
                    pass
            elif cat in ('base', 'misc') and len(name) <= 4 and name.isalnum():
                new_code = name
            elif cat in ('unique', 'set', 'base'):
                # D2R filters uniques/sets by their BASE ITEM CODE
                display_norm = normalize_name(display)
                name_norm = normalize_name(name)
                
                # Check mapping for both display and name
                if display_norm in db_base_codes: # E.g. 'arachnidmesh' -> base code? No, arachnid mesh base is spiderwebsash
                    new_code = db_base_codes[display_norm]
                elif name_norm in db_base_codes:
                    new_code = db_base_codes[name_norm]
                
                # If name is just the base name itself e.g. name="2_handed_sword" -> "2handedsword" -> "2hs"
                
                # Also try checking if the name ends with a known base
                # Not doing complex prefix matching yet unless necessary

            elif cat in ('charm', 'jewel', 'keyset', 'token', 'essence', 'facet', 'key'):
                display_norm = normalize_name(display)
                name_norm = normalize_name(name)
                if display_norm in db_base_codes:
                    new_code = db_base_codes[display_norm]
                elif name_norm in generic_types:
                    new_code = generic_types[name_norm]

        if new_code:
            updates.append((new_code, item["id"]))
        else:
            unmatched.append(item)

    print(f"Found {len(updates)} matches for missing D2R codes.")
    print(f"Still unmatched (excluding rw/bundle/market): {len(unmatched)}")
    
    # Preview some unmatched
    if unmatched:
        print("\nSample unmatched:")
        for u in unmatched[:30]:
            print(f"  {u['category']} | {u['variantKey']} | {u['name']} | {u['displayName']}")

    # Apply updates
    if updates:
        cursor.executemany("UPDATE D2Item SET d2rCode = ? WHERE id = ?", updates)
        conn.commit()
        print(f"\nUpdated {len(updates)} items in database.")

    conn.close()

if __name__ == "__main__":
    main()
