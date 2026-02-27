from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
import yaml
from pathlib import Path
from typing import Optional, Any, Dict, List, TYPE_CHECKING
from d2lut.models import PriceEstimate

if TYPE_CHECKING:
    from d2lut.exporters.d2r_affix_filter import AffixHighlighter
    from d2lut.exporters.d2r_base_hints import BaseHintGenerator
    from d2lut.exporters.rune_converter import RuneConverter

class D2RJsonFilterExporter:
    """Export d2lut price estimates into a D2R static localization mod (item-names.json)."""
    D2R_COLOR_PREFIX = "\u00ffc"  # "ÿc"
    D2R_COLOR_RESET = "\u00ffc0"  # "ÿc0"

    def __init__(
        self,
        min_fg: float = 0.0,
        format_str: str = " [{fg} fg]",
        price_mode: str = "estimate",
        always_include_kinds: List[str] = None,
        hide_junk: bool = False,
        use_short_names: bool = False,
        apply_colors: bool = False,
        collect_explain: bool = False,
        explain_limit: int = 20,
        affix_highlighter: Optional['AffixHighlighter'] = None,
        base_hint_generator: Optional['BaseHintGenerator'] = None,
        perfect_rolls_path: Optional[str | Path] = None,
        rune_converter: Optional['RuneConverter'] = None,
    ):
        self.min_fg = min_fg
        self.format_str = format_str
        self.price_mode = price_mode
        self.always_include_kinds = set(always_include_kinds) if always_include_kinds else set()
        self.hide_junk = hide_junk
        self.use_short_names = use_short_names
        self.apply_colors = apply_colors
        self.collect_explain = collect_explain
        self.explain_limit = max(0, int(explain_limit))
        self.affix_highlighter = affix_highlighter
        self.base_hint_generator = base_hint_generator
        self.rune_converter = rune_converter
        
        self.perfect_rolls: Dict[str, str] = {}
        if perfect_rolls_path:
            p = Path(perfect_rolls_path)
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    for k, v in data.get("rolls", {}).items():
                        if "display" in v:
                            self.perfect_rolls[k] = v["display"]
        
        # Color Tiers: [threshold, d2r_color_code]
        # ÿc5 = Gray, ÿc0 = White, ÿc8 = Orange, ÿc; = Purple, ÿc1 = Red
        self.color_tiers = {
            (0, 9): f"{self.D2R_COLOR_PREFIX}5",  # Trash
            (10, 29): f"{self.D2R_COLOR_PREFIX}0", # Low
            (30, 199): f"{self.D2R_COLOR_PREFIX}8", # Mid
            (200, 999): f"{self.D2R_COLOR_PREFIX};", # High
            (1000, float('inf')): f"{self.D2R_COLOR_PREFIX}1", # GG
        }
        
        self.audit_report: Dict[str, Any] = {
            "total_evaluated": 0,
            "eligible_count": 0,
            "eligible_by_threshold": 0,
            "eligible_by_forced": 0,
            "mapped_count": 0,
            "unmapped_variants": [],
            "multi_map_variants": [],
            "sample_injections": [],
            "sample_skipped_below_threshold": []
        }

    def export(self, price_index: dict[str, PriceEstimate], conn: sqlite3.Connection, base_json_path: str | None = None, base_runes_json_path: str | None = None) -> str:
        """
        Generate the JSON payload for item-names.json.
        """
        # Reset audit report on every export
        self.audit_report = {
            "total_evaluated": len(price_index),
            "eligible_count": 0,
            "eligible_by_threshold": 0,
            "eligible_by_forced": 0,
            "mapped_count": 0,
            "unmapped_variants": [],
            "multi_map_variants": [],
            "sample_injections": [],
            "sample_skipped_below_threshold": []
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

        # Process item-runes.json if base_runes_json_path is provided
        runes_mod_data = []
        is_runes_dict_format = False
        if base_runes_json_path and Path(base_runes_json_path).exists() and self.rune_converter:
            with open(base_runes_json_path, "r", encoding="utf-8") as f:
                runes_mod_data = json.load(f)
                is_runes_dict_format = isinstance(runes_mod_data, dict)

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

        def color_code_for_fg(fg_val: float) -> str:
            code = self.D2R_COLOR_RESET
            for (low, high), tier_code in self.color_tiers.items():
                if low <= fg_val <= high:
                    code = tier_code
                    break
            return code

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

        def apply_transform(key: str, val: str, price_text: str = "", fg_val: float = 0.0, apply_base_hint: bool = True) -> str:
            """Applies short name, junk hiding, base hints, and price injection to a string."""
            if self.hide_junk and key in JUNK_KEYS:
                return ""
                
            clean_val = clean_existing_price(val)
            
            if self.use_short_names and key in SHORT_NAMES:
                clean_val = SHORT_NAMES[key]
                
            # Append base hint if applicable
            if apply_base_hint and self.base_hint_generator:
                base_hint = self.base_hint_generator.get_base_hints(key)
                if base_hint:
                    clean_val = f"{clean_val}{base_hint}"
                
            if price_text and self.apply_colors:
                color_code = color_code_for_fg(fg_val)
                return f"{clean_val} {color_code}{price_text.strip()}{self.D2R_COLOR_RESET}"
                
            return f"{clean_val}{price_text}"

        def upsert_key(key: str, price_text: str = "", fg_val: float = 0.0, apply_base_hint: bool = True):
            if is_dict_format:
                if key in mod_data:
                    val = mod_data[key]
                    if isinstance(val, str):
                        mod_data[key] = apply_transform(key, val, price_text, fg_val, apply_base_hint)
                    elif isinstance(val, dict) and "enUS" in val:
                        val["enUS"] = apply_transform(key, val["enUS"], price_text, fg_val, apply_base_hint)
                else:
                    if self.hide_junk and key in JUNK_KEYS:
                        mod_data[key] = ""
                    else:
                        base_name = SHORT_NAMES.get(key, key) if self.use_short_names else key
                        if apply_base_hint and self.base_hint_generator:
                            hint = self.base_hint_generator.get_base_hints(key)
                            if hint: base_name = f"{base_name}{hint}"
                        
                        if price_text and self.apply_colors:
                            color_code = color_code_for_fg(fg_val)
                            mod_data[key] = f"{base_name} {color_code}{price_text.strip()}{self.D2R_COLOR_RESET}"
                        else:
                            mod_data[key] = f"{base_name}{price_text}"
            else:
                for item in mod_data:
                    if item.get("Key") == key:
                        item["enUS"] = apply_transform(key, item.get("enUS", ""), price_text, fg_val, apply_base_hint)
                        return
                
                if self.hide_junk and key in JUNK_KEYS:
                    en_us_val = ""
                else:
                    base_name = SHORT_NAMES.get(key, key) if self.use_short_names else key
                    if apply_base_hint and self.base_hint_generator:
                        hint = self.base_hint_generator.get_base_hints(key)
                        if hint: base_name = f"{base_name}{hint}"
                        
                    if price_text and self.apply_colors:
                        color_code = color_code_for_fg(fg_val)
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
                if self.collect_explain and len(self.audit_report["sample_skipped_below_threshold"]) < self.explain_limit:
                    self.audit_report["sample_skipped_below_threshold"].append({
                        "variant_key": variant_key,
                        "kind": kind,
                        "fg_value": round(float(val), 2),
                        "threshold": float(self.min_fg),
                        "forced_match": False,
                        "reason": "below_threshold",
                    })
                continue
                
            self.audit_report["eligible_count"] += 1
            if is_forced and val < self.min_fg:
                self.audit_report["eligible_by_forced"] += 1
            else:
                self.audit_report["eligible_by_threshold"] += 1
                
            price_suffix = self.format_str.format(fg=f"{val:.0f}")
            
            # Map canonical variants to D2R string keys
            keys = get_source_keys(variant_key)
            if not keys:
                self.audit_report["unmapped_variants"].append(variant_key)
            else:
                self.audit_report["mapped_count"] += 1
                if len(keys) > 1:
                    self.audit_report["multi_map_variants"].append(variant_key)
            
            p_roll_display = self.perfect_rolls.get(variant_key, "")
            # Example format string: " [{fg} fg]"
            # If we have perfect rolls, we insert them right before the price string.
            # Arachnid Mesh ➔ Arachnid Mesh ÿcO[120ed] ÿc3(20-150 fg)
            actual_price_suffix = price_suffix
            if p_roll_display:
                if self.apply_colors:
                    actual_price_suffix = f" {self.D2R_COLOR_PREFIX}O{p_roll_display}{actual_price_suffix}"
                else:
                    actual_price_suffix = f" {p_roll_display}{actual_price_suffix}"

            # If it's a unique or set, we don't want to show base hints like "Spirit: 4os" on the already
            # identified unique item name. We disable apply_base_hint in this branch.
            apply_hint = kind not in ("unique", "set")

            for k in keys:
                if k:
                    upsert_key(k, actual_price_suffix, val, apply_base_hint=apply_hint)
            if self.collect_explain and len(self.audit_report["sample_injections"]) < self.explain_limit:
                self.audit_report["sample_injections"].append({
                    "variant_key": variant_key,
                    "kind": kind,
                    "fg_value": round(float(val), 2),
                    "price_mode": self.price_mode,
                    "forced_match": bool(is_forced and val < self.min_fg),
                    "mapped_keys": keys,
                    "mapped_key_count": len(keys),
                    "multi_map": len(keys) > 1,
                    "color_tag": color_code_for_fg(val) if self.apply_colors else None,
                    "tag_text": price_suffix,
                })

        # Process static runes
        if runes_mod_data and self.rune_converter:
            if is_runes_dict_format:
                for key, val in runes_mod_data.items():
                    name_str = val if isinstance(val, str) else val.get("enUS", "")
                    if name_str.lower().endswith(" rune"):
                        suffix = self.rune_converter.get_rune_price_suffix(name_str, self.format_str)
                        if suffix:
                            fg_val = self.rune_converter.get_rune_price(name_str)
                            # Apply the exact same formatting rules as upsert_key
                            if self.apply_colors:
                                color_code = color_code_for_fg(fg_val)
                                new_val = f"{name_str} {color_code}{suffix.strip()}{self.D2R_COLOR_RESET}"
                            else:
                                new_val = f"{name_str}{suffix}"
                                
                            if isinstance(val, str):
                                runes_mod_data[key] = new_val
                            else:
                                val["enUS"] = new_val
            else:
                for item in runes_mod_data:
                    name_str = item.get("enUS", "")
                    if name_str.lower().endswith(" rune"):
                        suffix = self.rune_converter.get_rune_price_suffix(name_str, self.format_str)
                        if suffix:
                            fg_val = self.rune_converter.get_rune_price(name_str)
                            if self.apply_colors:
                                color_code = color_code_for_fg(fg_val)
                                new_val = f"{name_str} {color_code}{suffix.strip()}{self.D2R_COLOR_RESET}"
                            else:
                                new_val = f"{name_str}{suffix}"
                            item["enUS"] = new_val

            # Write out item-runes.json if a path was given, saving to same dir as output (handled upstream)
            # This class just modifies the object. But we need to return it alongside mod_data.
            # A cleaner way is to let the caller handle runes file save.
            self.runes_mod_data_out = json.dumps(runes_mod_data, indent=2, ensure_ascii=False)

        return json.dumps(mod_data, indent=2, ensure_ascii=False)

    def export_affixes(self, base_affix_json_path: str) -> str:
        """
        Loads item-nameaffixes.json, applies AffixHighlighter, and returns the modified JSON text.
        """
        if not self.affix_highlighter or not Path(base_affix_json_path).exists():
            return "{}"

        with open(base_affix_json_path, "r", encoding="utf-8") as f:
            mod_data = json.load(f)

        is_dict_format = isinstance(mod_data, dict)

        if is_dict_format:
            for key, val in mod_data.items():
                if isinstance(val, str):
                    # We don't strictly know if it's prefix or suffix from just the string value in dict format,
                    # but usually suffixes start with "of "
                    if val.startswith("of "):
                        mod_data[key] = self.affix_highlighter.highlight_suffix(val)
                    else:
                        mod_data[key] = self.affix_highlighter.highlight_prefix(val)
                elif isinstance(val, dict) and "enUS" in val:
                    str_val = val["enUS"]
                    if str_val.startswith("of "):
                        val["enUS"] = self.affix_highlighter.highlight_suffix(str_val)
                    else:
                        val["enUS"] = self.affix_highlighter.highlight_prefix(str_val)
        else:
            for item in mod_data:
                str_val = item.get("enUS", "")
                if str_val.startswith("of "):
                    item["enUS"] = self.affix_highlighter.highlight_suffix(str_val)
                elif str_val:
                    item["enUS"] = self.affix_highlighter.highlight_prefix(str_val)

        return json.dumps(mod_data, indent=2, ensure_ascii=False)
