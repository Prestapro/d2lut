#!/usr/bin/env python3
"""
Re-parse existing threads/posts → observed_prices.
Useful when threads/posts are populated but observed_prices is empty/corrupted.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from d2lut.storage.sqlite import D2LutDB
from d2lut.normalize.d2jsp_market import parse_observations_from_threads


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Re-parse threads/posts → observed_prices")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite DB path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--clear-first", action="store_true", help="Clear observed_prices before re-parse")
    p.add_argument("--min-fg", type=float, help="Min FG filter")
    p.add_argument("--max-fg", type=float, help="Max FG filter")
    return p.parse_args()


def filter_observations_by_price(rows: list[dict], min_fg: float | None, max_fg: float | None) -> list[dict]:
    if min_fg is None and max_fg is None:
        return rows
    out = []
    for r in rows:
        fg = r.get("price_fg")
        if fg is None:
            continue
        if min_fg is not None and fg < min_fg:
            continue
        if max_fg is not None and fg > max_fg:
            continue
        out.append(r)
    return out


def main() -> int:
    args = parse_args()
    db = D2LutDB(args.db)
    
    if args.clear_first:
        cur = db.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM observed_prices WHERE market_key = ?", (args.market_key,))
        prev_count = cur.fetchone()[0]
        cur.execute("DELETE FROM observed_prices WHERE market_key = ?", (args.market_key,))
        db.conn.commit()
        print(f"Cleared {prev_count} observed_prices for market '{args.market_key}'")
    
    # Fetch all threads with posts
    cur = db.conn.cursor()
    cur.execute("""
        SELECT 
            t.id, t.source, t.forum_id, t.thread_id, t.url, t.title,
            t.reply_count, t.author, t.created_at, t.thread_trade_type, t.thread_category_id
        FROM threads t
        WHERE t.source = 'd2jsp'
        ORDER BY t.id
    """)
    thread_rows = cur.fetchall()
    print(f"Found {len(thread_rows)} threads")
    
    threads = []
    for row in thread_rows:
        thread_dict = {
            "id": row[0],
            "source": row[1],
            "forum_id": row[2],
            "thread_id": row[3],
            "url": row[4],
            "title": row[5],
            "reply_count": row[6],
            "author": row[7],
            "created_at": row[8],
            "thread_trade_type": row[9],
            "thread_category_id": row[10],
        }
        
        # Fetch posts for this thread
        cur.execute("""
            SELECT id, source, thread_id, post_id, author, posted_at, body_text
            FROM posts
            WHERE source = 'd2jsp' AND thread_id = ?
            ORDER BY id
        """, (row[3],))
        post_rows = cur.fetchall()
        
        thread_dict["posts"] = [
            {
                "id": p[0],
                "source": p[1],
                "thread_id": p[2],
                "post_id": p[3],
                "author": p[4],
                "posted_at": p[5],
                "body_text": p[6],
            }
            for p in post_rows
        ]
        threads.append(thread_dict)
    
    print(f"Parsing observations from {len(threads)} threads...")
    obs_rows = parse_observations_from_threads(threads, market_key=args.market_key)
    print(f"Parsed {len(obs_rows)} raw observations")
    
    obs_rows = filter_observations_by_price(obs_rows, args.min_fg, args.max_fg)
    print(f"After price filter: {len(obs_rows)} observations")
    
    n_obs = db.insert_observed_prices(obs_rows)
    print(f"Inserted {n_obs} observed_prices")
    
    # Show signal_kind breakdown
    cur.execute("""
        SELECT signal_kind, COUNT(*) 
        FROM observed_prices 
        WHERE market_key = ?
        GROUP BY signal_kind
    """, (args.market_key,))
    for sig, cnt in cur.fetchall():
        print(f"  {sig}: {cnt}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
