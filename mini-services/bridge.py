#!/usr/bin/env python3
"""Bridge service for D2LUT.

This module provides a JSON-based interface between the Next.js frontend
and the Python d2lut package. It can be called via subprocess or HTTP.

Usage:
    python bridge.py --action build_filter --preset default --threshold 0
    python bridge.py --action get_items
    python bridge.py --action get_price --item "rune:jah"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "d2lut" / "src"))

# Try to import d2lut modules
try:
    from d2lut.patterns import find_items_in_text, find_best_price_in_text, ITEM_PATTERNS
    D2LUT_AVAILABLE = True
except ImportError:
    D2LUT_AVAILABLE = False


def get_items() -> dict:
    """Get list of all known item patterns."""
    if not D2LUT_AVAILABLE:
        return {"error": "d2lut package not available", "items": []}
    
    items = []
    for variant_key in ITEM_PATTERNS.keys():
        parts = variant_key.split(":")
        category = parts[0] if len(parts) > 1 else "misc"
        name = parts[-1] if parts else variant_key
        
        items.append({
            "variantKey": variant_key,
            "name": name,
            "category": category,
            "displayName": name.replace("_", " ").title(),
        })
    
    return {"items": items, "total": len(items)}


def build_filter(preset: str = "default", threshold: float = 0) -> dict:
    """Build a D2R filter file.
    
    Args:
        preset: Filter preset name (default, roguecore, minimal, verbose)
        threshold: Minimum price threshold in FG
    
    Returns:
        Dict with filter content and metadata
    """
    from d2lut.scripts.build_d2r_filter import FilterBuilder
    
    builder = FilterBuilder(preset=preset)
    builder.load_prices()
    
    # Generate filter content
    output_path = Path("/tmp/d2lut_filter.filter")
    builder.build_filter(output_path)
    
    content = output_path.read_text(encoding="utf-8")
    
    return {
        "content": content,
        "preset": preset,
        "threshold": threshold,
        "itemsCount": builder.filtered_count,
        "filename": f"d2lut_{preset}.filter",
    }


def parse_text(text: str) -> dict:
    """Parse text for items and prices.
    
    Args:
        text: Text to parse (e.g., forum post)
    
    Returns:
        Dict with found items and prices
    """
    if not D2LUT_AVAILABLE:
        return {"error": "d2lut package not available", "items": [], "price": None}
    
    items = find_items_in_text(text)
    price = find_best_price_in_text(text)
    
    return {
        "items": items,
        "price": price,
        "text": text[:500] + "..." if len(text) > 500 else text,
    }


def main():
    parser = argparse.ArgumentParser(description="D2LUT Bridge Service")
    parser.add_argument(
        "--action", "-a",
        choices=["get_items", "build_filter", "parse_text", "get_price"],
        required=True,
        help="Action to perform"
    )
    parser.add_argument("--preset", "-p", default="default", help="Filter preset")
    parser.add_argument("--threshold", "-t", type=float, default=0, help="Price threshold")
    parser.add_argument("--text", help="Text to parse")
    parser.add_argument("--item", help="Item variant key")
    parser.add_argument("--output", "-o", type=Path, help="Output file path")
    
    args = parser.parse_args()
    
    result = {"action": args.action, "success": False}
    
    try:
        if args.action == "get_items":
            result = {**result, **get_items(), "success": True}
        
        elif args.action == "build_filter":
            result = {**result, **build_filter(args.preset, args.threshold), "success": True}
        
        elif args.action == "parse_text":
            if not args.text:
                result["error"] = "--text required for parse_text action"
            else:
                result = {**result, **parse_text(args.text), "success": True}
        
        elif args.action == "get_price":
            if not args.item:
                result["error"] = "--item required for get_price action"
            else:
                # Price lookup would go here
                result["item"] = args.item
                result["success"] = True
        
    except Exception as e:
        result["error"] = str(e)
    
    # Output
    output = json.dumps(result, indent=2)
    
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
