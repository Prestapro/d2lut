"""Category-aware parsing helpers for overlay OCR output.

This module enriches ``ParsedItem`` with lightweight category-specific hints
before catalog identification. It is intentionally conservative: it only adds
derived hints when confidence is reasonable and does not overwrite explicit OCR
parses unless the field is missing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Pattern, Callable

from .ocr_parser import ParsedItem, Property
from d2lut.normalize.modifier_lexicon import property_allowed_by_category_constraints


@dataclass(frozen=True)
class CategoryRules:
    """Minimal rule bundle for category-aware parsing."""
    name_patterns: list[Pattern[str]]
    special_handling: list[str]
    property_extraction: dict[str, Callable[[str], list[Property]]] = None

    def __post_init__(self):
        if self.property_extraction is None:
            object.__setattr__(self, 'property_extraction', {})


class CategoryAwareParser:
    """Apply conservative category-specific heuristics to OCR parsed items."""

    _RUNE_NAMES = {
        "el", "eld", "tir", "nef", "eth", "ith", "tal", "ral", "ort", "thul",
        "amn", "sol", "shael", "dol", "hel", "io", "lum", "ko", "fal", "lem",
        "pul", "um", "mal", "ist", "gul", "vex", "ohm", "lo", "sur", "ber",
        "jah", "cham", "zod",
    }
    _SET_MARKERS = ("tal rasha", "immortal king", "m'avina", "griswold", "natalya")
    _UNIQUE_HINTS = ("harlequin crest", "the stone of jordan", "arachnid mesh", "annihilus")
    
    # Property extraction regex patterns
    _RE_SOCKETS = re.compile(r"\b(\d+)\s*(?:sockets?|os)\b", re.I)
    _RE_ED = re.compile(r"\b(\d+)%?\s*(?:enhanced damage|ed)\b", re.I)
    _RE_DEFENSE = re.compile(r"\b(?:defense|def):\s*(\d+)\b", re.I)
    _RE_IAS = re.compile(r"\b(\d+)%?\s*(?:increased attack speed|ias)\b", re.I)
    _RE_FCR = re.compile(r"\b(\d+)%?\s*(?:faster cast rate|fcr)\b", re.I)
    _RE_FRW = re.compile(r"\b(\d+)%?\s*(?:faster run/walk|frw)\b", re.I)
    _RE_FHR = re.compile(r"\b(\d+)%?\s*(?:faster hit recovery|fhr)\b", re.I)
    _RE_LIFE = re.compile(r"\b\+?(\d+)\s*(?:to life|life)\b", re.I)
    _RE_MANA = re.compile(r"\b\+?(\d+)\s*(?:to mana|mana)\b", re.I)
    _RE_ALL_RES = re.compile(r"\b\+?(\d+)\s*(?:to all resistances|all res)\b", re.I)
    _RE_FIRE_RES = re.compile(r"\b\+?(\d+)%?\s*(?:fire resist(?:ance)?|fr)\b", re.I)
    _RE_COLD_RES = re.compile(r"\b\+?(\d+)%?\s*(?:cold resist(?:ance)?|cr)\b", re.I)
    _RE_LIGHT_RES = re.compile(r"\b\+?(\d+)%?\s*(?:lightning resist(?:ance)?|lr)\b", re.I)
    _RE_POISON_RES = re.compile(r"\b\+?(\d+)%?\s*(?:poison resist(?:ance)?|pr)\b", re.I)
    _RE_MAX_DMG = re.compile(r"\b\+?(\d+)\s*(?:to maximum damage|max(?:imum)? damage)\b", re.I)
    _RE_AR = re.compile(r"\b\+?(\d+)\s*(?:to attack rating|ar)\b", re.I)
    _RE_SKILLS = re.compile(r"\b\+?(\d+)\s*(?:to all skills|all skills|skills)\b", re.I)
    _RE_ETHEREAL = re.compile(r"\b(?:ethereal|eth)\b", re.I)
    _RE_MF = re.compile(r"\b(\d+)%?\s*(?:better chance of getting magic items|magic find|mf)\b", re.I)
    _RE_CHARM_SIZE = re.compile(r"\b(small|large|grand)\s+charm\b", re.I)
    
    # Base type patterns for weapons and armor (covers common D2R tooltip bases)
    _WEAPON_BASES = {
        "phase blade", "berserker axe", "colossus voulge", "thresher",
        "giant thresher", "cryptic axe", "great poleaxe",
        "colossus blade", "war pike", "thunder maul", "caduceus",
        "flail", "crystal sword", "broad sword", "dimensional blade",
        "matriarchal javelin", "matriarchal pike", "matriarchal bow",
        "hydra bow", "ward bow", "crusader bow",
        "suwayyah", "scissors suwayyah", "greater talons", "feral claws",
    }
    _ARMOR_BASES = {
        "archon plate", "mage plate", "dusk shroud", "wire fleece",
        "wyrmhide", "light plate",
        "lacquered plate", "shadow plate", "sacred armor",
        "shako", "diadem", "tiara", "circlet", "coronet",
        "bone visage", "spired helm", "corona",
        "druid pelt", "sky spirit", "dream spirit",
        "vortex shield", "troll nest", "blade barrier",
    }
    _SHIELD_BASES = {
        "monarch", "sacred targe", "sacred rondache",
        "kurast shield", "zakarum shield", "aegis",
        "ward", "heraldic shield",
    }

    def __init__(self) -> None:
        self._rules: dict[str, CategoryRules] = {
            "runes": CategoryRules(
                name_patterns=[re.compile(r"\b(" + "|".join(sorted(self._RUNE_NAMES)) + r")\b", re.I)],
                special_handling=["rune_disambiguation"],
                property_extraction={"rune_name": self._extract_rune_name},
            ),
            "charms": CategoryRules(
                name_patterns=[re.compile(r"\b(small|large|grand)\s+charm\b", re.I), re.compile(r"\bcharm\b", re.I)],
                special_handling=["charm_subtype"],
                property_extraction={
                    "charm_size": self._extract_charm_size,
                    "life": self._extract_life,
                    "mana": self._extract_mana,
                    "resistances": self._extract_resistances,
                    "skills": self._extract_skills,
                    "max_damage": self._extract_max_damage,
                    "ar": self._extract_ar,
                    "fhr": self._extract_fhr,
                    "frw": self._extract_frw,
                    "mf": self._extract_mf,
                },
            ),
            "jewels": CategoryRules(
                name_patterns=[re.compile(r"\bjewel\b", re.I)],
                special_handling=["jewel_properties"],
                property_extraction={
                    "ias": self._extract_ias,
                    "ed": self._extract_ed,
                    "resistances": self._extract_resistances,
                    "max_damage": self._extract_max_damage,
                    "fcr": self._extract_fcr,
                    "fhr": self._extract_fhr,
                    "mf": self._extract_mf,
                },
            ),
            "weapons": CategoryRules(
                name_patterns=[re.compile(r"\b(" + "|".join(self._WEAPON_BASES) + r")\b", re.I)],
                special_handling=["weapon_properties"],
                property_extraction={
                    "ed": self._extract_ed,
                    "sockets": self._extract_sockets,
                    "ethereal": self._extract_ethereal,
                    "ias": self._extract_ias,
                    "fcr": self._extract_fcr,
                    "base": self._extract_weapon_base,
                },
            ),
            "armor": CategoryRules(
                name_patterns=[re.compile(r"\b(" + "|".join(self._ARMOR_BASES | self._SHIELD_BASES) + r")\b", re.I)],
                special_handling=["armor_properties"],
                property_extraction={
                    "defense": self._extract_defense,
                    "sockets": self._extract_sockets,
                    "ethereal": self._extract_ethereal,
                    "resistances": self._extract_resistances,
                    "fcr": self._extract_fcr,
                    "fhr": self._extract_fhr,
                    "frw": self._extract_frw,
                    "life": self._extract_life,
                    "base": self._extract_armor_base,
                },
            ),
            "lld": CategoryRules(
                name_patterns=[re.compile(r"\blld\b", re.I)],
                special_handling=["lld_tag"],
                property_extraction={},
            ),
            "default": CategoryRules(name_patterns=[], special_handling=[], property_extraction={}),
        }

    def get_category_rules(self, category: str) -> CategoryRules:
        """Return rules for a category key."""
        return self._rules.get(category.lower(), self._rules["default"])

    def parse_with_category(self, parsed: ParsedItem, category_hint: str | None = None) -> ParsedItem:
        """Enrich a parsed item with category-specific hints.

        Args:
            parsed: OCR parsed item
            category_hint: Optional context hint, e.g. ``runes``, ``charms``, ``lld``
        """
        if parsed is None:
            raise ValueError("parsed cannot be None")

        text = (parsed.raw_text or "").lower()
        item_name = (parsed.item_name or "").lower()
        combined = f"{item_name}\n{text}".strip()

        enriched = replace(parsed)
        enriched.diagnostic = dict(parsed.diagnostic)

        detected_category = self._infer_category(combined, category_hint)
        if detected_category:
            enriched.diagnostic["category_hint_applied"] = detected_category

        # Item type inference (only fill when missing)
        if not enriched.item_type:
            inferred_type = self._infer_item_type(combined, detected_category)
            if inferred_type:
                enriched.item_type = inferred_type
                enriched.diagnostic["category_inferred_item_type"] = inferred_type

        # Quality hints (conservative)
        if not enriched.quality:
            inferred_quality = self._infer_quality(item_name, text)
            if inferred_quality:
                enriched.quality = inferred_quality
                enriched.diagnostic["category_inferred_quality"] = inferred_quality

        # LLD marker is useful even if it doesn't change type/quality
        if detected_category == "lld" or " lld " in f" {combined} ":
            enriched.diagnostic["lld_context"] = True

        # Extract category-specific properties
        # For LLD items, also extract properties from the underlying item type
        categories_to_extract = [detected_category] if detected_category else []
        
        # If LLD, also detect and extract from the underlying item category
        if detected_category == "lld":
            underlying_category = self._infer_underlying_category(combined)
            if underlying_category:
                categories_to_extract.append(underlying_category)
        
        extracted_props = []
        for cat in categories_to_extract:
            if cat:
                rules = self.get_category_rules(cat)
                for prop_name, extractor in rules.property_extraction.items():
                    props = extractor(combined)
                    extracted_props.extend(props)

        # Apply coarse category constraints to reduce impossible property combos.
        # This is intentionally conservative and only removes obvious mismatches.
        # Note: "weapons"/"armor" detected categories are NOT mapped to base_weapon/base_armor
        # constraints because those allowlists are too restrictive for equipped/runeword items.
        constraint_category = None
        if detected_category in {"runes", "torch", "anni", "jewels"}:
            constraint_category = "jewel" if detected_category == "jewels" else detected_category
        elif detected_category == "charms":
            constraint_category = "charm"
        if extracted_props and constraint_category:
            before_n = len(extracted_props)
            extracted_props = [
                p for p in extracted_props
                if property_allowed_by_category_constraints(constraint_category, p.name)
            ]
            if len(extracted_props) != before_n:
                enriched.diagnostic["category_constraints_filtered"] = before_n - len(extracted_props)

        # Add extracted properties to base_properties if not already present
        if extracted_props:
            existing_prop_names = {p.name for p in enriched.base_properties}
            new_props = [p for p in extracted_props if p.name not in existing_prop_names]
            if new_props:
                enriched.base_properties = list(enriched.base_properties) + new_props
                enriched.diagnostic["category_extracted_properties"] = [p.name for p in new_props]

        return enriched

    def _infer_category(self, text: str, category_hint: str | None) -> str | None:
        if category_hint:
            hint = category_hint.lower().strip()
            if hint in self._rules:
                return hint
            # Normalize common numeric/label forms
            aliases = {
                "c=2": "runes",
                "2": "runes",
                "rune": "runes",
                "c=3": "charms",
                "3": "charms",
                "charm": "charms",
                "c=5": "lld",
                "5": "lld",
            }
            if hint in aliases:
                return aliases[hint]

        # Check for weapons
        for base in self._WEAPON_BASES:
            if base in text:
                return "weapons"
        
        # Check for armor
        for base in self._ARMOR_BASES | self._SHIELD_BASES:
            if base in text:
                return "armor"
        
        # Check for jewels
        if "jewel" in text and "jewel fragment" not in text:
            return "jewels"
        
        # Check for runes
        if self.get_category_rules("runes").name_patterns[0].search(text) and " rune" in text:
            return "runes"
        
        # Check for charms
        if "charm" in text:
            return "charms"
        
        # Check for LLD
        if "lld" in text:
            return "lld"
        
        return None

    def _infer_underlying_category(self, text: str) -> str | None:
        """Infer the underlying item category for LLD items."""
        # Check for weapons
        for base in self._WEAPON_BASES:
            if base in text:
                return "weapons"
        
        # Check for armor
        for base in self._ARMOR_BASES | self._SHIELD_BASES:
            if base in text:
                return "armor"
        
        # Check for jewels
        if "jewel" in text and "jewel fragment" not in text:
            return "jewels"
        
        # Check for charms
        if "charm" in text:
            return "charms"
        
        # Check for runes
        if self.get_category_rules("runes").name_patterns[0].search(text) and " rune" in text:
            return "runes"
        
        return None

    def _infer_item_type(self, text: str, detected_category: str | None) -> str | None:
        if detected_category == "runes":
            # Require either explicit "rune" or bare rune name as item name-like token
            if "rune" in text:
                return "rune"
            tokens = re.findall(r"[a-z']+", text)
            if any(t in self._RUNE_NAMES for t in tokens[:4]):
                return "rune"

        if "small charm" in text:
            return "charm"
        if "large charm" in text:
            return "charm"
        if "grand charm" in text:
            return "charm"
        if " charm" in text:
            return "charm"
        if " amulet" in text or text.strip().endswith("amulet"):
            return "amulet"
        if " ring" in text or text.strip().endswith("ring"):
            return "ring"
        if " jewel" in text or text.strip().endswith("jewel"):
            return "jewel"
        return None

    def _infer_quality(self, item_name: str, raw_text: str) -> str | None:
        combined = f"{item_name} {raw_text}".lower()
        if any(marker in combined for marker in self._SET_MARKERS):
            return "set"
        if any(marker in combined for marker in self._UNIQUE_HINTS):
            return "unique"
        if "unique" in combined:
            return "unique"
        if "set " in combined or " set" in combined:
            return "set"
        if "rare" in combined:
            return "rare"
        if "magic" in combined:
            return "magic"
        return None

    # Property extraction methods
    def _extract_sockets(self, text: str) -> list[Property]:
        """Extract socket count from text."""
        m = self._RE_SOCKETS.search(text)
        if m:
            return [Property(name="sockets", value=m.group(1))]
        return []

    def _extract_ed(self, text: str) -> list[Property]:
        """Extract enhanced damage percentage from text."""
        m = self._RE_ED.search(text)
        if m:
            return [Property(name="enhanced_damage", value=f"{m.group(1)}%")]
        return []

    def _extract_defense(self, text: str) -> list[Property]:
        """Extract defense value from text."""
        m = self._RE_DEFENSE.search(text)
        if m:
            return [Property(name="defense", value=m.group(1))]
        return []

    def _extract_ias(self, text: str) -> list[Property]:
        """Extract increased attack speed from text."""
        m = self._RE_IAS.search(text)
        if m:
            return [Property(name="ias", value=f"{m.group(1)}%")]
        return []

    def _extract_fcr(self, text: str) -> list[Property]:
        """Extract faster cast rate from text."""
        m = self._RE_FCR.search(text)
        if m:
            return [Property(name="fcr", value=f"{m.group(1)}%")]
        return []

    def _extract_frw(self, text: str) -> list[Property]:
        """Extract faster run/walk from text."""
        m = self._RE_FRW.search(text)
        if m:
            return [Property(name="frw", value=f"{m.group(1)}%")]
        return []

    def _extract_fhr(self, text: str) -> list[Property]:
        """Extract faster hit recovery from text."""
        m = self._RE_FHR.search(text)
        if m:
            return [Property(name="fhr", value=f"{m.group(1)}%")]
        return []

    def _extract_mana(self, text: str) -> list[Property]:
        """Extract mana bonus from text."""
        m = self._RE_MANA.search(text)
        if m:
            return [Property(name="mana", value=m.group(1))]
        return []

    def _extract_mf(self, text: str) -> list[Property]:
        """Extract magic find from text."""
        m = self._RE_MF.search(text)
        if m:
            return [Property(name="magic_find", value=f"{m.group(1)}%")]
        return []

    def _extract_life(self, text: str) -> list[Property]:
        """Extract life bonus from text."""
        m = self._RE_LIFE.search(text)
        if m:
            return [Property(name="life", value=m.group(1))]
        return []

    def _extract_resistances(self, text: str) -> list[Property]:
        """Extract resistance values from text."""
        props = []
        
        # Check for all resistances first
        m = self._RE_ALL_RES.search(text)
        if m:
            props.append(Property(name="all_resistances", value=m.group(1)))
            return props
        
        # Check individual resistances
        m = self._RE_FIRE_RES.search(text)
        if m:
            props.append(Property(name="fire_resistance", value=m.group(1)))
        
        m = self._RE_COLD_RES.search(text)
        if m:
            props.append(Property(name="cold_resistance", value=m.group(1)))
        
        m = self._RE_LIGHT_RES.search(text)
        if m:
            props.append(Property(name="lightning_resistance", value=m.group(1)))
        
        m = self._RE_POISON_RES.search(text)
        if m:
            props.append(Property(name="poison_resistance", value=m.group(1)))
        
        return props

    def _extract_skills(self, text: str) -> list[Property]:
        """Extract skill bonuses from text."""
        m = self._RE_SKILLS.search(text)
        if m:
            return [Property(name="all_skills", value=m.group(1))]
        return []

    def _extract_max_damage(self, text: str) -> list[Property]:
        """Extract maximum damage from text."""
        m = self._RE_MAX_DMG.search(text)
        if m:
            return [Property(name="max_damage", value=m.group(1))]
        return []

    def _extract_ar(self, text: str) -> list[Property]:
        """Extract attack rating from text."""
        m = self._RE_AR.search(text)
        if m:
            return [Property(name="attack_rating", value=m.group(1))]
        return []

    def _extract_ethereal(self, text: str) -> list[Property]:
        """Extract ethereal status from text."""
        if self._RE_ETHEREAL.search(text):
            return [Property(name="ethereal", value="true")]
        return []

    def _extract_charm_size(self, text: str) -> list[Property]:
        """Extract charm size from text."""
        m = self._RE_CHARM_SIZE.search(text)
        if m:
            size = m.group(1).lower()
            return [Property(name="charm_size", value=size)]
        return []

    def _extract_rune_name(self, text: str) -> list[Property]:
        """Extract rune name from text."""
        for rune_name in self._RUNE_NAMES:
            if re.search(r"\b" + rune_name + r"\b", text, re.I):
                return [Property(name="rune_name", value=rune_name)]
        return []

    def _extract_weapon_base(self, text: str) -> list[Property]:
        """Extract weapon base type from text."""
        for base in self._WEAPON_BASES:
            if base in text:
                return [Property(name="base_type", value=base)]
        return []

    def _extract_armor_base(self, text: str) -> list[Property]:
        """Extract armor base type from text."""
        for base in self._ARMOR_BASES | self._SHIELD_BASES:
            if base in text:
                return [Property(name="base_type", value=base)]
        return []
