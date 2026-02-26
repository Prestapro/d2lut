#!/usr/bin/env python3
"""CLI wrapper for the image recovery pipeline orchestrator.

Usage:
    PYTHONPATH=src python scripts/run_image_recovery_pipeline.py --db data/cache/d2lut.db
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure src is importable when run from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from d2lut.overlay.image_recovery_pipeline import run_image_recovery


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run the full image-only recovery pipeline (enqueue -> fetch -> OCR -> stage -> promote)"
    )
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--min-fg", type=float, default=300.0, help="High-value FG threshold")
    p.add_argument("--topic-dir", default="data/raw/d2jsp/topic_pages", help="Topic HTML directory")
    p.add_argument("--image-out-dir", default="data/raw/d2jsp/topic_images", help="Image download directory")
    p.add_argument("--quiet", action="store_true", help="Suppress info logging")
    args = p.parse_args()

    level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    result = run_image_recovery(
        args.db,
        min_fg=args.min_fg,
        quiet=args.quiet,
        market_key=args.market_key,
        topic_dir=args.topic_dir,
        image_out_dir=args.image_out_dir,
    )

    if result.errors:
        print(f"Image recovery finished with {len(result.errors)} error(s):")
        for e in result.errors:
            print(f"  - {e}")
        return 1

    print("Image recovery pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
