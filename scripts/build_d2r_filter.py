#!/usr/bin/env python3
"""D2R Loot Filter Builder.

Builds item filter files for Diablo 2 Resurrected based on FG prices.

Usage:
    python build_d2r_filter.py --preset roguecore --db d2lut.db
    python build_d2r_filter.py --help
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

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

# Price tiers (FG)
PRICE_TIERS = {
    "GG": (500, float("inf")),    # 500+ FG
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
    """Item with FG price."""
    name: str
    variant_key: str
    price_fg: float
    tier: str
    category: str = "misc"


class FilterBuilder:
    """Builds D2R item filter files."""

    def __init__(self, db_path: Optional[Path] = None, preset: str = "default"):
        self.db_path = db_path
        self.preset = preset
        self.items: list[PricedItem] = []

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

            cursor.execute("""
                SELECT variant_key, price_fg, category
                FROM price_estimates
                WHERE price_fg > 0
                ORDER BY price_fg DESC
            """)

            for row in cursor.fetchall():
                item = self._row_to_item(row)
                if item:
                    self.items.append(item)

            conn.close()
            logger.info(f"Loaded {len(self.items)} priced items from database")

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            self._load_default_prices()

    def _row_to_item(self, row: sqlite3.Row) -> Optional[PricedItem]:
        """Convert database row to PricedItem."""
        variant_key = row["variant_key"]
        price_fg = row["price_fg"]
        # sqlite3.Row doesn't have .get() method, use keys() check
        row_keys = row.keys()
        category = row["category"] if "category" in row_keys else "misc"

        # Extract name from variant_key
        parts = variant_key.split(":")
        name = parts[-1] if parts else variant_key

        # Determine tier
        tier = self._get_tier(price_fg)

        return PricedItem(
            name=name,
            variant_key=variant_key,
            price_fg=price_fg,
            tier=tier,
            category=category,
        )

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
            ("rune:jah", 150, "rune"),
            ("rune:ber", 140, "rune"),
            ("rune:sur", 35, "rune"),
            ("rune:lo", 30, "rune"),
            ("rune:ohm", 28, "rune"),
            ("rune:vex", 22, "rune"),
            ("rune:gul", 12, "rune"),
            ("rune:ist", 18, "rune"),
            ("rune:mal", 8, "rune"),
            ("rune:um", 4, "rune"),

            # Uniques - High value
            ("unique:shako", 15, "unique"),
            ("unique:arachnid", 45, "unique"),
            ("unique:mara", 25, "unique"),
            ("unique:tyraels", 200, "unique"),
            ("unique:torch", 50, "unique"),  # Average torch
            ("unique:anni", 80, "unique"),   # Average anni

            # Runewords
            ("runeword:enigma", 160, "runeword"),
            ("runeword:infinity", 180, "runeword"),
            ("runeword:cta", 40, "runeword"),
            ("runeword:grief", 35, "runeword"),
            ("runeword:fortitude", 45, "runeword"),
            ("runeword:spirit", 5, "runeword"),
        ]

        for variant_key, price, category in default_prices:
            tier = self._get_tier(price)
            name = variant_key.split(":")[-1]
            self.items.append(PricedItem(
                name=name,
                variant_key=variant_key,
                price_fg=price,
                tier=tier,
                category=category,
            ))

        logger.info(f"Loaded {len(self.items)} default prices")

    def build_filter(self, output_path: Path) -> None:
        """Build the filter file."""
        lines = []

        # Header
        lines.append(f"# D2R Loot Filter - Built {datetime.now().isoformat()}")
        lines.append(f"# Preset: {self.preset}")
        lines.append(f"# Items: {len(self.items)}")
        lines.append("")

        # Add filter rules by tier
        for tier in ["GG", "HIGH", "MID", "LOW", "TRASH"]:
            tier_items = [i for i in self.items if i.tier == tier]
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

    def _build_item_line(self, item: PricedItem) -> str:
        """Build a single filter line for an item."""
        color = TIER_COLORS.get(item.tier, COLORS["WHITE"])

        # Format price display
        if item.price_fg >= 100:
            price_str = f"{int(item.price_fg)}"
        elif item.price_fg >= 10:
            price_str = f"{item.price_fg:.0f}"
        else:
            price_str = f"{item.price_fg:.1f}"

        # Build the display format
        # D2R filter syntax: ItemDisplay[NAME]: %COLOR%%NAME% %PRICE%
        return f'ItemDisplay[{item.name}]: {color}{item.name} {COLORS["GOLD"]}[{price_str} FG]'


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
    print(f"  Items: {len(builder.items)}")
    print(f"  Output: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
