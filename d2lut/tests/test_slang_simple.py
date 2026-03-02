"""Tests for slang normalization and item pattern detection."""

import pytest
from pathlib import Path

from d2lut.patterns import find_items_in_text, find_best_price_in_text, ITEM_PATTERNS


class TestItemPatterns:
    """Tests for item pattern detection."""

    def test_find_items_jah_rune(self):
        """Test finding Jah rune in text."""
        text = "WTS Jah rune 150fg"
        items = find_items_in_text(text)
        assert "rune:jah" in items

    def test_find_items_enigma(self):
        """Test finding Enigma runeword in text."""
        text = "Selling enigma armor for 200fg"
        items = find_items_in_text(text)
        assert "runeword:enigma" in items

    def test_find_items_shako(self):
        """Test finding Shako unique in text."""
        text = "WTS shako 20fg bin"
        items = find_items_in_text(text)
        assert "unique:shako" in items

    def test_find_items_multiple(self):
        """Test finding multiple items in text."""
        text = "WTS Jah Ber and enigma, also shako available"
        items = find_items_in_text(text)
        assert "rune:jah" in items
        assert "rune:ber" in items
        assert "runeword:enigma" in items
        assert "unique:shako" in items

    def test_find_items_no_match(self):
        """Test when no items match."""
        text = "Hello world, how are you?"
        items = find_items_in_text(text)
        assert len(items) == 0

    def test_no_duplicate_botd(self):
        """Test that BotD is not duplicated (it's only a runeword, not unique)."""
        text = "WTS BotD eth 300fg"
        items = find_items_in_text(text)
        # Should find runeword:botd, but NOT unique:botd
        assert "runeword:botd" in items
        assert "unique:botd" not in items

    def test_no_duplicate_phoenix(self):
        """Test that Phoenix weapon and shield are properly separated."""
        text = "WTS phoenix shield 100fg"
        items = find_items_in_text(text)
        # phoenix shield should match phoenixshield
        assert "runeword:phoenixshield" in items

    def test_cta_vs_hoto(self):
        """Test that CTA and HotO are properly separated."""
        text = "WTS CTA 50fg"
        items = find_items_in_text(text)
        assert "runeword:cta" in items
        assert "runeword:hoto" not in items

        text2 = "WTS HotO 40fg"
        items2 = find_items_in_text(text2)
        assert "runeword:hoto" in items2
        assert "runeword:cta" not in items2


class TestPricePatterns:
    """Tests for price pattern detection."""

    def test_find_price_sold(self):
        """Test finding sold price."""
        text = "Sold 150fg for Jah rune"
        price = find_best_price_in_text(text)
        assert price is not None
        assert price["price"] == 150.0
        assert price["signal_kind"] == "sold"
        assert price["confidence"] == 0.9

    def test_find_price_bin(self):
        """Test finding BIN price."""
        text = "WTS Jah BIN 100"
        price = find_best_price_in_text(text)
        assert price is not None
        assert price["price"] == 100.0
        assert price["signal_kind"] == "bin"
        assert price["confidence"] == 0.8

    def test_find_price_fg(self):
        """Test finding FG price."""
        text = "WTS Jah 150 fg"
        price = find_best_price_in_text(text)
        assert price is not None
        assert price["price"] == 150.0
        assert price["signal_kind"] == "fg"

    def test_best_price_priority(self):
        """Test that SOLD has higher priority than BIN."""
        text = "BIN 100 but SOLD 150"
        price = find_best_price_in_text(text)
        assert price is not None
        # SOLD has higher confidence (0.9) than BIN (0.8)
        assert price["confidence"] == 0.9

    def test_no_price_found(self):
        """Test when no price is found."""
        text = "Just some random text without prices"
        price = find_best_price_in_text(text)
        assert price is None


class TestPatternKeys:
    """Tests for pattern key consistency."""

    def test_no_spaces_in_keys(self):
        """Test that no keys have spaces after colon."""
        for key in ITEM_PATTERNS.keys():
            # Key format should be "category:itemname" with no spaces after colon
            if ":" in key:
                parts = key.split(":")
                # No space after colon
                assert not parts[1].startswith(" "), f"Key '{key}' has space after colon"

    def test_all_keys_lowercase(self):
        """Test that all keys follow consistent format."""
        for key in ITEM_PATTERNS.keys():
            # Category part should be lowercase
            if ":" in key:
                category = key.split(":")[0]
                assert category.islower(), f"Category in '{key}' should be lowercase"

    def test_oath_not_oice(self):
        """Test that 'oath' runeword key is correct, not 'oice'."""
        assert "runeword:oath" in ITEM_PATTERNS
        assert "runeword:oice" not in ITEM_PATTERNS


class TestSlangAliases:
    """Tests for slang alias handling with actual d2lut code."""

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
