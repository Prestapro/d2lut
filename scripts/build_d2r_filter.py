#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
import json

from d2lut.exporters.d2r_json_filter import D2RJsonFilterExporter
from d2lut.models import ObservedPrice
from d2lut.pricing.engine import PricingEngine
from d2lut.storage.sqlite import D2LutDB
import sqlite3

# Define the configurable override presets
PRESETS = {
    "leveling": {
        "min_fg": 0.0,
        "hide_junk": False,
        "use_short_names": True,
        "apply_colors": False,
        "always_include_kinds": ["rune", "gem"]
    },
    "crafting": {
        "min_fg": 20.0,
        "hide_junk": True,
        "use_short_names": True,
        "apply_colors": True,
        "always_include_kinds": ["rune", "base", "jewel", "gem"]
    },
    "endgame": {
        "min_fg": 50.0,
        "hide_junk": True,
        "use_short_names": True,
        "apply_colors": True,
        "always_include_kinds": ["rune", "key", "token"]
    },
    "wealth": {
        "min_fg": 200.0,
        "hide_junk": True,
        "use_short_names": True,
        "apply_colors": True,
        "always_include_kinds": ["rune:jah", "rune:ber"] # Example: only extremely high runes bypass
    }
}

def get_app_dir() -> Path:
    # Determine execution context (PyInstaller bundle or normal script)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

APP_DIR = get_app_dir()

TAG_STYLES = {
    "bracket": " [{fg} fg]",
    "bracket-upper": " [{fg} FG]",
    "paren": " ({fg} fg)",
    "pipe": " | {fg} fg",
    "pipe-upper": " | {fg} FG",
    "bare": " {fg} fg",
    "bare-upper": " {fg} FG",
}

def interactive_prompt() -> str:
    print("Welcome to the D2Lut Static Loot Filter Generator!")
    print("\nSelect a Preset Profile to generate:")
    print("  [1] Leveling: Show all items, highlight runes/gems (0+ fg)")
    print("  [2] Crafting: Hide trash, show bases/jewels/gems (20+ fg)")
    print("  [3] Endgame : Hide trash, show keys/tokens (50+ fg)")
    print("  [4] Wealth  : Hide trash, show ONLY Jah/Ber (200+ fg)\n")
    
    choice = ""
    try:
        while choice not in ["1", "2", "3", "4"]:
            choice = input("Enter choice (1-4): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
        sys.exit(0)
        
    mapping = {"1": "leveling", "2": "crafting", "3": "endgame", "4": "wealth"}
    preset_name = mapping[choice]
    
    print(f"\n[+] Selected {preset_name.title()} preset.")
    return preset_name

def main() -> None:
    # If run via double-click (no arguments provided except script name)
    is_interactive = len(sys.argv) == 1
    default_preset = "crafting"
    
    if is_interactive:
        default_preset = interactive_prompt()

    parser = argparse.ArgumentParser(description="Generate D2R Static Loot Filter Mod (item-names.json)")
    parser.add_argument("--db", type=str, default=str(APP_DIR / "data" / "cache" / "d2lut.db"), help="Path to SQLite DB (d2lut.db)")
    parser.add_argument("--market-key", type=str, default="d2r_sc_ladder", help="Market key namespace")
    parser.add_argument("--min-fg", type=float, default=20.0, help="Minimum fg estimate to inject into filter")
    parser.add_argument("--price-mode", type=str, choices=["estimate", "range_low", "range_high"], default="estimate", help="Price field to inject")
    parser.add_argument("--format-str", type=str, default=" [{fg} fg]", help="Template for the price string. Use '{fg}' as the placeholder (e.g., ' | {fg} FG')")
    parser.add_argument("--tag-style", type=str, choices=list(TAG_STYLES.keys()), default="bracket", help="Convenience style for the price tag (ignored if --format-str is explicitly provided)")
    parser.add_argument("--always-include-kinds", type=str, default=None, help="Comma-separated list of item kinds (e.g., rune,key) to bypass min-fg threshold")
    parser.add_argument("--base-json", type=str, default=str(APP_DIR / "data" / "templates" / "item-names.json"), help="Base item-names.json to modify")
    parser.add_argument("--out", type=str, default=str(APP_DIR / "output" / "item-names.json"), help="Output path for item-names.json")
    parser.add_argument("--audit-json", type=str, default=None, help="Optional path to write mapping audit report as JSON")
    parser.add_argument("--dry-run", action="store_true", help="Generate the filter in memory and print the audit report without writing to disk")
    parser.add_argument("--hide-junk", action="store_true", default=None, help="Hide low-value trash items like arrows, low potions, and chips")
    parser.add_argument("--use-short-names", action="store_true", default=None, help="Rename common items like potions and scrolls to take up less screen space")
    parser.add_argument("--apply-colors", action="store_true", default=None, help="Inject D2R format tags (e.g. ÿc8) based on Forum Gold tiers")
    parser.add_argument("--preset", type=str, choices=list(PRESETS.keys()), default=default_preset if is_interactive else None, help="Apply a pre-configured set of filters and thresholds")

    raw_argv = [] if is_interactive else sys.argv[1:]
    args = parser.parse_args(raw_argv)
    format_str_explicit = any(a == "--format-str" or a.startswith("--format-str=") for a in raw_argv)
    
    # Merge CLI args with selected preset
    cfg = {
        "min_fg": args.min_fg,
        "hide_junk": args.hide_junk if args.hide_junk is not None else False,
        "use_short_names": args.use_short_names if args.use_short_names is not None else False,
        "apply_colors": args.apply_colors if args.apply_colors is not None else False,
        "always_include_kinds": args.always_include_kinds,
        "format_str": args.format_str,
    }
    
    if args.preset:
        preset_cfg = PRESETS[args.preset]
        print(f"Applying preset: {args.preset}")
        # CLI overrides preset if explicitly passed, else fallback
        if getattr(args, 'min_fg', None) != 20.0:  # If user changed default
            cfg["min_fg"] = args.min_fg
        else:
            cfg["min_fg"] = preset_cfg.get("min_fg", 20.0)
            
        cfg["hide_junk"] = True if args.hide_junk else preset_cfg.get("hide_junk", False)
        cfg["use_short_names"] = True if args.use_short_names else preset_cfg.get("use_short_names", False)
        cfg["apply_colors"] = True if args.apply_colors else preset_cfg.get("apply_colors", False)
        
        if args.always_include_kinds is not None:
             cfg["always_include_kinds"] = args.always_include_kinds
        else:
            # Reconstruct list into comma-delimited string for consistency downstream
             cfg["always_include_kinds"] = ",".join(preset_cfg.get("always_include_kinds", []))

    if not format_str_explicit:
        cfg["format_str"] = TAG_STYLES.get(args.tag_style, args.format_str)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to DB {args.db} ...")
    market_db = D2LutDB(str(db_path))
    
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    
    print("Loading recent observations...")
    # we don't need raw posts, just observations
    # For a snapshot workflow, observations are already in the DB.
    # Alternatively we can query estimates directly if we persisted them.
    # We will compute estimates on the fly from the DB.
    raw_obs = market_db.load_observations(args.market_key)
    observations = []
    for row in raw_obs:
        # Based on how observed prices are stored in sqlite (signal_kind, price_fg)
        # we map this back to ask/bin/sold
        ask, bin_val, sold = None, None, None
        if row["signal_kind"] == "ask":
            ask = row["price_fg"]
        elif row["signal_kind"] == "bin":
            bin_val = row["price_fg"]
        elif row["signal_kind"] == "sold":
            sold = row["price_fg"]
            
        observations.append(ObservedPrice(
            canonical_item_id=row["canonical_item_id"],
            variant_key=row["variant_key"],
            ask_fg=ask,
            bin_fg=bin_val,
            sold_fg=sold,
            confidence=row["confidence"],
            source_url=row["source_url"] or ""
        ))        
    print(f"Loaded {len(observations)} observations.")
    
    pricing = PricingEngine()
    price_index = pricing.build_index(observations)
    print(f"Computed {len(price_index)} price estimates.")

    included_kinds = [k.strip().lower() for k in cfg["always_include_kinds"].split(",") if k.strip()] if cfg["always_include_kinds"] else []
    print(f"Generating filter with minimum threshold: {cfg['min_fg']} fg (mode: {args.price_mode})")
    print(f"Price tag format: {cfg['format_str']!r}")
    if included_kinds:
        print(f"Bypassing threshold for kinds: {included_kinds}")
        
    exporter = D2RJsonFilterExporter(
        min_fg=cfg["min_fg"], 
        format_str=cfg["format_str"],
        price_mode=args.price_mode,
        always_include_kinds=included_kinds,
        hide_junk=cfg["hide_junk"],
        use_short_names=cfg["use_short_names"],
        apply_colors=cfg["apply_colors"]
    )
    json_text = exporter.export(price_index, conn=conn, base_json_path=args.base_json)
    
    # Print mapping audit report
    report = exporter.audit_report
    print("\n--- Mapping Audit Report ---")
    print(f"Total estimates evaluated: {report['total_evaluated']}")
    print(f"Passed min-fg or forced inclusion: {report['eligible_count']}")
    print(f"Successfully mapped keys: {report['mapped_count']}")
    if report["unmapped_variants"]:
        print(f"Unmapped variants (Top 10): {report['unmapped_variants'][:10]}")
    if report["multi_map_variants"]:
        print(f"Multi-map warnings (Top 10): {report['multi_map_variants'][:10]}")
    print("----------------------------\n")

    if args.audit_json:
        audit_path = Path(args.audit_json)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote audit report to: {audit_path}")

    if args.dry_run:
        print("Dry run complete. No files were written.")
        sys.exit(0)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json_text, encoding="utf-8")
    
    print(f"Successfully wrote D2R filter mod to: {out_path}")
    print(f"Total entries generated: {len(json.loads(json_text))}")

    if is_interactive:
        try:
            input("\nPress Enter to exit...")
        except (EOFError, KeyboardInterrupt):
            pass

if __name__ == "__main__":
    main()
