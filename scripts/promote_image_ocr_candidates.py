#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    p = argparse.ArgumentParser(
        description="Promote image OCR staging candidates into observed_prices (marks candidates accepted)."
    )
    p.add_argument("--db", default="data/cache/d2lut.db")
    p.add_argument("--market-key", default="d2r_sc_ladder")
    p.add_argument("--status", default="candidate", help="Candidate status to promote (default: candidate)")
    p.add_argument("--min-fg", type=float, default=300.0)
    p.add_argument("--min-confidence", type=float, default=0.2, help="Minimum staging confidence for promotion")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Ensure idempotence marker table.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS image_market_ocr_promotions (
              id INTEGER PRIMARY KEY,
              candidate_id INTEGER NOT NULL UNIQUE,
              queue_id INTEGER NOT NULL,
              observed_price_id INTEGER,
              market_key TEXT NOT NULL,
              promoted_at TEXT NOT NULL,
              note TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_img_ocr_promotions_market ON image_market_ocr_promotions(market_key, promoted_at)"
        )
        conn.commit()

        rows = conn.execute(
            """
            SELECT c.*,
                   t.thread_category_id,
                   t.thread_trade_type
            FROM image_market_ocr_candidates c
            LEFT JOIN threads t
              ON t.source='d2jsp'
             AND t.thread_id = c.thread_id
            WHERE c.market_key = ?
              AND c.status = ?
              AND c.price_fg >= ?
              AND COALESCE(c.confidence, 0) >= ?
              AND COALESCE(c.variant_key, '') <> ''
              AND NOT EXISTS (
                SELECT 1 FROM image_market_ocr_promotions p
                WHERE p.candidate_id = c.id
              )
            ORDER BY c.price_fg DESC, c.id ASC
            LIMIT ?
            """,
            (args.market_key, args.status, args.min_fg, args.min_confidence, args.limit),
        ).fetchall()

        promoted = 0
        skipped_dupe = 0
        samples: list[str] = []
        now = utc_now_iso()

        for r in rows:
            candidate_id = int(r["id"])
            queue_id = int(r["queue_id"])
            source_url = str(r["source_url"] or "")
            variant_key = str(r["variant_key"] or "")
            canonical_item_id = str(r["canonical_item_id"] or "")
            raw_text = str(r["ocr_raw_text"] or "")
            ocr_item_name = str(r["ocr_item_name"] or "")
            raw_excerpt = f"[image-ocr] {ocr_item_name}\n{raw_text}".strip()[:5000]
            source = f"image_ocr_candidate:{candidate_id}"

            # Soft duplicate guard: if same market/thread/post/variant/price already inserted from image_ocr, skip.
            dupe = conn.execute(
                """
                SELECT id FROM observed_prices
                WHERE source = ?
                   OR (
                     market_key = ?
                     AND thread_id = ?
                     AND COALESCE(post_id,-1) = COALESCE(?, -1)
                     AND variant_key = ?
                     AND ABS(price_fg - ?) < 1e-9
                     AND source LIKE 'image_ocr_candidate:%'
                   )
                LIMIT 1
                """,
                (
                    source,
                    args.market_key,
                    int(r["thread_id"]),
                    int(r["post_id"]),
                    variant_key,
                    float(r["price_fg"]),
                ),
            ).fetchone()
            if dupe:
                skipped_dupe += 1
                if not args.dry_run:
                    conn.execute(
                        "UPDATE image_market_ocr_candidates SET status='accepted', note=?, updated_at=? WHERE id=?",
                        ("already promoted (duplicate detected)", now, candidate_id),
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO image_market_ocr_promotions(candidate_id, queue_id, observed_price_id, market_key, promoted_at, note)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (candidate_id, queue_id, int(dupe["id"]), args.market_key, now, "duplicate existing image_ocr row"),
                    )
                continue

            if len(samples) < 20:
                samples.append(
                    f"cand={candidate_id} q={queue_id} fg={float(r['price_fg']):g} "
                    f"variant={variant_key} conf={float(r['confidence'] or 0):.2f}"
                )

            if args.dry_run:
                promoted += 1
                continue

            cur = conn.execute(
                """
                INSERT INTO observed_prices(
                  source, market_key, forum_id, thread_id, post_id, source_kind, signal_kind,
                  thread_category_id, thread_trade_type, canonical_item_id, variant_key, price_fg,
                  confidence, observed_at, source_url, raw_excerpt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    args.market_key,
                    int(r["forum_id"]),
                    int(r["thread_id"]),
                    int(r["post_id"]),
                    "manual",  # image-derived backfill
                    str(r["signal_kind"] or "ask"),
                    r["thread_category_id"],
                    r["thread_trade_type"],
                    canonical_item_id or variant_key,
                    variant_key,
                    float(r["price_fg"]),
                    float(r["confidence"] or 0.0),
                    now,
                    source_url,
                    raw_excerpt,
                ),
            )
            observed_id = int(cur.lastrowid)
            conn.execute(
                "UPDATE image_market_ocr_candidates SET status='accepted', note=?, updated_at=? WHERE id=?",
                ("promoted to observed_prices", now, candidate_id),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO image_market_ocr_promotions(candidate_id, queue_id, observed_price_id, market_key, promoted_at, note)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (candidate_id, queue_id, observed_id, args.market_key, now, "promoted"),
            )
            promoted += 1

        if not args.dry_run:
            conn.commit()

        print(
            f"eligible={len(rows)} promoted={promoted} skipped_duplicate={skipped_dupe} "
            f"status_in={args.status} min_fg={args.min_fg:g} min_conf={args.min_confidence:g}"
        )
        for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM image_market_ocr_candidates WHERE market_key=? GROUP BY status ORDER BY n DESC, status",
            (args.market_key,),
        ):
            print(f"candidate_status {r['status']}={r['n']}")
        pstats = conn.execute(
            "SELECT COUNT(*) AS n FROM image_market_ocr_promotions WHERE market_key=?",
            (args.market_key,),
        ).fetchone()
        print(f"promotions_total={int(pstats['n'])}")
        if samples:
            print("# sample")
            for s in samples:
                print(s)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
