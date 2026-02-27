#!/usr/bin/env python3
"""Search diablo2.io for remaining items and add them to D2IO_ITEMS."""
import re
import sqlite3
import time
import urllib.request
from pathlib import Path

def load_diablo2io_index() -> dict[str, tuple[int, str]]:
    """Load full diablo2.io uniques/sets index once."""
    print("Loading diablo2.io index...")
    index = {}
    
    for page_type in ['uniques', 'sets']:
        url = f"https://diablo2.io/{page_type}/"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 d2lut-search/1.0",
        })
        
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            
            # Extract all items: /uniques/name-tID.html or /sets/name-tID.html
            pattern = rf'href="/{page_type}/([^"]+)-t(\d+)\.html"'
            matches = re.findall(pattern, html)
            
            for name_slug, item_id in matches:
                name = name_slug.replace("-", " ").title().replace(" S ", "'s ")
                name_lower = name.lower()
                index[name_lower] = (int(item_id), name, page_type)
            
            print(f"  Loaded {len(matches)} {page_type}")
        except Exception as e:
            print(f"  Error loading {page_type}: {e}")
    
    return index

def fuzzy_search(query: str, index: dict) -> list[tuple[int, str]]:
    """Fuzzy search in index."""
    query_lower = query.lower()
    query_clean = re.sub(r'[^a-z0-9\s]', '', query_lower)
    
    results = []
    for name_lower, (item_id, name, page_type) in index.items():
        name_clean = re.sub(r'[^a-z0-9\s]', '', name_lower)
        
        # Exact match
        if query_lower == name_lower:
            results.append((item_id, name, 100))
        # Clean match
        elif query_clean == name_clean:
            results.append((item_id, name, 90))
        # Contains
        elif query_clean in name_clean:
            results.append((item_id, name, 70))
        # Words match
        elif all(word in name_clean for word in query_clean.split()):
            results.append((item_id, name, 60))
    
    # Sort by score
    results.sort(key=lambda x: -x[2])
    return [(item_id, name) for item_id, name, score in results]

def main():
    # Load index once
    index = load_diablo2io_index()
    print(f"Index loaded: {len(index)} items\n")
    
    # Load remaining items
    conn = sqlite3.connect('data/cache/d2lut.db')
    remaining = conn.execute("""
        SELECT ci.canonical_item_id, ci.display_name, ci.source_key, ci.category
        FROM catalog_items ci
        JOIN catalog_price_map cpm ON ci.canonical_item_id = cpm.canonical_item_id
        WHERE ci.tradeable = 1 AND cpm.price_status = 'heuristic_range'
        AND ci.category IN ('unique', 'set')
        ORDER BY ci.category, ci.source_key
    """).fetchall()
    
    print(f'Searching for {len(remaining)} items...\n')
    
    found = []
    not_found = []
    
    for cid, display, source_key, cat in remaining:
        name = source_key if source_key else display
        if not name or len(name) < 3:
            not_found.append((cid, name, cat))
            continue
        
        results = fuzzy_search(name, index)
        
        if results:
            item_id, match_name = results[0]
            found.append((item_id, cid, match_name))
            if len(results) == 1:
                print(f'✓ {name} -> {match_name} (id={item_id})')
            else:
                print(f'? {name} -> {match_name} (id={item_id}) [{len(results)} matches]')
        else:
            not_found.append((cid, name, cat))
            print(f'✗ {name} (no match)')
    
    print(f'\n\nFound: {len(found)} items')
    print(f'Not found: {len(not_found)} items')
    
    # Write additions
    with open('/tmp/search_additions.txt', 'w') as f:
        for item_id, cid, name in found:
            f.write(f'    {{"d2io_id": {item_id}, "canonical": "{cid}", "name": "{name}"}},\n')
    
    print(f'\nWrote {len(found)} additions to /tmp/search_additions.txt')
    
    # Write not found
    with open('/tmp/not_found.txt', 'w') as f:
        for cid, name, cat in not_found:
            f.write(f'{cid}\t{name}\t{cat}\n')
    
    print(f'Wrote {len(not_found)} not found to /tmp/not_found.txt')
    
    conn.close()

if __name__ == "__main__":
    main()
