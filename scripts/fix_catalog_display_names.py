#!/usr/bin/env python3
"""Fix catalog display_name to use source_key for unique/set items.

Problem: Many unique/set items have generic display_name (e.g. "Blade", "Cap")
but specific source_key (e.g. "Irices Shard", "War Bonnet").

This causes market matching failures because d2jsp uses specific names.

Solution: Update display_name = source_key for unique/set items where they differ.

Usage:
    PYTHONPATH=src python3 scripts/fix_catalog_display_names.py --db data/cache/d2lut.db
    PYTHONPATH=src python3 scripts/fix_catalog_display_names.py --db data/cache/d2lut.db --dry-run
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="Fix catalog display_name from source_key")
    p.add_argument("--db", default="data/cache/d2lut.db", help="SQLite database path")
    p.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Find rows where display_name != source_key
    rows = conn.execute(
        """
        SELECT canonical_item_id, display_name, source_key, category
        FROM catalog_items
        WHERE category IN ('unique', 'set')
          AND source_key IS NOT NULL
          AND lower(display_name) != lower(source_key)
        ORDER BY category, canonical_item_id
        """
    ).fetchall()

    if not rows:
        print("No rows to fix.")
        return 0

    print(f"Found {len(rows)} rows to fix:")
    print(f"{'canonical_item_id':<40} {'old_display':<30} -> {'new_display':<30}")
    print("=" * 100)

    updated = 0
    for r in rows:
        cid = r["canonical_item_id"]
        old_display = r["display_name"]
        new_display = r["source_key"]
        
        print(f"{cid:<40} {old_display:<30} -> {new_display:<30}")
        
        if not args.dry_run:
            conn.execute(
                "UPDATE catalog_items SET display_name = ? WHERE canonical_item_id = ?",
                (new_display, cid),
            )
            updated += 1

    if not args.dry_run:
        conn.commit()
        print(f"\n✅ Updated {updated} rows")
    else:
        print(f"\n🔍 DRY-RUN: Would update {len(rows)} rows")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
