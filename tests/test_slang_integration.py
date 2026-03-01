"""Tests for slang alias integration in d2jsp normalizer."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from d2lut.normalize.d2jsp_market import (
    apply_slang_normalization,
    init_slang_cache,
    normalize_item_hint,
)


@pytest.fixture
def test_db():
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
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


def test_load_slang_aliases(test_db):
    """Test loading slang aliases from database."""
    init_slang_cache(test_db)
    
    # Test that cache was initialized
    from d2lut.normalize.d2jsp_market import _SLANG_CACHE
    assert _SLANG_CACHE is not None
    assert "gt" in _SLANG_CACHE
    assert "amy" in _SLANG_CACHE


def test_apply_slang_normalization_base_aliases(test_db):
    """Test that base aliases are applied correctly."""
    init_slang_cache(test_db)
    
    # Test base shorthand expansion
    result = apply_slang_normalization("4os gt eth", test_db)
    assert "giant thresher" in result.lower()
    
    result = apply_slang_normalization("cv 4os", test_db)
    assert "colossus voulge" in result.lower()
    
    result = apply_slang_normalization("pb 5os", test_db)
    assert "phase blade" in result.lower()


def test_apply_slang_normalization_item_aliases(test_db):
    """Test that item aliases are applied correctly."""
    init_slang_cache(test_db)
    
    # Test item alias expansion
    result = apply_slang_normalization("tal amy bin 300", test_db)
    assert "tal ammy" in result.lower()


def test_normalize_item_hint_with_slang(test_db):
    """Test that normalize_item_hint uses slang aliases."""
    init_slang_cache(test_db)
    
    # Test that slang normalization is applied before pattern matching
    result = normalize_item_hint("4os gt eth")
    assert result is not None
    # Should match base pattern after slang expansion
    assert "base:" in result[0]


def test_slang_normalization_preserves_case_insensitivity(test_db):
    """Test that slang normalization works case-insensitively."""
    init_slang_cache(test_db)
    
    result1 = apply_slang_normalization("GT 4os", test_db)
    result2 = apply_slang_normalization("gt 4os", test_db)
    result3 = apply_slang_normalization("Gt 4os", test_db)
    
    # All should produce the same normalized result
    assert result1.lower() == result2.lower() == result3.lower()


def test_slang_normalization_without_cache():
    """Test that normalization works gracefully without cache."""
    # Reset cache
    from d2lut.normalize import d2jsp_market
    d2jsp_market._SLANG_CACHE = None
    
    # Should return text unchanged when no cache and no db_path
    result = apply_slang_normalization("gt 4os")
    assert result == "gt 4os"


def test_slang_normalization_word_boundaries(test_db):
    """Test that slang normalization respects word boundaries."""
    init_slang_cache(test_db)
    
    # "gt" should be replaced, but "gtx" should not
    result = apply_slang_normalization("gt 4os gtx", test_db)
    assert "giant thresher" in result.lower()
    assert "gtx" in result.lower()  # Should remain unchanged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
