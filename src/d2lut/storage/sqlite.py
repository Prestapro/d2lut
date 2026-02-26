from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from d2lut.models import PriceEstimate


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class D2LutDB:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        
        # Initialize slang cache for normalization
        self._init_slang_cache()
    
    def _init_slang_cache(self) -> None:
        """Initialize the slang alias cache for the normalizer."""
        try:
            from d2lut.normalize.d2jsp_market import init_slang_cache
            init_slang_cache(str(self.path))
        except ImportError:
            # Normalizer module not available - skip cache initialization
            pass

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        self.conn.executescript(schema_path.read_text(encoding="utf-8"))
        
        # Initialize slang schema
        slang_schema_path = Path(__file__).parents[1] / "catalog" / "slang_schema.sql"
        if slang_schema_path.exists():
            self.conn.executescript(slang_schema_path.read_text(encoding="utf-8"))
        
        # Lightweight migrations for existing local DBs.
        try:
            self.conn.execute("ALTER TABLE threads ADD COLUMN reply_count INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            self.conn.execute("ALTER TABLE threads ADD COLUMN thread_trade_type TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.conn.execute("ALTER TABLE threads ADD COLUMN thread_category_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            self.conn.execute("ALTER TABLE observed_prices ADD COLUMN thread_trade_type TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.conn.execute("ALTER TABLE observed_prices ADD COLUMN thread_category_id INTEGER")
        except sqlite3.OperationalError:
            pass
        self.conn.commit()
        
        # Reinitialize slang cache after schema changes
        self._init_slang_cache()

    def insert_snapshot(self, source: str, forum_id: int, path: str | None, note: str | None = None) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO source_snapshots(source, forum_id, captured_at, path, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source, forum_id, utc_now_iso(), path, note),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def upsert_threads(self, rows: Iterable[dict]) -> int:
        count = 0
        for row in rows:
            self.conn.execute(
                """
                INSERT INTO threads(source, forum_id, thread_id, url, title, thread_category_id, thread_trade_type, reply_count, author, created_at, snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, thread_id) DO UPDATE SET
                  title=excluded.title,
                  url=excluded.url,
                  thread_category_id=COALESCE(excluded.thread_category_id, threads.thread_category_id),
                  thread_trade_type=COALESCE(excluded.thread_trade_type, threads.thread_trade_type),
                  reply_count=COALESCE(excluded.reply_count, threads.reply_count),
                  author=COALESCE(excluded.author, threads.author),
                  created_at=COALESCE(excluded.created_at, threads.created_at),
                  snapshot_id=COALESCE(excluded.snapshot_id, threads.snapshot_id)
                """,
                (
                    row["source"],
                    row["forum_id"],
                    row["thread_id"],
                    row["url"],
                    row["title"],
                    row.get("thread_category_id"),
                    row.get("thread_trade_type"),
                    row.get("reply_count"),
                    row.get("author"),
                    row.get("created_at"),
                    row.get("snapshot_id"),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def upsert_posts(self, rows: Iterable[dict], snapshot_id: int | None = None) -> int:
        count = 0
        for row in rows:
            post_id = row.get("post_id")
            if post_id is None:
                # Synthetic topic-text rows for MVP parsing.
                self.conn.execute(
                    """
                    INSERT INTO posts(source, thread_id, post_id, author, posted_at, body_text, snapshot_id)
                    VALUES (?, ?, NULL, ?, ?, ?, ?)
                    """,
                    (
                        row["source"],
                        row["thread_id"],
                        row.get("author"),
                        row.get("posted_at"),
                        row["body_text"],
                        snapshot_id if snapshot_id is not None else row.get("snapshot_id"),
                    ),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO posts(source, thread_id, post_id, author, posted_at, body_text, snapshot_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, post_id) DO UPDATE SET
                      body_text=excluded.body_text,
                      author=COALESCE(excluded.author, posts.author),
                      posted_at=COALESCE(excluded.posted_at, posts.posted_at),
                      snapshot_id=COALESCE(excluded.snapshot_id, posts.snapshot_id)
                    """,
                    (
                        row["source"],
                        row["thread_id"],
                        post_id,
                        row.get("author"),
                        row.get("posted_at"),
                        row["body_text"],
                        snapshot_id if snapshot_id is not None else row.get("snapshot_id"),
                    ),
                )
            count += 1
        self.conn.commit()
        return count

    def insert_observed_prices(self, rows: Iterable[dict]) -> int:
        count = 0
        for row in rows:
            self.conn.execute(
                """
                INSERT INTO observed_prices(
                  source, market_key, forum_id, thread_id, post_id, source_kind, signal_kind, thread_category_id, thread_trade_type,
                  canonical_item_id, variant_key, price_fg, confidence, observed_at, source_url, raw_excerpt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["source"],
                    row["market_key"],
                    row["forum_id"],
                    row.get("thread_id"),
                    row.get("post_id"),
                    row["source_kind"],
                    row["signal_kind"],
                    row.get("thread_category_id"),
                    row.get("thread_trade_type"),
                    row["canonical_item_id"],
                    row["variant_key"],
                    row["price_fg"],
                    row["confidence"],
                    row.get("observed_at"),
                    row.get("source_url"),
                    row.get("raw_excerpt"),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def replace_price_estimates(self, market_key: str, estimates: dict[str, PriceEstimate]) -> int:
        self.conn.execute("DELETE FROM price_estimates WHERE market_key = ?", (market_key,))
        count = 0
        for variant_key, est in estimates.items():
            self.conn.execute(
                """
                INSERT INTO price_estimates(
                  market_key, variant_key, estimate_fg, range_low_fg, range_high_fg, confidence, sample_count, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    market_key,
                    variant_key,
                    est.estimate_fg,
                    est.range_low_fg,
                    est.range_high_fg,
                    est.confidence,
                    est.sample_count,
                    est.last_updated.isoformat(),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def load_observations(self, market_key: str) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            """
            SELECT * FROM observed_prices
            WHERE market_key = ?
            ORDER BY COALESCE(observed_at, '') DESC, id DESC
            """,
            (market_key,),
        )
        return list(cur.fetchall())
