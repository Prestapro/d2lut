"""Simple standalone test for slang alias integration."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from d2lut.normalize.d2jsp_market import (
    apply_slang_normalization,
    init_slang_cache,
    normalize_item_hint,
)


def create_test_db():
    """Create a temporary database with slang aliases."""
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
    
    # Insert test slang aliases
    test_aliases = [
        ("gt", "gt", "base_alias", "", "giant thresher", 0.95, "test"),
        ("cv", "cv", "base_alias", "", "colossus voulge", 0.95, "test"),
        ("pb", "pb", "base_alias", "", "phase blade", 0.95, "test"),
        ("amy", "amy", "item_alias", "set:tal_rashas_adjudication", "tal ammy", 0.99, "test"),
        ("shako", "shako", "item_alias", "unique:harlequin_crest", "", 0.99, "test"),
        ("fg", "fg", "noise", "", "", 0.99, "test"),
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


def test_load_slang_aliases(db_path):
    """Test loading slang aliases from database."""
    print("Test: load_slang_aliases")
    init_slang_cache(db_path)
    
    from d2lut.normalize.d2jsp_market import _SLANG_CACHE
    assert _SLANG_CACHE is not None, "Cache should be initialized"
    assert "gt" in _SLANG_CACHE, "gt should be in cache"
    assert "amy" in _SLANG_CACHE, "amy should be in cache"
    print("  ✓ Slang cache loaded successfully")


def test_apply_slang_normalization_base_aliases(db_path):
    """Test that base aliases are applied correctly."""
    print("\nTest: apply_slang_normalization_base_aliases")
    init_slang_cache(db_path)
    
    result = apply_slang_normalization("4os gt eth", db_path)
    assert "giant thresher" in result.lower(), f"Expected 'giant thresher' in '{result}'"
    print(f"  ✓ '4os gt eth' -> '{result}'")
    
    result = apply_slang_normalization("cv 4os", db_path)
    assert "colossus voulge" in result.lower(), f"Expected 'colossus voulge' in '{result}'"
    print(f"  ✓ 'cv 4os' -> '{result}'")
    
    result = apply_slang_normalization("pb 5os", db_path)
    assert "phase blade" in result.lower(), f"Expected 'phase blade' in '{result}'"
    print(f"  ✓ 'pb 5os' -> '{result}'")


def test_apply_slang_normalization_item_aliases(db_path):
    """Test that item aliases are applied correctly."""
    print("\nTest: apply_slang_normalization_item_aliases")
    init_slang_cache(db_path)
    
    result = apply_slang_normalization("tal amy bin 300", db_path)
    assert "tal ammy" in result.lower(), f"Expected 'tal ammy' in '{result}'"
    print(f"  ✓ 'tal amy bin 300' -> '{result}'")


def test_normalize_item_hint_with_slang(db_path):
    """Test that normalize_item_hint uses slang aliases."""
    print("\nTest: normalize_item_hint_with_slang")
    init_slang_cache(db_path)
    
    result = normalize_item_hint("4os gt eth")
    assert result is not None, "Should match after slang expansion"
    assert "base:" in result[0], f"Expected 'base:' in '{result[0]}'"
    print(f"  ✓ '4os gt eth' normalized to: {result}")


def test_slang_normalization_case_insensitive(db_path):
    """Test that slang normalization works case-insensitively."""
    print("\nTest: slang_normalization_case_insensitive")
    init_slang_cache(db_path)
    
    result1 = apply_slang_normalization("GT 4os", db_path)
    result2 = apply_slang_normalization("gt 4os", db_path)
    result3 = apply_slang_normalization("Gt 4os", db_path)
    
    assert result1.lower() == result2.lower() == result3.lower(), \
        f"Case insensitive results should match: '{result1}', '{result2}', '{result3}'"
    print(f"  ✓ Case insensitive: 'GT'/'gt'/'Gt' all -> '{result1}'")


def test_slang_normalization_word_boundaries(db_path):
    """Test that slang normalization respects word boundaries."""
    print("\nTest: slang_normalization_word_boundaries")
    init_slang_cache(db_path)
    
    result = apply_slang_normalization("gt 4os gtx", db_path)
    assert "giant thresher" in result.lower(), f"Expected 'giant thresher' in '{result}'"
    assert "gtx" in result.lower(), f"Expected 'gtx' to remain unchanged in '{result}'"
    print(f"  ✓ 'gt 4os gtx' -> '{result}' (gtx preserved)")


def main():
    print("=" * 60)
    print("Testing Slang Alias Integration")
    print("=" * 60)
    
    db_path = create_test_db()
    
    try:
        test_load_slang_aliases(db_path)
        test_apply_slang_normalization_base_aliases(db_path)
        test_apply_slang_normalization_item_aliases(db_path)
        test_normalize_item_hint_with_slang(db_path)
        test_slang_normalization_case_insensitive(db_path)
        test_slang_normalization_word_boundaries(db_path)
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
