"""Pytest fixtures for d2lut test suite."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a temporary database with slang_aliases table for testing.
    
    Yields:
        Path to temporary SQLite database file.
    """
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    
    # Create slang_aliases table (used by test_slang_simple.py)
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
    
    # Insert default test aliases
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
    
    yield db_file
    # Cleanup happens automatically via tmp_path fixture
