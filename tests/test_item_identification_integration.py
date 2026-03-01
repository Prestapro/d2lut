"""Integration tests for the complete item identification flow."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from src.d2lut.overlay.ocr_parser import ParsedItem
from src.d2lut.overlay.slang_normalizer import SlangNormalizer
from src.d2lut.overlay.item_identifier import ItemIdentifier


@pytest.fixture
def integrated_db():
    """Create a comprehensive test database with catalog and slang data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name
    
    conn = sqlite3.connect(db_path)
    
    # Create all required tables
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
    
    # Insert comprehensive test data
    catalog_items = [
        ("harlequin_crest", "Harlequin Crest", "unique", "unique", "shako", "catalog_uniques", "shako", 1, 1),
        ("stone_of_jordan", "Stone of Jordan", "unique", "unique", "ring", "catalog_uniques", "soj", 1, 1),
        ("ber_rune", "Ber Rune", "rune", "misc", None, "catalog_runes", "ber", 1, 1),
        ("jah_rune", "Jah Rune", "rune", "misc", None, "catalog_runes", "jah", 1, 1),
        ("giant_thresher", "Giant Thresher", "base", "base", "gt", "catalog_bases", "gt", 1, 1),
        ("enigma", "Enigma", "runeword", "runeword", None, "catalog_runewords", "enigma", 1, 1),
    ]
    
    for item in catalog_items:
        conn.execute("""
            INSERT INTO catalog_items 
            (canonical_item_id, display_name, category, quality_class, base_code, 
             source_table, source_key, tradeable, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, item)
    
    # Insert aliases
    aliases = [
        ("harlequin crest", "Harlequin Crest", "harlequin_crest", "name", 10),
        ("shako", "Shako", "harlequin_crest", "shorthand", 20),
        ("stone of jordan", "Stone of Jordan", "stone_of_jordan", "name", 10),
        ("soj", "SoJ", "stone_of_jordan", "shorthand", 20),
        ("ber rune", "Ber Rune", "ber_rune", "name", 10),
        ("ber", "Ber", "ber_rune", "shorthand", 20),
        ("jah rune", "Jah Rune", "jah_rune", "name", 10),
        ("jah", "Jah", "jah_rune", "shorthand", 20),
        ("giant thresher", "Giant Thresher", "giant_thresher", "name", 10),
        ("gt", "GT", "giant_thresher", "shorthand", 20),
        ("enigma", "Enigma", "enigma", "name", 10),
    ]
    
    for alias_norm, alias_raw, canonical_id, alias_type, priority in aliases:
        conn.execute("""
            INSERT INTO catalog_aliases 
            (alias_norm, alias_raw, canonical_item_id, alias_type, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (alias_norm, alias_raw, canonical_id, alias_type, priority))
    
    # Insert slang terms
    slang_data = [
        ("shako", "Shako", "item_alias", "harlequin_crest", "Harlequin Crest", 0.95),
        ("soj", "SoJ", "item_alias", "stone_of_jordan", "Stone of Jordan", 0.98),
        ("ber", "Ber", "item_alias", "ber_rune", "Ber Rune", 0.95),
        ("jah", "Jah", "item_alias", "jah_rune", "Jah Rune", 0.95),
        ("gt", "GT", "base_alias", "", "Giant Thresher", 0.85),
        ("eth", "eth", "stat_alias", "", "ethereal", 0.99),
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


def test_end_to_end_exact_match(integrated_db):
    """Test complete flow with exact item name match."""
    identifier = ItemIdentifier(integrated_db)
    
    # Simulate OCR parsing result
    parsed = ParsedItem(
        raw_text="Harlequin Crest\nShako\nDefense: 141",
        item_name="Harlequin Crest",
        item_type="unique",
        quality="unique",
        confidence=0.95
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id == "harlequin_crest"
    assert result.match_type == "exact"
    assert result.matched_name == "Harlequin Crest"
    assert result.confidence == 0.95
    assert len(result.candidates) > 0


def test_end_to_end_slang_resolution(integrated_db):
    """Test complete flow with slang term resolution."""
    identifier = ItemIdentifier(integrated_db)
    
    # Simulate OCR parsing with slang term
    parsed = ParsedItem(
        raw_text="Shako\nDefense: 141",
        item_name="Shako",
        confidence=0.90
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id == "harlequin_crest"
    assert result.match_type == "slang"
    assert result.matched_name == "Harlequin Crest"
    assert "slang_term" in result.context_used


def test_end_to_end_fuzzy_match(integrated_db):
    """Test complete flow with fuzzy matching."""
    identifier = ItemIdentifier(integrated_db, fuzzy_threshold=0.7)
    
    # Simulate OCR parsing with typo
    parsed = ParsedItem(
        raw_text="Harlequn Crest",  # Typo
        item_name="Harlequn Crest",
        confidence=0.85
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id == "harlequin_crest"
    assert result.match_type == "fuzzy"
    assert result.confidence < 0.85  # Reduced due to fuzzy match


def test_end_to_end_multiple_items(integrated_db):
    """Test identifying multiple items in sequence."""
    identifier = ItemIdentifier(integrated_db)
    
    items = [
        ParsedItem(raw_text="Shako", item_name="Shako", confidence=0.90),
        ParsedItem(raw_text="SoJ", item_name="SoJ", confidence=0.92),
        ParsedItem(raw_text="Ber Rune", item_name="Ber Rune", confidence=0.95),
    ]
    
    results = [identifier.identify(item) for item in items]
    
    assert results[0].canonical_item_id == "harlequin_crest"
    assert results[1].canonical_item_id == "stone_of_jordan"
    assert results[2].canonical_item_id == "ber_rune"


def test_end_to_end_with_item_type_context(integrated_db):
    """Test identification with item type context."""
    identifier = ItemIdentifier(integrated_db)
    
    # "Ber" could be ambiguous, but with type context it's clear
    parsed = ParsedItem(
        raw_text="Ber",
        item_name="Ber",
        item_type="rune",
        confidence=0.95
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id == "ber_rune"
    assert result.match_type in ["exact", "slang"]


def test_end_to_end_no_match(integrated_db):
    """Test handling of unrecognized items."""
    identifier = ItemIdentifier(integrated_db, fuzzy_threshold=0.95)
    
    parsed = ParsedItem(
        raw_text="Completely Unknown Item",
        item_name="Completely Unknown Item",
        confidence=0.90
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id is None
    assert result.match_type == "no_match"
    assert result.confidence == 0.0


def test_end_to_end_parsing_error(integrated_db):
    """Test handling of OCR parsing errors."""
    identifier = ItemIdentifier(integrated_db)
    
    parsed = ParsedItem(
        raw_text="",
        item_name=None,
        error="OCR confidence too low",
        confidence=0.0
    )
    
    result = identifier.identify(parsed)
    
    assert result.canonical_item_id is None
    assert result.match_type == "error"
    assert result.confidence == 0.0


def test_slang_normalizer_standalone(integrated_db):
    """Test SlangNormalizer as standalone component."""
    normalizer = SlangNormalizer(integrated_db)
    
    # Test normalization
    text = "Trading Shako and SoJ for Ber + Jah"
    normalized = normalizer.normalize(text)
    
    assert "Harlequin Crest" in normalized
    assert "Stone of Jordan" in normalized
    assert "Ber Rune" in normalized
    assert "Jah Rune" in normalized


def test_slang_normalizer_with_base_alias(integrated_db):
    """Test slang normalization with base item aliases."""
    normalizer = SlangNormalizer(integrated_db)
    
    text = "eth GT"
    normalized = normalizer.normalize(text)
    
    assert "ethereal" in normalized
    assert "Giant Thresher" in normalized


def test_identifier_resolve_slang_method(integrated_db):
    """Test the resolve_slang method of ItemIdentifier."""
    identifier = ItemIdentifier(integrated_db)
    
    text = "WTB Shako and SoJ"
    resolved = identifier.resolve_slang(text)
    
    assert "Harlequin Crest" in resolved
    assert "Stone of Jordan" in resolved


def test_identifier_find_candidates(integrated_db):
    """Test finding candidates with various filters."""
    identifier = ItemIdentifier(integrated_db)
    
    # Find by name
    candidates = identifier.find_candidates("Harlequin Crest")
    assert len(candidates) > 0
    assert any(c.canonical_item_id == "harlequin_crest" for c in candidates)
    
    # Find by type
    rune_candidates = identifier.find_candidates("Ber", item_type="rune")
    assert len(rune_candidates) > 0
    assert all(c.category == "rune" for c in rune_candidates)


def test_cache_reload(integrated_db):
    """Test cache reloading after database updates."""
    identifier = ItemIdentifier(integrated_db)
    
    # Add new item to database
    conn = sqlite3.connect(integrated_db)
    conn.execute("""
        INSERT INTO catalog_items 
        (canonical_item_id, display_name, category, quality_class, 
         source_table, tradeable, enabled)
        VALUES ('sur_rune', 'Sur Rune', 'rune', 'misc', 'catalog_runes', 1, 1)
    """)
    conn.execute("""
        INSERT INTO catalog_aliases 
        (alias_norm, alias_raw, canonical_item_id, alias_type, priority)
        VALUES ('sur rune', 'Sur Rune', 'sur_rune', 'name', 10)
    """)
    conn.commit()
    conn.close()
    
    # Reload cache
    identifier.reload_cache()
    
    # Should now find the new item
    parsed = ParsedItem(
        raw_text="Sur Rune",
        item_name="Sur Rune",
        confidence=0.95
    )
    
    result = identifier.identify(parsed)
    assert result.canonical_item_id == "sur_rune"
