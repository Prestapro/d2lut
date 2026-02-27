"""Unit tests for LLD Pricing configuration and integration.

Validates LLD bucket assignment, pricing multipliers, and item prices.
"""

import yaml
from pathlib import Path


class TestLLDConfig:
    """Tests for LLD prices configuration."""
    
    def test_config_file_exists(self):
        """Test that LLD config file exists."""
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        assert config_path.exists(), "lld_prices.yml should exist"
    
    def test_config_valid_yaml(self):
        """Test that LLD config is valid YAML."""
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        assert data is not None
        assert "multipliers" in data
        assert "items" in data
    
    def test_lld_multipliers(self):
        """Test LLD bucket multipliers."""
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        multipliers = data.get("multipliers", {})
        
        # LLD9 should have highest multiplier
        assert multipliers.get("lld9", 0) >= multipliers.get("lld18", 0)
        assert multipliers.get("lld18", 0) >= multipliers.get("lld30", 0)
        assert multipliers.get("lld30", 0) >= multipliers.get("mld", 0)
    
    def test_lld_items_structure(self):
        """Test LLD items have proper structure."""
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        items = data.get("items", {})
        
        # Each item should have estimate_fg
        for key, value in items.items():
            assert isinstance(value, dict), f"{key} should be a dict"
            assert "estimate_fg" in value, f"{key} should have estimate_fg"
            assert "bucket" in value, f"{key} should have bucket"
    
    def test_lld_jewel_prices(self):
        """Test LLD jewel prices are defined."""
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        items = data.get("items", {})
        
        # IAS jewel should be valuable for LLD
        assert "jewel:ias_lld" in items
        assert items["jewel:ias_lld"]["estimate_fg"] > 0
    
    def test_lld_charm_prices(self):
        """Test LLD charm prices are defined."""
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        items = data.get("items", {})
        
        # Skillers with life are valuable for LLD
        assert "charm:gc_skill_lld" in items
        assert items["charm:gc_skill_lld"]["estimate_fg"] > 0
    
    def test_affix_bonuses(self):
        """Test LLD affix bonuses."""
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        affix_bonuses = data.get("affix_bonuses", {})
        
        # IAS should have high multiplier for LLD
        if "ias" in affix_bonuses:
            assert affix_bonuses["ias"]["multiplier"] >= 1.0
        
        # -requirements should be valuable for LLD
        if "-requirements" in affix_bonuses:
            assert affix_bonuses["-requirements"]["multiplier"] >= 1.0


class TestLLDBucketLogic:
    """Tests for LLD bucket assignment logic."""
    
    def test_bucket_assignment_by_req_level(self):
        """Test bucket assignment based on requirement level."""
        # Replicate the logic from the existing test file
        def _assign_lld_bucket(req_level: int) -> str:
            if req_level <= 9:
                return "LLD9"
            if req_level <= 18:
                return "LLD18"
            if req_level <= 30:
                return "LLD30"
            return "MLD" if req_level <= 49 else "HLD"
        
        assert _assign_lld_bucket(1) == "LLD9"
        assert _assign_lld_bucket(9) == "LLD9"
        assert _assign_lld_bucket(10) == "LLD18"
        assert _assign_lld_bucket(18) == "LLD18"
        assert _assign_lld_bucket(19) == "LLD30"
        assert _assign_lld_bucket(30) == "LLD30"
        assert _assign_lld_bucket(31) == "MLD"
        assert _assign_lld_bucket(49) == "MLD"
        assert _assign_lld_bucket(50) == "HLD"
        assert _assign_lld_bucket(99) == "HLD"
    
    def test_lld_relevant_items(self):
        """Test items that are relevant for LLD."""
        # These items should be in LLD config
        lld_relevant = [
            "jewel:ias_lld",
            "charm:sc_max_dmg_ar_lld",
            "charm:gc_skill_lld",
            "unique:bloodfist_lld",
        ]
        
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        items = data.get("items", {})
        
        for item_key in lld_relevant:
            assert item_key in items, f"{item_key} should be in LLD config"


class TestLLDIntegration:
    """Tests for LLD integration with pricing engine."""
    
    def test_lld_price_lookup(self):
        """Test that LLD prices can be looked up."""
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        items = data.get("items", {})
        
        # Check specific items have reasonable prices
        spirit_lld = items.get("runeword:spirit_lld", {})
        assert spirit_lld.get("estimate_fg", 0) > 0, "LLD Spirit should have a price"
        
        ias_jewel = items.get("jewel:ias_lld", {})
        assert ias_jewel.get("estimate_fg", 0) > 5, "IAS jewel should be valuable for LLD"
    
    def test_set_bonuses(self):
        """Test LLD set item bonuses."""
        config_path = Path(__file__).parent.parent / "config" / "lld_prices.yml"
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        set_bonuses = data.get("set_bonuses", {})
        
        # Angelic combo should be valuable
        assert "angelic_combo" in set_bonuses
        assert set_bonuses["angelic_combo"]["estimate_fg"] > 0
