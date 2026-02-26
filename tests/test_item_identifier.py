"""Unit tests for ItemIdentifier class."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from src.d2lut.overlay.item_identifier import ItemIdentifier, MatchResult, CatalogItem
from src.d2lut.overlay.ocr_parser import ParsedItem


@pytest.fixture
def test_db():
    """Create a temporary test database with catalog and slang data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name
    
    conn = sqlite3.connect(db_path)
    
    # Create catalog_items table
    conn.execute("""
        CREATE TABLE catalog_items (
            canonical_item_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quality_class TEXT NOT NULL,
            base_code TEXT,
            source_table TEXT NOT NULL,
            source_key TEXT,
            tradeable INTEGER NOT NULL DEFAULT 1,
            enabled INTEGER NOT NULL DEFAULT 1,
            metadata_json TEXT
        )
    """)
    
    # Create catalog_aliases table
    conn.execute("""
        CREATE TABLE catalog_aliases (
            id INTEGER PRIMARY KEY,
            alias_norm TEXT NOT NULL,
            alias_raw TEXT NOT NULL,
            canonical_item_id TEXT NOT NULL,
            alias_type TEXT NOT NULL DEFAULT 'name',
            priority INTEGER NOT NULL DEFAULT 100,
            source TEXT NOT NULL DEFAULT 'catalog_seed',
            UNIQUE(alias_norm, canonical_item_id),
            FOREIGN KEY(canonical_item_id) REFERENCES catalog_items(canonical_item_id)
        )
    """)
    
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
    
    # Insert test catalog items
    catalog_items = [
        ("harlequin_crest", "Harlequin Crest", "unique", "unique", "shako", "catalog_uniques", "shako", 1, 1),
        ("stone_of_jordan", "Stone of Jordan", "unique", "unique", "ring", "catalog_uniques", "soj", 1, 1),
        ("ber_rune", "Ber Rune", "rune", "misc", None, "catalog_runes", "ber", 1, 1),
        ("giant_thresher", "Giant Thresher", "base", "base", "gt", "catalog_bases", "gt", 1, 1),
    ]
    
    for item in catalog_items:
        conn.execute("""
            INSERT INTO catalog_items 
            (canonical_item_id, display_name, category, quality_class, base_code, 
             source_table, source_key, tradeable, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, item)
    
    # Insert test aliases
    aliases = [
        ("harlequin crest", "Harlequin Crest", "harlequin_crest", "name", 10),
        ("shako", "Shako", "harlequin_crest", "shorthand", 20),
        ("stone of jordan", "Stone of Jordan", "stone_of_jordan", "name", 10),
        ("soj", "SoJ", "stone_of_jordan", "shorthand", 20),
        ("ber rune", "Ber Rune", "ber_rune", "name", 10),
        ("ber", "Ber", "ber_rune", "shorthand", 20),
        ("giant thresher", "Giant Thresher", "giant_thresher", "name", 10),
        ("gt", "GT", "giant_thresher", "shorthand", 20),
    ]
    
    for alias_norm, alias_raw, canonical_id, alias_type, priority in aliases:
        conn.execute("""
            INSERT INTO catalog_aliases 
            (alias_norm, alias_raw, canonical_item_id, alias_type, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (alias_norm, alias_raw, canonical_id, alias_type, priority))
    
    # Insert test slang
    slang_data = [
        ("shako", "Shako", "item_alias", "harlequin_crest", "Harlequin Crest", 0.95),
        ("soj", "SoJ", "item_alias", "stone_of_jordan", "Stone of Jordan", 0.98),
    ]
    
    for term_norm, term_raw, term_type, canonical_id, replacement, confidence in slang_data:
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


def test_item_identifier_init(test_db):
    """Test ItemIdentifier initialization."""
    identifier = ItemIdentifier(test_db)
    assert identifier.db_path == Path(test_db)
    assert len(identifier._catalog_cache) > 0
    assert len(identifier._alias_cache) > 0


def test_item_identifier_init_missing_db():
    """Test ItemIdentifier initialization with missing database."""
    with pytest.raises(FileNotFoundError):
        ItemIdentifier("/nonexistent/path.db")


def test_identify_exact_match(test_db):
    """Test identifying an item with exact name match."""
    identifier = ItemIdentifier(test_db)
    
    parsed = ParsedItem(
        raw_text="Harlequin Crest\nShako",
        item_name="Harlequin Crest",
        confidence=0.95
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id == "harlequin_crest"
    assert result.match_type == "exact"
    assert result.confidence == 0.95
    assert result.matched_name == "Harlequin Crest"
    assert len(result.candidates) > 0


def test_identify_slang_match(test_db):
    """Test identifying an item using slang term."""
    identifier = ItemIdentifier(test_db)
    
    parsed = ParsedItem(
        raw_text="Shako\nUnique Shako",
        item_name="Shako",
        confidence=0.90
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id == "harlequin_crest"
    assert result.match_type == "slang"
    assert result.matched_name == "Harlequin Crest"
    assert "slang_term" in result.context_used


def test_identify_fuzzy_match(test_db):
    """Test identifying an item with fuzzy matching."""
    identifier = ItemIdentifier(test_db, fuzzy_threshold=0.7)
    
    parsed = ParsedItem(
        raw_text="Harlequn Crest",  # Typo
        item_name="Harlequn Crest",
        confidence=0.85
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id == "harlequin_crest"
    assert result.match_type == "fuzzy"
    assert result.confidence < 0.85  # Reduced due to fuzzy match
    assert len(result.candidates) > 0


def test_identify_case_insensitive(test_db):
    """Test that identification is case-insensitive."""
    identifier = ItemIdentifier(test_db)
    
    parsed = ParsedItem(
        raw_text="HARLEQUIN CREST",
        item_name="HARLEQUIN CREST",
        confidence=0.95
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id == "harlequin_crest"
    assert result.match_type == "exact"


def test_identify_with_item_type_filter(test_db):
    """Test identifying an item with item type filtering."""
    identifier = ItemIdentifier(test_db)
    
    parsed = ParsedItem(
        raw_text="Ber Rune",
        item_name="Ber",
        item_type="rune",
        confidence=0.95
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id == "ber_rune"
    assert result.match_type in ["exact", "slang"]


def test_identify_no_match(test_db):
    """Test identifying an item with no match."""
    identifier = ItemIdentifier(test_db, fuzzy_threshold=0.95)
    
    parsed = ParsedItem(
        raw_text="Nonexistent Item",
        item_name="Nonexistent Item",
        confidence=0.90
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id is None
    assert result.match_type == "no_match"
    assert result.confidence == 0.0
    assert len(result.candidates) == 0


def test_identify_with_parsing_error(test_db):
    """Test identifying an item with parsing error."""
    identifier = ItemIdentifier(test_db)
    
    parsed = ParsedItem(
        raw_text="",
        item_name=None,
        error="OCR failed",
        confidence=0.0
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id is None
    assert result.match_type == "error"
    assert result.confidence == 0.0


def test_resolve_slang(test_db):
    """Test resolving slang terms."""
    identifier = ItemIdentifier(test_db)
    
    result = identifier.resolve_slang("Trading Shako for SoJ")
    
    assert "Harlequin Crest" in result
    assert "Stone of Jordan" in result


def test_find_candidates_by_name(test_db):
    """Test finding candidates by name."""
    identifier = ItemIdentifier(test_db)
    
    candidates = identifier.find_candidates("Harlequin Crest")
    
    assert len(candidates) > 0
    assert any(c.canonical_item_id == "harlequin_crest" for c in candidates)


def test_find_candidates_with_type_filter(test_db):
    """Test finding candidates with item type filter."""
    identifier = ItemIdentifier(test_db)
    
    candidates = identifier.find_candidates("Ber", item_type="rune")
    
    assert len(candidates) > 0
    assert all(c.category == "rune" for c in candidates)


def test_find_candidates_fuzzy(test_db):
    """Test finding candidates with fuzzy matching."""
    identifier = ItemIdentifier(test_db, fuzzy_threshold=0.7)
    
    candidates = identifier.find_candidates("Harlequn")  # Typo
    
    assert len(candidates) > 0
    assert any(c.canonical_item_id == "harlequin_crest" for c in candidates)


def test_find_candidates_no_match(test_db):
    """Test finding candidates with no match."""
    identifier = ItemIdentifier(test_db, fuzzy_threshold=0.95)
    
    candidates = identifier.find_candidates("Completely Different Item")
    
    assert len(candidates) == 0


def test_reload_cache(test_db):
    """Test reloading the catalog cache."""
    identifier = ItemIdentifier(test_db)
    
    initial_count = len(identifier._catalog_cache)
    
    # Add new item to database
    conn = sqlite3.connect(test_db)
    conn.execute("""
        INSERT INTO catalog_items 
        (canonical_item_id, display_name, category, quality_class, 
         source_table, tradeable, enabled)
        VALUES ('jah_rune', 'Jah Rune', 'rune', 'misc', 'catalog_runes', 1, 1)
    """)
    conn.execute("""
        INSERT INTO catalog_aliases 
        (alias_norm, alias_raw, canonical_item_id, alias_type, priority)
        VALUES ('jah rune', 'Jah Rune', 'jah_rune', 'name', 10)
    """)
    conn.commit()
    conn.close()
    
    # Reload cache
    identifier.reload_cache()
    
    # Should have one more item
    assert len(identifier._catalog_cache) == initial_count + 1
    assert "jah_rune" in identifier._catalog_cache


def test_multiple_candidates_ambiguous(test_db):
    """Test handling ambiguous matches with multiple candidates."""
    # Add another item with similar name
    conn = sqlite3.connect(test_db)
    conn.execute("""
        INSERT INTO catalog_items 
        (canonical_item_id, display_name, category, quality_class, 
         source_table, tradeable, enabled)
        VALUES ('harlequin_crest_eth', 'Ethereal Harlequin Crest', 'unique', 'unique', 
                'catalog_uniques', 1, 1)
    """)
    conn.execute("""
        INSERT INTO catalog_aliases 
        (alias_norm, alias_raw, canonical_item_id, alias_type, priority)
        VALUES ('harlequin crest', 'Harlequin Crest', 'harlequin_crest_eth', 'name', 15)
    """)
    conn.commit()
    conn.close()
    
    identifier = ItemIdentifier(test_db)
    
    parsed = ParsedItem(
        raw_text="Harlequin Crest",
        item_name="Harlequin Crest",
        confidence=0.95
    )
    
    result = identifier.identify(parsed)
    
    # Should return the highest priority match
    assert result.canonical_item_id in ["harlequin_crest", "harlequin_crest_eth"]
    # Should have multiple candidates
    assert len(result.candidates) >= 2
