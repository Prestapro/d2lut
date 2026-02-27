#!/usr/bin/env python3
"""Find diablo2.io IDs for items by searching their site."""
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path


def search_d2io(item_name: str) -> list[tuple[int, str]]:
    """Search diablo2.io for item and return list of (id, name) matches."""
    # Try direct URL patterns first
    slug = item_name.lower().replace("'", "").replace(" ", "-")
    
    # Try uniques page
    url = f"https://diablo2.io/uniques/{slug}-t"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            # Extract ID from URL or page
            match = re.search(r'/uniques/[^"]*-t(\d+)\.html', html)
            if match:
                return [(int(match.group(1)), item_name)]
    except:
        pass
    
    # Try sets page
    url = f"https://diablo2.io/sets/{slug}-t"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            match = re.search(r'/sets/[^"]*-t(\d+)\.html', html)
            if match:
                return [(int(match.group(1)), item_name)]
    except:
        pass
    
    return []


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: find_d2io_ids.py <items_file>")
        return 1
    
    items_file = Path(sys.argv[1])
    if not items_file.exists():
        print(f"ERROR: {items_file} not found")
        return 2
    
    # Read items
    items = []
    with open(items_file) as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) >= 3:
                cid, name, cat = parts[0], parts[1], parts[2]
                items.append((cid, name, cat))
    
    print(f"Searching for {len(items)} items...")
    
    found = []
    not_found = []
    
    for i, (cid, name, cat) in enumerate(items):
        print(f"[{i+1}/{len(items)}] Searching: {name} ({cat})...", end=" ")
        
        results = search_d2io(name)
        if results:
            d2io_id, matched_name = results[0]
            print(f"FOUND: {d2io_id}")
            found.append((d2io_id, cid, name))
        else:
            print("NOT FOUND")
            not_found.append((cid, name, cat))
        
        time.sleep(0.3)  # Rate limit
    
    print(f"\n{'='*60}")
    print(f"Found: {len(found)}")
    print(f"Not found: {len(not_found)}")
    print(f"{'='*60}")
    
    # Write found items
    if found:
        with open('/tmp/found_d2io_ids.txt', 'w') as f:
            for d2io_id, cid, name in found:
                f.write(f'    {{"d2io_id": {d2io_id}, "canonical": "{cid}", "name": "{name}"}},\n')
        print(f"Wrote {len(found)} items to /tmp/found_d2io_ids.txt")
    
    # Write not found
    if not_found:
        with open('/tmp/not_found_items.txt', 'w') as f:
            for cid, name, cat in not_found:
                f.write(f"{cid}|{name}|{cat}\n")
        print(f"Wrote {len(not_found)} not found items to /tmp/not_found_items.txt")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
