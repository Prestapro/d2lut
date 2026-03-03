#!/usr/bin/env python3
"""D2R Loot Filter Builder.

Builds item filter files for Diablo 2 Resurrected based on FG prices.

Usage:
    python build_d2r_filter.py --preset roguecore --db d2lut.db
    python build_d2r_filter.py --help

D2R Filter Syntax:
    ItemDisplay[CODE]: DisplayText
    
    Where CODE can be:
    - Item type code (e.g., "cap", "uui" for unique helm)
    - Rune code (r01-r33)
    - Custom code for runewords/sets
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# D2R Filter color codes
COLORS = {
    "WHITE": "ÿc0",
    "RED": "ÿc1",
    "GREEN": "ÿc2",
    "BLUE": "ÿc3",
    "GOLD": "ÿc4",
    "GRAY": "ÿc5",
    "BLACK": "ÿc6",
    "ORANGE": "ÿc7",
    "YELLOW": "ÿc8",
    "PURPLE": "ÿc9",
    "CYAN": "ÿc;",
}

# Price tiers (FG) - use 999_999 instead of float("inf") for JSON serialization
PRICE_TIERS = {
    "GG": (500, 999_999),         # 500+ FG
    "HIGH": (100, 500),           # 100-500 FG
    "MID": (20, 100),             # 20-100 FG
    "LOW": (5, 20),               # 5-20 FG
    "TRASH": (0, 5),              # <5 FG
}

TIER_COLORS = {
    "GG": COLORS["PURPLE"],
    "HIGH": COLORS["ORANGE"],
    "MID": COLORS["YELLOW"],
    "LOW": COLORS["WHITE"],
    "TRASH": COLORS["GRAY"],
}


@dataclass
class PricedItem:
    """Item with FG price and D2R codes."""
    name: str  # Short name (e.g., "shako")
    variant_key: str  # Full key (e.g., "unique:shako")
    d2r_code: str  # D2R item code for filter (e.g., "uui")
    display_name: str  # Full display name (e.g., "Harlequin Crest")
    price_fg: float
    tier: str
    category: str = "misc"


@dataclass
class PresetConfig:
    """Configuration for a filter preset."""
    name: str
    description: str = ""
    show_trash: bool = False
    show_prices: bool = True
    show_tier_colors: bool = True
    show_bases: bool = True
    hide_low_value: bool = False
    price_threshold: float = 0
    tier_visibility: dict = field(default_factory=dict)
    display_format: str = "{color}{name} {price_color}[{price} FG]"
    price_format: str = "int"  # int, float, or none


def load_item_codes() -> dict[str, str]:
    """Load D2R item code mapping from JSON file.

    Returns:
        Dict mapping variant_key to D2R item code
    """
    script_dir = Path(__file__).parent
    codes_path = script_dir.parent / "data" / "item_codes.json"
    
    if not codes_path.exists():
        logger.warning(f"Item codes file not found: {codes_path}")
        return {}
    
    try:
        with open(codes_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Flatten all categories into single dict
        codes = {}
        for category_items in data.values():
            if isinstance(category_items, dict):
                codes.update(category_items)
        
        logger.info(f"Loaded {len(codes)} D2R item codes")
        return codes
        
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading item codes: {e}")
        return {}


def load_display_names() -> dict[str, str]:
    """Load display names from item-names-full.json.

    Returns:
        Dict mapping variant_key to display name
    """
    script_dir = Path(__file__).parent
    names_path = script_dir.parent / "data" / "templates" / "item-names-full.json"
    
    if not names_path.exists():
        logger.warning(f"Display names file not found: {names_path}")
        return {}
    
    try:
        with open(names_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Flatten nested structure and add prefixes
        names = {}
        item_names = data.get("item_names", {})
        
        # Map category to prefix
        category_prefix = {
            "uniques": "unique",
            "runes": "rune",
            "runewords": "runeword",
            "set_items": "set",
        }
        
        for category, items in item_names.items():
            prefix = category_prefix.get(category, "")
            for key, display_name in items.items():
                # Store both with and without prefix
                names[key] = display_name
                if prefix:
                    names[f"{prefix}:{key}"] = display_name
        
        logger.info(f"Loaded {len(names)} display names")
        return names
        
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading display names: {e}")
        return {}


def load_preset_config(preset_name: str) -> PresetConfig:
    """Load preset configuration from presets.yml.

    Args:
        preset_name: Name of the preset to load

    Returns:
        PresetConfig with loaded settings or default if not found
    """
    # Find presets.yml
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / "config" / "presets.yml"

    if not config_path.exists():
        logger.warning(f"Presets file not found: {config_path}, using defaults")
        return PresetConfig(name=preset_name)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        presets = config.get("presets", {})
        tier_visibility = config.get("tier_visibility", {})
        display_formats = config.get("display_formats", {})

        if preset_name not in presets:
            logger.warning(f"Preset '{preset_name}' not found, using defaults")
            return PresetConfig(name=preset_name)

        preset_data = presets[preset_name]
        tier_vis = tier_visibility.get(preset_name, {})
        format_data = display_formats.get(preset_name, {})
        display_format = format_data.get("format", "{color}{name} {price_color}[{price} FG]")
        price_format = format_data.get("price_format", "int")

        return PresetConfig(
            name=preset_data.get("name", preset_name),
            description=preset_data.get("description", ""),
            show_trash=preset_data.get("show_trash", False),
            show_prices=preset_data.get("show_prices", True),
            show_tier_colors=preset_data.get("show_tier_colors", True),
            show_bases=preset_data.get("show_bases", True),
            hide_low_value=preset_data.get("hide_low_value", False),
            price_threshold=preset_data.get("price_threshold", 0),
            tier_visibility=tier_vis,
            display_format=display_format,
            price_format=price_format,
        )

    except yaml.YAMLError as e:
        logger.error(f"Error parsing presets.yml: {e}")
        return PresetConfig(name=preset_name)


class FilterBuilder:
    """Builds D2R item filter files."""

    def __init__(self, db_path: Optional[Path] = None, preset: str = "default"):
        self.db_path = db_path
        self.preset = preset
        self.preset_config = load_preset_config(preset)
        self.items: list[PricedItem] = []
        self.filtered_count: int = 0  # Track items after threshold filtering
        self._missing_codes: set[str] = set()  # Track items without valid D2R codes
        
        # Load item codes and display names
        self.item_codes = load_item_codes()
        self.display_names = load_display_names()

    def _get_valid_d2r_code(self, variant_key: str) -> Optional[str]:
        """Get valid D2R item code for a variant.
        
        Args:
            variant_key: Item variant key (e.g., "rune:jah")
            
        Returns:
            Valid D2R code (e.g., "r31") or None if not found
            
        Note:
            Logs a warning if no valid code is found. D2R filter lines
            with invalid codes will be silently ignored by the game.
        """
        code = self.item_codes.get(variant_key)
        if code:
            return code
            
        # Track missing codes for summary warning
        if variant_key not in self._missing_codes:
            self._missing_codes.add(variant_key)
            logger.warning(
                f"No D2R code found for '{variant_key}'. "
                f"Filter line will use variant name but may not work in-game. "
                f"Add code to data/item_codes.json for proper support."
            )
        return None

    def load_prices(self) -> None:
        """Load item prices from database."""
        if not self.db_path or not self.db_path.exists():
            logger.warning(f"Database not found: {self.db_path}, using defaults")
            self._load_default_prices()
            return

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Try to detect schema and use appropriate query
            items = self._try_load_from_schema(cursor, conn)

            if not items:
                logger.warning("No items loaded from database, using defaults")
                self._load_default_prices()
            else:
                self.items = items
                logger.info(f"Loaded {len(self.items)} priced items from database")

            conn.close()

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            self._load_default_prices()

    def _try_load_from_schema(
        self, cursor: sqlite3.Cursor, conn: sqlite3.Connection
    ) -> list[PricedItem]:
        """Try different SQL queries based on database schema.

        Supports multiple schema versions for backwards compatibility.
        """
        items: list[PricedItem] = []

        # Check available tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}

        # Schema 1: price_estimates with variant_key, price_fg
        if "price_estimates" in tables:
            try:
                cursor.execute("""
                    SELECT variant_key, price_fg
                    FROM price_estimates
                    WHERE price_fg > 0
                    ORDER BY price_fg DESC
                """)
                for row in cursor.fetchall():
                    item = self._row_to_item_simple(row)
                    if item:
                        items.append(item)
                if items:
                    return items
            except sqlite3.OperationalError:
                pass

        # Schema 2: price_estimates with estimate_fg + catalog_items join
        if "price_estimates" in tables and "catalog_items" in tables:
            try:
                cursor.execute("""
                    SELECT
                        ci.variant_key,
                        pe.estimate_fg as price_fg,
                        ci.category
                    FROM price_estimates pe
                    JOIN catalog_items ci ON pe.item_id = ci.id
                    WHERE pe.estimate_fg > 0
                    ORDER BY pe.estimate_fg DESC
                """)
                for row in cursor.fetchall():
                    item = self._row_to_item(row)
                    if item:
                        items.append(item)
                if items:
                    return items
            except sqlite3.OperationalError:
                pass

        # Schema 3: items table with price column
        if "items" in tables:
            try:
                cursor.execute("""
                    SELECT variant_key, price as price_fg, category
                    FROM items
                    WHERE price > 0
                    ORDER BY price DESC
                """)
                for row in cursor.fetchall():
                    item = self._row_to_item(row)
                    if item:
                        items.append(item)
                if items:
                    return items
            except sqlite3.OperationalError:
                pass

        # Schema 4: observed_prices aggregation
        if "observed_prices" in tables:
            try:
                cursor.execute("""
                    SELECT
                        variant_key,
                        AVG(price_fg) as price_fg
                    FROM observed_prices
                    WHERE price_fg > 0
                    GROUP BY variant_key
                    HAVING COUNT(*) >= 1
                    ORDER BY price_fg DESC
                """)
                for row in cursor.fetchall():
                    item = self._row_to_item_simple(row)
                    if item:
                        items.append(item)
                if items:
                    return items
            except sqlite3.OperationalError:
                pass

        return items

    def _row_to_item_simple(self, row: sqlite3.Row) -> Optional[PricedItem]:
        """Convert database row to PricedItem (simple schema)."""
        try:
            variant_key = row["variant_key"]
            price_fg = row["price_fg"]

            # Extract name from variant_key
            parts = variant_key.split(":")
            name = parts[-1] if parts else variant_key

            # Determine tier
            tier = self._get_tier(price_fg)
            
            # Get D2R code (with validation) and display name
            d2r_code = self._get_valid_d2r_code(variant_key) or name
            display_name = self.display_names.get(variant_key, name.title())

            return PricedItem(
                name=name,
                variant_key=variant_key,
                d2r_code=d2r_code,
                display_name=display_name,
                price_fg=price_fg,
                tier=tier,
                category=parts[0] if len(parts) > 1 else "misc",
            )
        except (KeyError, TypeError):
            return None

    def _row_to_item(self, row: sqlite3.Row) -> Optional[PricedItem]:
        """Convert database row to PricedItem."""
        try:
            variant_key = row["variant_key"]
            price_fg = row["price_fg"]

            # Get category safely
            row_keys = row.keys()
            category = row["category"] if "category" in row_keys else "misc"

            # Extract name from variant_key
            parts = variant_key.split(":")
            name = parts[-1] if parts else variant_key

            # Determine tier
            tier = self._get_tier(price_fg)
            
            # Get D2R code (with validation) and display name
            d2r_code = self._get_valid_d2r_code(variant_key) or name
            display_name = self.display_names.get(variant_key, name.title())

            return PricedItem(
                name=name,
                variant_key=variant_key,
                d2r_code=d2r_code,
                display_name=display_name,
                price_fg=price_fg,
                tier=tier,
                category=category,
            )
        except (KeyError, TypeError):
            return None

    def _get_tier(self, price: float) -> str:
        """Determine price tier."""
        for tier, (low, high) in PRICE_TIERS.items():
            if low <= price < high:
                return tier
        return "TRASH"

    def _load_default_prices(self) -> None:
        """Load default hardcoded prices."""
        default_prices = [
            # Runes - High value
            ("rune:jah", 150, "rune", "Jah Rune"),
            ("rune:ber", 140, "rune", "Ber Rune"),
            ("rune:sur", 35, "rune", "Sur Rune"),
            ("rune:lo", 30, "rune", "Lo Rune"),
            ("rune:ohm", 28, "rune", "Ohm Rune"),
            ("rune:vex", 22, "rune", "Vex Rune"),
            ("rune:gul", 12, "rune", "Gul Rune"),
            ("rune:ist", 18, "rune", "Ist Rune"),
            ("rune:mal", 8, "rune", "Mal Rune"),
            ("rune:um", 4, "rune", "Um Rune"),

            # Uniques - High value
            ("unique:shako", 15, "unique", "Harlequin Crest"),
            ("unique:arachnid", 45, "unique", "Arachnid Mesh"),
            ("unique:mara", 25, "unique", "Mara's Kaleidoscope"),
            ("unique:tyraels", 200, "unique", "Tyrael's Might"),
            ("unique:torch", 50, "unique", "Hellfire Torch"),
            ("unique:anni", 80, "unique", "Annihilus"),

            # Runewords
            ("runeword:enigma", 160, "runeword", "Enigma"),
            ("runeword:infinity", 180, "runeword", "Infinity"),
            ("runeword:cta", 40, "runeword", "Call to Arms"),
            ("runeword:grief", 35, "runeword", "Grief"),
            ("runeword:fortitude", 45, "runeword", "Fortitude"),
            ("runeword:spirit", 5, "runeword", "Spirit"),
        ]

        for variant_key, price, category, display_name in default_prices:
            tier = self._get_tier(price)
            name = variant_key.split(":")[-1]
            d2r_code = self._get_valid_d2r_code(variant_key) or name
            self.items.append(PricedItem(
                name=name,
                variant_key=variant_key,
                d2r_code=d2r_code,
                display_name=display_name,
                price_fg=price,
                tier=tier,
                category=category,
            ))

        logger.info(f"Loaded {len(self.items)} default prices")

    def build_filter(self, output_path: Path) -> None:
        """Build the filter file using preset configuration."""
        lines = []
        cfg = self.preset_config

        # Filter items by price threshold
        if cfg.hide_low_value and cfg.price_threshold > 0:
            filtered_items = [i for i in self.items if i.price_fg >= cfg.price_threshold]
            logger.info(f"Filtered to {len(filtered_items)} items (threshold: {cfg.price_threshold} FG)")
        else:
            filtered_items = self.items

        # Header
        lines.append(f"# D2R Loot Filter - Built {datetime.now().isoformat()}")
        lines.append(f"# Preset: {cfg.name}")
        lines.append(f"# Description: {cfg.description}")
        lines.append(f"# Items: {len(filtered_items)}")
        lines.append("")

        # Determine tier order based on preset
        tier_order = ["GG", "HIGH", "MID", "LOW", "TRASH"]

        # Add filter rules by tier (respecting tier_visibility)
        for tier in tier_order:
            # Skip TRASH tier unless show_trash is True
            if tier == "TRASH" and not cfg.show_trash:
                continue

            # Check tier visibility
            if cfg.tier_visibility and not cfg.tier_visibility.get(tier, True):
                continue

            tier_items = [i for i in filtered_items if i.tier == tier]
            if tier_items:
                lines.append(f"# === {tier} TIER ({len(tier_items)} items) ===")
                lines.append("")
                for item in tier_items:
                    line = self._build_item_line(item)
                    lines.append(line)
                lines.append("")

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Filter written to: {output_path}")

        # Store filtered count for reporting
        self.filtered_count = len(filtered_items)
        
        # Summary warning for missing D2R codes
        if self._missing_codes:
            logger.warning(
                f"Built filter with {len(self._missing_codes)} items missing D2R codes. "
                f"These items may not display correctly in-game. "
                f"Add codes to data/item_codes.json to fix."
            )

    def _build_item_line(self, item: PricedItem) -> str:
        """Build a single filter line for an item using preset config.

        Uses display_format and price_format from preset configuration.
        Outputs valid D2R filter syntax with D2R item codes.
        
        D2R Filter Format:
            ItemDisplay[CODE]: DisplayText
            
        Where CODE is the D2R item code (e.g., "r32" for Jah, "uui" for Shako)
        """
        cfg = self.preset_config

        # Get color based on tier (or white if show_tier_colors is False)
        if cfg.show_tier_colors:
            color = TIER_COLORS.get(item.tier, COLORS["WHITE"])
        else:
            color = COLORS["WHITE"]

        price_color = COLORS["GOLD"]

        # Format price based on price_format setting
        if cfg.price_format == "none" or not cfg.show_prices:
            price_str = ""
        elif cfg.price_format == "float":
            price_str = f"{item.price_fg:.1f}"
        else:  # "int" or default
            if item.price_fg >= 100:
                price_str = f"{int(item.price_fg)}"
            elif item.price_fg >= 10:
                price_str = f"{item.price_fg:.0f}"
            else:
                price_str = f"{item.price_fg:.1f}"

        # Build display using template from preset
        # Use display_name for the visible text, d2r_code for the filter code
        display_name = item.display_name or item.name.title()
        
        try:
            display = cfg.display_format.format(
                color=color,
                name=display_name,
                price_color=price_color,
                price=price_str,
                tier=item.tier,
            )
        except KeyError:
            # Fallback if template has unknown placeholders
            display = f"{color}{display_name}"
            if cfg.show_prices and price_str:
                display += f" {price_color}[{price_str} FG]"

        # Use D2R item code for the filter key (not the display name)
        return f'ItemDisplay[{item.d2r_code}]: {display}'


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build D2R loot filter with FG prices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --preset roguecore --db d2lut.db
    %(prog)s --output custom_filter.filter
    %(prog)s --list-tiers
        """,
    )

    parser.add_argument(
        "--preset", "-p",
        default="default",
        choices=["default", "roguecore", "minimal", "verbose"],
        help="Filter preset to use (default: default)",
    )
    parser.add_argument(
        "--db", "-d",
        type=Path,
        help="Path to d2lut database file",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("dist/d2r_filter.filter"),
        help="Output filter file path (default: dist/d2r_filter.filter)",
    )
    parser.add_argument(
        "--list-tiers",
        action="store_true",
        help="List price tier thresholds and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_tiers:
        print("\nPrice Tiers (FG):")
        print("-" * 30)
        for tier, (low, high) in PRICE_TIERS.items():
            if high == float("inf"):
                print(f"  {tier}: {low}+ FG")
            else:
                print(f"  {tier}: {low}-{high} FG")
        return 0

    # Build filter
    builder = FilterBuilder(db_path=args.db, preset=args.preset)
    builder.load_prices()
    builder.build_filter(args.output)

    print(f"\nFilter built successfully!")
    print(f"  Preset: {args.preset}")
    print(f"  Items: {builder.filtered_count} (of {len(builder.items)} loaded)")
    print(f"  Output: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
