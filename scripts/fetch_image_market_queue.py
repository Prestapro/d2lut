#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_ext_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        if path.endswith(ext):
            return ext
    return ".img"


def _safe_ext_from_content_type(content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if "png" in ct:
        return ".png"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    if "bmp" in ct:
        return ".bmp"
    return ".img"


def _extract_image_from_html(html_text: str, base_url: str) -> str | None:
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html_text, flags=re.IGNORECASE)
        if not m:
            continue
        src = (m.group(1) or "").strip()
        if not src:
            continue
        return urljoin(base_url, src)
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Download pending image_market_queue rows to local files")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--status", default="pending", help="Queue status to fetch (default: pending)")
    p.add_argument("--out-dir", default="data/raw/d2jsp/topic_images", help="Output image directory")
    p.add_argument("--limit", type=int, default=100, help="Max queue rows to fetch (default: 100)")
    p.add_argument("--timeout-sec", type=float, default=20.0, help="HTTP timeout in seconds")
    p.add_argument("--user-agent", default="Mozilla/5.0 (compatible; d2lut-image-fetch/0.1)", help="User-Agent")
    p.add_argument("--dry-run", action="store_true", help="Show rows without downloading")
    args = p.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"ERROR: DB not found: {db}")
        return 2
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, thread_id, post_id, image_url, source_url, local_image_path, status
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

        opener = urllib.request.build_opener()
        opener.addheaders = [("User-Agent", args.user_agent)]

        scanned = 0
        downloaded = 0
        skipped = 0
        failed = 0
        for r in rows:
            scanned += 1
            row_id = int(r["id"])
            tid = int(r["thread_id"])
            post_id = int(r["post_id"])
            image_url = str(r["image_url"] or "")
            pre_ext = _safe_ext_from_url(image_url)
            pre_path = out_dir / f"imgq_{row_id}_t{tid}_p{post_id}{pre_ext}"
            if pre_path.exists():
                skipped += 1
                if not args.dry_run:
                    conn.execute(
                        """
                        UPDATE image_market_queue
                        SET status = CASE WHEN status='pending' THEN 'downloaded' ELSE status END,
                            local_image_path = COALESCE(local_image_path, ?),
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (str(pre_path), utc_now_iso(), row_id),
                    )
                continue
            if args.dry_run:
                print(f"would_download id={row_id} t={tid} p={post_id} -> imgq_{row_id}_t{tid}_p{post_id}{pre_ext} {image_url}")
                continue
            try:
                final_image_url = image_url
                with opener.open(image_url, timeout=args.timeout_sec) as resp:
                    ct = str(resp.headers.get("Content-Type") or "")
                    data = resp.read()
                    if "html" in ct.lower() or data[:200].lstrip().lower().startswith(b"<!doctype html") or data[:100].lstrip().lower().startswith(b"<html"):
                        html_text = data.decode("utf-8", errors="ignore")
                        wrapped_image_url = _extract_image_from_html(html_text, image_url)
                        if not wrapped_image_url:
                            raise OSError("html wrapper without extractable image URL")
                        final_image_url = wrapped_image_url
                        with opener.open(wrapped_image_url, timeout=args.timeout_sec) as img_resp:
                            ct = str(img_resp.headers.get("Content-Type") or "")
                            data = img_resp.read()
                ext = _safe_ext_from_url(final_image_url)
                if ext == ".img":
                    ext = _safe_ext_from_content_type(ct)
                path = out_dir / f"imgq_{row_id}_t{tid}_p{post_id}{ext}"
                path.write_bytes(data)
                conn.execute(
                    """
                    UPDATE image_market_queue
                    SET status = 'downloaded',
                        local_image_path = ?,
                        note = CASE WHEN ? <> image_url THEN ? ELSE NULL END,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        str(path),
                        final_image_url,
                        f"resolved wrapper to {final_image_url}"[:500],
                        utc_now_iso(),
                        row_id,
                    ),
                )
                downloaded += 1
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                failed += 1
                conn.execute(
                    """
                    UPDATE image_market_queue
                    SET status = 'failed',
                        note = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (str(e)[:500], utc_now_iso(), row_id),
                )
        if not args.dry_run:
            conn.commit()
        print(f"scanned={scanned} downloaded={downloaded} skipped={skipped} failed={failed} out_dir={out_dir}")
        q = conn.execute(
            "SELECT status, COUNT(*) AS n FROM image_market_queue WHERE market_key=? GROUP BY status ORDER BY n DESC",
            (args.market_key,),
        ).fetchall()
        for row in q:
            print(f"queue_status {row['status']}={row['n']}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
