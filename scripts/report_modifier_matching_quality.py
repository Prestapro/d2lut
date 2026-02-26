#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def _norm_variant(v: str | None) -> str:
    return (v or "").strip().lower()


def main() -> int:
    p = argparse.ArgumentParser(
        description="Report modifier/item matching quality on image OCR queue using observed_variant_hint as weak ground truth"
    )
    p.add_argument("--db", default="data/cache/d2lut.db")
    p.add_argument("--market-key", default="d2r_sc_ladder")
    p.add_argument("--min-fg", type=float, default=300.0)
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--write-json")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, thread_id, post_id, max_price_fg, status, image_url,
                   observed_variant_hint, ocr_variant_hint, ocr_confidence, ocr_item_name
            FROM image_market_queue
            WHERE market_key = ?
              AND coalesce(max_price_fg, 0) >= ?
              AND status = 'ocr_parsed'
            ORDER BY coalesce(max_price_fg, 0) DESC, id ASC
            """,
            (args.market_key, args.min_fg),
        ).fetchall()

        total = len(rows)
        comparable = 0
        exact = 0
        missing_pred = 0
        missing_truth = 0
        mismatches: list[dict[str, object]] = []

        by_pred_prefix: dict[str, int] = {}
        by_truth_prefix: dict[str, int] = {}

        for r in rows:
            truth = _norm_variant(r["observed_variant_hint"])
            pred = _norm_variant(r["ocr_variant_hint"])
            if not truth:
                missing_truth += 1
            if not pred:
                missing_pred += 1
            if not truth or not pred:
                continue
            comparable += 1

            truth_prefix = truth.split(":", 1)[0]
            pred_prefix = pred.split(":", 1)[0]
            by_truth_prefix[truth_prefix] = by_truth_prefix.get(truth_prefix, 0) + 1
            by_pred_prefix[pred_prefix] = by_pred_prefix.get(pred_prefix, 0) + 1

            if pred == truth:
                exact += 1
            else:
                mismatches.append(
                    {
                        "id": int(r["id"]),
                        "thread_id": int(r["thread_id"] or 0),
                        "post_id": int(r["post_id"] or 0) if r["post_id"] is not None else None,
                        "fg": float(r["max_price_fg"] or 0.0),
                        "truth": truth,
                        "pred": pred,
                        "ocr_confidence": float(r["ocr_confidence"] or 0.0),
                        "ocr_item_name": (r["ocr_item_name"] or "")[:180],
                        "image_url": r["image_url"],
                    }
                )

        precision = (exact / comparable) if comparable else 0.0
        recall_vs_truth_rows = (exact / (total - missing_truth)) if (total - missing_truth) > 0 else 0.0
        pred_fill_rate = ((total - missing_pred) / total) if total else 0.0

        report = {
            "db": str(db_path),
            "market_key": args.market_key,
            "min_fg": args.min_fg,
            "queue_rows_evaluated": total,
            "comparable_rows": comparable,
            "missing_truth_rows": missing_truth,
            "missing_pred_rows": missing_pred,
            "pred_fill_rate": round(pred_fill_rate, 4),
            "exact_match_rows": exact,
            "exact_match_precision_vs_truth": round(precision, 4),
            "exact_match_recall_vs_truth_rows": round(recall_vs_truth_rows, 4),
            "pred_prefix_counts": dict(sorted(by_pred_prefix.items(), key=lambda kv: (-kv[1], kv[0]))),
            "truth_prefix_counts": dict(sorted(by_truth_prefix.items(), key=lambda kv: (-kv[1], kv[0]))),
            "top_mismatches": sorted(mismatches, key=lambda d: (-float(d["fg"]), int(d["id"])))[: args.top],
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
