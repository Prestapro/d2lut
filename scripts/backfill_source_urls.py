#!/usr/bin/env python3
"""Idempotent backfill of source_url from thread_id in observed_prices.

Looks up thread URLs from the threads table and populates missing source_url
values. Logs unresolvable rows (thread_id not found in threads table).

Usage:
    python scripts/backfill_source_urls.py --db data/cache/d2lut.db
    python scripts/backfill_source_urls.py --dry-run
    python scripts/backfill_source_urls.py --json
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Core logic
# ------------------------------------------------------------------

def count_source_url_stats(
    conn: sqlite3.Connection,
    market_key: str,
) -> dict[str, int]:
    """Count rows with/without source_url for the given market."""
    row = conn.execute(
        """
        SELECT
            COUNT(*)                                                    AS total,
            COUNT(CASE WHEN source_url IS NOT NULL
                         AND source_url != '' THEN 1 END)              AS with_url,
            COUNT(CASE WHEN source_url IS NULL
                         OR  source_url  = '' THEN 1 END)              AS without_url
        FROM observed_prices
        WHERE market_key = ?
        """,
        (market_key,),
    ).fetchone()
    return {
        "total": row[0],
        "with_url": row[1],
        "without_url": row[2],
    }


def find_backfillable_rows(
    conn: sqlite3.Connection,
    market_key: str,
) -> list[dict]:
    """Find rows missing source_url but having a non-NULL thread_id."""
    rows = conn.execute(
        """
        SELECT id, thread_id
        FROM observed_prices
        WHERE market_key = ?
          AND (source_url IS NULL OR source_url = '')
          AND thread_id IS NOT NULL
          AND thread_id != ''
        """,
        (market_key,),
    ).fetchall()
    return [{"id": r[0], "thread_id": r[1]} for r in rows]


def build_thread_url_map(
    conn: sqlite3.Connection,
    thread_ids: list[str],
) -> dict[str, str]:
    """Map thread_id -> url from the threads table."""
    if not thread_ids:
        return {}
    # Use a temp approach to avoid huge IN clauses: batch lookup.
    url_map: dict[str, str] = {}
    batch_size = 500
    for i in range(0, len(thread_ids), batch_size):
        batch = thread_ids[i : i + batch_size]
        placeholders = ",".join("?" for _ in batch)
        rows = conn.execute(
            f"""
            SELECT thread_id, url
            FROM threads
            WHERE thread_id IN ({placeholders})
              AND url IS NOT NULL
              AND url != ''
            """,
            batch,
        ).fetchall()
        for r in rows:
            url_map[r[0]] = r[1]
    return url_map


def backfill(
    conn: sqlite3.Connection,
    market_key: str,
    *,
    dry_run: bool = False,
) -> dict:
    """Run the backfill and return a summary dict.

    Returns dict with keys:
        before: stats before backfill
        after: stats after backfill
        updated: number of rows updated
        unresolvable: list of {id, thread_id} that could not be resolved
    """
    before = count_source_url_stats(conn, market_key)

    candidates = find_backfillable_rows(conn, market_key)
    if not candidates:
        return {
            "before": before,
            "after": before,
            "updated": 0,
            "unresolvable": [],
        }

    unique_tids = list({c["thread_id"] for c in candidates})
    url_map = build_thread_url_map(conn, unique_tids)

    to_update: list[tuple[str, int]] = []  # (url, row_id)
    unresolvable: list[dict] = []

    for c in candidates:
        url = url_map.get(c["thread_id"])
        if url:
            to_update.append((url, c["id"]))
        else:
            unresolvable.append({"id": c["id"], "thread_id": c["thread_id"]})

    if unresolvable:
        for entry in unresolvable:
            log.warning(
                "Unresolvable row id=%s thread_id=%s — no matching thread",
                entry["id"],
                entry["thread_id"],
            )

    updated = 0
    if to_update and not dry_run:
        conn.execute("BEGIN")
        try:
            conn.executemany(
                "UPDATE observed_prices SET source_url = ? WHERE id = ?",
                to_update,
            )
            conn.commit()
            updated = len(to_update)
        except Exception:
            conn.rollback()
            raise
    elif to_update:
        updated = len(to_update)  # dry-run: report what would happen

    after = count_source_url_stats(conn, market_key) if not dry_run else before

    return {
        "before": before,
        "after": after,
        "updated": updated,
        "unresolvable": unresolvable,
    }


# ------------------------------------------------------------------
# Output formatting
# ------------------------------------------------------------------

def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0.0"
    return f"{n / total * 100:.1f}"


def _print_human(result: dict, *, market_key: str, dry_run: bool) -> None:
    mode = " (DRY RUN)" if dry_run else ""
    print(f"=== Source Link Backfill{mode} ===")
    print(f"Market: {market_key}")
    print()
    b = result["before"]
    print("Before:")
    print(f"  total rows:       {b['total']}")
    print(f"  with source_url:  {b['with_url']}  ({_pct(b['with_url'], b['total'])}%)")
    print(f"  without:          {b['without_url']}")
    print()
    print(f"Updated: {result['updated']}")
    print(f"Unresolvable: {len(result['unresolvable'])}")
    if result["unresolvable"]:
        for entry in result["unresolvable"][:20]:
            print(f"  row {entry['id']}: thread_id={entry['thread_id']}")
        if len(result["unresolvable"]) > 20:
            print(f"  ... and {len(result['unresolvable']) - 20} more")
    print()
    a = result["after"]
    print("After:")
    print(f"  total rows:       {a['total']}")
    print(f"  with source_url:  {a['with_url']}  ({_pct(a['with_url'], a['total'])}%)")
    print(f"  without:          {a['without_url']}")


def _print_json(result: dict, *, market_key: str, dry_run: bool) -> None:
    payload = {
        "market_key": market_key,
        "dry_run": dry_run,
        "before": result["before"],
        "after": result["after"],
        "updated": result["updated"],
        "unresolvable_count": len(result["unresolvable"]),
        "unresolvable": result["unresolvable"],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="Backfill missing source_url from thread_id in observed_prices",
    )
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--market-key", default="d2r_sc_ladder", help="Market key")
    p.add_argument("--dry-run", action="store_true", help="Show what would be updated without modifying the DB")
    p.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    try:
        result = backfill(conn, args.market_key, dry_run=args.dry_run)
    finally:
        conn.close()

    if args.json_output:
        _print_json(result, market_key=args.market_key, dry_run=args.dry_run)
    else:
        _print_human(result, market_key=args.market_key, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
