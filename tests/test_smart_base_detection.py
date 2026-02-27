"""Unit tests for Smart Base Detection.

Validates base item valuation, runeword potential, and LLD detection.
"""

from d2lut.overlay.smart_base_detection import (
    SmartBaseDetector,
    BaseValuation,
    RunewordInfo,
    UniqueInfo,
)


class TestSmartBaseDetector:
    """Tests for SmartBaseDetector class."""
    
    def setup_method(self):
        self.detector = SmartBaseDetector()
    
    def test_analyze_monarch_4os(self):
        """Monarch with 4os should show Spirit/Phoenix potential."""
        result = self.detector.analyze_base(
            base_code="uit",
            base_name="Monarch",
            sockets=4,
            ethereal=False,
        )
        
        assert result.base_code == "uit"
        assert result.sockets == 4
        
        # Should have Spirit runeword potential
        assert len(result.runeword_potential) >= 1
        spirit_found = any(rw.name == "Spirit" for rw in result.runeword_potential)
        assert spirit_found, "Should show Spirit runeword potential"
        
        # Should have JMOD potential
        assert result.gg_magic_potential is True
        
        # Should be high tier
        assert result.overall_tier in ("gg", "high")
    
    def test_analyze_archon_plate_3os(self):
        """Archon Plate with 3os should show Enigma potential."""
        result = self.detector.analyze_base(
            base_code="uap",
            base_name="Archon Plate",
            sockets=3,
            ethereal=False,
        )
        
        # Should have Enigma potential
        enigma_found = any(rw.name == "Enigma" for rw in result.runeword_potential)
        assert enigma_found, "Should show Enigma runeword potential"
        
        # Enigma is GG tier
        assert result.max_potential_fg >= 30  # Enigma is valuable
    
    def test_analyze_ethereal_polearm(self):
        """Ethereal polearm should have bonus for Infinity/Insight."""
        result = self.detector.analyze_base(
            base_code="7pa",
            base_name="Cryptic Axe",
            sockets=4,
            ethereal=True,
        )
        
        # Should have Infinity potential
        infinity_found = any(rw.name == "Infinity" for rw in result.runeword_potential)
        assert infinity_found, "Should show Infinity runeword potential"
        
        # Ethereal bonus should apply
        assert result.ethereal is True
        assert result.max_potential_fg > 0
    
    def test_analyze_diadem(self):
        """Diadem should show Griffon's potential and GG magic."""
        result = self.detector.analyze_base(
            base_code="uhm",
            base_name="Diadem",
            sockets=None,
            ethereal=False,
        )
        
        # Should have unique potential (Griffon's)
        assert len(result.unique_potential) >= 1
        griffon_found = any(u.name == "Griffon's Eye" for u in result.unique_potential)
        assert griffon_found, "Should show Griffon's Eye unique potential"
        
        # Should have GG magic potential
        assert result.gg_magic_potential is True
    
    def test_analyze_ring(self):
        """Ring should show SoJ and other unique potential."""
        result = self.detector.analyze_base(
            base_code="rin",
            base_name="Ring",
            sockets=None,
            ethereal=False,
        )
        
        # Should have multiple unique potentials
        assert len(result.unique_potential) >= 4
        
        # Should have GG uniques (SoJ, BK)
        gg_uniques = [u for u in result.unique_potential if u.value_tier == "gg"]
        assert len(gg_uniques) >= 1
    
    def test_analyze_phase_blade(self):
        """Phase Blade should show Grief potential."""
        result = self.detector.analyze_base(
            base_code="7wa",
            base_name="Phase Blade",
            sockets=5,
            ethereal=False,
        )
        
        # Should have Grief potential
        grief_found = any(rw.name == "Grief" for rw in result.runeword_potential)
        assert grief_found, "Should show Grief runeword potential"
        
        # Phase blade can't be ethereal in game, but we test the logic
        assert result.overall_tier in ("gg", "high")
    
    def test_lld_detection(self):
        """Bases should detect LLD relevance."""
        # Circlet is LLD relevant
        result = self.detector.analyze_base(
            base_code="ci0",
            base_name="Circlet",
            sockets=None,
            ethereal=False,
            req_level=18,
        )
        
        assert result.is_lld_relevant is True
        assert result.lld_bucket == "LLD18"
    
    def test_lld_bucket_assignment(self):
        """Test LLD bucket assignment by req level."""
        assert self.detector._assign_lld_bucket(9) == "LLD9"
        assert self.detector._assign_lld_bucket(18) == "LLD18"
        assert self.detector._assign_lld_bucket(30) == "LLD30"
        assert self.detector._assign_lld_bucket(45) == "MLD"
        assert self.detector._assign_lld_bucket(75) == "HLD"
    
    def test_base_hint_string(self):
        """Test hint string generation for loot filter."""
        hint = self.detector.get_base_hint_string("uit", sockets=4)
        
        # Should contain Spirit
        assert "Spirit" in hint
        
        # Should have color code
        assert "ÿc" in hint
    
    def test_recommendation_generation(self):
        """Test human-readable recommendation."""
        result = self.detector.analyze_base(
            base_code="uit",
            base_name="Monarch",
            sockets=4,
            ethereal=False,
        )
        
        assert result.recommendation != ""
        assert "Spirit" in result.recommendation or "GG" in result.recommendation
    
    def test_low_value_base(self):
        """Low value base should have low tier."""
        result = self.detector.analyze_base(
            base_code="xxx",  # Unknown base code
            base_name="Unknown",
            sockets=2,
            ethereal=False,
        )
        
        # Should be low or trash tier
        assert result.overall_tier in ("low", "trash")


class TestRunewordInfo:
    """Tests for RunewordInfo dataclass."""
    
    def test_runeword_creation(self):
        """Test runeword info creation."""
        rw = RunewordInfo(
            name="Spirit",
            sockets=4,
            value_tier="high",
            estimated_fg=5.0,
            notes="FCR, skills, res",
        )
        
        assert rw.name == "Spirit"
        assert rw.sockets == 4
        assert rw.value_tier == "high"
        assert rw.estimated_fg == 5.0
        assert rw.requires_ethereal is False
        assert rw.lld_relevant is False


class TestUniqueInfo:
    """Tests for UniqueInfo dataclass."""
    
    def test_unique_creation(self):
        """Test unique info creation."""
        u = UniqueInfo(
            name="Harlequin Crest",
            value_tier="gg",
            estimated_fg=35.0,
            notes="+2 skills, DR",
        )
        
        assert u.name == "Harlequin Crest"
        assert u.value_tier == "gg"
        assert u.estimated_fg == 35.0


class TestBaseValuation:
    """Tests for BaseValuation dataclass."""
    
    def test_valuation_creation(self):
        """Test base valuation creation."""
        val = BaseValuation(
            base_code="uit",
            base_name="Monarch",
            quality="elite",
            ethereal=False,
            sockets=4,
            defense=1337,
        )
        
        assert val.base_code == "uit"
        assert val.sockets == 4
        assert val.defense == 1337
        assert val.runeword_potential == []
        assert val.unique_potential == []
        assert val.gg_magic_potential is False
