#!/usr/bin/env python3
"""D2R Layered Filter Generator — Python version.

Reads from SQLite (Prisma-compatible), outputs .filter file.
Mirrors the TypeScript generator logic exactly.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone

# ============================================================
# D2R COLOR CODES
# ============================================================
COLORS = {
    "GG":    "ÿc9",
    "HIGH":  "ÿc7",
    "MID":   "ÿc8",
    "LOW":   "ÿc0",
    "TRASH": "ÿc5",
    "SET":   "ÿc2",
    "MAGIC": "ÿc3",
    "RARE":  "ÿc4",
    "DIM":   "ÿc6",
}

TIER_THRESHOLDS = [
    ("GG",    500, float("inf")),
    ("HIGH",  100, 500),
    ("MID",    20, 100),
    ("LOW",     5,  20),
    ("TRASH",   0,   5),
]

def get_tier(price: float) -> str:
    for name, low, high in TIER_THRESHOLDS:
        if low <= price < high:
            return name
    return "TRASH"

def tier_color(price: float | None) -> str:
    if price is None:
        return COLORS["DIM"]
    return COLORS.get(get_tier(price), COLORS["DIM"])

def price_tag(price: float | None) -> str:
    if not price or price <= 0:
        return ""
    return f" ÿc6[{round(price)} FG]"

# ============================================================
# RUNEWORD BASES MAP
# ============================================================
@dataclass
class RunewordBase:
    name: str
    codes: list[str]
    sockets: int
    price: float

RUNEWORD_BASES: list[RunewordBase] = [
    RunewordBase("Enigma",    ["xtp","uea","utp"],            3, 160),
    RunewordBase("Infinity",  ["7s8","7vo","7pa","7b8"],      4, 180),
    RunewordBase("BotD",      ["7wa","7wh","7bt","7fb"],      6, 120),
    RunewordBase("Last Wish", ["7wa","7wh","7bt","7fb"],      6,  90),
    RunewordBase("Grief",     ["7cr","7ls","7gy"],            5,  35),
    RunewordBase("CTA",       ["7cr","7ls","7gy"],            5,  40),
    RunewordBase("Fortitude", ["xtp","uea","utp","7wa"],      4,  50),
    RunewordBase("CoH",       ["xtp","uea","utp"],            4,  60),
    RunewordBase("Faith",     ["am6","8lx","8rx"],            4,  45),
    RunewordBase("Beast",     ["7wa","7wh"],                  5,  30),
    RunewordBase("HotO",      ["obf","ob7","obb"],            4,  35),
    RunewordBase("Spirit",    ["pa9","7pa","ush","xrn"],      4,   5),
    RunewordBase("Insight",   ["7s8","7vo","7pa"],            4,   8),
    RunewordBase("Oath",      ["7cr","7ls","7gy","7bt"],      4,   5),
    RunewordBase("Exile",     ["upa","upb","upc"],            4,  15),
    RunewordBase("Phoenix",   ["xtp","uea","utp"],            4,  25),
    RunewordBase("Dragon",    ["xtp","uea","utp"],            3,  10),
]

def build_runeword_map() -> dict[str, RunewordBase]:
    """One code → best (most expensive) runeword."""
    result: dict[str, RunewordBase] = {}
    for rw in RUNEWORD_BASES:
        for code in rw.codes:
            if code not in result or rw.price > result[code].price:
                result[code] = rw
    return result

# ============================================================
# PRESET CONFIGS
# ============================================================
@dataclass
class PresetConfig:
    show_unique: bool = True
    show_set: bool = True
    show_runeword_bases: bool = True
    show_normal_bases: bool = True
    suppress_trash: bool = False
    auto_threshold: float | None = None  # None = use user threshold

PRESETS: dict[str, PresetConfig] = {
    "default":   PresetConfig(),
    "ggplus":    PresetConfig(suppress_trash=True, auto_threshold=100.0),
    "gg":        PresetConfig(show_set=False, show_normal_bases=False,
                              suppress_trash=True, auto_threshold=500.0),
    "roguecore": PresetConfig(suppress_trash=True),
    "minimal":   PresetConfig(show_set=False, show_runeword_bases=False,
                              show_normal_bases=False, suppress_trash=True,
                              auto_threshold=100.0),
    "verbose":   PresetConfig(),
}

# ============================================================
# LAYER GENERATOR
# ============================================================
@dataclass
class FilterItem:
    code: str
    display_name: str
    price: float | None
    category: str

def generate_layers(
    item: FilterItem,
    runeword_map: dict[str, RunewordBase],
    threshold: float,
    cfg: PresetConfig,
) -> list[str]:
    lines: list[str] = []
    code = item.code
    color = tier_color(item.price)
    tag = price_tag(item.price)
    above = (item.price or 0) >= threshold

    # Layer 1: UNIQUE — %NAME% resolves collisions natively
    if cfg.show_unique:
        lines.append(f"ItemDisplay[{code}&UNIQUE]: {COLORS['GG']}%NAME%{tag}")

    # Layer 2: SET
    if cfg.show_set:
        lines.append(f"ItemDisplay[{code}&SET]: {COLORS['SET']}%NAME%{tag}")

    # Layer 3: Runeword base
    if cfg.show_runeword_bases:
        rw = runeword_map.get(code)
        if rw and rw.price >= threshold:
            rw_color = tier_color(rw.price)
            rw_tag = price_tag(rw.price)
            lines.append(
                f"ItemDisplay[{code}>{rw.sockets - 1}]: "
                f"{rw_color}{rw.name} BASE ÿc6[{rw.sockets}os]{rw_tag}"
            )

    # Layer 4: Normal base
    if cfg.show_normal_bases:
        if above:
            if cfg.suppress_trash and item.price is not None and item.price < 5:
                lines.append(f"ItemDisplay[{code}]: ")
            else:
                lines.append(f"ItemDisplay[{code}]: {color}{item.display_name}{tag}")
        else:
            lines.append(f"ItemDisplay[{code}]: ")  # suppress

    return lines

# ============================================================
# DB READER
# ============================================================
def load_items_from_db(db_path: Path) -> list[FilterItem]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT
                i.d2rCode  AS code,
                i.displayName AS display_name,
                i.category,
                p.priceFg  AS price
            FROM D2Item i
            LEFT JOIN PriceEstimate p ON p.itemId = i.id
            WHERE i.d2rCode IS NOT NULL
              AND i.d2rCode != ''
        """).fetchall()
    finally:
        conn.close()

    items: list[FilterItem] = []
    for r in rows:
        items.append(FilterItem(
            code=r["code"],
            display_name=r["display_name"] or r["code"],
            price=float(r["price"]) if r["price"] is not None else None,
            category=r["category"] or "",
        ))
    return items

def deduplicate(items: list[FilterItem]) -> dict[str, FilterItem]:
    """One code → highest price item."""
    by_code: dict[str, FilterItem] = {}
    for item in items:
        existing = by_code.get(item.code)
        if not existing or (item.price or 0) > (existing.price or 0):
            by_code[item.code] = item
    return by_code

# ============================================================
# MAIN GENERATOR
# ============================================================
def generate_filter(
    preset: str,
    threshold: float,
    db_path: Path,
) -> str:
    cfg = PRESETS.get(preset, PRESETS["default"])
    effective_threshold = cfg.auto_threshold if cfg.auto_threshold is not None else threshold
    runeword_map = build_runeword_map()

    items = load_items_from_db(db_path)
    by_code = deduplicate(items)

    header = "\n".join([
        "# D2R Layered Loot Filter — D2LUT",
        f"# Generated: {datetime.now(timezone.utc).isoformat()}Z",
        f"# Preset: {preset} | Threshold: {effective_threshold} FG",
        "# Architecture: 4-layer (UNIQUE > SET > RUNEWORD_BASE > NORMAL)",
        "# %NAME% token: D2R resolves unique/set names natively",
        "",
        "# Layer 1: [code&UNIQUE]  → %NAME% (no base collisions!)",
        "# Layer 2: [code&SET]     → %NAME% set color",
        "# Layer 3: [code>N]       → RUNEWORD BASE (N = min sockets)",
        "# Layer 4: [code]         → normal base / suppress",
        "",
    ])

    # Group by tier for readability
    tier_order = ["GG", "HIGH", "MID", "LOW", "TRASH", "UNKNOWN"]
    tier_groups: dict[str, list[str]] = {t: [] for t in tier_order}

    for code, item in by_code.items():
        tier = get_tier(item.price) if item.price is not None else "UNKNOWN"
        layers = generate_layers(item, runeword_map, effective_threshold, cfg)
        if layers:
            group = tier_groups.get(tier, tier_groups["UNKNOWN"])
            group.append(f"# --- {item.display_name} ({item.price or '?'} FG) ---")
            group.extend(layers)
            group.append("")

    sections = [header]
    for tier in tier_order:
        lines = tier_groups[tier]
        if not lines:
            continue
        rule_count = sum(1 for l in lines if l.startswith("ItemDisplay"))
        sections.append("=" * 60)
        sections.append(f"# {tier} TIER — {rule_count} rules")
        sections.append("=" * 60)
        sections.append("")
        sections.extend(lines)

    return "\n".join(sections)

# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="D2R Layered Filter Generator")
    parser.add_argument("--preset",    default="default",
                        choices=list(PRESETS.keys()))
    parser.add_argument("--threshold", type=float, default=0)
    parser.add_argument("--db",        type=Path,
                        default=Path("db/custom.db"),
                        help="Path to Prisma SQLite database")
    parser.add_argument("--output",    type=Path, default=None,
                        help="Output file path (default: stdout)")
    args = parser.parse_args()

    if not args.db.exists():
        # Try fallback path
        fallback = Path("prisma/dev.db")
        if fallback.exists():
            args.db = fallback
        else:
            print(f"ERROR: DB not found at {args.db}", file=sys.stderr)
            sys.exit(1)

    content = generate_filter(args.preset, args.threshold, args.db)

    if args.output:
        args.output.write_text(content, encoding="utf-8")
        print(f"✓ Filter written to {args.output} ({content.count('ItemDisplay')} rules)")
    else:
        print(content)

if __name__ == "__main__":
    main()
