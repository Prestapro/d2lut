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
        # Should NOT match weapon phoenix (negative lookahead working)
        assert "runeword:phoenix" not in items

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

    def test_lava_gout_is_unique_not_set(self):
        """Test that Lava Gout is correctly identified as UNIQUE, not SET."""
        text = "WTS lava gout 10fg"
        items = find_items_in_text(text)
        # Lava Gout is a UNIQUE item, not a set item
        assert "unique:lavagout" in items
        # Should NOT be in set category
        assert "set:lava" not in items
        
    def test_laying_of_hands_is_set(self):
        """Test that Laying of Hands is correctly identified as SET."""
        text = "WTS laying of hands 15fg"
        items = find_items_in_text(text)
        # Laying of Hands is a SET item (Disciple set)
        assert "set:layingofhands" in items


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
        # SOLD price should be selected, not BIN price
        assert price["price"] == 150.0
        assert price["signal_kind"] == "sold"

    def test_no_price_found(self):
        """Test when no price is found."""
        text = "Just some random text without prices"
        price = find_best_price_in_text(text)
        assert price is None

    def test_zero_price_ignored(self):
        """Test that zero prices are ignored (not free/giveaway posts)."""
        text = "sold: 0 enigma"
        price = find_best_price_in_text(text)
        assert price is None  # Zero price should be ignored

        text2 = "bin 0 shako"  
        price2 = find_best_price_in_text(text2)
        assert price2 is None  # Zero price should be ignored


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
    """Tests for slang alias handling.

    NOTE: These tests verify database schema functionality but the main
    d2lut code currently uses hardcoded patterns in patterns.py instead
    of database lookups. This is a placeholder for future enhancement.

    See: https://github.com/Prestapro/d2lut/issues/XX
    """

    @pytest.mark.skip(reason="slang_aliases table not used by main code yet - placeholder for future feature")
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

    @pytest.mark.skip(reason="slang_aliases table not used by main code yet - placeholder for future feature")
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

    def test_pattern_based_detection_works(self):
        """Test that current pattern-based detection works for common slang."""
        # This test verifies the CURRENT implementation works
        # without needing database slang_aliases

        # Common slang should work via patterns.py
        text = "WTS shako cta jah ber"
        items = find_items_in_text(text)

        assert "unique:shako" in items
        assert "runeword:cta" in items
        assert "rune:jah" in items
        assert "rune:ber" in items
