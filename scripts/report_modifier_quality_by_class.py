#!/usr/bin/env python3
"""Precision/recall diagnostics for modifier matching broken down by item class.

Reports matching quality on the image-OCR queue grouped by item class
(runeword, torch, anni, base, jewel, charm, unique, set, generic).

Usage:
    PYTHONPATH=src python scripts/report_modifier_quality_by_class.py [--db data/cache/d2lut.db]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path


def _norm_variant(v: str | None) -> str:
    return (v or "").strip().lower()


def _classify_variant(variant: str) -> str:
    """Map a variant key to a broad item class for diagnostics."""
    v = variant.lower()
    if v.startswith("runeword:"):
        return "runeword"
    if "hellfire_torch" in v:
        return "torch"
    if "annihilus" in v:
        return "anni"
    if v.startswith("base:"):
        return "base"
    if v.startswith("jewel:") or v == "jewel":
        return "jewel"
    if "charm" in v:
        return "charm"
    if v.startswith("unique:"):
        return "unique"
    if v.startswith("set:"):
        return "set"
    if v.startswith("rune:"):
        return "rune"
    return "generic"


def main() -> int:
    p = argparse.ArgumentParser(description="Per-class modifier matching quality on image-OCR queue")
    p.add_argument("--db", default="data/cache/d2lut.db")
    p.add_argument("--market-key", default="d2r_sc_ladder")
    p.add_argument("--min-fg", type=float, default=0.0)
    p.add_argument("--write-json", default=None)
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                """
                SELECT id, thread_id, post_id, max_price_fg, status,
                       observed_variant_hint, ocr_variant_hint, ocr_confidence, ocr_item_name
                FROM image_market_queue
                WHERE market_key = ?
                  AND coalesce(max_price_fg, 0) >= ?
                  AND status = 'ocr_parsed'
                ORDER BY coalesce(max_price_fg, 0) DESC, id ASC
                """,
                (args.market_key, args.min_fg),
            ).fetchall()
        except sqlite3.OperationalError:
            print("WARN: image_market_queue table not found; reporting empty results")
            rows = []

        # Per-class accumulators
        class_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "comparable": 0, "exact": 0, "mismatch": 0})
        mismatches_by_class: dict[str, list[dict]] = defaultdict(list)

        for r in rows:
            truth = _norm_variant(r["observed_variant_hint"])
            pred = _norm_variant(r["ocr_variant_hint"])

            # Classify by truth first, fall back to pred
            item_class = _classify_variant(truth) if truth else (_classify_variant(pred) if pred else "generic")
            class_stats[item_class]["total"] += 1

            if not truth or not pred:
                continue
            class_stats[item_class]["comparable"] += 1
            if pred == truth:
                class_stats[item_class]["exact"] += 1
            else:
                class_stats[item_class]["mismatch"] += 1
                mismatches_by_class[item_class].append({
                    "id": int(r["id"]),
                    "fg": float(r["max_price_fg"] or 0),
                    "truth": truth,
                    "pred": pred,
                })

        # Build per-class report
        by_class = {}
        for cls in sorted(class_stats.keys()):
            s = class_stats[cls]
            comp = s["comparable"]
            precision = (s["exact"] / comp) if comp else 0.0
            by_class[cls] = {
                "total_rows": s["total"],
                "comparable_rows": comp,
                "exact_match": s["exact"],
                "mismatch": s["mismatch"],
                "precision": round(precision, 4),
                "top_mismatches": sorted(mismatches_by_class.get(cls, []), key=lambda d: -d["fg"])[:5],
            }

        # Aggregate
        total = sum(s["total"] for s in class_stats.values())
        comparable = sum(s["comparable"] for s in class_stats.values())
        exact = sum(s["exact"] for s in class_stats.values())
        overall_precision = (exact / comparable) if comparable else 0.0

        report = {
            "db": str(db_path),
            "market_key": args.market_key,
            "min_fg": args.min_fg,
            "total_rows": total,
            "comparable_rows": comparable,
            "exact_match_total": exact,
            "overall_precision": round(overall_precision, 4),
            "by_class": by_class,
        }

        print(json.dumps(report, indent=2, ensure_ascii=True))
        if args.write_json:
            out = Path(args.write_json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
            print(f"\nWrote {out}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
