"""Unit tests for SlangNormalizer class."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from src.d2lut.overlay.slang_normalizer import SlangNormalizer, SlangMatch


@pytest.fixture
def test_db():
    """Create a temporary test database with slang data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name
    
    conn = sqlite3.connect(db_path)
    
    # Create slang_aliases table
    conn.execute("""
        CREATE TABLE slang_aliases (
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
        )
    """)
    
    # Insert test data
    test_data = [
        ("shako", "Shako", "item_alias", "harlequin_crest", "Harlequin Crest", 0.95),
        ("soj", "SoJ", "item_alias", "stone_of_jordan", "Stone of Jordan", 0.98),
        ("bk", "BK", "item_alias", "bul_kathos_wedding_band", "Bul-Kathos' Wedding Band", 0.90),
        ("gt", "GT", "base_alias", "", "Giant Thresher", 0.85),
        ("eth", "eth", "stat_alias", "", "ethereal", 0.99),
        ("ber", "Ber", "item_alias", "ber_rune", "Ber Rune", 0.95),
    ]
    
    for term_norm, term_raw, term_type, canonical_id, replacement, confidence in test_data:
        conn.execute("""
            INSERT INTO slang_aliases 
            (term_norm, term_raw, term_type, canonical_item_id, replacement_text, confidence, enabled)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (term_norm, term_raw, term_type, canonical_id, replacement, confidence))
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink()


def test_slang_normalizer_init(test_db):
    """Test SlangNormalizer initialization."""
    normalizer = SlangNormalizer(test_db)
    assert normalizer.db_path == Path(test_db)
    assert len(normalizer._slang_cache) > 0


def test_slang_normalizer_init_missing_db():
    """Test SlangNormalizer initialization with missing database."""
    with pytest.raises(FileNotFoundError):
        SlangNormalizer("/nonexistent/path.db")


def test_find_slang_matches_single(test_db):
    """Test finding a single slang match."""
    normalizer = SlangNormalizer(test_db)
    
    matches = normalizer.find_slang_matches("I have a Shako for trade")
    
    assert len(matches) == 1
    assert matches[0].term_raw == "Shako"  # Original case from DB
    assert matches[0].canonical_item_id == "harlequin_crest"
    assert matches[0].replacement_text == "Harlequin Crest"
    assert matches[0].confidence == 0.95
    assert matches[0].match_position == (9, 14)


def test_find_slang_matches_multiple(test_db):
    """Test finding multiple slang matches."""
    normalizer = SlangNormalizer(test_db)
    
    matches = normalizer.find_slang_matches("Trading SoJ and BK for Ber")
    
    assert len(matches) == 3
    assert matches[0].term_raw == "SoJ"  # Original case from DB
    assert matches[1].term_raw == "BK"
    assert matches[2].term_raw == "Ber"


def test_find_slang_matches_case_insensitive(test_db):
    """Test that slang matching is case-insensitive."""
    normalizer = SlangNormalizer(test_db)
    
    matches = normalizer.find_slang_matches("SHAKO and shako and ShAkO")
    
    assert len(matches) == 3
    for match in matches:
        assert match.canonical_item_id == "harlequin_crest"


def test_find_slang_matches_no_overlap(test_db):
    """Test that overlapping matches are handled correctly."""
    normalizer = SlangNormalizer(test_db)
    
    # Add a longer term that contains a shorter one
    conn = sqlite3.connect(test_db)
    conn.execute("""
        INSERT INTO slang_aliases 
        (term_norm, term_raw, term_type, canonical_item_id, replacement_text, confidence, enabled)
        VALUES ('eth shako', 'eth shako', 'item_alias', 'eth_harlequin_crest', 'Ethereal Harlequin Crest', 0.99, 1)
    """)
    conn.commit()
    conn.close()
    
    # Reload cache
    normalizer.reload_cache()
    
    matches = normalizer.find_slang_matches("I have eth shako")
    
    # Should match the longer term, not both "eth" and "shako"
    assert len(matches) == 1
    assert matches[0].term_raw == "eth shako"
    assert matches[0].canonical_item_id == "eth_harlequin_crest"


def test_normalize_single_term(test_db):
    """Test normalizing text with a single slang term."""
    normalizer = SlangNormalizer(test_db)
    
    result = normalizer.normalize("I have a Shako")
    
    assert result == "I have a Harlequin Crest"


def test_normalize_multiple_terms(test_db):
    """Test normalizing text with multiple slang terms."""
    normalizer = SlangNormalizer(test_db)
    
    result = normalizer.normalize("Trading SoJ and BK for Ber")
    
    assert result == "Trading Stone of Jordan and Bul-Kathos' Wedding Band for Ber Rune"


def test_normalize_no_slang(test_db):
    """Test normalizing text with no slang terms."""
    normalizer = SlangNormalizer(test_db)
    
    result = normalizer.normalize("This is normal text")
    
    assert result == "This is normal text"


def test_normalize_preserves_case_outside_matches(test_db):
    """Test that normalization preserves case of non-matched text."""
    normalizer = SlangNormalizer(test_db)
    
    result = normalizer.normalize("TRADING shako FOR RUNES")
    
    assert result == "TRADING Harlequin Crest FOR RUNES"


def test_get_all_matches_single(test_db):
    """Test getting all matches for a slang term with single match."""
    normalizer = SlangNormalizer(test_db)
    
    matches = normalizer.get_all_matches("shako")
    
    assert len(matches) == 1
    assert matches[0]["canonical_item_id"] == "harlequin_crest"
    assert matches[0]["replacement_text"] == "Harlequin Crest"
    assert matches[0]["confidence"] == 0.95


def test_get_all_matches_ambiguous(test_db):
    """Test getting all matches for an ambiguous slang term."""
    # Add ambiguous term
    conn = sqlite3.connect(test_db)
    conn.execute("""
        INSERT INTO slang_aliases 
        (term_norm, term_raw, term_type, canonical_item_id, replacement_text, confidence, enabled)
        VALUES ('bk', 'BK', 'item_alias', 'bul_kathos_sacred_charge', 'Bul-Kathos'' Sacred Charge', 0.85, 1)
    """)
    conn.commit()
    conn.close()
    
    # Reload cache
    normalizer = SlangNormalizer(test_db)
    
    matches = normalizer.get_all_matches("bk")
    
    # Should return both matches, sorted by confidence
    assert len(matches) == 2
    assert matches[0]["confidence"] >= matches[1]["confidence"]


def test_get_all_matches_nonexistent(test_db):
    """Test getting matches for a non-existent slang term."""
    normalizer = SlangNormalizer(test_db)
    
    matches = normalizer.get_all_matches("nonexistent")
    
    assert len(matches) == 0


def test_reload_cache(test_db):
    """Test reloading the slang cache."""
    normalizer = SlangNormalizer(test_db)
    
    initial_count = len(normalizer._slang_cache)
    
    # Add new term to database
    conn = sqlite3.connect(test_db)
    conn.execute("""
        INSERT INTO slang_aliases 
        (term_norm, term_raw, term_type, canonical_item_id, replacement_text, confidence, enabled)
        VALUES ('jah', 'Jah', 'item_alias', 'jah_rune', 'Jah Rune', 0.95, 1)
    """)
    conn.commit()
    conn.close()
    
    # Reload cache
    normalizer.reload_cache()
    
    # Should have one more term
    assert len(normalizer._slang_cache) == initial_count + 1
    assert "jah" in normalizer._slang_cache


def test_disabled_slang_not_loaded(test_db):
    """Test that disabled slang terms are not loaded."""
    # Add disabled term
    conn = sqlite3.connect(test_db)
    conn.execute("""
        INSERT INTO slang_aliases 
        (term_norm, term_raw, term_type, canonical_item_id, replacement_text, confidence, enabled)
        VALUES ('disabled', 'disabled', 'item_alias', 'test_item', 'Test Item', 0.95, 0)
    """)
    conn.commit()
    conn.close()
    
    normalizer = SlangNormalizer(test_db)
    
    matches = normalizer.find_slang_matches("This is disabled")
    
    # Should not match the disabled term
    assert len(matches) == 0
