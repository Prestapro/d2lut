#!/usr/bin/env python3
"""Export catalog_items to item-names.json format."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    db_path = Path("data/cache/d2lut.db")
    output_path = Path("data/templates/item-names-full.json")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    cur = conn.execute("""
        SELECT 
            canonical_item_id,
            display_name,
            source_key,
            category,
            quality_class
        FROM catalog_items
        ORDER BY category, canonical_item_id
    """)
    
    items = []
    for idx, row in enumerate(cur.fetchall(), start=1):
        items.append({
            "id": idx,
            "Key": row["canonical_item_id"],
            "enUS": row["display_name"],
            "category": row["category"],
            "quality": row["quality_class"]
        })
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    
    print(f"Exported {len(items)} items to {output_path}")
    conn.close()


if __name__ == "__main__":
    main()
