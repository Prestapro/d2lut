"""End-to-end integration test for slang normalization in the market pipeline."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from d2lut.normalize.d2jsp_market import (
    init_slang_cache,
    normalize_item_hint,
    extract_title_fg_signals,
    observations_from_thread_row,
)


def create_test_db_with_slang():
    """Create a test database with slang aliases."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    conn = sqlite3.connect(db_path)
    
    # Create slang_aliases table
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS slang_aliases (
          id INTEGER PRIMARY KEY,
          term_norm TEXT NOT NULL,
          term_raw TEXT NOT NULL,
          term_type TEXT NOT NULL,
          canonical_item_id TEXT NOT NULL DEFAULT '',
          replacement_text TEXT NOT NULL DEFAULT '',
          confidence REAL NOT NULL DEFAULT 0.5,
          source TEXT NOT NULL DEFAULT 'manual',
          notes TEXT,
          enabled INTEGER NOT NULL DEFAULT 1,
          UNIQUE(term_norm, canonical_item_id, replacement_text)
        );
    """)
    
    # Insert common d2jsp slang
    test_aliases = [
        # Base shorthand
        ("gt", "gt", "base_alias", "", "giant thresher", 0.95, "test"),
        ("cv", "cv", "base_alias", "", "colossus voulge", 0.95, "test"),
        ("pb", "pb", "base_alias", "", "phase blade", 0.95, "test"),
        ("ba", "ba", "base_alias", "", "berserker axe", 0.95, "test"),
        ("ap", "ap", "base_alias", "", "archon plate", 0.95, "test"),
        
        # Item slang
        ("amy", "amy", "item_alias", "", "ammy", 0.99, "test"),
        ("ammy", "ammy", "item_alias", "", "amulet", 0.99, "test"),
    ]
    
    for term_norm, term_raw, term_type, canonical_id, replacement, confidence, source in test_aliases:
        conn.execute(
            """
            INSERT INTO slang_aliases(term_norm, term_raw, term_type, canonical_item_id, replacement_text, confidence, source, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (term_norm, term_raw, term_type, canonical_id, replacement, confidence, source),
        )
    
    conn.commit()
    conn.close()
    
    return db_path


def test_e2e_thread_parsing_with_slang():
    """Test end-to-end thread parsing with slang normalization."""
    print("\n" + "=" * 60)
    print("End-to-End Integration Test: Thread Parsing with Slang")
    print("=" * 60)
    
    db_path = create_test_db_with_slang()
    
    try:
        # Initialize slang cache
        init_slang_cache(db_path)
        print("✓ Slang cache initialized")
        
        # Test 1: Thread title with base shorthand
        print("\nTest 1: Base shorthand in thread title")
        thread1 = {
            "forum_id": 271,
            "thread_id": 12345,
            "url": "https://forums.d2jsp.org/topic.php?t=12345",
            "title": "4os gt eth bin 150",
            "created_at": "2024-01-01T00:00:00Z",
        }
        
        # First, test that normalize_item_hint works
        hint = normalize_item_hint(thread1["title"])
        print(f"  Title: '{thread1['title']}'")
        print(f"  Normalized hint: {hint}")
        assert hint is not None, "Should recognize base after slang expansion"
        assert "base:giant_thresher" in hint[0], f"Expected giant_thresher, got {hint}"
        print("  ✓ Base shorthand 'gt' expanded to 'giant thresher'")
        
        # Test price extraction still works
        signals = extract_title_fg_signals(thread1["title"])
        print(f"  Price signals: {signals}")
        assert len(signals) > 0, "Should extract price signals"
        print("  ✓ Price signals extracted")
        
        # Test full observation generation
        obs = observations_from_thread_row(thread1, market_key="test")
        print(f"  Observations: {len(obs)} generated")
        if obs:
            print(f"    - canonical_item_id: {obs[0]['canonical_item_id']}")
            print(f"    - variant_key: {obs[0]['variant_key']}")
            print(f"    - price_fg: {obs[0]['price_fg']}")
            print(f"    - signal_kind: {obs[0]['signal_kind']}")
        assert len(obs) > 0, "Should generate observations"
        assert obs[0]["canonical_item_id"] == "base:giant_thresher", \
            f"Expected base:giant_thresher, got {obs[0]['canonical_item_id']}"
        print("  ✓ Full observation generated with correct item ID")
        
        # Test 2: Thread title with multiple shorthand
        print("\nTest 2: Multiple shorthand terms")
        thread2 = {
            "forum_id": 271,
            "thread_id": 12346,
            "url": "https://forums.d2jsp.org/topic.php?t=12346",
            "title": "ft: 4os cv, 5os pb, 4os ba",
            "created_at": "2024-01-01T00:00:00Z",
        }
        
        hint = normalize_item_hint(thread2["title"])
        print(f"  Title: '{thread2['title']}'")
        print(f"  Normalized hint: {hint}")
        # Should match at least one base
        assert hint is not None, "Should recognize at least one base"
        print("  ✓ Multiple shorthand terms handled")
        
        # Test 3: Rune with slang (should still work)
        print("\nTest 3: Rune parsing (no slang interference)")
        thread3 = {
            "forum_id": 271,
            "thread_id": 12347,
            "url": "https://forums.d2jsp.org/topic.php?t=12347",
            "title": "jah bin 2500",
            "created_at": "2024-01-01T00:00:00Z",
        }
        
        hint = normalize_item_hint(thread3["title"])
        print(f"  Title: '{thread3['title']}'")
        print(f"  Normalized hint: {hint}")
        assert hint is not None, "Should recognize rune"
        assert "rune:jah" in hint[0], f"Expected rune:jah, got {hint}"
        print("  ✓ Rune parsing unaffected by slang system")
        
        # Test 4: Tal set items (should still work)
        print("\nTest 4: Tal set item parsing")
        thread4 = {
            "forum_id": 271,
            "thread_id": 12348,
            "url": "https://forums.d2jsp.org/topic.php?t=12348",
            "title": "tal amy bin 300",
            "created_at": "2024-01-01T00:00:00Z",
        }
        
        hint = normalize_item_hint(thread4["title"])
        print(f"  Title: '{thread4['title']}'")
        print(f"  Normalized hint: {hint}")
        assert hint is not None, "Should recognize tal ammy"
        assert "tal_rashas" in hint[0], f"Expected tal_rashas, got {hint}"
        print("  ✓ Tal set item parsing works with slang")
        
        print("\n" + "=" * 60)
        print("All integration tests passed! ✓")
        print("=" * 60)
        # pytest expects None (or no return) from test functions
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        raise  # Re-raise for pytest to handle
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise for pytest to handle
    finally:
        # Cleanup
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        test_e2e_thread_parsing_with_slang()
        sys.exit(0)
    except Exception:
        sys.exit(1)
