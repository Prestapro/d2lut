#!/usr/bin/env python3
"""
Item-names.json generator - preserves existing FG values and adds missing ones.
"""

import json
import yaml
import re
from pathlib import Path

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
    "gmb": "Flawless Sapphire", "gmg": "Flawless Emerald", "gmr": "Flawless Ruby",
    "gmv": "Flawless Amethyst", "gmw": "Flawless Diamond", "gmy": "Flawless Topaz",
    "skm": "Flawless Skull",
}

KEY_NAMES = {
    "pk1": "Key of Terror", "pk2": "Key of Hate", "pk3": "Key of Destruction",
}


def normalize(s):
    """Normalize string for matching."""
    return re.sub(r'[^a-z0-9]', '', s.lower())


def load_all_prices(app_dir: Path) -> dict:
    """Load prices from all YAML configs."""
    prices = {}
    
    config_files = [
        "config/comprehensive_prices.yml",
        "config/extended_prices.yml",
        "config/additional_prices.yml",
        "config/additional_unique_prices.yml",
        "config/unique_prices_complete.yml",
        "config/set_prices_complete.yml",
        "config/rune_prices.yml",
    ]
    
    for config_file in config_files:
        path = app_dir / config_file
        if not path.exists():
            continue
        
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
            if not data:
                continue
        
        def extract(obj, prefix='', category=''):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (int, float)):
                        # Store with full prefix (category:key)
                        key_with_prefix = f"{prefix}{k}" if prefix else k
                        prices[key_with_prefix] = float(v)
                        
                        # Also store just the key name (for exact matching)
                        prices[k] = float(v)
                        
                        # Normalized version
                        prices[normalize(k)] = float(v)
                        
                        # Underscore version
                        underscore = k.replace(" ", "_").replace("'", "").replace("-", "_").lower()
                        prices[underscore] = float(v)
                    elif isinstance(v, dict):
                        extract(v, f"{prefix}{k}:" if prefix else f"{k}:", k)
        
        extract(data)
    
    return prices


def extract_fg(enus: str) -> float:
    """Extract FG value from enUS string."""
    match = re.search(r'(\d+(?:\.\d+)?)\s*FG', enus, re.I)
    if match:
        return float(match.group(1))
    return 0


def match_price(item: dict, prices: dict) -> float:
    """Try to match item to a price."""
    key = item.get("Key", "")
    enus = item.get("enUS", "")
    
    # Already has FG - don't override
    if "FG" in enus:
        return 0
    
    # Strip any existing suffix for matching
    enus_base = re.sub(r'\s*\|.*$', '', enus).strip()
    enus_norm = normalize(enus_base)
    
    # Try exact enUS match first (for quoted YAML keys like "Healing Potion")
    if enus_base in prices:
        return prices[enus_base]
    
    # Direct matches
    if key in prices:
        return prices[key]
    if enus_norm in prices:
        return prices[enus_norm]
    
    # Key patterns like "unique:griffons_eye"
    if ":" in key:
        name_part = key.split(":", 1)[1]
        norm = normalize(name_part)
        if norm in prices:
            return prices[norm]
    
    # enUS variations - try many different formats
    variations = [
        normalize(enus_base),
        enus_base.lower().replace(" ", "_"),
        enus_base.lower().replace(" ", "_").replace("'", ""),
        enus_base.lower().replace("'", ""),
        enus_base.lower().replace("-", "_"),
        enus_base.lower().replace(" ", ""),  # No spaces
        enus_base.replace(" ", ""),  # No spaces, keep case
        enus_base.lower(),
        enus_base.lower().replace(" ", "").replace("'", "").replace("-", ""),
        # Try partial matches
        normalize(enus_base.split()[0]) if enus_base else "",  # First word
    ]
    
    for var in variations:
        if var and var in prices:
            return prices[var]
    
    # Try partial matching - if any price key is contained in the item name
    for price_key, price_val in prices.items():
        if len(price_key) >= 4:  # Only for reasonably long keys
            if price_key in enus_norm or enus_norm in price_key:
                return price_val
    
    return 0


def format_fg(fg: float) -> str:
    """Format FG for display."""
    if fg >= 1:
        return str(int(fg))
    return str(fg).rstrip('0').rstrip('.')


def main():
    app_dir = Path(__file__).resolve().parent.parent
    
    input_path = app_dir / "data" / "templates" / "item-names-full.json"
    output_path = app_dir / "data" / "templates" / "item-names.json"
    
    # Load prices
    prices = load_all_prices(app_dir)
    print(f"Loaded {len(prices)} price entries")
    
    # Load items
    with open(input_path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    print(f"Loaded {len(items)} items")
    
    # Track stats
    already_had_fg = 0
    new_fg_added = 0
    no_match = 0
    
    # Process items
    for item in items:
        enus = item.get("enUS", "")
        
        # Already has FG
        if "FG" in enus:
            already_had_fg += 1
            continue
        
        # Try to match
        fg = match_price(item, prices)
        
        if fg > 0:
            fg_text = format_fg(fg)
            item["enUS"] = f"{enus} | {fg_text} FG"
            new_fg_added += 1
        else:
            no_match += 1
    
    # Add missing special items
    by_key = {i.get("Key"): i for i in items}
    
    # Runes
    for code, name in RUNE_NAMES.items():
        if code not in by_key:
            fg = prices.get(code, prices.get(normalize(name.replace(" Rune", "")), 0.1))
            items.append({
                "id": len(items) + 1,
                "Key": code,
                "enUS": f"{name} | {format_fg(fg)} FG",
                "category": "rune",
                "quality": "normal"
            })
            new_fg_added += 1
    
    # Gems
    for code, name in GEM_NAMES.items():
        if code not in by_key:
            fg = prices.get(code, 0.2)
            items.append({
                "id": len(items) + 1,
                "Key": code,
                "enUS": f"{name} | {format_fg(fg)} FG",
                "category": "gem",
                "quality": "normal"
            })
            new_fg_added += 1
    
    # Keys
    for code, name in KEY_NAMES.items():
        if code not in by_key:
            items.append({
                "id": len(items) + 1,
                "Key": code,
                "enUS": f"{name} | 3 FG",
                "category": "key",
                "quality": "normal"
            })
            new_fg_added += 1
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Written {len(items)} items")
    print(f"Already had FG: {already_had_fg}")
    print(f"New FG added: {new_fg_added}")
    print(f"No price match: {no_match}")
    
    # By category
    cats = {}
    fg_cats = {}
    for item in items:
        cat = item.get("category", "unknown")
        cats[cat] = cats.get(cat, 0) + 1
        if "FG" in item.get("enUS", ""):
            fg_cats[cat] = fg_cats.get(cat, 0) + 1
    
    print("\nBy category:")
    for cat in sorted(cats.keys(), key=lambda x: -cats[x]):
        fg = fg_cats.get(cat, 0)
        total = cats[cat]
        pct = (fg / total * 100) if total > 0 else 0
        print(f"  {cat}: {fg}/{total} ({pct:.0f}%)")


if __name__ == "__main__":
    main()
