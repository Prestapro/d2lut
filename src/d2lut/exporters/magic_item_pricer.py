"""Extended Affix Highlighter with FG pricing and ilvl display.

When magic items drop, this module:
1. Detects prefix + suffix combinations
2. Estimates FG value based on affix prices
3. Shows item level
4. Applies color coding by value tier
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class AffixPriceResult:
    """Result of affix price lookup."""
    estimated_fg: float
    tier: str  # gg, high, medium, low, trash
    color: str
    tag: str
    ilvl_display: str
    notes: str
    is_lld: bool


class MagicItemPricer:
    """Price magic items based on affix combinations and item level."""
    
    # Color codes for D2R
    COLORS = {
        "gg": "ÿc1",      # Red
        "high": "ÿc;",    # Purple
        "medium": "ÿc8",  # Orange
        "low": "ÿc3",     # Blue
        "trash": "ÿc5",   # Gray
    }
    
    TIER_THRESHOLDS = {
        "gg": 1000,     # 1000+ fg = GG tier
        "high": 500,    # 500+ fg = High tier
        "medium": 100,  # 100+ fg = Medium tier
        "low": 10,      # 10+ fg = Low tier
    }
    
    def __init__(self, config_path: str | Path | None = None):
        self.combinations: dict = {}
        self.single_affix_values: dict = {}
        self.ilvl_multipliers: dict = {}
        self.lld_ilvl_tiers: dict = {}
        
        # Complete affix database
        self.magic_prefixes: dict = {}
        self.magic_suffixes: dict = {}
        self.rare_prefixes: dict = {}
        self.gg_combinations: dict = {}
        
        if config_path:
            self._load_config(Path(config_path))
        else:
            # Default config paths
            default_path = Path(__file__).parent.parent.parent.parent / "config" / "magic_affix_prices.yml"
            if default_path.exists():
                self._load_config(default_path)
            
            # Load comprehensive affix database (prefer d2data version)
            # Priority: d2data > complete > base
            affix_db_path = Path(__file__).parent.parent.parent.parent / "config" / "affix_database_d2data.yml"
            if not affix_db_path.exists():
                affix_db_path = Path(__file__).parent.parent.parent.parent / "config" / "affix_database_complete.yml"
            if not affix_db_path.exists():
                affix_db_path = Path(__file__).parent.parent.parent.parent / "config" / "affix_database.yml"
            if affix_db_path.exists():
                self._load_affix_database(affix_db_path)
    
    def _load_config(self, config_path: Path) -> None:
        """Load affix pricing configuration."""
        if not config_path.exists():
            return
        
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        self.combinations = data.get("combinations", {})
        self.single_affix_values = data.get("single_affix_values", {})
        self.ilvl_multipliers = data.get("ilvl_multipliers", {})
        self.lld_ilvl_tiers = data.get("lld_ilvl_tiers", {})
    
    def _load_affix_database(self, db_path: Path) -> None:
        """Load comprehensive affix database with all affixes from game files."""
        if not db_path.exists():
            return
        
        with open(db_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        # Support both old and new structure
        self.magic_prefixes = data.get("magic_prefixes", data.get("prefixes", {}))
        self.magic_suffixes = data.get("magic_suffixes", data.get("suffixes", {}))
        self.rare_prefixes = data.get("rare_prefixes", {})
        self.gg_combinations = data.get("gg_combinations", {})
        
        # Merge tier thresholds from database if present
        if "tier_thresholds" in data:
            self.TIER_THRESHOLDS = data["tier_thresholds"]
        
        # Merge ilvl multipliers from database if not already loaded
        if not self.ilvl_multipliers and "ilvl_multipliers" in data:
            self.ilvl_multipliers = data["ilvl_multipliers"]
        
        # Merge LLD tiers if not already loaded
        if not self.lld_ilvl_tiers and "lld_ilvl_tiers" in data:
            self.lld_ilvl_tiers = data["lld_ilvl_tiers"]
        
        # Build single_affix_values from prefixes + suffixes
        # This provides fallback pricing for any affix in the database
        for name, info in self.magic_prefixes.items():
            if name not in self.single_affix_values:
                # Handle variants
                if "variants" in info:
                    # Use highest price from variants
                    max_price = max(v.get("base_price", 0) for v in info["variants"])
                    self.single_affix_values[name] = {
                        "base_price": max_price,
                        "property": info.get("notes", ""),
                        "notes": info.get("notes", ""),
                    }
                else:
                    self.single_affix_values[name] = {
                        "base_price": info.get("base_price", 0),
                        "property": info.get("property", ""),
                        "notes": info.get("notes", ""),
                    }
        
        for name, info in self.magic_suffixes.items():
            # Handle "of " prefix for lookup
            lookup_name = name
            if lookup_name not in self.single_affix_values:
                if "variants" in info:
                    max_price = max(v.get("base_price", 0) for v in info["variants"])
                    self.single_affix_values[lookup_name] = {
                        "base_price": max_price,
                        "property": info.get("notes", ""),
                        "notes": info.get("notes", ""),
                    }
                else:
                    self.single_affix_values[lookup_name] = {
                        "base_price": info.get("base_price", 0),
                        "property": info.get("property", ""),
                        "notes": info.get("notes", ""),
                    }
        
        for name, info in self.rare_prefixes.items():
            if name not in self.single_affix_values:
                self.single_affix_values[name] = {
                    "base_price": info.get("base_price", 0),
                    "property": info.get("property", ""),
                    "notes": info.get("notes", ""),
                }
    
    def price_item(
        self,
        prefix: str,
        suffix: str,
        item_type: str,
        ilvl: int,
        roll_percent: float = 50.0,  # 0-100, how good the roll is
    ) -> AffixPriceResult:
        """
        Estimate FG value for a magic item.
        
        Args:
            prefix: Item prefix (e.g., "Jeweler's")
            suffix: Item suffix (e.g., "of Deflecting")
            item_type: Base item type code (e.g., "uit", "amu")
            ilvl: Item level (0-99)
            roll_percent: Quality of roll (0-100)
        
        Returns:
            AffixPriceResult with estimated value and display info
        """
        
        # 1. Check for exact prefix + suffix combination
        combo_key = f"{prefix} + {suffix}"
        combo_data = self.combinations.get(combo_key)
        
        base_price = 0.0
        notes = ""
        is_lld = False
        
        if combo_data:
            # Check if item type matches
            valid_types = combo_data.get("item_types", [])
            if not valid_types or item_type in valid_types:
                # Check min ilvl
                min_ilvl = combo_data.get("min_ilvl", 0)
                if ilvl >= min_ilvl:
                    # Calculate price based on roll quality
                    base_price = combo_data.get("base_price", 0)
                    perfect_price = combo_data.get("perfect_price", base_price * 2)
                    
                    # Interpolate based on roll percent
                    price = base_price + (perfect_price - base_price) * (roll_percent / 100.0)
                    notes = combo_data.get("notes", "")
                    is_lld = combo_data.get("lld_only", False)
        
        # 2. Check GG combinations from database
        if base_price == 0:
            gg_combo_key = f"{prefix} {suffix}"  # e.g., "Jeweler's Monarch of Deflecting"
            for combo_name, combo_data in self.gg_combinations.items():
                if combo_data.get("prefix") == prefix and combo_data.get("suffix") == suffix:
                    base_price = combo_data.get("base_price", 0)
                    perfect_price = combo_data.get("perfect_price", base_price * 2)
                    price = base_price + (perfect_price - base_price) * (roll_percent / 100.0)
                    notes = combo_data.get("notes", "")
                    break
        
        # 3. If no combo match, sum single affix values
        if base_price == 0:
            prefix_price = self.single_affix_values.get(prefix, {}).get("base_price", 0)
            suffix_price = self.single_affix_values.get(suffix, {}).get("base_price", 0)
            base_price = (prefix_price + suffix_price) * (roll_percent / 100.0)
            price = base_price  # Initialize price from single affix calculation
        
        # 4. Apply ilvl multiplier to price
        ilvl_mult = self._get_ilvl_multiplier(ilvl)
        price = price * ilvl_mult
        
        # 5. Check for LLD bonus
        lld_mult = self._get_lld_multiplier(ilvl)
        if lld_mult > 1.0:
            price *= lld_mult
            is_lld = True
        
        # 6. Determine tier
        tier = self._price_to_tier(price)
        color = self.COLORS.get(tier, "ÿc0")
        
        # 7. Generate tag based on value
        if price >= 10000:
            tag = "[GG]"
        elif price >= 5000:
            tag = "[$$$$$]"
        elif price >= 1000:
            tag = "[$$$$]"
        elif price >= 500:
            tag = "[$$$]"
        elif price >= 100:
            tag = "[$$]"
        elif price >= 10:
            tag = "[$]"
        else:
            tag = ""
        
        # 8. Generate ilvl display
        ilvl_display = self._format_ilvl(ilvl, is_lld)
        
        return AffixPriceResult(
            estimated_fg=round(price, 1),
            tier=tier,
            color=color,
            tag=tag,
            ilvl_display=ilvl_display,
            notes=notes,
            is_lld=is_lld,
        )
    
    def _get_ilvl_multiplier(self, ilvl: int) -> float:
        """Get price multiplier based on item level."""
        for threshold, mult in sorted(self.ilvl_multipliers.items(), key=lambda x: -x[0]):
            if ilvl >= threshold:
                return mult
        return 1.0
    
    def _get_lld_multiplier(self, ilvl: int) -> float:
        """Get LLD bonus multiplier."""
        for threshold, mult in sorted(self.lld_ilvl_tiers.items(), key=lambda x: x[0]):
            if ilvl <= threshold:
                return mult
        return 1.0
    
    def _price_to_tier(self, price: float) -> str:
        """Convert price to tier string."""
        if price >= self.TIER_THRESHOLDS["gg"]:
            return "gg"
        elif price >= self.TIER_THRESHOLDS["high"]:
            return "high"
        elif price >= self.TIER_THRESHOLDS["medium"]:
            return "medium"
        elif price >= self.TIER_THRESHOLDS["low"]:
            return "low"
        return "trash"
    
    def _format_ilvl(self, ilvl: int, is_lld: bool) -> str:
        """Format ilvl for display."""
        if is_lld:
            return f"ÿc;ilvl{ilvl} LLDÿc0"
        elif ilvl >= 90:
            return f"ÿc1ilvl{ilvl}ÿc0"
        elif ilvl >= 80:
            return f"ÿc;ilvl{ilvl}ÿc0"
        else:
            return f"ÿc8ilvl{ilvl}ÿc0"
    
    def format_magic_item_name(
        self,
        prefix: str,
        base_name: str,
        suffix: str,
        item_type: str,
        ilvl: int,
        roll_percent: float = 50.0,
    ) -> str:
        """
        Format a complete magic item name with price and ilvl.
        
        Example output:
            "ÿc1[$$$] Jeweler's Monarch of Deflecting ÿc1[50fg] ÿc8ilvl90ÿc0"
        """
        result = self.price_item(prefix, suffix, item_type, ilvl, roll_percent)
        
        parts = []
        
        # Prefix with color and tag
        if result.tag:
            parts.append(f"{result.color}{result.tag}")
        
        # Item name
        parts.append(f"{result.color}{prefix} {base_name}")
        if suffix:
            parts.append(f" {suffix}")
        
        # Price tag
        if result.estimated_fg >= 1:
            parts.append(f" {result.color}[{result.estimated_fg:.0f}fg]")
        
        # ilvl
        parts.append(f" {result.ilvl_display}")
        
        # Reset color
        parts.append("ÿc0")
        
        return "".join(parts)


class ExtendedAffixHighlighter:
    """Extended version with FG pricing and ilvl display."""
    
    def __init__(
        self,
        gg_affixes_path: str | Path,
        magic_prices_path: str | Path | None = None,
    ):
        self.gg_affixes_path = Path(gg_affixes_path)
        self.prefixes: dict = {}
        self.suffixes: dict = {}
        self.pricer = MagicItemPricer(magic_prices_path)
        self._load_gg_affixes()
    
    def _load_gg_affixes(self) -> None:
        """Load GG affixes configuration."""
        if not self.gg_affixes_path.exists():
            return
        
        with open(self.gg_affixes_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        self.prefixes = data.get("prefixes", {})
        self.suffixes = data.get("suffixes", {})
    
    def highlight_prefix_with_price(
        self,
        prefix: str,
        item_type: str = "",
        ilvl: int = 0,
    ) -> str:
        """Highlight prefix with price estimation if possible."""
        
        if prefix not in self.prefixes:
            # Try to price it anyway
            if ilvl > 0:
                single_data = self.pricer.single_affix_values.get(prefix, {})
                if single_data:
                    price = single_data.get("base_price", 0) * self.pricer._get_ilvl_multiplier(ilvl)
                    color = "ÿc;" if price >= 5 else "ÿc8"
                    return f"{color}{prefix} [{price:.0f}fg]ÿc0"
            return prefix
        
        conf = self.prefixes[prefix]
        color = conf.get("color", "ÿc0")
        tag = conf.get("tag", "")
        
        if tag:
            return f"{color}{tag} {prefix}ÿc0"
        return f"{color}{prefix}ÿc0"
    
    def highlight_suffix_with_price(
        self,
        suffix: str,
        item_type: str = "",
        ilvl: int = 0,
    ) -> str:
        """Highlight suffix with price estimation if possible."""
        
        if suffix not in self.suffixes:
            # Try to price it anyway
            if ilvl > 0:
                single_data = self.pricer.single_affix_values.get(suffix, {})
                if single_data:
                    price = single_data.get("base_price", 0) * self.pricer._get_ilvl_multiplier(ilvl)
                    color = "ÿc;" if price >= 5 else "ÿc8"
                    return f"ÿc9{suffix} {color}[{price:.0f}fg]ÿc0"
            return suffix
        
        conf = self.suffixes[suffix]
        color = conf.get("color", "")
        tag = conf.get("tag", "")
        
        if tag:
            return f"ÿc9{suffix} {color}{tag}ÿc0"
        return f"{color}{suffix}ÿc0"
    
    def format_magic_item(
        self,
        prefix: str,
        base_name: str,
        suffix: str,
        item_type: str,
        ilvl: int,
        roll_percent: float = 50.0,
    ) -> str:
        """
        Format a complete magic item with affix highlighting + price + ilvl.
        
        This is the main entry point for displaying magic items on ground.
        """
        return self.pricer.format_magic_item_name(
            prefix=prefix,
            base_name=base_name,
            suffix=suffix,
            item_type=item_type,
            ilvl=ilvl,
            roll_percent=roll_percent,
        )


# ---------------------------------------------------------------------------
# Convenience function for loot filter integration
# ---------------------------------------------------------------------------

def get_magic_item_display(
    prefix: str,
    base_name: str,
    suffix: str,
    item_type: str,
    ilvl: int,
    roll_quality: float = 50.0,
) -> str:
    """
    Get formatted display string for a magic item.
    
    Args:
        prefix: Item prefix (e.g., "Jeweler's", "Arch-Angel's")
        base_name: Base item name (e.g., "Monarch", "Amulet")
        suffix: Item suffix (e.g., "of Deflecting", "of the Magus")
        item_type: D2R item type code (e.g., "uit", "amu", "rin")
        ilvl: Item level (0-99)
        roll_quality: Roll quality 0-100 (default 50 for average)
    
    Returns:
        Formatted string for D2R display with colors, price, and ilvl
    
    Example:
        >>> get_magic_item_display("Jeweler's", "Monarch", "of Deflecting", "uit", 50)
        "ÿc1[$$$] Jeweler's Monarch of Deflecting ÿc1[50fg] ÿc8ilvl50ÿc0"
    """
    highlighter = ExtendedAffixHighlighter(
        gg_affixes_path=Path(__file__).parent.parent.parent.parent / "config" / "gg_affixes.yml",
        magic_prices_path=Path(__file__).parent.parent.parent.parent / "config" / "magic_affix_prices.yml",
    )
    
    return highlighter.format_magic_item(
        prefix=prefix,
        base_name=base_name,
        suffix=suffix,
        item_type=item_type,
        ilvl=ilvl,
        roll_percent=roll_quality,
    )
