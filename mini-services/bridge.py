#!/usr/bin/env python3
"""Bridge service for D2LUT.

This module provides a JSON-based interface between the Next.js frontend
and the Python d2lut package. It can be called via subprocess or HTTP.

Usage:
    python bridge.py --action build_filter --preset default --threshold 0
    python bridge.py --action get_items
    python bridge.py --action get_price --item "rune:jah"
    python bridge.py --action scrape_prices --forum_id 271
    python bridge.py --action sync_db --db_path /path/to/db
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "d2lut" / "src"))

# Try to import d2lut modules
try:
    from d2lut.patterns import find_items_in_text, find_best_price_in_text, ITEM_PATTERNS
    from d2lut.collect.d2jsp import D2JspCollector
    from d2lut.models import PriceObservation
    D2LUT_AVAILABLE = True
except ImportError:
    D2LUT_AVAILABLE = False


def get_items() -> dict:
    """Get list of all known item patterns."""
    if not D2LUT_AVAILABLE:
        return {"error": "d2lut package not available", "items": [], "success": False}
    
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
    
    return {"items": items, "total": len(items), "success": True}


def build_filter(preset: str = "default", threshold: float = 0, db_path: str = None) -> dict:
    """Build a D2R filter file.
    
    Args:
        preset: Filter preset name (default, roguecore, minimal, verbose)
        threshold: Minimum price threshold in FG
        db_path: Optional path to SQLite database
    
    Returns:
        Dict with filter content and metadata
    """
    try:
        from d2lut.scripts.build_d2r_filter import FilterBuilder
        
        # Find database path
        if not db_path:
            # Check common locations
            possible_paths = [
                Path(__file__).parent.parent / "db" / "custom.db",
                Path(__file__).parent.parent / "db" / "d2lut.db",
                Path(__file__).parent.parent / "d2lut.db",
            ]
            for p in possible_paths:
                if p.exists():
                    db_path = p
                    break
        
        builder = FilterBuilder(
            db_path=Path(db_path) if db_path else None,
            preset=preset
        )
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
            "success": True,
        }
    except Exception as e:
        return {"error": str(e), "success": False}


def parse_text(text: str) -> dict:
    """Parse text for items and prices.
    
    Args:
        text: Text to parse (e.g., forum post)
    
    Returns:
        Dict with found items and prices
    """
    if not D2LUT_AVAILABLE:
        return {"error": "d2lut package not available", "items": [], "price": None, "success": False}
    
    items = find_items_in_text(text)
    price = find_best_price_in_text(text)
    
    return {
        "items": items,
        "price": price,
        "text": text[:500] + "..." if len(text) > 500 else text,
        "success": True,
    }


def scrape_prices(forum_id: int = 271, use_live: bool = False, max_items: int = 100) -> dict:
    """Scrape prices from d2jsp forum.
    
    Args:
        forum_id: D2JSP forum ID (default: 271 for D2R Ladder)
        use_live: Use Playwright-based live collector (requires playwright)
        max_items: Maximum items to return
    
    Returns:
        Dict with scraped price observations
    """
    if not D2LUT_AVAILABLE:
        return {"error": "d2lut package not available", "observations": [], "success": False}
    
    observations = []
    errors = []
    
    try:
        collector = D2JspCollector(forum_id=forum_id, use_live_collector=use_live)
        
        for post in collector.fetch_recent():
            try:
                # Parse post for items and prices
                text = f"{post.title}\n{post.body_text}"
                items_found = find_items_in_text(text)
                price_info = find_best_price_in_text(text)
                
                if items_found and price_info:
                    for variant_key in items_found[:5]:  # Limit items per post
                        observations.append({
                            "variantKey": variant_key,
                            "priceFg": price_info["price"],
                            "confidence": price_info["confidence"],
                            "signalKind": price_info["signal_kind"],
                            "source": "d2jsp",
                            "sourceId": str(post.thread_id),
                            "author": post.author,
                            "observedAt": post.timestamp.isoformat() if post.timestamp else datetime.now().isoformat(),
                        })
                        
                        if len(observations) >= max_items:
                            break
                
                if len(observations) >= max_items:
                    break
                    
            except Exception as e:
                errors.append(f"Error processing post: {str(e)}")
                continue
                
    except Exception as e:
        return {"error": str(e), "observations": [], "success": False}
    
    return {
        "observations": observations,
        "total": len(observations),
        "errors": errors[:5] if errors else [],  # Limit error messages
        "success": True,
    }


def sync_db(db_path: str, observations: list[dict] = None) -> dict:
    """Sync observations to the SQLite database.
    
    Args:
        db_path: Path to SQLite database file
        observations: List of observation dicts to sync
    
    Returns:
        Dict with sync results
    """
    import sqlite3
    
    if not observations:
        return {"message": "No observations to sync", "synced": 0, "success": True}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        synced = 0
        
        for obs in observations:
            try:
                # Try to find existing item
                cursor.execute(
                    "SELECT id FROM D2Item WHERE variantKey = ?",
                    (obs["variantKey"],)
                )
                item = cursor.fetchone()
                
                if item:
                    item_id = item[0]
                    
                    # Check if price estimate exists
                    cursor.execute(
                        "SELECT id, nObservations FROM PriceEstimate WHERE itemId = ?",
                        (item_id,)
                    )
                    estimate = cursor.fetchone()
                    
                    if estimate:
                        # Update existing estimate (simple average)
                        estimate_id, n_obs = estimate
                        new_n = n_obs + 1
                        
                        cursor.execute("""
                            UPDATE PriceEstimate 
                            SET priceFg = (priceFg * ? + ?) / ?,
                                nObservations = ?,
                                lastUpdated = ?
                            WHERE id = ?
                        """, (n_obs, obs["priceFg"], new_n, new_n, datetime.now().isoformat(), estimate_id))
                    else:
                        # Create new estimate
                        cursor.execute("""
                            INSERT INTO PriceEstimate (itemId, priceFg, confidence, nObservations, lastUpdated)
                            VALUES (?, ?, ?, 1, ?)
                        """, (item_id, obs["priceFg"], "medium" if obs.get("confidence", 0) > 0.7 else "low", datetime.now().isoformat()))
                    
                    # Add observation record
                    cursor.execute("""
                        INSERT INTO PriceObservation (itemId, priceFg, confidence, signalKind, source, sourceId, author, observedAt)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (item_id, obs["priceFg"], obs.get("confidence", 0.5), obs.get("signalKind", "bin"),
                          obs.get("source", "d2jsp"), obs.get("sourceId", ""), obs.get("author", ""),
                          obs.get("observedAt", datetime.now().isoformat())))
                    
                    synced += 1
                    
            except Exception as e:
                continue
        
        conn.commit()
        conn.close()
        
        return {"synced": synced, "total": len(observations), "success": True}
        
    except Exception as e:
        return {"error": str(e), "synced": 0, "success": False}


def get_price_stats(db_path: str = None) -> dict:
    """Get price statistics from the database.
    
    Args:
        db_path: Path to SQLite database file
    
    Returns:
        Dict with price statistics
    """
    import sqlite3
    
    if not db_path:
        possible_paths = [
            Path(__file__).parent.parent / "db" / "custom.db",
            Path(__file__).parent.parent / "db" / "d2lut.db",
        ]
        for p in possible_paths:
            if p.exists():
                db_path = str(p)
                break
    
    if not db_path or not Path(db_path).exists():
        return {"error": "Database not found", "stats": {}, "success": False}
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get item count
        cursor.execute("SELECT COUNT(*) FROM D2Item")
        total_items = cursor.fetchone()[0]
        
        # Get items with prices
        cursor.execute("""
            SELECT COUNT(*) FROM D2Item d
            JOIN PriceEstimate p ON d.id = p.itemId
        """)
        items_with_prices = cursor.fetchone()[0]
        
        # Get average price
        cursor.execute("SELECT AVG(priceFg) FROM PriceEstimate")
        avg_price = cursor.fetchone()[0] or 0
        
        # Get last update
        cursor.execute("SELECT MAX(lastUpdated) FROM PriceEstimate")
        last_updated = cursor.fetchone()[0]
        
        # Get tier counts
        cursor.execute("SELECT priceFg FROM PriceEstimate")
        prices = [row[0] for row in cursor.fetchall()]
        
        tier_counts = {"GG": 0, "HIGH": 0, "MID": 0, "LOW": 0, "TRASH": 0}
        for price in prices:
            if price >= 500:
                tier_counts["GG"] += 1
            elif price >= 100:
                tier_counts["HIGH"] += 1
            elif price >= 20:
                tier_counts["MID"] += 1
            elif price >= 5:
                tier_counts["LOW"] += 1
            else:
                tier_counts["TRASH"] += 1
        
        conn.close()
        
        return {
            "stats": {
                "totalItems": total_items,
                "itemsWithPrices": items_with_prices,
                "avgPrice": round(avg_price, 2),
                "lastUpdated": last_updated,
                "tierCounts": tier_counts,
            },
            "success": True,
        }
        
    except Exception as e:
        return {"error": str(e), "stats": {}, "success": False}


def get_slang_aliases() -> dict:
    """Get slang aliases for items.
    
    Returns:
        Dict mapping slang terms to canonical variant keys
    """
    # Common D2 slang aliases
    aliases = {
        # Runes
        "jah": "rune:jah",
        "ber": "rune:ber",
        "zod": "rune:zod",
        "cham": "rune:cham",
        "sur": "rune:sur",
        "lo": "rune:lo",
        "ohm": "rune:ohm",
        "vex": "rune:vex",
        "gul": "rune:gul",
        "ist": "rune:ist",
        "mal": "rune:mal",
        "um": "rune:um",
        "pul": "rune:pul",
        "lem": "rune:lem",
        "ko": "rune:ko",
        "hel": "rune:hel",
        
        # Uniques - Common Names
        "shako": "unique:shako",
        "harlequin": "unique:shako",
        "harlequin crest": "unique:shako",
        "griffon": "unique:griffon",
        "griffons": "unique:griffon",
        "andy": "unique:andariel",
        "andys": "unique:andariel",
        "coa": "unique:crownofages",
        "crown of ages": "unique:crownofages",
        "kira": "unique:kira",
        
        # Uniques - Armor
        "tyrael": "unique:tyraels",
        "tyraels": "unique:tyraels",
        "vipermagi": "unique:skinofvipermagi",
        "viper": "unique:skinofvipermagi",
        "skullder": "unique:skullder",
        
        # Uniques - Belts
        "arach": "unique:arachnid",
        "arachnid": "unique:arachnid",
        "spider": "unique:arachnid",
        "dungo": "unique:verdungo",
        "verdungo": "unique:verdungo",
        "tgod": "unique:tgods",
        "tgods": "unique:tgods",
        "thundergod": "unique:tgods",
        
        # Uniques - Boots
        "wartraveler": "unique:wartraveler",
        "wt": "unique:wartraveler",
        "wartrav": "unique:wartraveler",
        "sandstorm": "unique:sandstorm",
        "sst": "unique:sandstorm",
        "trek": "unique:sandstorm",
        "gore": "unique:goredriver",
        "goredriver": "unique:goredriver",
        "waterwalk": "unique:waterwalk",
        
        # Uniques - Gloves
        "drac": "unique:dracul",
        "dracs": "unique:dracul",
        "dracul": "unique:dracul",
        "chance": "unique:chanceguards",
        "chancy": "unique:chanceguards",
        "magefist": "unique:magefist",
        "mage": "unique:magefist",
        "steelrend": "unique:steelrend",
        
        # Uniques - Shields
        "stormshield": "unique:stormshield",
        "ss": "unique:stormshield",
        "storm": "unique:stormshield",
        "homu": "unique:homunculus",
        "homunculus": "unique:homunculus",
        "medusa": "unique:medusa",
        "tiamat": "unique:tiamat",
        
        # Uniques - Weapons
        "wf": "unique:windforce",
        "windforce": "unique:windforce",
        "buriza": "unique:buriza",
        "occy": "unique:occulus",
        "occulus": "unique:occulus",
        "wizzy": "unique:wizardspike",
        "wiz": "unique:wizardspike",
        "wizardspike": "unique:wizardspike",
        "leoric": "unique:leoric",
        "aokl": "unique:leoric",
        
        # Uniques - Jewelry
        "soj": "unique:soj",
        "stone of jordan": "unique:soj",
        "bk": "unique:bk",
        "bul kathos": "unique:bk",
        "raven": "unique:raven",
        "ravenfrost": "unique:raven",
        "mara": "unique:mara",
        "maras": "unique:mara",
        "highlord": "unique:highlord",
        "hlw": "unique:highlord",
        "catseye": "unique:catseye",
        "cats eye": "unique:catseye",
        
        # Uniques - Charms
        "anni": "unique:anni",
        "annihilus": "unique:anni",
        "torch": "unique:torch",
        "hellfire": "unique:torch",
        "gheed": "unique:gheed",
        "gheeds": "unique:gheed",
        
        # Runewords
        "eni": "runeword:enigma",
        "enigma": "runeword:enigma",
        "enig": "runeword:enigma",
        "infy": "runeword:infinity",
        "infinity": "runeword:infinity",
        "botd": "runeword:botd",
        "breath of the dying": "runeword:botd",
        "grief": "runeword:grief",
        "beast": "runeword:beast",
        "lw": "runeword:lastwish",
        "last wish": "runeword:lastwish",
        "lastwish": "runeword:lastwish",
        "cta": "runeword:cta",
        "call to arms": "runeword:cta",
        "hoto": "runeword:hoto",
        "heart of the oak": "runeword:hoto",
        "forti": "runeword:fortitude",
        "fortitude": "runeword:fortitude",
        "spirit": "runeword:spirit",
        "coh": "runeword:coh",
        "chains of honor": "runeword:coh",
        "insight": "runeword:insight",
        "exile": "runeword:exile",
        "phoenix": "runeword:phoenix",
        "faith": "runeword:faith",
        "doom": "runeword:doom",
        
        # Set Items
        "tal": "set:talrasha",
        "tals": "set:talrasha",
        "tal rasha": "set:talrasha",
        "ik": "set:ik",
        "immortal king": "set:ik",
        "arreat": "set:arreat",
        "arreats": "set:arreat",
        "trang": "set:trang",
        "trang oul": "set:trang",
        "loh": "set:layingofhands",
        "laying of hands": "set:layingofhands",
        "guillaume": "set:guillaume",
        "guillaumes": "set:guillaume",
        
        # Bases
        "monarch": "base:monarch",
        "mon": "base:monarch",
        "archon": "base:archon",
        "ap": "base:archon",
        "dusk": "base:dusk",
        "ds": "base:dusk",
        "thresh": "base:thresher",
        "thresher": "base:thresher",
        "gt": "base:giantthresher",
        "giant thresher": "base:giantthresher",
        "cv": "base:colossusvoulge",
        "colossus voulge": "base:colossusvoulge",
        "ba": "base:berserkeraxe",
        "berserker axe": "base:berserkeraxe",
        "pb": "base:phaseblade",
        "phase blade": "base:phaseblade",
        "sa": "base:sacredarmor",
        "sacred armor": "base:sacredarmor",
        
        # Facets
        "fire facet": "facet:fire",
        "cold facet": "facet:cold",
        "light facet": "facet:light",
        "lightning facet": "facet:light",
        "poison facet": "facet:poison",
        "rainbow": "facet:fire",  # Default assumption
        
        # Misc
        "token": "misc:token",
        "retoken": "misc:token",
        
        # Crafts
        "blood ring": "craft:bloodring",
        "blood gloves": "craft:bloodgloves",
        "caster amulet": "craft:casteramulet",
        "2/20 ammy": "craft:casteramulet",
        "kb gloves": "craft:hitgloves",
    }
    
    return {"aliases": aliases, "total": len(aliases), "success": True}


def resolve_alias(term: str) -> dict:
    """Resolve a slang term to canonical variant key.
    
    Args:
        term: Slang term to resolve
    
    Returns:
        Dict with resolved variant key or suggestions
    """
    result = get_slang_aliases()
    aliases = result.get("aliases", {})
    
    term_lower = term.lower().strip()
    
    # Direct match
    if term_lower in aliases:
        return {
            "term": term,
            "variantKey": aliases[term_lower],
            "success": True,
        }
    
    # Partial match (starts with)
    matches = {k: v for k, v in aliases.items() if k.startswith(term_lower)}
    
    if matches:
        return {
            "term": term,
            "suggestions": matches,
            "success": False,
        }
    
    return {
        "term": term,
        "error": "No matching alias found",
        "success": False,
    }


def main():
    parser = argparse.ArgumentParser(description="D2LUT Bridge Service")
    parser.add_argument(
        "--action", "-a",
        choices=[
            "get_items", "build_filter", "parse_text", "get_price",
            "scrape_prices", "sync_db", "get_price_stats",
            "get_slang_aliases", "resolve_alias"
        ],
        required=True,
        help="Action to perform"
    )
    parser.add_argument("--preset", "-p", default="default", help="Filter preset")
    parser.add_argument("--threshold", "-t", type=float, default=0, help="Price threshold")
    parser.add_argument("--text", help="Text to parse")
    parser.add_argument("--item", help="Item variant key or alias")
    parser.add_argument("--forum-id", "-f", type=int, default=271, help="D2JSP forum ID")
    parser.add_argument("--use-live", "-l", action="store_true", help="Use live collector")
    parser.add_argument("--max-items", "-m", type=int, default=100, help="Max items to scrape")
    parser.add_argument("--db-path", "-d", help="Database path")
    parser.add_argument("--output", "-o", type=Path, help="Output file path")
    parser.add_argument("--observations", type=str, help="JSON observations for sync")
    
    args = parser.parse_args()
    
    result: dict[str, Any] = {"action": args.action, "success": False}
    
    try:
        if args.action == "get_items":
            result = {**result, **get_items()}
        
        elif args.action == "build_filter":
            result = {**result, **build_filter(args.preset, args.threshold, args.db_path)}
        
        elif args.action == "parse_text":
            if not args.text:
                result["error"] = "--text required for parse_text action"
            else:
                result = {**result, **parse_text(args.text)}
        
        elif args.action == "get_price":
            if not args.item:
                result["error"] = "--item required for get_price action"
            else:
                result["item"] = args.item
                result["success"] = True
        
        elif args.action == "scrape_prices":
            result = {**result, **scrape_prices(args.forum_id, args.use_live, args.max_items)}
        
        elif args.action == "sync_db":
            if not args.db_path:
                result["error"] = "--db-path required for sync_db action"
            elif args.observations:
                obs = json.loads(args.observations)
                result = {**result, **sync_db(args.db_path, obs)}
            else:
                result = {**result, **sync_db(args.db_path, [])}
        
        elif args.action == "get_price_stats":
            result = {**result, **get_price_stats(args.db_path)}
        
        elif args.action == "get_slang_aliases":
            result = {**result, **get_slang_aliases()}
        
        elif args.action == "resolve_alias":
            if not args.item:
                result["error"] = "--item required for resolve_alias action"
            else:
                result = {**result, **resolve_alias(args.item)}
        
    except Exception as e:
        result["error"] = str(e)
    
    # Output
    output = json.dumps(result, indent=2, default=str)
    
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
