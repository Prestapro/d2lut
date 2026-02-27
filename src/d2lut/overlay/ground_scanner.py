"""Ground item scanner and detector for D2R.

This module provides functionality to detect and price items
dropped on the ground in Diablo 2 Resurrected.
"""

from __future__ import annotations

import logging
import time
import hashlib
from dataclasses import dataclass
from typing import Any

from d2lut.overlay.websocket_server import DroppedItem, GroundScanResult
from d2lut.exporters.magic_item_pricer import MagicItemPricer, AffixPriceResult

logger = logging.getLogger(__name__)


@dataclass
class DetectedAffix:
    """A detected affix from OCR."""
    name: str
    is_prefix: bool
    property_text: str
    confidence: float = 1.0


class GroundItemScanner:
    """Scanner for detecting and pricing dropped items on ground."""
    
    # Tier colors matching the web UI
    TIER_COLORS = {
        "gg": "#ff4444",
        "high": "#aa66ff",
        "medium": "#ff8844",
        "low": "#4488ff",
        "trash": "#888888",
    }
    
    # Quality color mapping (D2R colors)
    QUALITY_COLORS = {
        "magic": "#6888ff",     # Blue
        "rare": "#ffdd66",      # Yellow
        "unique": "#c7b377",    # Gold/Dark Yellow
        "set": "#00ff00",       # Green
        "craft": "#ff8800",     # Orange
        "white": "#c0c0c0",     # Gray
        "gray": "#808080",      # Low Gray
    }
    
    # Item base type patterns (from OCR)
    BASE_TYPE_PATTERNS = {
        # Circlets
        "circlet": ["circlet", "coronet", "tiara", "diadem"],
        # Amulets & Rings
        "amulet": ["amulet", "ammy"],
        "ring": ["ring"],
        # Charms
        "grand charm": ["grand charm", "gc", "gcharms"],
        "large charm": ["large charm", "lc"],
        "small charm": ["small charm", "sc", "scharms"],
        # Jewels
        "jewel": ["jewel"],
        # Weapons
        "wand": ["wand"],
        "staff": ["staff"],
        "orb": ["orb"],
        "sword": ["sword"],
        "dagger": ["dagger", "knife"],
        "axe": ["axe"],
        "mace": ["mace"],
        "scepter": ["scepter"],
        "bow": ["bow"],
        "crossbow": ["crossbow"],
        # Armor
        "shield": ["shield", "monarch", "tower", "round"],
        "armor": ["armor", "plate", "mail", "leather"],
        "helm": ["helm", "helmet", "circlet", "mask"],
        "boots": ["boots", "greaves"],
        "gloves": ["gloves", "gauntlets"],
        "belt": ["belt"],
    }
    
    # GG Prefix patterns to detect
    GG_PREFIX_PATTERNS = {
        "Arch-Angel's": ["arch-angel", "arch angel", "archangel"],
        "Necromancer's": ["necromancer", "necro"],
        "Sorceress's": ["sorceress", "sorc"],
        "Paladin's": ["paladin", "pally"],
        "Druid's": ["druid"],
        "Assassin's": ["assassin", "assa", "sin"],
        "Barbarian's": ["barbarian", "barb"],
        "Amazon's": ["amazon", "zon"],
        "Venomous": ["venomous", "venom"],
        "Echoing": ["echoing", "echo"],
        "Cunning": ["cunning"],
        "Charged": ["charged"],
        "Blazing": ["blazing", "blaze"],
        "Jeweler's": ["jeweler", "jewelers"],
        "Artificer's": ["artificer", "artificers"],
        "Cruel": ["cruel"],
        "Chromatic": ["chromatic"],
        "Prismatic": ["prismatic"],
        "Apprentice's": ["apprentice", "apprentices"],
    }
    
    # GG Suffix patterns to detect
    GG_SUFFIX_PATTERNS = {
        "of the Magus": ["magus", "20 fcr", "20% fcr"],
        "of Deflecting": ["deflecting", "20 block", "20% block", "fbr"],
        "of the Apprentice": ["apprentice", "10 fcr", "10% fcr"],
        "of the Whale": ["whale", "100 life", "81-100 life"],
        "of Vita": ["vita", "vita"],
        "of Speed": ["speed", "30 frw", "30% frw"],
        "of Haste": ["haste", "20 frw", "20% frw"],
        "of Fortune": ["fortune", "mf"],
        "of the Vampire": ["vampire", "mana leech", "ml"],
        "of the Locust": ["locust", "life leech", "ll"],
        "of Atlas": ["atlas", "str"],
        "of Teleportation": ["teleportation", "teleport", "tele"],
    }
    
    def __init__(self, pricer: MagicItemPricer | None = None):
        """Initialize the ground item scanner.
        
        Args:
            pricer: MagicItemPricer instance (creates new if None)
        """
        self.pricer = pricer or MagicItemPricer()
        self._item_counter = 0
    
    def _generate_item_id(self) -> str:
        """Generate unique item ID."""
        self._item_counter += 1
        timestamp = int(time.time() * 1000)
        return f"item_{timestamp}_{self._item_counter}"
    
    def _detect_base_type(self, text: str) -> str:
        """Detect item base type from OCR text."""
        text_lower = text.lower()
        
        for base_type, patterns in self.BASE_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    return base_type
        
        return "unknown"
    
    def _detect_quality(self, text: str) -> str:
        """Detect item quality from OCR text."""
        text_lower = text.lower()
        
        # Check for explicit quality indicators
        if "unique" in text_lower:
            return "unique"
        if "set item" in text_lower or any(word in text_lower for word in ["angelic", "arctic", "beserker", "cathan", "civerb", "cleglaw", "death", "disciple", "griswold", "hadriel", "heaven's", "hsaru", "infernal", "iratha", "isenhart", "milabrega", "naj", "orphan", "sazabi", "tancred", "vidala"]):
            return "set"
        if "rare" in text_lower:
            return "rare"
        if "magic" in text_lower:
            return "magic"
        if "crafted" in text_lower or "craft" in text_lower:
            return "craft"
        
        # Default to magic if has affix-like structure
        if any(prefix.lower() in text_lower for prefix in self.GG_PREFIX_PATTERNS.keys()):
            return "magic"
        if any(suffix.lower() in text_lower for suffix in ["of the", "of"]):
            return "magic"
        
        return "white"
    
    def _detect_ilvl(self, text: str) -> int:
        """Detect item level from OCR text."""
        import re
        
        # Look for "ilvl XX" pattern
        ilvl_match = re.search(r'ilvl\s*(\d+)', text.lower())
        if ilvl_match:
            return int(ilvl_match.group(1))
        
        # Look for "Item Level: XX" pattern
        ilvl_match2 = re.search(r'item\s*level[:\s]*(\d+)', text.lower())
        if ilvl_match2:
            return int(ilvl_match2.group(1))
        
        # Look for "Level: XX" pattern
        level_match = re.search(r'level[:\s]*(\d+)', text.lower())
        if level_match:
            return int(level_match.group(1))
        
        # Default for GG items (high ilvl assumed)
        return 90
    
    def _detect_prefix(self, text: str) -> str | None:
        """Detect prefix from OCR text."""
        text_lower = text.lower()
        
        for prefix_name, patterns in self.GG_PREFIX_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    return prefix_name
        
        return None
    
    def _detect_suffix(self, text: str) -> str | None:
        """Detect suffix from OCR text."""
        text_lower = text.lower()
        
        for suffix_name, patterns in self.GG_SUFFIX_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    return suffix_name
        
        return None
    
    def _extract_affixes(self, text: str) -> list[str]:
        """Extract all affixes from OCR text."""
        affixes = []
        
        # Check prefixes
        for prefix_name, patterns in self.GG_PREFIX_PATTERNS.items():
            for pattern in patterns:
                if pattern in text.lower():
                    if prefix_name not in affixes:
                        affixes.append(prefix_name)
                    break
        
        # Check suffixes
        for suffix_name, patterns in self.GG_SUFFIX_PATTERNS.items():
            for pattern in patterns:
                if pattern in text.lower():
                    if suffix_name not in affixes:
                        affixes.append(suffix_name)
                    break
        
        return affixes
    
    def scan_text(self, tooltip_text: str, screen_x: int = 0, screen_y: int = 0) -> DroppedItem | None:
        """Scan tooltip text and create a priced item.
        
        Args:
            tooltip_text: OCR text from tooltip
            screen_x: X coordinate on screen
            screen_y: Y coordinate on screen
            
        Returns:
            DroppedItem with pricing, or None if not parseable
        """
        if not tooltip_text or len(tooltip_text.strip()) < 5:
            return None
        
        # Detect item properties
        name = self._extract_item_name(tooltip_text)
        base_type = self._detect_base_type(tooltip_text)
        quality = self._detect_quality(tooltip_text)
        ilvl = self._detect_ilvl(tooltip_text)
        prefix = self._detect_prefix(tooltip_text)
        suffix = self._detect_suffix(tooltip_text)
        affixes = self._extract_affixes(tooltip_text)
        
        # Get price from pricer
        price_result = self.pricer.price_item(
            prefix=prefix or "",
            suffix=suffix or "",
            item_type=base_type,
            ilvl=ilvl,
            roll_percent=75.0,  # Assume good roll
        )
        
        # Create DroppedItem
        item = DroppedItem(
            id=self._generate_item_id(),
            name=name,
            base_type=base_type,
            quality=quality,
            ilvl=ilvl,
            prefix=prefix,
            suffix=suffix,
            affixes=affixes,
            estimated_fg=price_result.estimated_fg,
            tier=price_result.tier,
            color=price_result.color,
            tag=price_result.tag,
            prefix_price=price_result.estimated_fg * 0.5 if prefix else 0,  # Approximate
            suffix_price=price_result.estimated_fg * 0.5 if suffix else 0,
            ilvl_multiplier=price_result.ilvl_display,
            is_lld=price_result.is_lld,
            notes=price_result.notes,
            detected_at=time.time(),
            screen_x=screen_x,
            screen_y=screen_y,
            tooltip_text=tooltip_text[:500],  # Truncate for storage
            confidence=0.8,  # Default confidence
        )
        
        return item
    
    def _extract_item_name(self, text: str) -> str:
        """Extract item name from tooltip text."""
        lines = text.strip().split('\n')
        
        if lines:
            # First non-empty line is usually the name
            for line in lines:
                line = line.strip()
                if line and len(line) > 2:
                    # Remove quality prefix if present
                    for quality in ["Magic ", "Rare ", "Unique ", "Set ", "Crafted "]:
                        if line.startswith(quality):
                            line = line[len(quality):]
                    return line[:50]  # Truncate long names
        
        return "Unknown Item"
    
    def scan_multiple(self, tooltip_texts: list[str]) -> GroundScanResult:
        """Scan multiple tooltips from ground scan.
        
        Args:
            tooltip_texts: List of OCR tooltip texts
            
        Returns:
            GroundScanResult with all items and summary
        """
        items = []
        total_value = 0.0
        gg_count = 0
        high_count = 0
        start_time = time.time()
        
        for i, text in enumerate(tooltip_texts):
            # Estimate screen position based on index
            x = (i % 10) * 80 + 100
            y = (i // 10) * 80 + 100
            
            item = self.scan_text(text, x, y)
            if item:
                items.append(item)
                total_value += item.estimated_fg
                
                if item.tier == "gg":
                    gg_count += 1
                elif item.tier == "high":
                    high_count += 1
        
        return GroundScanResult(
            items=items,
            total_value_fg=total_value,
            gg_items_count=gg_count,
            high_items_count=high_count,
            scan_time=time.time() - start_time,
        )
    
    def create_mock_items(self, count: int = 5) -> list[DroppedItem]:
        """Create mock items for testing/demo.
        
        Args:
            count: Number of mock items to create
            
        Returns:
            List of mock DroppedItems
        """
        mock_configs = [
            {
                "name": "Necromancer's Amulet of the Magus",
                "base_type": "amulet",
                "quality": "magic",
                "ilvl": 92,
                "prefix": "Necromancer's",
                "suffix": "of the Magus",
                "estimated_fg": 6500.0,
                "tier": "gg",
            },
            {
                "name": "Jeweler's Monarch of Deflecting",
                "base_type": "shield",
                "quality": "magic",
                "ilvl": 50,
                "prefix": "Jeweler's",
                "suffix": "of Deflecting",
                "estimated_fg": 4500.0,
                "tier": "gg",
            },
            {
                "name": "Venomous Diadem of the Magus",
                "base_type": "circlet",
                "quality": "magic",
                "ilvl": 95,
                "prefix": "Venomous",
                "suffix": "of the Magus",
                "estimated_fg": 15000.0,
                "tier": "gg",
            },
            {
                "name": "Echoing Amulet of the Magus",
                "base_type": "amulet",
                "quality": "magic",
                "ilvl": 90,
                "prefix": "Echoing",
                "suffix": "of the Magus",
                "estimated_fg": 3500.0,
                "tier": "gg",
            },
            {
                "name": "Chromatic Amulet",
                "base_type": "amulet",
                "quality": "magic",
                "ilvl": 85,
                "prefix": "Chromatic",
                "suffix": None,
                "estimated_fg": 150.0,
                "tier": "medium",
            },
            {
                "name": "Grand Charm of Vita",
                "base_type": "grand charm",
                "quality": "magic",
                "ilvl": 91,
                "prefix": None,
                "suffix": "of Vita",
                "estimated_fg": 800.0,
                "tier": "high",
            },
            {
                "name": "Cruel Colossus Blade",
                "base_type": "sword",
                "quality": "magic",
                "ilvl": 75,
                "prefix": "Cruel",
                "suffix": None,
                "estimated_fg": 200.0,
                "tier": "medium",
            },
            {
                "name": "Small Charm of Life",
                "base_type": "small charm",
                "quality": "magic",
                "ilvl": 50,
                "prefix": None,
                "suffix": "of Life",
                "estimated_fg": 5.0,
                "tier": "low",
            },
        ]
        
        items = []
        for i in range(min(count, len(mock_configs))):
            config = mock_configs[i]
            
            item = DroppedItem(
                id=self._generate_item_id(),
                name=config["name"],
                base_type=config["base_type"],
                quality=config["quality"],
                ilvl=config["ilvl"],
                prefix=config["prefix"],
                suffix=config["suffix"],
                affixes=[config["prefix"], config["suffix"]] if config["prefix"] else [],
                estimated_fg=config["estimated_fg"],
                tier=config["tier"],
                color=self.TIER_COLORS[config["tier"]],
                tag="[GG]" if config["tier"] == "gg" else "",
                prefix_price=config["estimated_fg"] * 0.5 if config["prefix"] else 0,
                suffix_price=config["estimated_fg"] * 0.5 if config["suffix"] else 0,
                ilvl_multiplier=1.3 if config["ilvl"] >= 90 else 1.0,
                is_lld=config["ilvl"] <= 30,
                notes="",
                detected_at=time.time() - (count - i) * 10,  # Stagger times
                screen_x=100 + i * 100,
                screen_y=200,
                tooltip_text="",
                confidence=1.0,
            )
            items.append(item)
        
        return items
