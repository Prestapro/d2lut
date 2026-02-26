from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Optional, Any, Dict, List

from d2lut.models import PriceEstimate


class D2RJsonFilterExporter:
    """Export d2lut price estimates into a D2R static localization mod (item-names.json)."""
    D2R_COLOR_PREFIX = "\u00ffc"  # "ÿc"
    D2R_COLOR_RESET = "\u00ffc0"  # "ÿc0"

    def __init__(self, min_fg: float = 0.0, format_str: str = " [{fg} fg]", price_mode: str = "estimate", always_include_kinds: List[str] = None, hide_junk: bool = False, use_short_names: bool = False, apply_colors: bool = False):
        self.min_fg = min_fg
        self.format_str = format_str
        self.price_mode = price_mode
        self.always_include_kinds = set(always_include_kinds) if always_include_kinds else set()
        self.hide_junk = hide_junk
        self.use_short_names = use_short_names
        self.apply_colors = apply_colors
        
        # Color Tiers: [threshold, d2r_color_code]
        # ÿc5 = Gray, ÿc0 = White, ÿc4 = Gold, ÿc; = Purple
        self.color_tiers = {
            (0, 49): f"{self.D2R_COLOR_PREFIX}5",
            (50, 199): f"{self.D2R_COLOR_PREFIX}0",
            (200, 999): f"{self.D2R_COLOR_PREFIX}4",
            (1000, float('inf')): f"{self.D2R_COLOR_PREFIX};",
        }
        
        self.audit_report: Dict[str, Any] = {
            "total_evaluated": 0,
            "eligible_count": 0,
            "mapped_count": 0,
            "unmapped_variants": [],
            "multi_map_variants": []
        }

    def export(self, price_index: dict[str, PriceEstimate], conn: sqlite3.Connection, base_json_path: str | None = None) -> str:
        """
        Generate the JSON payload for item-names.json.
        """
        # Reset audit report on every export
        self.audit_report = {
            "total_evaluated": len(price_index),
            "eligible_count": 0,
            "mapped_count": 0,
            "unmapped_variants": [],
            "multi_map_variants": []
        }
        
        # D2R JSON files can be an array of objects [{"id": 1, "Key": "abc", "enUS": "Abc"}]
        # or a dictionary of keys to objects/strings, depending on the modding tool used.
        mod_data: Any = []
        is_dict_format = False

        if base_json_path and Path(base_json_path).exists():
            with open(base_json_path, "r", encoding="utf-8") as f:
                mod_data = json.load(f)
                if isinstance(mod_data, dict):
                    is_dict_format = True

        # Mapping dictionaries for Short Names
        SHORT_NAMES = {
            "hp1": "Minor HP", "hp2": "Light HP", "hp3": "HP", "hp4": "Greater HP", "hp5": "Super HP",
            "mp1": "Minor MP", "mp2": "Light MP", "mp3": "MP", "mp4": "Greater MP", "mp5": "Super MP",
            "rvs": "Rejuv", "rvl": "Full Rejuv",
            "tsc": "TP Scroll", "isc": "ID Scroll",
            "tbk": "TP Tome", "ibk": "ID Tome",
            "key": "Key"
        }
        
        # Keys to completely hide by setting string to empty
        JUNK_KEYS = {
            "aq2", "cq2", # Arrows, Bolts
            "vps", "yps", "wms", # Stamina, Antidote, Thawing potions
            "hp1", "hp2", "hp3", # Low level health
            "mp1", "mp2", "mp3", # Low level mana
            "gcv", "gcw", "gcy", "gcb", "gcg", "gcr", "skc", # Chipped gems
            "gfv", "gfw", "gfy", "gfb", "gfg", "gfr", "skf", # Flawed gems
            "gsv", "gsw", "gsy", "gsb", "gsg", "gsr", "sku", # Standard gems
        }

        RUNE_MAP = {"el":"r01","eld":"r02","tir":"r03","nef":"r04","eth":"r05","ith":"r06","tal":"r07","ral":"r08","ort":"r09","thul":"r10","amn":"r11","sol":"r12","shael":"r13","dol":"r14","hel":"r15","io":"r16","lum":"r17","ko":"r18","fal":"r19","lem":"r20","pul":"r21","um":"r22","mal":"r23","ist":"r24","gul":"r25","vex":"r26","ohm":"r27","lo":"r28","sur":"r29","ber":"r30","jah":"r31","cham":"r32","zod":"r33"}

        def get_source_keys(variant_key: str) -> list[str]:
            parts = variant_key.split(":")
            if len(parts) < 2:
                return [variant_key]
            kind, slug = parts[0], parts[1]
            
            if kind == "rune":
                if slug in RUNE_MAP:
                    return [RUNE_MAP[slug]]
                
            if kind == "key":
                if "terror" in slug: return ["pk1"]
                if "hate" in slug: return ["pk2"]
                if "destruction" in slug: return ["pk3"]
                
            if kind == "token":
                return ["toa"]
                
            if kind in ("unique", "set"):
                # Exact match against canonical ID
                cur = conn.execute("SELECT source_key, display_name FROM catalog_items WHERE canonical_item_id = ?", (variant_key,))
                rows = cur.fetchall()
                if rows:
                    source_keys = [r["source_key"] for r in rows if r["source_key"]]
                    if source_keys:
                        return source_keys
                    # If source_key is null but they have a display name in catalog, use as fallback
                    return [r["display_name"] for r in rows if r["display_name"]]
                    
                # Strict fallback
                return [slug.replace("_", " ").title()]
                
            if kind in ("prefix", "suffix", "automagic", "rareprefix", "raresuffix"):
                # Always exact match via canonical ID to affix name, never guess "of X"
                cur = conn.execute("SELECT affix_name FROM catalog_affixes WHERE affix_id = ?", (variant_key,))
                rows = cur.fetchall()
                if rows:
                    return [r["affix_name"] for r in rows if r["affix_name"]]
                return []
                    
            if kind == "base":
                cur = conn.execute("SELECT source_key FROM catalog_items WHERE canonical_item_id = ?", (variant_key,))
                rows = cur.fetchall()
                if rows:
                    return [r["source_key"] for r in rows if r["source_key"]]
                
            return [variant_key]

        def get_price_val(est: PriceEstimate) -> float:
            if self.price_mode == "range_low":
                return est.range_low_fg
            elif self.price_mode == "range_high":
                return est.range_high_fg
            return est.estimate_fg

        def deterministic_id(key: str) -> int:
            return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)

        def clean_existing_price(text: str) -> str:
            # We want to remove the price tag we generated previously. Since the user can pass ANY --format-str
            # (e.g., " | {fg} FG" or " [{fg} fg]"), we must dynamically generate a regex to match it.
            # We escape the stripped format_str so exact characters match, then replace the escaped \{fg\} placeholder
            # with the regex for our numeric price values.
            escaped_fmt = re.escape(self.format_str.strip())
            price_regex = r'(?:\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?|\d+(?:\.\d+)?\+?)'
            # Note: re.escape turns "{fg}" into "\{fg\}"
            fmt_regex = escaped_fmt.replace(r'\{fg\}', price_regex)
            
            # Match optional D2R color tags (ÿcX) around the formatting block.
            # Example target: " ÿc2[9999 fg]ÿc0"
            color_prefix = re.escape(self.D2R_COLOR_PREFIX)
            full_regex = fr'\s*(?:{color_prefix}.)?\s*{fmt_regex}(?:{color_prefix}.)?\s*'
            return re.sub(full_regex, '', text).strip()

        def apply_transform(key: str, val: str, price_text: str = "", fg_val: float = 0.0) -> str:
            """Applies short name, junk hiding, and price injection to a string."""
            if self.hide_junk and key in JUNK_KEYS:
                return ""
                
            clean_val = clean_existing_price(val)
            
            if self.use_short_names and key in SHORT_NAMES:
                clean_val = SHORT_NAMES[key]
                
            if price_text and self.apply_colors:
                color_code = self.D2R_COLOR_RESET  # Default white
                for (low, high), code in self.color_tiers.items():
                    if low <= fg_val <= high:
                        color_code = code
                        break
                # D2R formatting is: [Base Name] [Color Code][Price Tag][Reset Color]
                # We revert to White (ÿc0) after the tag so trailing text isn't dyed accidentally.
                return f"{clean_val} {color_code}{price_text.strip()}{self.D2R_COLOR_RESET}"
                
            return clean_val + price_text

        def upsert_key(key: str, price_text: str = "", fg_val: float = 0.0):
            if is_dict_format:
                if key in mod_data:
                    # In dict format, it could be {"r33": "Zod Rune"} or {"r33": {"enUS": "Zod Rune"}}
                    val = mod_data[key]
                    if isinstance(val, str):
                        mod_data[key] = apply_transform(key, val, price_text, fg_val)
                    elif isinstance(val, dict) and "enUS" in val:
                        val["enUS"] = apply_transform(key, val["enUS"], price_text, fg_val)
                else:
                    if self.hide_junk and key in JUNK_KEYS:
                        mod_data[key] = ""
                    else:
                        base_name = SHORT_NAMES.get(key, key) if self.use_short_names else key
                        # Mimic apply_transform formatting for fallback paths
                        if price_text and self.apply_colors:
                            color_code = self.D2R_COLOR_RESET
                            for (low, high), code in self.color_tiers.items():
                                if low <= fg_val <= high:
                                    color_code = code
                                    break
                            mod_data[key] = f"{base_name} {color_code}{price_text.strip()}{self.D2R_COLOR_RESET}"
                        else:
                            mod_data[key] = f"{base_name}{price_text}"
            else:
                for item in mod_data:
                    if item.get("Key") == key:
                        item["enUS"] = apply_transform(key, item.get("enUS", ""), price_text, fg_val)
                        return
                        
                # Sparse fallback creation
                if self.hide_junk and key in JUNK_KEYS:
                    en_us_val = ""
                else:
                    base_name = SHORT_NAMES.get(key, key) if self.use_short_names else key
                    if price_text and self.apply_colors:
                        color_code = self.D2R_COLOR_RESET
                        for (low, high), code in self.color_tiers.items():
                            if low <= fg_val <= high:
                                color_code = code
                                break
                        en_us_val = f"{base_name} {color_code}{price_text.strip()}{self.D2R_COLOR_RESET}"
                    else:
                        en_us_val = f"{base_name}{price_text}"
                    
                mod_data.append({
                    "id": deterministic_id(key),
                    "Key": key,
                    "enUS": en_us_val
                })

        # Apply short names and junk hiding globally across the entire dictionary/list first
        # This ensures items that aren't in the price index are still transformed
        if self.use_short_names or self.hide_junk:
            if is_dict_format:
                for key in list(mod_data.keys()):
                    upsert_key(key, "")
            else:
                for item in mod_data:
                    key = item.get("Key")
                    if key:
                        upsert_key(key, "")

        for variant_key, est in price_index.items():
            val = get_price_val(est)
            
            parts = variant_key.split(":")
            kind = parts[0] if len(parts) > 0 else ""
            
            # Allow forced inclusion of specific categories (e.g. runes) or exact variants (e.g. rune:jah)
            is_forced = (kind in self.always_include_kinds) or (variant_key in self.always_include_kinds)
            if val < self.min_fg and not is_forced:
                continue
                
            self.audit_report["eligible_count"] += 1
                
            price_suffix = self.format_str.format(fg=f"{val:.0f}")
            
            # Map canonical variants to D2R string keys
            keys = get_source_keys(variant_key)
            if not keys:
                self.audit_report["unmapped_variants"].append(variant_key)
            else:
                self.audit_report["mapped_count"] += 1
                if len(keys) > 1:
                    self.audit_report["multi_map_variants"].append(variant_key)
                
            for k in keys:
                if k:
                    upsert_key(k, price_suffix, val)

        return json.dumps(mod_data, indent=2, ensure_ascii=False)
