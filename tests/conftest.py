"""Pytest fixtures for d2lut tests."""

import tempfile
import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def db_path():
    """Create a temporary database for testing.
    
    Yields:
        Path to temporary database file
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    
    # Initialize with slang table
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS slang_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT UNIQUE NOT NULL,
            canonical TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    
    yield path
    
    # Cleanup
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def temp_db(db_path):
    """Create a database connection for testing.
    
    Yields:
        sqlite3.Connection to temporary database
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
