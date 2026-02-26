#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class BodyImageRef:
    post_id: int | None
    image_url: str


class D2JspBodyImageParser(HTMLParser):
    """Extract image URLs from post-body (`div.bts`) blocks only.

    This intentionally excludes avatars (`class="av"`) and most signatures.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._div_stack: list[tuple[bool, int | None]] = []
        self._in_bts_depth = 0
        self._current_post_id_stack: list[int | None] = []
        self.images: list[BodyImageRef] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "div":
            cls = (attr.get("class") or "").lower()
            div_id = attr.get("id") or ""
            is_bts = "bts" in {c.strip() for c in cls.split()}
            post_id = None
            m = re.fullmatch(r"tp(\d+)", div_id)
            if m:
                post_id = int(m.group(1))
            self._div_stack.append((is_bts, post_id))
            if is_bts:
                self._in_bts_depth += 1
                self._current_post_id_stack.append(post_id)
            return

        if tag == "img" and self._in_bts_depth > 0:
            src = (attr.get("src") or "").strip()
            if not src:
                return
            if src.startswith("//"):
                src = "https:" + src
            # Skip d2jsp emoticons/assets inside post body text.
            if "forums.d2jsp.org/images/e/" in src:
                return
            if not _looks_like_image_url(src):
                return
            post_id = self._current_post_id_stack[-1] if self._current_post_id_stack else None
            self.images.append(BodyImageRef(post_id=post_id, image_url=src))

    def handle_endtag(self, tag: str) -> None:
        if tag != "div" or not self._div_stack:
            return
        is_bts, _post_id = self._div_stack.pop()
        if is_bts:
            self._in_bts_depth = max(0, self._in_bts_depth - 1)
            if self._current_post_id_stack:
                self._current_post_id_stack.pop()


def _looks_like_image_url(url: str) -> bool:
    low = url.lower()
    if low.startswith("data:"):
        return False
    # d2jsp image hosts + common external hosts; fallback to image-like extension.
    if any(host in low for host in ("imgur.com/", "i.ibb.co/", "postimg.", "i.postimg.", "ibb.co/", "prnt.sc/")):
        return True
    path = urlparse(url).path.lower()
    return path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))


def extract_body_images_from_html(html_text: str) -> list[BodyImageRef]:
    p = D2JspBodyImageParser()
    p.feed(html_text)
    # de-dupe by (post_id, url) preserving order
    out: list[BodyImageRef] = []
    seen: set[tuple[int | None, str]] = set()
    for img in p.images:
        key = (img.post_id, img.image_url)
        if key in seen:
            continue
        seen.add(key)
        out.append(img)
    return out


def ensure_queue_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS image_market_queue (
          id INTEGER PRIMARY KEY,
          market_key TEXT NOT NULL,
          forum_id INTEGER NOT NULL,
          thread_id INTEGER NOT NULL,
          post_id INTEGER NOT NULL DEFAULT -1,
          source_url TEXT,
          topic_html_path TEXT,
          image_url TEXT NOT NULL,
          local_image_path TEXT,
          max_price_fg REAL,
          observed_variant_hint TEXT,
          reason TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', -- pending|downloaded|ocr_parsed|failed|manual_review
          note TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(market_key, thread_id, post_id, image_url)
        );
        CREATE INDEX IF NOT EXISTS idx_image_queue_status ON image_market_queue(status, market_key);
        CREATE INDEX IF NOT EXISTS idx_image_queue_thread ON image_market_queue(thread_id, market_key);
        """
    )
    # Lightweight migrations for existing queue table revisions.
    try:
        conn.execute("ALTER TABLE image_market_queue ADD COLUMN local_image_path TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def _topic_path_for_thread(topic_dir: Path, thread_id: int) -> Path | None:
    # Prefer exact filename with forum suffix if present.
    matches = sorted(topic_dir.glob(f"topic_t{thread_id}*.html"))
    return matches[0] if matches else None


def _thread_candidates(
    conn: sqlite3.Connection,
    *,
    market_key: str,
    forum_id: int,
    min_fg: float,
    require_title_only_high_value: bool,
) -> list[sqlite3.Row]:
    title_only_clause = (
        """
        AND NOT EXISTS (
          SELECT 1 FROM observed_prices op2
          WHERE op2.market_key = op.market_key
            AND op2.thread_id = op.thread_id
            AND op2.price_fg >= ?
            AND op2.source_kind = 'post'
        )
        """
        if require_title_only_high_value
        else ""
    )
    params: list[object] = [market_key, forum_id, min_fg]
    if require_title_only_high_value:
        params.append(min_fg)
    q = f"""
      SELECT
        t.thread_id,
        t.url AS thread_url,
        t.title,
        MAX(op.price_fg) AS max_price_fg,
        MIN(op.source_kind) AS min_source_kind,
        MAX(op.source_kind) AS max_source_kind,
        GROUP_CONCAT(DISTINCT op.variant_key) AS variant_hints
      FROM observed_prices op
      JOIN threads t
        ON t.thread_id = op.thread_id
       AND t.forum_id = ?
       AND t.source = 'd2jsp'
      WHERE op.market_key = ?
        AND op.price_fg >= ?
        AND op.thread_id IS NOT NULL
      {title_only_clause}
      GROUP BY t.thread_id, t.url, t.title
      ORDER BY MAX(op.price_fg) DESC, t.thread_id DESC
    """
    # Reorder params to match query placeholders.
    if require_title_only_high_value:
        qparams = [forum_id, market_key, min_fg, min_fg]
    else:
        qparams = [forum_id, market_key, min_fg]
    return list(conn.execute(q, qparams).fetchall())


def _post_price_map_for_thread(
    conn: sqlite3.Connection,
    *,
    market_key: str,
    thread_id: int,
) -> dict[int, tuple[float, str]]:
    """Map post_id -> (max_price_fg, variant_hints_csv) for observed post-derived prices in a thread."""
    rows = conn.execute(
        """
        SELECT
          COALESCE(post_id, -1) AS post_id,
          MAX(price_fg) AS max_price_fg,
          GROUP_CONCAT(DISTINCT variant_key) AS variant_hints
        FROM observed_prices
        WHERE market_key = ?
          AND thread_id = ?
          AND source_kind = 'post'
          AND post_id IS NOT NULL
        GROUP BY COALESCE(post_id, -1)
        """,
        (market_key, thread_id),
    ).fetchall()
    out: dict[int, tuple[float, str]] = {}
    for r in rows:
        pid = int(r["post_id"])
        out[pid] = (float(r["max_price_fg"] or 0.0), str(r["variant_hints"] or ""))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Enqueue high-value topic image attachments for OCR recovery")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--forum-id", type=int, default=271, help="Forum ID")
    p.add_argument("--topic-dir", default="data/raw/d2jsp/topic_pages", help="Directory with saved topic.php HTML")
    p.add_argument("--min-fg", type=float, default=300.0, help="Priority threshold (default: 300)")
    p.add_argument(
        "--require-title-only-high-value",
        action="store_true",
        default=True,
        help="Only enqueue threads whose >=min-fg observations are title-derived (default: on)",
    )
    p.add_argument(
        "--no-require-title-only-high-value",
        dest="require_title_only_high_value",
        action="store_false",
        help="Also include threads with post-derived high-value observations",
    )
    p.add_argument("--limit-threads", type=int, default=0, help="Optional cap on candidate threads (0=all)")
    p.add_argument("--dry-run", action="store_true", help="Scan and report but do not write queue rows")
    args = p.parse_args()

    db_path = Path(args.db)
    topic_dir = Path(args.topic_dir)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2
    if not topic_dir.exists():
        print(f"ERROR: topic dir not found: {topic_dir}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_queue_schema(conn)
        cands = _thread_candidates(
            conn,
            market_key=args.market_key,
            forum_id=args.forum_id,
            min_fg=args.min_fg,
            require_title_only_high_value=args.require_title_only_high_value,
        )
        if args.limit_threads and args.limit_threads > 0:
            cands = cands[: args.limit_threads]

        scanned = 0
        missing_html = 0
        no_body_images = 0
        queued = 0
        existing = 0
        sample_lines: list[str] = []

        for th in cands:
            scanned += 1
            tid = int(th["thread_id"])
            post_price_map = _post_price_map_for_thread(conn, market_key=args.market_key, thread_id=tid)
            topic_path = _topic_path_for_thread(topic_dir, tid)
            if topic_path is None:
                missing_html += 1
                continue
            html_text = topic_path.read_text(encoding="utf-8", errors="ignore")
            imgs = extract_body_images_from_html(html_text)
            if not imgs:
                no_body_images += 1
                continue

            thread_variant_hints = str(th["variant_hints"] or "")
            base_reason = (
                "high_value_title_only_with_body_image"
                if args.require_title_only_high_value
                else "high_value_with_body_image"
            )
            for img in imgs:
                img_post_id = int(img.post_id) if img.post_id is not None else -1
                match_scope = "thread"
                matched_fg = float(th["max_price_fg"] or 0)
                matched_variant_hints = thread_variant_hints
                if img_post_id >= 0 and img_post_id in post_price_map:
                    post_fg, post_variants = post_price_map[img_post_id]
                    # Prefer exact post-level linkage even if lower than thread max.
                    matched_fg = post_fg
                    matched_variant_hints = post_variants or thread_variant_hints
                    match_scope = "post"
                reason = f"{base_reason}_{match_scope}_price_match"
                if args.dry_run:
                    queued += 1
                    if len(sample_lines) < 20:
                        sample_lines.append(
                            f"thread={tid} post={img.post_id or '-'} fg={matched_fg:g} match={match_scope} {img.image_url}"
                        )
                    continue
                now = utc_now_iso()
                cur = conn.execute(
                    """
                    INSERT INTO image_market_queue(
                      market_key, forum_id, thread_id, post_id, source_url, topic_html_path,
                      image_url, max_price_fg, observed_variant_hint, reason, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    ON CONFLICT(market_key, thread_id, post_id, image_url) DO UPDATE SET
                      max_price_fg = MAX(image_market_queue.max_price_fg, excluded.max_price_fg),
                      observed_variant_hint = COALESCE(image_market_queue.observed_variant_hint, excluded.observed_variant_hint),
                      reason = excluded.reason,
                      source_url = COALESCE(image_market_queue.source_url, excluded.source_url),
                      topic_html_path = COALESCE(image_market_queue.topic_html_path, excluded.topic_html_path),
                      updated_at = excluded.updated_at
                    """,
                    (
                        args.market_key,
                        args.forum_id,
                        tid,
                        img_post_id,
                        str(th["thread_url"] or ""),
                        str(topic_path),
                        img.image_url,
                        matched_fg,
                        matched_variant_hints[:500],
                        reason,
                        now,
                        now,
                    ),
                )
                if cur.rowcount == 1:
                    queued += 1
                else:
                    existing += 1
                if len(sample_lines) < 20:
                    sample_lines.append(
                        f"thread={tid} post={img.post_id or '-'} fg={matched_fg:g} match={match_scope} {img.image_url}"
                    )
        if not args.dry_run:
            conn.commit()

        q_rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM image_market_queue WHERE market_key = ? GROUP BY status ORDER BY n DESC",
            (args.market_key,),
        ).fetchall()
        print(
            f"scanned_threads={scanned} min_fg={args.min_fg:g} "
            f"title_only_filter={'on' if args.require_title_only_high_value else 'off'} "
            f"missing_html={missing_html} no_body_images={no_body_images} "
            f"{'would_queue' if args.dry_run else 'queued'}={queued} existing={existing}"
        )
        for r in q_rows:
            print(f"queue_status {r['status']}={r['n']}")
        if sample_lines:
            print("# sample")
            for ln in sample_lines[:20]:
                print(ln)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
