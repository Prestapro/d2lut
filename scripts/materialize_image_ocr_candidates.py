#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS image_market_ocr_candidates (
          id INTEGER PRIMARY KEY,
          queue_id INTEGER NOT NULL UNIQUE,
          market_key TEXT NOT NULL,
          forum_id INTEGER NOT NULL,
          thread_id INTEGER NOT NULL,
          post_id INTEGER NOT NULL DEFAULT -1,
          source_url TEXT,
          image_url TEXT NOT NULL,
          local_image_path TEXT,
          variant_key TEXT NOT NULL,
          canonical_item_id TEXT NOT NULL,
          price_fg REAL NOT NULL,
          signal_kind TEXT NOT NULL DEFAULT 'ask',
          confidence REAL NOT NULL,
          ocr_confidence REAL,
          ocr_item_name TEXT,
          ocr_raw_text TEXT,
          status TEXT NOT NULL DEFAULT 'candidate', -- candidate|accepted|rejected
          note TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_img_ocr_cand_status ON image_market_ocr_candidates(status, market_key);
        CREATE INDEX IF NOT EXISTS idx_img_ocr_cand_variant ON image_market_ocr_candidates(variant_key, market_key);
        """
    )
    conn.commit()


def _canonical_from_variant(variant_key: str) -> str:
    if not variant_key:
        return ""
    # Most variants are prefixed `kind:name...`; canonical is typically the first 2 segments at most.
    parts = variant_key.split(":")
    if len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    return variant_key


def main() -> int:
    p = argparse.ArgumentParser(description="Materialize OCR-parsed image queue rows into staging candidates")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--min-fg", type=float, default=300.0, help="Only materialize queue rows with max_price_fg >= threshold")
    p.add_argument("--min-ocr-confidence", type=float, default=0.5, help="Minimum OCR confidence")
    p.add_argument("--limit", type=int, default=100, help="Max queue rows to process")
    p.add_argument("--dry-run", action="store_true", help="Preview without inserting/updating")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT id, market_key, forum_id, thread_id, post_id, source_url, image_url, local_image_path,
                   max_price_fg, ocr_confidence, ocr_item_name, ocr_variant_hint, ocr_raw_text, status
            FROM image_market_queue
            WHERE market_key = ?
              AND status = 'ocr_parsed'
              AND COALESCE(max_price_fg, 0) >= ?
              AND COALESCE(ocr_confidence, 0) >= ?
              AND COALESCE(ocr_variant_hint, '') <> ''
            ORDER BY max_price_fg DESC, id ASC
            LIMIT ?
            """,
            (args.market_key, args.min_fg, args.min_ocr_confidence, args.limit),
        ).fetchall()

        inserted = 0
        updated = 0
        samples: list[str] = []
        for r in rows:
            queue_id = int(r["id"])
            variant_key = str(r["ocr_variant_hint"] or "")
            canonical_item_id = _canonical_from_variant(variant_key)
            conf = float(r["ocr_confidence"] or 0)
            # Conservative confidence for market staging (OCR confidence attenuated).
            market_conf = max(0.15, min(0.6, conf * 0.6))
            now = utc_now_iso()
            if len(samples) < 20:
                samples.append(
                    f"queue_id={queue_id} fg={float(r['max_price_fg'] or 0):g} conf={conf:.2f} "
                    f"variant={variant_key} item={canonical_item_id}"
                )
            if args.dry_run:
                continue
            cur = conn.execute(
                """
                INSERT INTO image_market_ocr_candidates(
                  queue_id, market_key, forum_id, thread_id, post_id, source_url, image_url, local_image_path,
                  variant_key, canonical_item_id, price_fg, signal_kind, confidence, ocr_confidence,
                  ocr_item_name, ocr_raw_text, status, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ask', ?, ?, ?, ?, 'candidate', ?, ?, ?)
                ON CONFLICT(queue_id) DO UPDATE SET
                  variant_key = excluded.variant_key,
                  canonical_item_id = excluded.canonical_item_id,
                  price_fg = excluded.price_fg,
                  confidence = excluded.confidence,
                  ocr_confidence = excluded.ocr_confidence,
                  ocr_item_name = excluded.ocr_item_name,
                  ocr_raw_text = excluded.ocr_raw_text,
                  source_url = COALESCE(image_market_ocr_candidates.source_url, excluded.source_url),
                  local_image_path = COALESCE(image_market_ocr_candidates.local_image_path, excluded.local_image_path),
                  updated_at = excluded.updated_at
                """,
                (
                    queue_id,
                    args.market_key,
                    int(r["forum_id"]),
                    int(r["thread_id"]),
                    int(r["post_id"]),
                    str(r["source_url"] or ""),
                    str(r["image_url"] or ""),
                    str(r["local_image_path"] or ""),
                    variant_key,
                    canonical_item_id,
                    float(r["max_price_fg"] or 0),
                    market_conf,
                    conf,
                    str(r["ocr_item_name"] or "")[:500],
                    str(r["ocr_raw_text"] or "")[:5000],
                    "auto-materialized from image_market_queue",
                    now,
                    now,
                ),
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1

        if not args.dry_run:
            conn.commit()

        print(
            f"eligible_rows={len(rows)} inserted={inserted} updated={updated} "
            f"min_fg={args.min_fg:g} min_ocr_conf={args.min_ocr_confidence:g}"
        )
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM image_market_ocr_candidates WHERE market_key=? GROUP BY status ORDER BY n DESC",
            (args.market_key,),
        ):
            print(f"candidate_status {row['status']}={row['n']}")
        if samples:
            print("# sample")
            for s in samples:
                print(s)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
