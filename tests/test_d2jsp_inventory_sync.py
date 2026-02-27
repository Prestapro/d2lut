"""Unit tests for d2jsp Inventory Sync.

Tests FT list generation, ISO parsing, and trade matching.
"""

from d2lut.overlay.d2jsp_inventory_sync import (
    FTListGenerator,
    ISOListParser,
    TradeMatcher,
    TradeItem,
    FTList,
    ISOList,
    TradeMatch,
    export_ft_list,
    parse_iso_list,
    find_trade_matches,
)


class TestFTListGenerator:
    """Tests for FT list generation."""
    
    def setup_method(self):
        self.generator = FTListGenerator(use_bb_code=False, use_icons=False)
        self.sample_items = [
            TradeItem(name="Jah Rune", price_fg=50.0, category="rune"),
            TradeItem(name="Ber Rune", price_fg=55.0, category="rune"),
            TradeItem(name="Shako", price_fg=35.0, category="unique", premium_info="15ed"),
            TradeItem(name="Arachnid Mesh", price_fg=28.0, category="unique"),
        ]
    
    def test_generate_standard_format(self):
        """Test standard format generation."""
        result = self.generator.generate_ft_post(
            self.sample_items,
            title="Items For Trade",
            format_style="standard",
        )
        
        assert "Items For Trade" in result
        assert "Jah Rune" in result
        assert "Ber Rune" in result
        assert "50 fg" in result
        assert "Total Value" in result
    
    def test_generate_compact_format(self):
        """Test compact format generation."""
        result = self.generator.generate_ft_post(
            self.sample_items,
            format_style="compact",
        )
        
        # Compact should have multiple items per line (|)
        assert "|" in result
    
    def test_generate_categorized_format(self):
        """Test categorized format generation."""
        result = self.generator.generate_ft_post(
            self.sample_items,
            format_style="categorized",
        )
        
        # Should have category headers
        assert "RUNE" in result or "rune" in result.lower()
        assert "UNIQUE" in result or "unique" in result.lower()
    
    def test_total_value_calculation(self):
        """Test total value is calculated correctly."""
        result = self.generator.generate_ft_post(self.sample_items)
        
        # 50 + 55 + 35 + 28 = 168
        assert "168" in result
    
    def test_premium_info_display(self):
        """Test premium info is shown."""
        result = self.generator.generate_ft_post(self.sample_items)
        
        assert "15ed" in result
    
    def test_iso_section(self):
        """Test ISO items section."""
        iso_items = [
            TradeItem(name="Enigma", price_fg=50.0, is_ft=False, category="runeword"),
        ]
        
        result = self.generator.generate_ft_post(
            self.sample_items,
            iso_items=iso_items,
        )
        
        assert "ISO" in result
        assert "Enigma" in result
    
    def test_bb_code_enabled(self):
        """Test BB code formatting."""
        generator = FTListGenerator(use_bb_code=True, use_icons=False)
        result = generator.generate_ft_post(self.sample_items)
        
        assert "[b]" in result or "[size=" in result


class TestISOListParser:
    """Tests for ISO list parsing."""
    
    def setup_method(self):
        self.parser = ISOListParser()
    
    def test_parse_runes(self):
        """Test parsing rune ISO."""
        text = """
        ISO:
        - Jah Rune - budget 45 fg
        - Ber Rune - paying 50 fg
        """
        
        result = self.parser.parse_iso_text(text)
        
        assert len(result.items) >= 1
        # At least one rune should be parsed
    
    def test_parse_items_with_prices(self):
        """Test parsing items with FG prices."""
        text = """
        Looking for:
        Shako - 30 fg
        Arach - 25 fg budget
        """
        
        result = self.parser.parse_iso_text(text)
        
        # Should parse some items
        assert isinstance(result, ISOList)
    
    def test_parse_runewords(self):
        """Test parsing runeword names."""
        text = "ISO Enigma, Infinity, CTA"
        
        result = self.parser.parse_iso_text(text)
        
        # Should find runewords
        assert len(result.items) >= 1


class TestTradeMatcher:
    """Tests for trade matching."""
    
    def setup_method(self):
        self.matcher = TradeMatcher()
    
    def test_exact_match(self):
        """Test exact name match."""
        ft_items = [
            TradeItem(name="Jah Rune", price_fg=50.0, category="rune", is_ft=True),
        ]
        iso_items = [
            TradeItem(name="Jah Rune", price_fg=55.0, category="rune", is_ft=False),
        ]
        
        matches = self.matcher.find_matches(ft_items, iso_items)
        
        assert len(matches) >= 1
        assert matches[0].match_score >= 0.8
        assert matches[0].price_match is True
    
    def test_partial_match(self):
        """Test partial name match."""
        ft_items = [
            TradeItem(name="Shako", price_fg=35.0, category="unique", is_ft=True),
        ]
        iso_items = [
            TradeItem(name="Harlequin Crest Shako", price_fg=40.0, category="unique", is_ft=False),
        ]
        
        matches = self.matcher.find_matches(ft_items, iso_items)
        
        # Should match because names overlap
        assert len(matches) >= 1
    
    def test_price_mismatch(self):
        """Test price mismatch detection."""
        ft_items = [
            TradeItem(name="Jah Rune", price_fg=50.0, category="rune", is_ft=True),
        ]
        iso_items = [
            TradeItem(name="Jah Rune", price_fg=30.0, category="rune", is_ft=False),
        ]
        
        matches = self.matcher.find_matches(ft_items, iso_items)
        
        # Match should exist but price_match should be False
        assert len(matches) >= 1
        assert matches[0].price_match is False
    
    def test_no_match(self):
        """Test when no matches exist."""
        ft_items = [
            TradeItem(name="Jah Rune", price_fg=50.0, category="rune", is_ft=True),
        ]
        iso_items = [
            TradeItem(name="Monarch", price_fg=5.0, category="base", is_ft=False),
        ]
        
        matches = self.matcher.find_matches(ft_items, iso_items)
        
        # Should be no match or very low score
        assert len(matches) == 0 or matches[0].match_score < 0.5


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_export_ft_list(self):
        """Test export_ft_list function."""
        items = [
            {"name": "Jah Rune", "price_fg": 50.0, "category": "rune"},
            {"name": "Shako", "price_fg": 35.0, "category": "unique", "premium_info": "15ed"},
        ]
        
        result = export_ft_list(items, format_style="standard")
        
        assert "Jah Rune" in result
        assert "Shako" in result
        assert "50" in result
    
    def test_parse_iso_list(self):
        """Test parse_iso_list function."""
        text = "ISO Jah Rune, Ber Rune"
        
        result = parse_iso_list(text)
        
        assert isinstance(result, ISOList)
    
    def test_find_trade_matches(self):
        """Test find_trade_matches function."""
        ft = [
            {"name": "Jah Rune", "price_fg": 50.0, "category": "rune", "is_ft": True},
        ]
        iso = [
            {"name": "Jah Rune", "price_fg": 55.0, "category": "rune", "is_ft": False},
        ]
        
        result = find_trade_matches(ft, iso)
        
        assert isinstance(result, list)
        if result:
            assert "ft_name" in result[0]
            assert "match_score" in result[0]


class TestTradeItem:
    """Tests for TradeItem dataclass."""
    
    def test_trade_item_creation(self):
        """Test TradeItem creation."""
        item = TradeItem(
            name="Jah Rune",
            canonical_id="rune:jah",
            price_fg=50.0,
            quantity=2,
            notes="Perfect for Enigma",
            category="rune",
        )
        
        assert item.name == "Jah Rune"
        assert item.price_fg == 50.0
        assert item.quantity == 2
        assert item.is_ft is True  # Default
        assert item.category == "rune"


class TestFTList:
    """Tests for FTList dataclass."""
    
    def test_ft_list_creation(self):
        """Test FTList creation."""
        items = [
            TradeItem(name="Jah", price_fg=50.0, category="rune"),
        ]
        
        ft = FTList(items=items, total_value_fg=50.0, title="My FT List")
        
        assert len(ft.items) == 1
        assert ft.total_value_fg == 50.0
        assert ft.title == "My FT List"


class TestISOList:
    """Tests for ISOList dataclass."""
    
    def test_iso_list_creation(self):
        """Test ISOList creation."""
        items = [
            TradeItem(name="Enigma", price_fg=55.0, is_ft=False, category="runeword"),
        ]
        
        iso = ISOList(items=items, budget_fg=100.0)
        
        assert len(iso.items) == 1
        assert iso.budget_fg == 100.0
