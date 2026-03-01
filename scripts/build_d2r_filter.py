#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
import json
import os
import time
import tempfile
import subprocess
import shlex

from d2lut.exporters.d2r_json_filter import D2RJsonFilterExporter
from d2lut.exporters.d2r_affix_filter import AffixHighlighter
from d2lut.exporters.d2r_base_hints import BaseHintGenerator
from d2lut.exporters.rune_converter import RuneConverter
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

def run_cmd(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"[refresh] $ {' '.join(shlex.quote(c) for c in cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(f"[refresh] command failed with code {proc.returncode}")
    return proc.returncode

def refresh_market_on_exit(args) -> int:
    if args.refresh_command:
        return run_cmd(args.refresh_command, cwd=APP_DIR)

    # Local snapshot refresh path (no web fetch): just re-run parser/estimates on existing snapshot dirs.
    if not args.refresh_web:
        cmd = [
            sys.executable, "scripts/run_d2jsp_snapshot_pipeline.py",
            "--db", args.db,
            "--market-key", args.market_key,
            "--forum-pages-dir", args.forum_pages_dir,
            "--topic-pages-dir", args.topic_pages_dir,
            "--candidate-limit", str(args.refresh_candidate_limit),
            "--top-limit", str(args.refresh_top_limit),
            "--candidate-skip-liquid-singletons",
            "--candidate-singleton-recent-hours", str(args.candidate_singleton_recent_hours),
            "--candidate-singleton-min-recent-observations", str(args.candidate_singleton_min_recent_observations),
            "--quiet",
        ]
        return run_cmd(cmd, cwd=APP_DIR)

    # Web refresh path:
    # 1) fetch top forum pages
    fetch_forum_cmd = [
        sys.executable, "scripts/fetch_d2jsp_forum_pages.py",
        "--forum-id", str(args.forum_id),
        "--pages", str(args.refresh_forum_pages),
        "--categories", args.refresh_categories,
        "--out-dir", args.forum_pages_dir,
        "--profile-dir", args.refresh_profile_dir,
        "--delay-ms", str(args.refresh_delay_ms),
        "--retries", str(args.refresh_retries),
        "--no-skip-existing",
    ]
    if args.refresh_manual_start:
        fetch_forum_cmd.append("--manual-start")
    else:
        fetch_forum_cmd.append("--no-manual-start")
    if run_cmd(fetch_forum_cmd, cwd=APP_DIR) != 0:
        return 1

    # 2) build fresh candidate URL list from refreshed forum snapshots
    candidates_out = str(APP_DIR / "data" / "cache" / "topic_candidates_monitor.txt")
    plan_cmd = [
        sys.executable, "scripts/run_d2jsp_snapshot_pipeline.py",
        "--db", args.db,
        "--market-key", args.market_key,
        "--forum-pages-dir", args.forum_pages_dir,
        "--topic-pages-dir", args.topic_pages_dir,
        "--candidate-limit", str(args.refresh_candidate_limit),
        "--candidate-urls-out", candidates_out,
        "--skip-topic-import",
        "--skip-top",
        "--candidate-skip-liquid-singletons",
        "--candidate-singleton-recent-hours", str(args.candidate_singleton_recent_hours),
        "--candidate-singleton-min-recent-observations", str(args.candidate_singleton_min_recent_observations),
        "--quiet",
    ]
    if run_cmd(plan_cmd, cwd=APP_DIR) != 0:
        return 1

    # 3) fetch candidate topic pages (refetch top set each run)
    fetch_topic_cmd = [
        sys.executable, "scripts/fetch_d2jsp_topic_pages.py",
        "--url-file", candidates_out,
        "--out-dir", args.topic_pages_dir,
        "--profile-dir", args.refresh_profile_dir,
        "--delay-ms", str(args.refresh_delay_ms),
        "--retries", str(args.refresh_retries),
        "--no-skip-existing",
        "--limit", str(args.refresh_topic_limit),
    ]
    if args.refresh_manual_start:
        fetch_topic_cmd.append("--manual-start")
    else:
        fetch_topic_cmd.append("--no-manual-start")
    if run_cmd(fetch_topic_cmd, cwd=APP_DIR) != 0:
        return 1

    # 4) import refreshed topic pages + rebuild top estimates
    final_cmd = [
        sys.executable, "scripts/run_d2jsp_snapshot_pipeline.py",
        "--db", args.db,
        "--market-key", args.market_key,
        "--forum-pages-dir", args.forum_pages_dir,
        "--topic-pages-dir", args.topic_pages_dir,
        "--skip-forum-import",
        "--skip-candidates",
        "--top-limit", str(args.refresh_top_limit),
        "--quiet",
    ]
    return run_cmd(final_cmd, cwd=APP_DIR)

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
            affix_highlighter=AffixHighlighter(APP_DIR / "config" / "gg_affixes.yml") if cfg["apply_colors"] else None,
            base_hint_generator=BaseHintGenerator(APP_DIR / "config" / "base_potential.yml"),
            perfect_rolls_path=APP_DIR / "config" / "perfect_rolls.yml",
            rune_converter=RuneConverter(APP_DIR / "config" / "rune_prices.yml"),
            magic_combos_path=APP_DIR / "data" / "templates" / "item-magic-combos.json"
        )
        json_text = exporter.export(price_index, conn=conn, base_json_path=args.base_json, base_runes_json_path=args.base_runes_json)
        
        if args.dry_run:
            print("Dry run complete. No files were written.")
            # Still print audit report for dry run
        else:
            # Write primary item-names.json
            out_path = Path(args.out)
            atomic_write_text(out_path, json_text, encoding="utf-8")
            print(f"Successfully wrote D2R filter mod to: {out_path}")
            print(f"Total entries generated: {len(json.loads(json_text))}")
            
            # Process and write item-runes.json if evaluated
            if hasattr(exporter, 'runes_mod_data_out') and exporter.runes_mod_data_out:
                runes_out_path = Path(args.out).parent / "item-runes.json"
                atomic_write_text(runes_out_path, exporter.runes_mod_data_out, encoding="utf-8")
                print(f"Successfully wrote D2R runes mod to: {runes_out_path}")

            # Also process affixes if requested
            if exporter.affix_highlighter:
                affix_out_path = Path(args.out).parent / "item-nameaffixes.json"
                affix_text = exporter.export_affixes(base_affix_json_path=args.base_affix_json)
                atomic_write_text(affix_out_path, affix_text, encoding="utf-8")
                print(f"Successfully wrote D2R affix filter mod to: {affix_out_path}")

            # Export magic item combinations (GG combos with full pricing)
            if exporter.magic_combos:
                magic_combos_out_path = Path(args.out).parent / "item-magic-combos.json"
                magic_combos_text = exporter.export_magic_combos()
                atomic_write_text(magic_combos_out_path, magic_combos_text, encoding="utf-8")
                print(f"Successfully wrote D2R magic combos to: {magic_combos_out_path} ({len(exporter.magic_combos)} entries)")

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
    parser.add_argument("--forum-id", type=int, default=271, help="d2jsp forum id used for refresh flows")
    parser.add_argument("--forum-pages-dir", type=str, default=str(APP_DIR / "data" / "raw" / "d2jsp" / "forum_pages"), help="Forum snapshot directory")
    parser.add_argument("--topic-pages-dir", type=str, default=str(APP_DIR / "data" / "raw" / "d2jsp" / "topic_pages"), help="Topic snapshot directory")
    parser.add_argument("--candidate-singleton-recent-hours", type=int, default=24, help="Hours window for liquid singleton candidate skip")
    parser.add_argument("--candidate-singleton-min-recent-observations", type=int, default=5, help="Minimum recent obs for liquid singleton skip")
    parser.add_argument("--min-fg", type=float, default=20.0, help="Minimum fg estimate to inject into filter")
    parser.add_argument("--price-mode", type=str, choices=["estimate", "range_low", "range_high"], default="estimate", help="Price field to inject")
    parser.add_argument("--format-str", type=str, default=" [{fg} fg]", help="Template for the price string. Use '{fg}' as the placeholder (e.g., ' | {fg} FG')")
    parser.add_argument("--tag-style", type=str, choices=list(TAG_STYLES.keys()), default="bracket", help="Convenience style for the price tag (ignored if --format-str is explicitly provided)")
    parser.add_argument("--always-include-kinds", type=str, default=None, help="Comma-separated list of item kinds (e.g., rune,key) to bypass min-fg threshold")
    parser.add_argument("--base-json", type=str, default=str(APP_DIR / "data" / "templates" / "item-names-full.json"), help="Base item-names.json to modify")
    parser.add_argument("--base-runes-json", type=str, default=str(APP_DIR / "data" / "templates" / "item-runes.json"), help="Base item-runes.json to modify")
    parser.add_argument("--base-affix-json", type=str, default=str(APP_DIR / "data" / "templates" / "item-nameaffixes.json"), help="Base item-nameaffixes.json to modify")
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
    parser.add_argument("--refresh-on-exit", action="store_true", help="When game exits, refresh market snapshots/prices before generating filter")
    parser.add_argument("--refresh-command", nargs="+", default=None, help="Custom command to run for market refresh on exit")
    parser.add_argument("--refresh-web", action="store_true", help="Use web snapshot fetchers during refresh-on-exit")
    parser.add_argument("--refresh-profile-dir", type=str, default=str(APP_DIR / "data" / "cache" / "playwright-d2jsp-profile"), help="Playwright profile dir for web refresh")
    parser.add_argument("--refresh-manual-start", action="store_true", help="Pause for Cloudflare/login before web refresh crawl")
    parser.add_argument("--refresh-forum-pages", type=int, default=10, help="Forum pages per category to refresh in web mode")
    parser.add_argument("--refresh-categories", type=str, default="2,3,4,5", help="Categories to refresh in web mode")
    parser.add_argument("--refresh-topic-limit", type=int, default=250, help="Max candidate topics to fetch per refresh cycle")
    parser.add_argument("--refresh-candidate-limit", type=int, default=500, help="Candidate pool size for refresh pipeline")
    parser.add_argument("--refresh-top-limit", type=int, default=200, help="Top estimates rebuilt per refresh cycle")
    parser.add_argument("--refresh-delay-ms", type=int, default=300, help="Delay between page fetches in web refresh mode")
    parser.add_argument("--refresh-retries", type=int, default=2, help="Retries for page fetches in web refresh mode")

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
                        print(f"[monitor] Detected game exit: {proc_name}.")
                        if args.refresh_on_exit:
                            print("[monitor] Running market refresh before filter generation...")
                            refresh_rc = refresh_market_on_exit(args)
                            if refresh_rc != 0:
                                print("[monitor] Refresh failed. Skipping filter rebuild for this cycle.")
                                if args.run_once_after_exit:
                                    sys.exit(refresh_rc)
                                seen_running = False
                                print("[monitor] Waiting for next game launch...")
                                time.sleep(poll_seconds)
                                continue
                        print("[monitor] Rebuilding filter...")
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
