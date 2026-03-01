#!/usr/bin/env python3
"""Topic replay tool — reparse a thread_id and show before/after diff.

Read-only diagnostic: queries observed_prices for a given thread_id,
re-runs extract_props() + props_signature() with the *current* parser,
and displays a diff against the stored variant_key.

Flags
-----
  thread_id        Positional — the d2jsp thread ID to replay.
  --db             SQLite database path (default: data/cache/d2lut.db).
  --market-key     Market key filter (default: d2r_sc_ladder).
  --dry-run        Explicit read-only flag (tool is always read-only).
  --json           Output as JSON instead of human-readable text.

Requirements: 24.1, 24.2, 24.3, 24.4
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Allow standalone execution: python scripts/replay_topic.py
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_property_price_table_html import extract_props, props_signature


def _truncate(text: str, maxlen: int = 80) -> str:
    if len(text) <= maxlen:
        return text
    return text[: maxlen - 3] + "..."


def replay_thread(
    conn: sqlite3.Connection,
    thread_id: int,
    market_key: str,
) -> list[dict]:
    """Reparse all observations for *thread_id* and return diff records."""
    rows = conn.execute(
        """
        SELECT id, variant_key, price_fg, signal_kind,
               COALESCE(raw_excerpt, '') AS raw_excerpt, observed_at
        FROM observed_prices
        WHERE thread_id = ? AND market_key = ?
        ORDER BY id
        """,
        (thread_id, market_key),
    ).fetchall()

    results: list[dict] = []
    for row in rows:
        excerpt = row["raw_excerpt"]
        variant_key = row["variant_key"]

        props = extract_props(excerpt, variant_key)
        new_sig = props_signature(props)

        # Collect non-default extracted fields for display.
        extracted_fields = dict(props.non_empty_items())

        changed = (new_sig or "") != (variant_key or "")

        results.append(
            {
                "obs_id": row["id"],
                "variant_key": variant_key,
                "new_signature": new_sig,
                "changed": changed,
                "price_fg": row["price_fg"],
                "signal_kind": row["signal_kind"],
                "observed_at": row["observed_at"],
                "raw_excerpt": excerpt,
                "extracted_fields": extracted_fields,
            }
        )
    return results


def _print_human(
    results: list[dict], *, thread_id: int, market_key: str
) -> None:
    total = len(results)
    changed = sum(1 for r in results if r["changed"])
    unchanged = total - changed

    print(f"Thread {thread_id}  market={market_key}")
    print(f"Observations: {total}  changed: {changed}  unchanged: {unchanged}")
    print("=" * 72)

    for r in results:
        tag = "CHANGED" if r["changed"] else "ok"
        print(f"\n[{tag}] obs_id={r['obs_id']}  "
              f"signal={r['signal_kind']}  fg={r['price_fg']}")
        print(f"  excerpt : {_truncate(r['raw_excerpt'])}")
        print(f"  before  : {r['variant_key']}")
        print(f"  after   : {r['new_signature']}")
        if r["changed"] and r["extracted_fields"]:
            fields_str = ", ".join(
                f"{k}={v}" for k, v in r["extracted_fields"].items()
            )
            print(f"  fields  : {fields_str}")

    print()


def _print_json(
    results: list[dict], *, thread_id: int, market_key: str
) -> None:
    payload = {
        "thread_id": thread_id,
        "market_key": market_key,
        "total": len(results),
        "changed": sum(1 for r in results if r["changed"]),
        "observations": results,
    }
    print(json.dumps(payload, indent=2, default=str))


def main() -> int:
    p = argparse.ArgumentParser(
        description="Reparse a d2jsp thread and show before/after diff"
    )
    p.add_argument("thread_id", type=int, help="Thread ID to replay")
    p.add_argument(
        "--db", default="data/cache/d2lut.db", help="SQLite database path"
    )
    p.add_argument(
        "--market-key", default="d2r_sc_ladder", help="Market key"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show diff without modifying DB (default — tool is always read-only)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        results = replay_thread(conn, args.thread_id, args.market_key)
    finally:
        conn.close()

    if not results:
        print(
            f"No observations found for thread_id={args.thread_id} "
            f"market_key={args.market_key}",
            file=sys.stderr,
        )
        return 1

    if args.json_output:
        _print_json(results, thread_id=args.thread_id, market_key=args.market_key)
    else:
        _print_human(results, thread_id=args.thread_id, market_key=args.market_key)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
