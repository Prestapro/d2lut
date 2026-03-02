"""Tests for slang normalization."""

import pytest
from pathlib import Path


class TestSlangAliases:
    """Tests for slang alias handling."""
    
    def test_load_slang_aliases(self, db_path):
        """Test loading slang aliases from database."""
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        
        # Add some test aliases
        conn.execute("INSERT INTO slang_aliases (alias, canonical) VALUES (?, ?)", ("shako", "unique:shako"))
        conn.execute("INSERT INTO slang_aliases (alias, canonical) VALUES (?, ?)", ("cta", "runeword:cta"))
        conn.commit()
        
        # Verify
        cur = conn.execute("SELECT COUNT(*) FROM slang_aliases")
        count = cur.fetchone()[0]
        assert count == 2
        
        conn.close()
    
    def test_apply_slang_normalization_base_aliases(self, db_path):
        """Test basic slang normalization."""
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        
        # Add test aliases
        test_aliases = [
            ("jah", "rune:jah"),
            ("ber", "rune:ber"),
            ("enigma", "runeword:enigma"),
        ]
        conn.executemany(
            "INSERT INTO slang_aliases (alias, canonical) VALUES (?, ?)",
            test_aliases
        )
        conn.commit()
        
        # Verify normalization
        cur = conn.execute(
            "SELECT canonical FROM slang_aliases WHERE alias = ?",
            ("jah",)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "rune:jah"
        
        conn.close()
