#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import sqlite3
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str], *, env: dict[str, str] | None = None, quiet: bool = False) -> int:
    if not quiet:
        print("$ " + " ".join(shlex.quote(x) for x in cmd))
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


def ensure_dirs(paths: list[Path]) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="All-in-one d2jsp snapshot pipeline (forum -> candidates -> topics -> top)")
    p.add_argument("--db", default="data/cache/d2lut.db")
    p.add_argument("--forum-id", type=int, default=271)
    p.add_argument("--market-key", default="d2r_sc_ladder")
    p.add_argument("--max-fg", type=float, default=None, help="Optional upper price filter; unset = no cap")
    p.add_argument("--min-fg", type=float, default=None)

    p.add_argument("--forum-pages-dir", default="data/raw/d2jsp/forum_pages")
    p.add_argument("--topic-pages-dir", default="data/raw/d2jsp/topic_pages")
    p.add_argument("--recursive", action="store_true")
    p.add_argument("--pattern", default="*.html")

    p.add_argument("--skip-zero-replies", action="store_true", default=True,
                   help="Skip threads with zero replies (default: on)")
    p.add_argument("--no-skip-zero-replies", dest="skip_zero_replies",
                   action="store_false",
                   help="Include threads with zero replies")
    p.add_argument("--skip-bump-only-topic", action="store_true", default=True,
                   help="Skip topics that only have bump posts (default: on)")
    p.add_argument("--no-skip-bump-only-topic", dest="skip_bump_only_topic",
                   action="store_false",
                   help="Include topics that only have bump posts")

    p.add_argument("--candidate-limit", type=int, default=500)
    p.add_argument(
        "--candidate-prefer-recent",
        action="store_true",
        default=True,
        help="Prefer newest threads first when building topic candidates (default: on)",
    )
    p.add_argument(
        "--no-candidate-prefer-recent",
        dest="candidate_prefer_recent",
        action="store_false",
        help="Disable newest-first topic candidate ordering",
    )
    p.add_argument("--candidate-skip-liquid-singletons", action="store_true", help="Skip single-item liquid topics if enough fresh observations already exist")
    p.add_argument("--candidate-singleton-recent-hours", type=int, default=24)
    p.add_argument("--candidate-singleton-min-recent-observations", type=int, default=5)
    p.add_argument(
        "--candidate-include-terms",
        default="rune,key,torch,anni,facet,charm,skiller,lld,ring,amulet,ammy,circlet,diadem,jewel,gheed",
    )
    p.add_argument("--candidate-exclude-terms", default="rush,service,grush")
    p.add_argument("--candidate-urls-out", default="data/cache/topic_candidates_focus.txt")

    p.add_argument("--top-limit", type=int, default=100)
    p.add_argument("--generate-url-plans", action="store_true")
    p.add_argument("--pages", type=int, default=1000)
    p.add_argument("--plan-main-out", default="data/raw/d2jsp/forum_271_pages_1_1000.txt")
    p.add_argument("--plan-priority-out", default="data/raw/d2jsp/forum_271_priority_pages_1_1000.txt")
    p.add_argument("--priority-categories", default="2,3,4,5")

    p.add_argument("--skip-forum-import", action="store_true")
    p.add_argument("--skip-candidates", action="store_true")
    p.add_argument("--skip-topic-import", action="store_true")
    p.add_argument("--skip-top", action="store_true")
    p.add_argument("--clear-market", action="store_true", help="Delete observed_prices/price_estimates for market-key before import")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root_dirs = [
        Path(args.forum_pages_dir),
        Path(args.topic_pages_dir),
        Path(args.db).parent,
        Path(args.candidate_urls_out).parent,
        Path(args.plan_main_out).parent,
        Path(args.plan_priority_out).parent,
    ]
    ensure_dirs(root_dirs)

    env = dict(os.environ)
    env["PYTHONPATH"] = "src"

    if not args.quiet:
        cap_text = "none (uncapped)" if args.max_fg is None else str(args.max_fg)
        min_text = "none" if args.min_fg is None else str(args.min_fg)
        print(f"Market key: {args.market_key}")
        print(f"Price filters: min-fg={min_text} max-fg={cap_text}")

    if args.clear_market:
        db_path = Path(args.db)
        if not db_path.exists():
            if not args.quiet:
                print(f"Skipping --clear-market (DB not found yet): {db_path}")
        else:
            conn = sqlite3.connect(db_path)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM observed_prices WHERE market_key = ?", (args.market_key,))
                prev_obs = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM price_estimates WHERE market_key = ?", (args.market_key,))
                prev_est = int(cur.fetchone()[0])
                cur.execute("DELETE FROM observed_prices WHERE market_key = ?", (args.market_key,))
                cur.execute("DELETE FROM price_estimates WHERE market_key = ?", (args.market_key,))
                conn.commit()
                if not args.quiet:
                    print(f"Cleared market '{args.market_key}': observed_prices={prev_obs}, price_estimates={prev_est}")
            finally:
                conn.close()

    if args.generate_url_plans:
        cmd_main = [
            sys.executable,
            "scripts/generate_forum_url_plan.py",
            "--forum-id",
            str(args.forum_id),
            "--pages",
            str(args.pages),
        ]
        with Path(args.plan_main_out).open("w", encoding="utf-8") as f:
            if not args.quiet:
                print(f"$ {' '.join(shlex.quote(x) for x in cmd_main)} > {args.plan_main_out}")
            rc = subprocess.run(cmd_main, stdout=f).returncode
        if rc != 0:
            return rc

        cmd_pri = [
            sys.executable,
            "scripts/generate_forum_url_plan.py",
            "--forum-id",
            str(args.forum_id),
            "--pages",
            str(args.pages),
            "--categories",
            args.priority_categories,
            "--include-main",
        ]
        with Path(args.plan_priority_out).open("w", encoding="utf-8") as f:
            if not args.quiet:
                print(f"$ {' '.join(shlex.quote(x) for x in cmd_pri)} > {args.plan_priority_out}")
            rc = subprocess.run(cmd_pri, stdout=f).returncode
        if rc != 0:
            return rc

    if not args.skip_forum_import:
        cmd = [
            sys.executable,
            "scripts/build_market_db.py",
            "--db",
            args.db,
            "import-forum-dir",
            "--path",
            args.forum_pages_dir,
            "--pattern",
            args.pattern,
            "--forum-id",
            str(args.forum_id),
            "--market-key",
            args.market_key,
        ]
        if args.max_fg is not None:
            cmd += ["--max-fg", str(args.max_fg)]
        if args.min_fg is not None:
            cmd += ["--min-fg", str(args.min_fg)]
        if args.recursive:
            cmd.append("--recursive")
        if args.skip_zero_replies:
            cmd.append("--skip-zero-replies")
        if run_cmd(cmd, env=env, quiet=args.quiet) != 0:
            return 1

    if not args.skip_candidates:
        cmd = [
            sys.executable,
            "scripts/build_market_db.py",
            "--db",
            args.db,
            "dump-topic-candidates",
            "--market-key",
            args.market_key,
            "--forum-id",
            str(args.forum_id),
            "--limit",
            str(args.candidate_limit),
            "--export-urls",
            args.candidate_urls_out,
        ]
        if args.max_fg is not None:
            cmd += ["--max-fg", str(args.max_fg)]
        if args.min_fg is not None:
            cmd += ["--min-fg", str(args.min_fg)]
        if args.skip_zero_replies:
            cmd.append("--skip-zero-replies")
        if args.candidate_prefer_recent:
            cmd.append("--prefer-recent")
        if args.candidate_include_terms:
            cmd += ["--include-terms", args.candidate_include_terms]
        if args.candidate_exclude_terms:
            cmd += ["--exclude-terms", args.candidate_exclude_terms]
        if args.candidate_skip_liquid_singletons:
            cmd.append("--skip-liquid-singletons")
            cmd += ["--singleton-recent-hours", str(args.candidate_singleton_recent_hours)]
            cmd += ["--singleton-min-recent-observations", str(args.candidate_singleton_min_recent_observations)]
        if run_cmd(cmd, env=env, quiet=args.quiet) != 0:
            return 1

    if not args.skip_topic_import:
        cmd = [
            sys.executable,
            "scripts/build_market_db.py",
            "--db",
            args.db,
            "import-topic-dir",
            "--path",
            args.topic_pages_dir,
            "--pattern",
            args.pattern,
            "--forum-id",
            str(args.forum_id),
            "--market-key",
            args.market_key,
        ]
        if args.max_fg is not None:
            cmd += ["--max-fg", str(args.max_fg)]
        if args.min_fg is not None:
            cmd += ["--min-fg", str(args.min_fg)]
        if args.recursive:
            cmd.append("--recursive")
        if args.skip_bump_only_topic:
            cmd.append("--skip-bump-only-topic")
        if run_cmd(cmd, env=env, quiet=args.quiet) != 0:
            return 1

    if not args.skip_top:
        cmd = [
            sys.executable,
            "scripts/build_market_db.py",
            "--db",
            args.db,
            "dump-top",
            "--market-key",
            args.market_key,
            "--limit",
            str(args.top_limit),
        ]
        if run_cmd(cmd, env=env, quiet=args.quiet) != 0:
            return 1

    print("\nPipeline complete.")
    print(f"DB: {args.db}")
    print(f"Topic candidates URL list: {args.candidate_urls_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
