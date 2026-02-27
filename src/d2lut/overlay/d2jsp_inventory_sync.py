"""d2jsp Inventory Sync for FT/ISO list management.

Provides functionality to:
- Export inventory/stash items to d2jsp FT post format
- Parse ISO (In Search Of) lists for price alerts
- Sync with d2jsp trade threads
- Generate trade-ready listings with FG prices
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TradeItem:
    """An item for trade or wanted."""
    name: str
    canonical_id: str | None = None
    price_fg: float | None = None
    price_range: tuple[float, float] | None = None  # (low, high)
    quantity: int = 1
    notes: str = ""
    premium_info: str = ""  # e.g., "Perfect roll", "15ed"
    is_ft: bool = True  # FT (for trade) or ISO (in search of)
    category: str = ""  # rune, unique, set, base, charm, etc.


@dataclass
class FTList:
    """A complete For Trade list."""
    items: list[TradeItem] = field(default_factory=list)
    total_value_fg: float = 0.0
    generated_at: datetime = field(default_factory=datetime.now)
    title: str = "Items For Trade"
    notes: str = ""
    contact_info: str = ""


@dataclass
class ISOList:
    """A complete In Search Of list."""
    items: list[TradeItem] = field(default_factory=list)
    budget_fg: float | None = None
    generated_at: datetime = field(default_factory=datetime.now)
    title: str = "Items I'm Looking For"
    notes: str = ""


@dataclass
class TradeMatch:
    """A potential match between FT and ISO items."""
    ft_item: TradeItem
    iso_item: TradeItem
    price_match: bool  # ISO budget >= FT price
    match_score: float  # 0-1 similarity


# ---------------------------------------------------------------------------
# d2jsp formatting constants
# ---------------------------------------------------------------------------

D2JSP_BB_CODE = {
    "bold": ("[b]", "[/b]"),
    "italic": ("[i]", "[/i]"),
    "underline": ("[u]", "[/u]"),
    "color_red": ("[color=red]", "[/color]"),
    "color_green": ("[color=green]", "[/color]"),
    "color_blue": ("[color=blue]", "[/color]"),
    "color_purple": ("[color=purple]", "[/color]"),
    "color_orange": ("[color=orange]", "[/color]"),
    "size_large": ("[size=4]", "[/size]"),
    "url": ("[url=", "[/url]"),
    "quote": ("[quote]", "[/quote]"),
    "list": ("[list]", "[/list]"),
    "list_item": ("[*]", ""),
    "line": ("[hr]", ""),
}

# Category icons/emojis for d2jsp
CATEGORY_ICONS = {
    "rune": "💎",
    "unique": "🟡",
    "set": "🟢",
    "base": "📦",
    "charm": "🔮",
    "jewel": "💠",
    "runeword": "⚔️",
    "crafted": "🔨",
    "magic": "🔵",
    "rare": "🟠",
    "key": "🗝️",
    "token": "🎟️",
    "torch": "🔥",
    "anni": "⭐",
    "default": "•",
}


# ---------------------------------------------------------------------------
# FT List Generator
# ---------------------------------------------------------------------------

class FTListGenerator:
    """Generate d2jsp-compatible For Trade lists."""
    
    def __init__(self, use_bb_code: bool = True, use_icons: bool = True):
        self.use_bb_code = use_bb_code
        self.use_icons = use_icons
    
    def generate_ft_post(
        self,
        items: list[TradeItem],
        title: str = "Items For Trade",
        notes: str = "",
        iso_items: list[TradeItem] | None = None,
        format_style: str = "standard",  # "standard", "compact", "categorized"
    ) -> str:
        """Generate a complete d2jsp FT post."""
        
        lines = []
        
        # Title
        if self.use_bb_code:
            lines.append(f"{D2JSP_BB_CODE['size_large'][0]}{D2JSP_BB_CODE['bold'][0]}{title}{D2JSP_BB_CODE['bold'][1]}{D2JSP_BB_CODE['size_large'][1]}")
        else:
            lines.append(f"=== {title} ===")
        lines.append("")
        
        # Notes/intro
        if notes:
            lines.append(notes)
            lines.append("")
        
        # Total value
        total_value = sum(i.price_fg or 0 for i in items)
        if total_value > 0:
            if self.use_bb_code:
                lines.append(f"{D2JSP_BB_CODE['color_green'][0]}Total Value: ~{total_value:,.0f} fg{D2JSP_BB_CODE['color_green'][1]}")
            else:
                lines.append(f"Total Value: ~{total_value:,.0f} fg")
            lines.append("")
        
        # Items by format style
        if format_style == "categorized":
            lines.extend(self._format_categorized(items))
        elif format_style == "compact":
            lines.extend(self._format_compact(items))
        else:
            lines.extend(self._format_standard(items))
        
        # ISO section
        if iso_items:
            lines.append("")
            lines.append(D2JSP_BB_CODE['line'][0])
            lines.append("")
            iso_list = self._format_iso_section(iso_items)
            lines.extend(iso_list)
        
        # Footer
        lines.append("")
        lines.append(D2JSP_BB_CODE['line'][0])
        lines.append("")
        lines.append("PM me in-game or on d2jsp for trades.")
        lines.append("FG offers welcome, item trades considered.")
        
        return "\n".join(lines)
    
    def _format_standard(self, items: list[TradeItem]) -> list[str]:
        """Standard format with one item per line."""
        lines = []
        
        # Sort by price descending
        sorted_items = sorted(items, key=lambda x: x.price_fg or 0, reverse=True)
        
        for item in sorted_items:
            icon = self._get_icon(item.category)
            price_str = self._format_price(item)
            
            line = f"{icon} {item.name}"
            if item.premium_info:
                line += f" ({item.premium_info})"
            line += f" - {price_str}"
            if item.notes:
                line += f" [{item.notes}]"
            if item.quantity > 1:
                line = f"[x{item.quantity}] {line}"
            
            lines.append(line)
        
        return lines
    
    def _format_categorized(self, items: list[TradeItem]) -> list[str]:
        """Format items grouped by category."""
        lines = []
        
        # Group by category
        categories: dict[str, list[TradeItem]] = {}
        for item in items:
            cat = item.category or "other"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        # Category display order
        cat_order = ["rune", "unique", "set", "runeword", "base", "charm", "jewel", "key", "token", "other"]
        
        for cat in cat_order:
            if cat not in categories:
                continue
            
            cat_items = sorted(categories[cat], key=lambda x: x.price_fg or 0, reverse=True)
            icon = CATEGORY_ICONS.get(cat, CATEGORY_ICONS["default"])
            
            # Category header
            cat_title = cat.upper()
            if self.use_bb_code:
                lines.append(f"{D2JSP_BB_CODE['bold'][0]}{icon} {cat_title}{D2JSP_BB_CODE['bold'][1]}")
            else:
                lines.append(f"--- {icon} {cat_title} ---")
            
            for item in cat_items:
                price_str = self._format_price(item)
                line = f"  • {item.name}"
                if item.premium_info:
                    line += f" ({item.premium_info})"
                line += f" - {price_str}"
                if item.quantity > 1:
                    line = f"  • [x{item.quantity}] {item.name} - {price_str}"
                lines.append(line)
            
            lines.append("")
        
        return lines
    
    def _format_compact(self, items: list[TradeItem]) -> list[str]:
        """Compact format - multiple items per line."""
        lines = []
        
        # Sort by category, then price
        sorted_items = sorted(items, key=lambda x: (x.category or "zzz", -(x.price_fg or 0)))
        
        current_line = ""
        for item in sorted_items:
            icon = self._get_icon(item.category)
            price_str = self._format_price(item, compact=True)
            item_str = f"{icon}{item.name} {price_str}"
            
            if len(current_line) + len(item_str) > 80 and current_line:
                lines.append(current_line.strip())
                current_line = item_str
            else:
                if current_line:
                    current_line += f" | {item_str}"
                else:
                    current_line = item_str
        
        if current_line:
            lines.append(current_line.strip())
        
        return lines
    
    def _format_iso_section(self, items: list[TradeItem]) -> list[str]:
        """Format ISO items section."""
        lines = []
        
        if self.use_bb_code:
            lines.append(f"{D2JSP_BB_CODE['bold'][0]}{D2JSP_BB_CODE['color_blue'][0]}[ISO] Items I'm Looking For:{D2JSP_BB_CODE['color_blue'][1]}{D2JSP_BB_CODE['bold'][1]}")
        else:
            lines.append("--- [ISO] Items I'm Looking For ---")
        
        for item in items:
            icon = self._get_icon(item.category)
            budget = ""
            if item.price_fg:
                budget = f" (budget: {item.price_fg:.0f} fg)"
            elif item.price_range:
                budget = f" (budget: {item.price_range[0]:.0f}-{item.price_range[1]:.0f} fg)"
            
            line = f"{icon} {item.name}{budget}"
            if item.notes:
                line += f" - {item.notes}"
            lines.append(line)
        
        return lines
    
    def _format_price(self, item: TradeItem, compact: bool = False) -> str:
        """Format price string for display."""
        if item.price_fg is not None:
            if compact:
                return f"{item.price_fg:.0f}fg"
            return f"{item.price_fg:.0f} fg"
        elif item.price_range:
            return f"{item.price_range[0]:.0f}-{item.price_range[1]:.0f} fg"
        return "offer"
    
    def _get_icon(self, category: str) -> str:
        """Get category icon."""
        if not self.use_icons:
            return "•"
        return CATEGORY_ICONS.get(category, CATEGORY_ICONS["default"])


# ---------------------------------------------------------------------------
# ISO List Parser
# ---------------------------------------------------------------------------

class ISOListParser:
    """Parse d2jsp ISO posts into structured data."""
    
    # Common patterns for item names and prices
    ITEM_PATTERNS = [
        # Rune patterns
        r"(?i)\b(jah|ber|sur|lo|ohm|vex|cham|zod|gul|ist|mal|um|pul|lem)\b",
        # Runeword patterns  
        r"(?i)\b(enigma|infinity|cta|call to arms|grief|insight|spirit|fortitude|hots?|heart of the oak|hoto)\b",
        # Unique patterns
        r"(?i)\b(shako|arach|arachnid|soj|stone of jordan|bk|bul-kathos|griffon|death's fathom|anni|torch)\b",
        # Base patterns
        r"(?i)\b(monarch|archon|phase blade|berserker axe|cryptic axe|gt|giant thresher)\b",
        # Charm patterns
        r"(?i)\b(skille?r|gc|sc|small charm|grand charm|3/20/20|20/5)\b",
        # Jewel patterns
        r"(?i)\b(40/15|15/15|jewel|ias jewel)\b",
    ]
    
    PRICE_PATTERNS = [
        r"(\d+(?:\.\d+)?)\s*fg",
        r"(\d+)-(?:\d+)\s*fg",
        r"budget[:\s]+(\d+)",
        r"paying[:\s]+(\d+)",
    ]
    
    def parse_iso_text(self, text: str) -> ISOList:
        """Parse a d2jsp ISO post into structured ISOList."""
        items: list[TradeItem] = []
        
        lines = text.split("\n")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip headers/labels
            if any(skip in line.lower() for skip in ["[iso]", "looking for", "want to buy", "wtb"]):
                continue
            
            # Try to extract item name and price
            item = self._parse_line(line)
            if item:
                items.append(item)
        
        return ISOList(items=items)
    
    def _parse_line(self, line: str) -> TradeItem | None:
        """Parse a single line into a TradeItem."""
        
        # Extract price first
        price: float | None = None
        price_range: tuple[float, float] | None = None
        
        for pattern in self.PRICE_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                if "-" in line:
                    # Range
                    nums = re.findall(r"\d+", line)
                    if len(nums) >= 2:
                        price_range = (float(nums[0]), float(nums[1]))
                else:
                    price = float(match.group(1))
                break
        
        # Extract item name
        item_name = ""
        category = "other"
        
        for pattern in self.ITEM_PATTERNS:
            match = re.search(pattern, line)
            if match:
                item_name = match.group(1).title()
                category = self._detect_category(item_name)
                break
        
        if not item_name:
            return None
        
        return TradeItem(
            name=item_name,
            price_fg=price,
            price_range=price_range,
            is_ft=False,
            category=category,
            notes=line,
        )
    
    def _detect_category(self, name: str) -> str:
        """Detect item category from name."""
        name_lower = name.lower()
        
        if name_lower in ["jah", "ber", "sur", "lo", "ohm", "vex", "cham", "zod", "gul", "ist", "mal", "um", "pul", "lem"]:
            return "rune"
        if any(rw in name_lower for rw in ["enigma", "infinity", "cta", "grief", "insight", "spirit", "fortitude", "hoto"]):
            return "runeword"
        if name_lower in ["shako", "arach", "soj", "bk", "griffon", "fathom"]:
            return "unique"
        if any(base in name_lower for base in ["monarch", "archon", "phase", "berserker", "cryptic"]):
            return "base"
        if any(ch in name_lower for ch in ["skiller", "gc", "sc", "charm"]):
            return "charm"
        if "jewel" in name_lower or "/" in name_lower:
            return "jewel"
        if name_lower in ["anni", "torch"]:
            return name_lower
        
        return "other"


# ---------------------------------------------------------------------------
# Trade Matcher
# ---------------------------------------------------------------------------

class TradeMatcher:
    """Match FT items against ISO items for potential trades."""
    
    def find_matches(
        self,
        ft_items: list[TradeItem],
        iso_items: list[TradeItem],
        price_tolerance: float = 0.2,  # 20% tolerance
    ) -> list[TradeMatch]:
        """Find potential trade matches between FT and ISO lists."""
        matches: list[TradeMatch] = []
        
        for ft in ft_items:
            for iso in iso_items:
                match = self._check_match(ft, iso, price_tolerance)
                if match:
                    matches.append(match)
        
        # Sort by match score descending
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return matches
    
    def _check_match(
        self,
        ft: TradeItem,
        iso: TradeItem,
        tolerance: float,
    ) -> TradeMatch | None:
        """Check if two items match."""
        
        # Name similarity
        name_score = self._name_similarity(ft.name, iso.name)
        if name_score < 0.5:
            return None
        
        # Price check
        price_match = True
        if ft.price_fg and iso.price_fg:
            # ISO budget should cover FT price
            price_match = iso.price_fg >= ft.price_fg * (1 - tolerance)
        elif ft.price_fg and iso.price_range:
            price_match = iso.price_range[1] >= ft.price_fg * (1 - tolerance)
        
        # Category match bonus
        cat_bonus = 0.1 if ft.category == iso.category else 0
        
        match_score = min(1.0, name_score + cat_bonus)
        
        return TradeMatch(
            ft_item=ft,
            iso_item=iso,
            price_match=price_match,
            match_score=match_score,
        )
    
    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate name similarity score."""
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        
        # Exact match
        if n1 == n2:
            return 1.0
        
        # One contains the other
        if n1 in n2 or n2 in n1:
            return 0.8
        
        # Word overlap
        words1 = set(n1.split())
        words2 = set(n2.split())
        overlap = len(words1 & words2)
        max_words = max(len(words1), len(words2))
        
        if max_words == 0:
            return 0.0
        
        return overlap / max_words


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def export_ft_list(items: list[dict], format_style: str = "standard") -> str:
    """Convenience function to export items to FT list format.
    
    Args:
        items: List of item dicts with keys: name, price_fg, category, etc.
        format_style: "standard", "compact", or "categorized"
    
    Returns:
        Formatted FT post string ready for d2jsp
    """
    trade_items = []
    for d in items:
        trade_items.append(TradeItem(
            name=d.get("name", "Unknown"),
            canonical_id=d.get("canonical_id"),
            price_fg=d.get("price_fg"),
            price_range=d.get("price_range"),
            quantity=d.get("quantity", 1),
            notes=d.get("notes", ""),
            premium_info=d.get("premium_info", ""),
            category=d.get("category", ""),
        ))
    
    generator = FTListGenerator()
    return generator.generate_ft_post(trade_items, format_style=format_style)


def parse_iso_list(text: str) -> ISOList:
    """Convenience function to parse ISO text."""
    parser = ISOListParser()
    return parser.parse_iso_text(text)


def find_trade_matches(ft_items: list[dict], iso_items: list[dict]) -> list[dict]:
    """Convenience function to find trade matches.
    
    Returns list of dicts with match info.
    """
    ft = [TradeItem(**d) for d in ft_items]
    iso = [TradeItem(**d) for d in iso_items]
    
    matcher = TradeMatcher()
    matches = matcher.find_matches(ft, iso)
    
    return [
        {
            "ft_name": m.ft_item.name,
            "ft_price": m.ft_item.price_fg,
            "iso_name": m.iso_item.name,
            "iso_budget": m.iso_item.price_fg,
            "price_match": m.price_match,
            "match_score": m.match_score,
        }
        for m in matches
    ]
