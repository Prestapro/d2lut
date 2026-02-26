#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
import json
import os
import time
import tempfile
import subprocess

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
        "always_include_kinds": ["rune", "gem"],
        "tag_style": "bracket",
    },
    "crafting": {
        "min_fg": 20.0,
        "hide_junk": True,
        "use_short_names": True,
        "apply_colors": True,
        "always_include_kinds": ["rune", "base", "jewel", "gem"],
        "tag_style": "bracket",
    },
    "endgame": {
        "min_fg": 50.0,
        "hide_junk": True,
        "use_short_names": True,
        "apply_colors": True,
        "always_include_kinds": ["rune", "key", "token"],
        "tag_style": "bracket",
    },
    "wealth": {
        "min_fg": 200.0,
        "hide_junk": True,
        "use_short_names": True,
        "apply_colors": True,
        "always_include_kinds": ["rune:jah", "rune:ber"], # Example: only extremely high runes bypass
        "tag_style": "bracket",
    },
    # Inspired by d2jsp endgame D2R JSON filters (e.g. "Roguecore" style): sparse display, focus on trade-relevant drops.
    "roguecore": {
        "min_fg": 100.0,
        "hide_junk": True,
        "use_short_names": True,
        "apply_colors": True,
        "always_include_kinds": ["rune", "key", "token", "jewel", "base"],
        "tag_style": "pipe-upper",
    },
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
    print("  [4] Wealth  : Hide trash, show ONLY Jah/Ber (200+ fg)")
    print("  [5] Roguecore: Endgame-sparse styling, focus trade items (100+ fg)\n")
    
    choice = ""
    try:
        while choice not in ["1", "2", "3", "4", "5"]:
            choice = input("Enter choice (1-5): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
        sys.exit(0)
        
    mapping = {"1": "leveling", "2": "crafting", "3": "endgame", "4": "wealth", "5": "roguecore"}
    preset_name = mapping[choice]
    
    print(f"\n[+] Selected {preset_name.title()} preset.")
    return preset_name

def is_process_running(process_name: str) -> bool:
    name = (process_name or "").lower()
    if not name:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="ignore",
            )
            return name in result.stdout.lower()
        result = subprocess.run(
            ["ps", "-A", "-o", "comm="],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="ignore",
        )
        return any(name in line.lower() for line in result.stdout.splitlines())
    except Exception:
        return False

def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding=encoding) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)

def run_generation(args, cfg, is_interactive: bool = False) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {args.db}", file=sys.stderr)
        return 1

    print(f"Connecting to DB {args.db} ...")
    market_db = D2LutDB(str(db_path))
    
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        print("Loading recent observations...")
        raw_obs = market_db.load_observations(args.market_key)
        observations = []
        for row in raw_obs:
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
            apply_colors=cfg["apply_colors"],
            collect_explain=args.explain,
            explain_limit=args.explain_limit,
        )
        json_text = exporter.export(price_index, conn=conn, base_json_path=args.base_json)

        report = exporter.audit_report
        print("\n--- Mapping Audit Report ---")
        print(f"Total estimates evaluated: {report['total_evaluated']}")
        print(f"Passed min-fg or forced inclusion: {report['eligible_count']}")
        print(f"  - by threshold: {report.get('eligible_by_threshold', 0)}")
        print(f"  - by forced include: {report.get('eligible_by_forced', 0)}")
        print(f"Successfully mapped keys: {report['mapped_count']}")
        if report["unmapped_variants"]:
            print(f"Unmapped variants (Top 10): {report['unmapped_variants'][:10]}")
        if report["multi_map_variants"]:
            print(f"Multi-map warnings (Top 10): {report['multi_map_variants'][:10]}")
        if args.explain:
            if report.get("sample_injections"):
                print("Sample injections:")
                for row in report["sample_injections"][:args.explain_limit]:
                    forced = " forced" if row.get("forced_match") else ""
                    color = f" color={row['color_tag']}" if row.get("color_tag") else ""
                    print(f"  - {row['variant_key']} -> {row.get('mapped_keys', [])} | fg={row['fg_value']}{forced}{color} | tag={row['tag_text']!r}")
            if report.get("sample_skipped_below_threshold"):
                print("Sample skipped (below threshold):")
                for row in report["sample_skipped_below_threshold"][:args.explain_limit]:
                    print(f"  - {row['variant_key']} | fg={row['fg_value']} < threshold={row['threshold']}")
        print("----------------------------\n")

        if args.audit_json:
            audit_path = Path(args.audit_json)
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Wrote audit report to: {audit_path}")

        if args.dry_run:
            print("Dry run complete. No files were written.")
            return 0

        out_path = Path(args.out)
        atomic_write_text(out_path, json_text, encoding="utf-8")
        print(f"Successfully wrote D2R filter mod to: {out_path}")
        print(f"Total entries generated: {len(json.loads(json_text))}")

        if args.status_json:
            status_payload = {
                "ok": True,
                "timestamp": int(time.time()),
                "db": str(args.db),
                "out": str(args.out),
                "market_key": args.market_key,
                "mapped_count": report.get("mapped_count", 0),
                "eligible_count": report.get("eligible_count", 0),
            }
            atomic_write_text(Path(args.status_json), json.dumps(status_payload, indent=2, ensure_ascii=False) + "\n")
            print(f"Wrote status file: {args.status_json}")
        return 0
    finally:
        conn.close()

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
    parser.add_argument("--explain", action="store_true", help="Include sample injection/skip explanations in audit output")
    parser.add_argument("--explain-limit", type=int, default=20, help="Maximum number of sample explanations to collect")
    parser.add_argument("--dry-run", action="store_true", help="Generate the filter in memory and print the audit report without writing to disk")
    parser.add_argument("--hide-junk", action="store_true", default=None, help="Hide low-value trash items like arrows, low potions, and chips")
    parser.add_argument("--use-short-names", action="store_true", default=None, help="Rename common items like potions and scrolls to take up less screen space")
    parser.add_argument("--apply-colors", action="store_true", default=None, help="Inject D2R format tags (e.g. ÿc8) based on Forum Gold tiers")
    parser.add_argument("--preset", type=str, choices=list(PRESETS.keys()), default=default_preset if is_interactive else None, help="Apply a pre-configured set of filters and thresholds")
    parser.add_argument("--monitor-game", action="store_true", help="Wait for the game process to exit, then generate the filter (repeat loop)")
    parser.add_argument("--game-process-name", type=str, default="D2R.exe", help="Process name to watch in --monitor-game mode")
    parser.add_argument("--poll-seconds", type=int, default=10, help="Polling interval for --monitor-game mode")
    parser.add_argument("--build-on-start", action="store_true", help="Generate immediately on startup before monitor loop")
    parser.add_argument("--run-once-after-exit", action="store_true", help="In monitor mode, build once after one game exit and quit")
    parser.add_argument("--status-json", type=str, default=None, help="Optional path to write status JSON after each successful build")

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
        "tag_style": args.tag_style,
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
            cfg["tag_style"] = preset_cfg.get("tag_style", args.tag_style)

    if not format_str_explicit:
        cfg["format_str"] = TAG_STYLES.get(cfg.get("tag_style", args.tag_style), args.format_str)

    if args.monitor_game:
        poll_seconds = max(1, int(args.poll_seconds))
        proc_name = args.game_process_name
        seen_running = False
        print(f"Monitoring game process: {proc_name} (poll {poll_seconds}s)")
        if args.build_on_start:
            print("Build on start enabled.")
            rc = run_generation(args, cfg, is_interactive=False)
            if rc != 0:
                sys.exit(rc)
        try:
            while True:
                running = is_process_running(proc_name)
                if running:
                    if not seen_running:
                        print(f"[monitor] Detected game running: {proc_name}")
                    seen_running = True
                else:
                    if seen_running:
                        print(f"[monitor] Detected game exit: {proc_name}. Rebuilding filter...")
                        rc = run_generation(args, cfg, is_interactive=False)
                        if rc != 0:
                            sys.exit(rc)
                        if args.run_once_after_exit:
                            print("[monitor] run-once-after-exit complete.")
                            break
                        seen_running = False
                        print("[monitor] Waiting for next game launch...")
                time.sleep(poll_seconds)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            sys.exit(0)
    else:
        rc = run_generation(args, cfg, is_interactive=is_interactive)
        if rc != 0:
            sys.exit(rc)

    if is_interactive:
        try:
            input("\nPress Enter to exit...")
        except (EOFError, KeyboardInterrupt):
            pass

if __name__ == "__main__":
    main()
