"""Tests for Magic Item Pricer."""

import pytest
from pathlib import Path

from d2lut.exporters.magic_item_pricer import (
    MagicItemPricer,
    ExtendedAffixHighlighter,
    AffixPriceResult,
    get_magic_item_display,
)


class TestMagicItemPricer:
    """Tests for MagicItemPricer."""
    
    def setup_method(self):
        self.pricer = MagicItemPricer()
    
    def test_pricer_initialization(self):
        """Test pricer initializes without errors."""
        assert self.pricer is not None
        assert isinstance(self.pricer.combinations, dict)
    
    def test_price_jmod(self):
        """Test pricing JMOD (Jeweler's of Deflecting)."""
        result = self.pricer.price_item(
            prefix="Jeweler's",
            suffix="of Deflecting",
            item_type="uit",  # Monarch
            ilvl=50,
            roll_percent=50.0,
        )
        
        assert isinstance(result, AffixPriceResult)
        assert result.estimated_fg > 0
        assert result.tier in ("gg", "high", "medium", "low")
    
    def test_price_caster_amulet(self):
        """Test pricing caster amulet (+2 skills / FCR)."""
        result = self.pricer.price_item(
            prefix="Arch-Angel's",
            suffix="of the Magus",
            item_type="amu",
            ilvl=90,
            roll_percent=80.0,
        )
        
        assert result.estimated_fg > 0
        # High ilvl should give bonus
        assert "ilvl" in result.ilvl_display.lower() or str(90) in result.ilvl_display
    
    def test_ilvl_affects_price(self):
        """Test that ilvl affects price."""
        result_low = self.pricer.price_item(
            prefix="Jeweler's",
            suffix="of Deflecting",
            item_type="uit",
            ilvl=10,
            roll_percent=50.0,
        )
        
        result_high = self.pricer.price_item(
            prefix="Jeweler's",
            suffix="of Deflecting",
            item_type="uit",
            ilvl=90,
            roll_percent=50.0,
        )
        
        # Higher ilvl should give at least as much value
        assert result_high.estimated_fg >= result_low.estimated_fg
    
    def test_lld_detection(self):
        """Test LLD item detection."""
        # Low ilvl items for LLD
        result = self.pricer.price_item(
            prefix="Apprentice's",
            suffix="of the Whale",
            item_type="rin",
            ilvl=9,
            roll_percent=50.0,
        )
        
        # Very low ilvl might trigger LLD bonus
        # Depending on config
        assert result.estimated_fg >= 0
    
    def test_tier_assignment(self):
        """Test tier assignment based on price."""
        # GG tier (1000+)
        tier = self.pricer._price_to_tier(5000.0)
        assert tier == "gg"
        
        # High tier (500+)
        tier = self.pricer._price_to_tier(750.0)
        assert tier == "high"
        
        # Medium tier (100+)
        tier = self.pricer._price_to_tier(250.0)
        assert tier == "medium"
        
        # Low tier (10+)
        tier = self.pricer._price_to_tier(50.0)
        assert tier == "low"
        
        # Trash tier (< 10)
        tier = self.pricer._price_to_tier(5.0)
        assert tier == "trash"
    
    def test_format_ilvl(self):
        """Test ilvl formatting."""
        # Normal ilvl
        display = self.pricer._format_ilvl(50, is_lld=False)
        assert "50" in display
        
        # High ilvl
        display = self.pricer._format_ilvl(95, is_lld=False)
        assert "95" in display
        
        # LLD item
        display = self.pricer._format_ilvl(18, is_lld=True)
        assert "LLD" in display
    
    def test_color_codes(self):
        """Test color codes are valid D2R format."""
        colors = self.pricer.COLORS
        
        for tier, color in colors.items():
            assert color.startswith("ÿc"), f"Color for {tier} should start with ÿc"
    
    def test_format_magic_item_name(self):
        """Test full item name formatting."""
        name = self.pricer.format_magic_item_name(
            prefix="Jeweler's",
            base_name="Monarch",
            suffix="of Deflecting",
            item_type="uit",
            ilvl=50,
            roll_percent=50.0,
        )
        
        assert "Jeweler's" in name
        assert "Monarch" in name
        assert "of Deflecting" in name
        assert "ÿc" in name  # Has color codes
    
    def test_roll_quality_affects_price(self):
        """Test that roll quality affects price for items with variable rolls."""
        # Caster amulet has variable rolls (FCR can vary)
        result_low = self.pricer.price_item(
            prefix="Arch-Angel's",
            suffix="of the Magus",
            item_type="amu",
            ilvl=90,
            roll_percent=20.0,
        )
        
        result_high = self.pricer.price_item(
            prefix="Arch-Angel's",
            suffix="of the Magus",
            item_type="amu",
            ilvl=90,
            roll_percent=90.0,
        )
        
        # Better roll should give at least as much value (may be same if fixed)
        assert result_high.estimated_fg >= result_low.estimated_fg


class TestExtendedAffixHighlighter:
    """Tests for ExtendedAffixHighlighter."""
    
    def setup_method(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "gg_affixes.yml"
        if config_path.exists():
            self.highlighter = ExtendedAffixHighlighter(
                gg_affixes_path=config_path,
            )
        else:
            self.highlighter = None
    
    @pytest.mark.skipif(
        not Path(__file__).parent.parent.parent.joinpath("config/gg_affixes.yml").exists(),
        reason="gg_affixes.yml not found"
    )
    def test_highlight_prefix(self):
        """Test prefix highlighting."""
        result = self.highlighter.highlight_prefix_with_price("Jeweler's", "uit", 50)
        
        assert "Jeweler's" in result
        # Should have color code
        assert "ÿc" in result
    
    @pytest.mark.skipif(
        not Path(__file__).parent.parent.parent.joinpath("config/gg_affixes.yml").exists(),
        reason="gg_affixes.yml not found"
    )
    def test_highlight_suffix(self):
        """Test suffix highlighting."""
        result = self.highlighter.highlight_suffix_with_price("of Deflecting", "uit", 50)
        
        assert "Deflecting" in result


class TestConvenienceFunction:
    """Tests for convenience function."""
    
    def test_get_magic_item_display(self):
        """Test the main convenience function."""
        result = get_magic_item_display(
            prefix="Jeweler's",
            base_name="Monarch",
            suffix="of Deflecting",
            item_type="uit",
            ilvl=50,
            roll_quality=50.0,
        )
        
        # Should be a non-empty string
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Should contain the item name components
        assert "Jeweler's" in result
        assert "Monarch" in result
    
    def test_caster_ring_display(self):
        """Test caster ring display."""
        result = get_magic_item_display(
            prefix="Apprentice's",
            base_name="Ring",
            suffix="of the Whale",
            item_type="rin",
            ilvl=85,
            roll_quality=70.0,
        )
        
        assert "Apprentice's" in result
        assert "Ring" in result
        assert "ÿc" in result  # Has color


class TestAffixPriceResult:
    """Tests for AffixPriceResult dataclass."""
    
    def test_result_creation(self):
        """Test result creation."""
        result = AffixPriceResult(
            estimated_fg=25.5,
            tier="high",
            color="ÿc;",
            tag="[★]",
            ilvl_display="ÿc8ilvl50ÿc0",
            notes="Test item",
            is_lld=False,
        )
        
        assert result.estimated_fg == 25.5
        assert result.tier == "high"
        assert result.color == "ÿc;"
        assert result.tag == "[★]"
        assert result.is_lld is False
