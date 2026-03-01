#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_ocr_columns(conn: sqlite3.Connection) -> None:
    for sql in (
        "ALTER TABLE image_market_queue ADD COLUMN ocr_engine TEXT",
        "ALTER TABLE image_market_queue ADD COLUMN ocr_confidence REAL",
        "ALTER TABLE image_market_queue ADD COLUMN ocr_item_name TEXT",
        "ALTER TABLE image_market_queue ADD COLUMN ocr_variant_hint TEXT",
        "ALTER TABLE image_market_queue ADD COLUMN ocr_raw_text TEXT",
    ):
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _load_ocr_parser(engine: str, confidence_threshold: float):
    from d2lut.overlay.ocr_parser import OCRTooltipParser

    return OCRTooltipParser(engine=engine, confidence_threshold=confidence_threshold)


def _ocr_full_image(parser, image_path: Path):
    from PIL import Image
    from d2lut.overlay.ocr_parser import TooltipCoords

    data = image_path.read_bytes()
    with Image.open(image_path) as im:
        w, h = im.size
    coords = TooltipCoords(x=0, y=0, width=w, height=h)
    return parser.parse_tooltip(data, coords)


def _ocr_fold(s: str) -> str:
    s = (s or "").lower()
    trans = str.maketrans({
        "@": "o",
        "®": "o",
        "0": "o",
        "1": "l",
        "|": "l",
        "5": "s",
        "$": "s",
    })
    s = s.translate(trans)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _heuristic_variant_from_ocr_text(item_name: str | None, raw_text: str | None) -> str | None:
    text = " ".join([item_name or "", raw_text or ""]).strip()
    folded = _ocr_fold(text)
    if not folded:
        return None

    # Hellfire Torch screenshots often OCR as "LARGE CHARM ... Keep in inventory ... UNIDENTIFIED"
    if (
        ("large charm" in folded or "large char" in folded)
        and ("keep in inventory" in folded or "keep inventory" in folded)
        and "unidentified" in folded
    ):
        return "unique:hellfire_torch"

    # CTA OCR often misses exact phrase but includes battle command/orders/cry trio.
    if "battle command" in folded and "battle order" in folded:
        return "runeword:call_to_arms"
    if "call" in folded and "arms" in folded and "battle" in folded:
        return "runeword:call_to_arms"

    return None


def main() -> int:
    p = argparse.ArgumentParser(description="OCR downloaded rows from image_market_queue")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--status", default="downloaded", help="Queue status to process (default: downloaded)")
    p.add_argument("--limit", type=int, default=50, help="Max queue rows to OCR")
    p.add_argument("--engine", default="pytesseract", choices=["pytesseract", "easyocr"], help="OCR engine")
    p.add_argument("--confidence-threshold", type=float, default=0.25, help="OCR parser confidence threshold")
    p.add_argument("--dry-run", action="store_true", help="Run OCR but do not write queue updates")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    try:
        parser = _load_ocr_parser(args.engine, args.confidence_threshold)
    except Exception as e:  # ImportError/runtime OCR init errors
        print(f"ERROR: failed to initialize OCR parser engine={args.engine}: {e}")
        return 3

    # Import lazily so script can still be inspected without src path at parse time.
    from d2lut.normalize.d2jsp_market import normalize_item_hint
    from d2lut.normalize.modifier_lexicon import infer_variant_from_noisy_ocr

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_ocr_columns(conn)
        rows = conn.execute(
            """
            SELECT id, thread_id, post_id, image_url, local_image_path, observed_variant_hint
            FROM image_market_queue
            WHERE market_key = ? AND status = ?
            ORDER BY max_price_fg DESC, id ASC
            LIMIT ?
            """,
            (args.market_key, args.status, args.limit),
        ).fetchall()
        if not rows:
            print("no_queue_rows")
            return 0

        scanned = 0
        parsed_ok = 0
        low_conf = 0
        failed = 0
        samples: list[str] = []

        for r in rows:
            scanned += 1
            row_id = int(r["id"])
            image_path = Path(str(r["local_image_path"] or ""))
            if not image_path.exists():
                failed += 1
                if not args.dry_run:
                    conn.execute(
                        "UPDATE image_market_queue SET status='failed', note=?, updated_at=? WHERE id=?",
                        (f"missing local_image_path: {image_path}", utc_now_iso(), row_id),
                    )
                continue

            try:
                parsed = _ocr_full_image(parser, image_path)
                raw_text = (parsed.raw_text or "").strip()
                item_name = (parsed.item_name or "").strip() or None
                conf = float(parsed.confidence or 0.0)
                # Try item-name first; fallback to whole text.
                hint = None
                if item_name:
                    hint = normalize_item_hint(item_name)
                if hint is None and raw_text:
                    hint = normalize_item_hint(raw_text[:300])
                variant_hint = hint[1] if hint else None
                if variant_hint is None:
                    variant_hint = _heuristic_variant_from_ocr_text(item_name, raw_text)
                noisy_variant_hint = infer_variant_from_noisy_ocr(item_name, raw_text)
                if variant_hint is None:
                    variant_hint = noisy_variant_hint
                else:
                    # Allow noisy OCR heuristics to refine coarse generic hints (e.g. generic torch -> class torch).
                    if (
                        noisy_variant_hint
                        and variant_hint == "unique:hellfire_torch"
                        and noisy_variant_hint.startswith("unique:hellfire_torch:")
                    ):
                        variant_hint = noisy_variant_hint
                if variant_hint is None:
                    observed_hint = str(r["observed_variant_hint"] or "").strip()
                    # Conservative fallback only for image-only/unidentified OCR rows.
                    folded = _ocr_fold(" ".join([item_name or "", raw_text or ""]))
                    weak_ocr = (
                        not folded
                        or "unidentified" in folded
                        or ("left click" in folded and len(folded) < 80)
                    )
                    if weak_ocr and observed_hint:
                        variant_hint = observed_hint

                if conf < args.confidence_threshold:
                    low_conf += 1
                else:
                    parsed_ok += 1

                if len(samples) < 20:
                    samples.append(
                        f"id={row_id} conf={conf:.2f} item={item_name!r} variant={variant_hint or '-'} text={raw_text[:120]!r}"
                    )

                if args.dry_run:
                    continue

                now = utc_now_iso()
                status = "ocr_parsed" if raw_text else "failed"
                note = parsed.error[:500] if parsed.error else None
                conn.execute(
                    """
                    UPDATE image_market_queue
                    SET status = ?,
                        note = ?,
                        ocr_engine = ?,
                        ocr_confidence = ?,
                        ocr_item_name = ?,
                        ocr_variant_hint = ?,
                        ocr_raw_text = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        note,
                        args.engine,
                        conf,
                        item_name,
                        variant_hint,
                        raw_text[:5000] if raw_text else None,
                        now,
                        row_id,
                    ),
                )
            except Exception as e:
                failed += 1
                if len(samples) < 20:
                    samples.append(f"id={row_id} ERROR {e}")
                if not args.dry_run:
                    conn.execute(
                        "UPDATE image_market_queue SET status='failed', note=?, updated_at=? WHERE id=?",
                        (str(e)[:500], utc_now_iso(), row_id),
                    )

        if not args.dry_run:
            conn.commit()

        print(
            f"scanned={scanned} parsed_ok={parsed_ok} low_conf={low_conf} failed={failed} "
            f"engine={args.engine} status_in={args.status}"
        )
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM image_market_queue WHERE market_key=? GROUP BY status ORDER BY n DESC",
            (args.market_key,),
        ):
            print(f"queue_status {row['status']}={row['n']}")
        if samples:
            print("# sample")
            for s in samples:
                print(s)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
