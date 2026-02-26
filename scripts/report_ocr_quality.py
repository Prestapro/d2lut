#!/usr/bin/env python3
"""OCR quality dashboard — precision/recall by item class.

Reads the same SQLite DB as export_property_price_table_html.py and computes
precision and recall for property extraction grouped by item class, comparing
extracted Property_Signature against variant_key (when available) as ground
truth.

Item classes: runeword, torch, anni, base, jewel, charm, circlet, other

Usage:
    python scripts/report_ocr_quality.py --db data/cache/d2lut.db
    python scripts/report_ocr_quality.py --min-fg 200 --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# Allow standalone execution
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_property_price_table_html import extract_props, props_signature
from d2lut.normalize.modifier_lexicon import infer_item_category_from_variant

# ---------------------------------------------------------------------------
# Category → item class mapping
# ---------------------------------------------------------------------------

_CATEGORY_TO_CLASS: dict[str, str] = {
    "torch": "torch",
    "anni": "anni",
    "runeword_item": "runeword",
    "base_armor": "base",
    "base_weapon": "base",
    "jewel": "jewel",
    "charm": "charm",
    "circlet": "circlet",
}


def category_to_item_class(category: str) -> str:
    """Map an inferred category string to one of the 8 item classes."""
    return _CATEGORY_TO_CLASS.get(category, "other")


# ---------------------------------------------------------------------------
# Per-row evaluation
# ---------------------------------------------------------------------------

def evaluate_row(row: dict) -> dict | None:
    """Evaluate a single row for precision/recall.

    Returns a dict with keys: item_class, has_variant, has_sig, tp, fp, fn,
    variant_key, signature, excerpt.  Returns None if the row has no variant_key
    AND no signature (not useful for precision/recall).
    """
    variant_key = (row.get("variant_key") or "").strip()
    excerpt = (row.get("raw_excerpt") or "").strip()

    if not excerpt:
        return None

    props = extract_props(excerpt, row.get("variant_key"))
    sig = props_signature(props)

    has_variant = bool(variant_key)
    has_sig = sig is not None

    # We need at least one of variant_key or sig to compute metrics
    if not has_variant and not has_sig:
        return None

    # Determine item class from variant_key (ground truth source)
    if has_variant:
        category = infer_item_category_from_variant(variant_key)
        item_class = category_to_item_class(category)
    else:
        # No ground truth — we can only count FP if sig exists
        item_class = "other"

    # TP: has variant_key AND produces a property signature
    # FP: produces a property signature but has no variant_key
    # FN: has variant_key but fails to produce a property signature
    tp = 1 if has_variant and has_sig else 0
    fp = 1 if has_sig and not has_variant else 0
    fn = 1 if has_variant and not has_sig else 0

    is_mismatch = (fp == 1) or (fn == 1)

    return {
        "item_class": item_class,
        "has_variant": has_variant,
        "has_sig": has_sig,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "is_mismatch": is_mismatch,
        "variant_key": variant_key,
        "signature": sig or "",
        "excerpt": excerpt[:200],
        "price_fg": float(row.get("price_fg", 0)),
    }


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------

def compute_class_metrics(
    evaluations: list[dict],
) -> list[dict]:
    """Aggregate TP/FP/FN and compute precision/recall per item class.

    Returns a list of dicts sorted by class name, each with:
      item_class, tp, fp, fn, precision, recall, mismatch_samples
    """
    by_class: dict[str, dict] = defaultdict(lambda: {
        "tp": 0, "fp": 0, "fn": 0, "mismatches": [],
    })

    for ev in evaluations:
        cls = ev["item_class"]
        bucket = by_class[cls]
        bucket["tp"] += ev["tp"]
        bucket["fp"] += ev["fp"]
        bucket["fn"] += ev["fn"]
        if ev["is_mismatch"] and len(bucket["mismatches"]) < 3:
            bucket["mismatches"].append({
                "variant_key": ev["variant_key"],
                "signature": ev["signature"],
                "excerpt": ev["excerpt"],
                "price_fg": ev["price_fg"],
            })

    results: list[dict] = []
    for cls in sorted(by_class):
        b = by_class[cls]
        tp, fp, fn = b["tp"], b["fp"], b["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        results.append({
            "item_class": cls,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "mismatch_samples": b["mismatches"],
        })

    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _print_human(
    metrics: list[dict],
    *,
    market_key: str,
    min_fg: float,
    scanned: int,
    evaluated: int,
) -> None:
    print("=== OCR Quality Dashboard ===")
    print(f"Market: {market_key} | Min FG: {min_fg} | Scanned: {scanned} | Evaluated: {evaluated}")
    print()

    if not metrics:
        print("No rows evaluated.")
        return

    # Summary table
    print(f"{'Class':<12s} {'TP':>5s} {'FP':>5s} {'FN':>5s} {'Prec':>7s} {'Recall':>7s}")
    print("-" * 50)
    total_tp = total_fp = total_fn = 0
    for m in metrics:
        print(
            f"{m['item_class']:<12s} "
            f"{m['tp']:>5d} {m['fp']:>5d} {m['fn']:>5d} "
            f"{m['precision']:>6.1%} {m['recall']:>6.1%}"
        )
        total_tp += m["tp"]
        total_fp += m["fp"]
        total_fn += m["fn"]

    total_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    total_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    print("-" * 50)
    print(
        f"{'TOTAL':<12s} "
        f"{total_tp:>5d} {total_fp:>5d} {total_fn:>5d} "
        f"{total_prec:>6.1%} {total_rec:>6.1%}"
    )
    print()

    # Mismatch samples
    for m in metrics:
        if not m["mismatch_samples"]:
            continue
        print(f"--- {m['item_class']} mismatches (up to 3) ---")
        for i, s in enumerate(m["mismatch_samples"], 1):
            label = "FN" if not s["signature"] else "FP"
            print(f"  {i}. [{label}] [{s['price_fg']:.0f}fg] variant={s['variant_key']}")
            if s["signature"]:
                print(f"     sig: {s['signature'][:80]}")
            if s["excerpt"]:
                print(f"     excerpt: {s['excerpt'][:120]}")
        print()


def _print_json(
    metrics: list[dict],
    *,
    market_key: str,
    min_fg: float,
    scanned: int,
    evaluated: int,
) -> None:
    total_tp = sum(m["tp"] for m in metrics)
    total_fp = sum(m["fp"] for m in metrics)
    total_fn = sum(m["fn"] for m in metrics)
    payload = {
        "market_key": market_key,
        "min_fg": min_fg,
        "observations_scanned": scanned,
        "observations_evaluated": evaluated,
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "total_precision": round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else 0.0,
        "total_recall": round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else 0.0,
        "by_class": metrics,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="OCR quality dashboard — precision/recall by item class")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--min-fg", type=float, default=100.0, help="Minimum FG threshold (default: 100)")
    p.add_argument("--limit", type=int, default=5000, help="Max rows to scan (default: 5000)")
    p.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT source, forum_id, thread_id, source_url, signal_kind,
                   variant_key, price_fg, confidence,
                   COALESCE(raw_excerpt, '') AS raw_excerpt, observed_at
            FROM observed_prices
            WHERE market_key = ? AND price_fg >= ?
            ORDER BY price_fg DESC, id DESC
            LIMIT ?
            """,
            (args.market_key, args.min_fg, args.limit),
        ).fetchall()
    finally:
        conn.close()

    row_dicts = [dict(r) for r in rows]

    evaluations = []
    for rd in row_dicts:
        ev = evaluate_row(rd)
        if ev is not None:
            evaluations.append(ev)

    metrics = compute_class_metrics(evaluations)

    if args.json_output:
        _print_json(metrics, market_key=args.market_key, min_fg=args.min_fg,
                     scanned=len(rows), evaluated=len(evaluations))
    else:
        _print_human(metrics, market_key=args.market_key, min_fg=args.min_fg,
                      scanned=len(rows), evaluated=len(evaluations))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
