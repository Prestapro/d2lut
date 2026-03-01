#!/usr/bin/env python3
"""
Generate item-names.json with FG prices from static baseline data.
Reads from config/static_prices.yml and data/templates/item-names-full.json
"""

import json
import yaml
import re
from pathlib import Path
from typing import Any

# Item name mappings (internal key -> display name)
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
}

KEY_NAMES = {
    "pk1": "Key of Terror", "pk2": "Key of Hate", "pk3": "Key of Destruction",
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


def load_prices(prices_path: Path) -> dict[str, float]:
    """Load static prices from YAML config."""
    with open(prices_path, 'r') as f:
        config = yaml.safe_load(f)

    prices = {}

    # Flatten all price categories
    for category, items in config.items():
        if isinstance(items, dict):
            for key, value in items.items():
                if isinstance(value, (int, float)):
                    prices[key] = float(value)
                    # Also add with normalized key
                    norm_key = normalize_name(key)
                    prices[norm_key] = float(value)

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
    if key in GEM_NAMES and key in prices:
        return prices[key]

    # Key codes
    if key in KEY_NAMES and key in prices:
        return prices[key]

    # Normalize name and try to match
    norm_name = normalize_name(enus)
    if norm_name in prices:
        return prices[norm_name]

    # Try partial matches for unique/set items
    if category in ("unique", "set"):
        # Extract name from key like "unique:griffons_eye"
        if ":" in key:
            item_name = key.split(":", 1)[1]
            norm_item = normalize_name(item_name)
            if norm_item in prices:
                return prices[norm_item]

    # Try matching enUS name directly
    for price_key, price in prices.items():
        if normalize_name(price_key) == norm_name:
            return price

    return None


def main():
    app_dir = Path(__file__).resolve().parent.parent

    # Paths
    prices_path = app_dir / "config" / "static_prices.yml"
    base_path = app_dir / "data" / "templates" / "item-names-full.json"
    output_path = app_dir / "data" / "templates" / "item-names.json"

    # Load prices
    prices = load_prices(prices_path)
    print(f"Loaded {len(prices)} price entries from config")

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

    # Add missing runes if not in base
    for rune_code, rune_name in RUNE_NAMES.items():
        if rune_code not in by_key and rune_code in prices:
            fg_text = format_fg(prices[rune_code])
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
        if gem_code not in by_key and gem_code in prices:
            fg_text = format_fg(prices[gem_code])
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
        if key_code not in by_key and key_code in prices:
            fg_text = format_fg(prices[key_code])
            items.append({
                "id": len(items) + 1,
                "Key": key_code,
                "enUS": f"{key_name} | {fg_text} FG",
                "category": "key",
                "quality": "normal"
            })
            fg_count += 1

    # Add special items (Anni, Torch)
    special_items = [
        ("annihilus", "Annihilus", "charm", 25),
        ("hellfire_torch", "Hellfire Torch", "charm", 15),
        ("token_of_absolution", "Token of Absolution", "token", 3),
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
        print(f"  {cat}: {total} total, {fg} with FG")


if __name__ == "__main__":
    main()
