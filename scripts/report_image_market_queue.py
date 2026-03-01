#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="Report image_market_queue backlog and OCR recovery progress")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--min-fg", type=float, default=300.0, help="High-value threshold for reporting")
    p.add_argument("--top", type=int, default=15, help="Top rows/examples to print")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM image_market_queue WHERE market_key=?",
            (args.market_key,),
        ).fetchone()[0]
        high = conn.execute(
            "SELECT COUNT(*) FROM image_market_queue WHERE market_key=? AND COALESCE(max_price_fg,0) >= ?",
            (args.market_key, args.min_fg),
        ).fetchone()[0]
        parsed = conn.execute(
            "SELECT COUNT(*) FROM image_market_queue WHERE market_key=? AND status='ocr_parsed'",
            (args.market_key,),
        ).fetchone()[0]
        parsed_with_hint = conn.execute(
            """
            SELECT COUNT(*)
            FROM image_market_queue
            WHERE market_key=? AND status='ocr_parsed' AND COALESCE(ocr_variant_hint,'') <> ''
            """,
            (args.market_key,),
        ).fetchone()[0]
        cand_total = 0
        cand_high = 0
        cand_accepted = 0
        cand_accepted_high = 0
        promoted_total = 0
        promoted_high = 0
        try:
            cand_total = conn.execute(
                "SELECT COUNT(*) FROM image_market_ocr_candidates WHERE market_key=?",
                (args.market_key,),
            ).fetchone()[0]
            cand_high = conn.execute(
                "SELECT COUNT(*) FROM image_market_ocr_candidates WHERE market_key=? AND COALESCE(price_fg,0) >= ?",
                (args.market_key, args.min_fg),
            ).fetchone()[0]
            cand_accepted = conn.execute(
                "SELECT COUNT(*) FROM image_market_ocr_candidates WHERE market_key=? AND status='accepted'",
                (args.market_key,),
            ).fetchone()[0]
            cand_accepted_high = conn.execute(
                "SELECT COUNT(*) FROM image_market_ocr_candidates WHERE market_key=? AND status='accepted' AND COALESCE(price_fg,0) >= ?",
                (args.market_key, args.min_fg),
            ).fetchone()[0]
        except sqlite3.OperationalError:
            pass
        try:
            promoted_total = conn.execute(
                """
                SELECT COUNT(*) FROM observed_prices
                WHERE market_key=? AND source LIKE 'image_ocr_candidate:%'
                """,
                (args.market_key,),
            ).fetchone()[0]
            promoted_high = conn.execute(
                """
                SELECT COUNT(*) FROM observed_prices
                WHERE market_key=? AND source LIKE 'image_ocr_candidate:%' AND COALESCE(price_fg,0) >= ?
                """,
                (args.market_key, args.min_fg),
            ).fetchone()[0]
        except sqlite3.OperationalError:
            pass
        print(
            f"market={args.market_key} queue_rows={total} high_value_rows={high} "
            f"ocr_parsed={parsed} ocr_variant_hints={parsed_with_hint} "
            f"staging_candidates={cand_total} staging_candidates_high={cand_high} "
            f"accepted_candidates={cand_accepted} accepted_candidates_high={cand_accepted_high} "
            f"resolved_by_image_obs={promoted_total} resolved_by_image_obs_high={promoted_high}"
        )

        print("# by status")
        for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM image_market_queue WHERE market_key=? GROUP BY status ORDER BY n DESC, status ASC",
            (args.market_key,),
        ):
            print(f"{r['status']}: {r['n']}")

        print("# high-value OCR parsed examples")
        for r in conn.execute(
            """
            SELECT id, thread_id, post_id, max_price_fg, ocr_confidence, ocr_item_name, ocr_variant_hint, image_url
            FROM image_market_queue
            WHERE market_key=? AND status='ocr_parsed' AND COALESCE(max_price_fg,0) >= ?
            ORDER BY max_price_fg DESC, id ASC
            LIMIT ?
            """,
            (args.market_key, args.min_fg, args.top),
        ):
            print(
                f"id={r['id']} t={r['thread_id']} p={r['post_id']} fg={float(r['max_price_fg'] or 0):g} "
                f"conf={float(r['ocr_confidence'] or 0):.2f} variant={r['ocr_variant_hint'] or '-'} item={repr((r['ocr_item_name'] or '')[:80])}"
            )

        print("# pending/failed high-value backlog")
        for r in conn.execute(
            """
            SELECT id, status, thread_id, post_id, max_price_fg, image_url, COALESCE(note,'') AS note
            FROM image_market_queue
            WHERE market_key=? AND status IN ('pending','downloaded','failed','manual_review')
              AND COALESCE(max_price_fg,0) >= ?
            ORDER BY max_price_fg DESC, id ASC
            LIMIT ?
            """,
            (args.market_key, args.min_fg, args.top),
        ):
            note = str(r["note"] or "")[:100]
            print(
                f"id={r['id']} status={r['status']} t={r['thread_id']} p={r['post_id']} fg={float(r['max_price_fg'] or 0):g} "
                f"url={r['image_url']} note={note!r}"
            )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
