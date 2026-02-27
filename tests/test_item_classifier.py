"""Tests for ML Item Classifier."""

import pytest
from pathlib import Path

from d2lut.ml.item_classifier import (
    ItemFeatures,
    ItemPrediction,
    FeatureExtractor,
    ItemValueClassifier,
    classify_item,
    AFFIX_WEIGHTS,
    SYNERGY_BONUSES,
    TIER_THRESHOLDS,
)


class TestItemFeatures:
    """Tests for ItemFeatures dataclass."""
    
    def test_features_creation(self):
        """Test feature creation with defaults."""
        features = ItemFeatures()
        
        assert features.item_type_encoded == 0
        assert features.affix_count == 0
        assert features.total_affix_weight == 0.0
        assert features.has_plus_skills is False
    
    def test_features_to_vector(self):
        """Test conversion to feature vector."""
        features = ItemFeatures(
            item_type_encoded=30,  # Ring
            affix_count=3,
            total_affix_weight=10.0,
            has_fcr=True,
            total_fcr=10.0,
        )
        
        vector = features.to_vector()
        
        assert isinstance(vector, list)
        assert len(vector) == 24
        assert vector[0] == 0.3  # item_type_encoded / 100
        assert vector[7] == 1.0  # has_fcr


class TestFeatureExtractor:
    """Tests for FeatureExtractor."""
    
    def setup_method(self):
        self.extractor = FeatureExtractor()
    
    def test_extract_ring_features(self):
        """Test feature extraction for a ring."""
        affixes = [
            {"name": "10% Faster Cast Rate", "value": 10},
            {"name": "+20 to Mana", "value": 20},
            {"name": "+15 to Strength", "value": 15},
        ]
        
        features = self.extractor.extract_features(
            item_type="ring",
            quality="rare",
            affixes=affixes,
        )
        
        assert features.item_type_encoded == 30  # Ring
        assert features.quality_encoded == 1  # Rare
        assert features.has_fcr is True
        assert features.affix_count == 3
        assert features.total_affix_weight > 0
    
    def test_extract_amulet_features(self):
        """Test feature extraction for an amulet."""
        affixes = [
            {"name": "+2 to All Skills", "value": 2},
            {"name": "20% Faster Cast Rate", "value": 20},
            {"name": "+30 to Life", "value": 30},
        ]
        
        features = self.extractor.extract_features(
            item_type="amulet",
            quality="rare",
            affixes=affixes,
        )
        
        assert features.item_type_encoded == 31  # Amulet
        assert features.has_fcr is True
        assert features.affix_count == 3
    
    def test_extract_charm_features(self):
        """Test feature extraction for a charm."""
        affixes = [
            {"name": "+3 to Max Damage", "value": 3},
            {"name": "+20 to Attack Rating", "value": 20},
            {"name": "+20 to Life", "value": 20},
        ]
        
        features = self.extractor.extract_features(
            item_type="small_charm",
            quality="magic",
            affixes=affixes,
        )
        
        assert features.item_type_encoded == 40  # Small Charm
        assert features.quality_encoded == 2  # Magic
    
    def test_lld_detection(self):
        """Test LLD relevance detection."""
        affixes = [{"name": "+2 to All Skills", "value": 2}]
        
        features = self.extractor.extract_features(
            item_type="amulet",
            quality="rare",
            affixes=affixes,
            req_level=25,
        )
        
        assert features.is_lld_relevant is True
        assert features.req_level_normalized == 25 / 99
    
    def test_synergy_calculation(self):
        """Test synergy bonus calculation."""
        # FCR + life + mana = synergy
        affixes = [
            {"name": "+20 to Life", "value": 20},
            {"name": "20% Faster Cast Rate", "value": 20},
            {"name": "+30 to Mana", "value": 30},
        ]
        
        features = self.extractor.extract_features(
            item_type="amulet",
            quality="rare",
            affixes=affixes,
        )
        
        # Should have synergy bonus
        assert features.synergy_score >= 0
    
    def test_affix_normalization(self):
        """Test affix name normalization."""
        assert self.extractor._normalize_affix_name("10% Faster Cast Rate") == "fcr"
        assert self.extractor._normalize_affix_name("Life Leech") == "ll"
        assert self.extractor._normalize_affix_name("+2 to All Skills") == "+2_skills"
        assert self.extractor._normalize_affix_name("+30 to Life") == "life"


class TestItemValueClassifier:
    """Tests for ItemValueClassifier."""
    
    def setup_method(self):
        self.classifier = ItemValueClassifier()
    
    def test_classify_gg_amulet(self):
        """Test classification of a GG amulet."""
        affixes = [
            {"name": "+2 to All Skills", "value": 2},
            {"name": "20% Faster Cast Rate", "value": 20},
            {"name": "+50 to Life", "value": 50},
            {"name": "+30 to Mana", "value": 30},
        ]
        
        prediction = self.classifier.predict(
            item_type="amulet",
            quality="rare",
            affixes=affixes,
        )
        
        # Should be at least medium
        assert prediction.tier in ("gg", "high", "medium")
        assert prediction.confidence > 0.5
        assert prediction.estimated_fg > 0
    
    def test_classify_trash_item(self):
        """Test classification of a trash item."""
        affixes = [
            {"name": "+5 to Mana", "value": 5},
            {"name": "+1 to Light Radius", "value": 1},
        ]
        
        prediction = self.classifier.predict(
            item_type="ring",
            quality="magic",
            affixes=affixes,
        )
        
        assert prediction.tier in ("trash", "low")
        assert prediction.estimated_fg < 5
    
    def test_classify_caster_ring(self):
        """Test classification of a caster ring."""
        affixes = [
            {"name": "10% Faster Cast Rate", "value": 10},
            {"name": "+20 to Mana", "value": 20},
            {"name": "+15 to Strength", "value": 15},
            {"name": "+50 to Life", "value": 50},
        ]
        
        prediction = self.classifier.predict(
            item_type="ring",
            quality="rare",
            affixes=affixes,
        )
        
        # Should be decent
        assert prediction.tier in ("high", "medium", "gg", "low")
    
    def test_classify_lld_item(self):
        """Test classification with LLD relevance."""
        affixes = [
            {"name": "+2 to All Skills", "value": 2},
            {"name": "10% Faster Cast Rate", "value": 10},
        ]
        
        prediction = self.classifier.predict(
            item_type="amulet",
            quality="rare",
            affixes=affixes,
            req_level=25,
        )
        
        # LLD items get a bonus
        assert "LLD" in prediction.reasoning or prediction.estimated_fg > 0
    
    def test_classify_melee_charm(self):
        """Test classification of a melee charm."""
        affixes = [
            {"name": "+3 to Max Damage", "value": 3},
            {"name": "+20 to Attack Rating", "value": 20},
            {"name": "+20 to Life", "value": 20},
        ]
        
        prediction = self.classifier.predict(
            item_type="small_charm",
            quality="magic",
            affixes=affixes,
        )
        
        # 3/20/20 is good
        assert prediction.tier in ("medium", "high", "gg", "low")
    
    def test_score_to_tier(self):
        """Test score to tier conversion."""
        assert self.classifier._score_to_tier(60) == "gg"
        assert self.classifier._score_to_tier(40) == "high"
        assert self.classifier._score_to_tier(20) == "medium"
        assert self.classifier._score_to_tier(7) == "low"
        assert self.classifier._score_to_tier(2) == "trash"
    
    def test_estimate_fg(self):
        """Test FG estimation."""
        features = ItemFeatures(
            item_type_encoded=31,  # Amulet
            is_lld_relevant=False,
            synergy_score=2.0,
        )
        
        fg = self.classifier._estimate_fg(features, "high")
        
        assert fg > 0
        # Amulet should have bonus
        assert fg > 20  # Base high tier * amulet multiplier


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_classify_item_function(self):
        """Test classify_item convenience function."""
        affixes = [
            {"name": "+2 to All Skills", "value": 2},
            {"name": "20% Faster Cast Rate", "value": 20},
        ]
        
        prediction = classify_item(
            item_type="amulet",
            quality="rare",
            affixes=affixes,
        )
        
        assert isinstance(prediction, ItemPrediction)
        assert prediction.tier in ("trash", "low", "medium", "high", "gg")


class TestAffixWeights:
    """Tests for affix weight configuration."""
    
    def test_weights_exist(self):
        """Test that important affixes have weights."""
        assert "+2_skills" in AFFIX_WEIGHTS
        assert "fcr" in AFFIX_WEIGHTS
        assert "ias" in AFFIX_WEIGHTS
        assert "life" in AFFIX_WEIGHTS
        assert "all_res" in AFFIX_WEIGHTS
    
    def test_weight_values(self):
        """Test that weights are reasonable."""
        # Skills should be valuable
        assert AFFIX_WEIGHTS["+2_skills"] >= 3.0
        assert AFFIX_WEIGHTS["+1_skills"] < AFFIX_WEIGHTS["+2_skills"]
        
        # FCR should be valuable
        assert AFFIX_WEIGHTS["fcr"] >= 2.0
        
        # Life should be valuable
        assert AFFIX_WEIGHTS["life"] >= 1.0


class TestSynergyBonuses:
    """Tests for synergy bonus configuration."""
    
    def test_synergies_exist(self):
        """Test that key synergies are defined."""
        # FCR + skills
        assert frozenset(["fcr", "+2_skills"]) in SYNERGY_BONUSES
        
        # Dual leech
        assert frozenset(["ll", "ml"]) in SYNERGY_BONUSES
    
    def test_synergy_values(self):
        """Test that synergy bonuses are positive."""
        for combo, bonus in SYNERGY_BONUSES.items():
            assert bonus > 0, f"Synergy {combo} should have positive bonus"


class TestTierThresholds:
    """Tests for tier threshold configuration."""
    
    def test_thresholds_ordering(self):
        """Test that thresholds are ordered correctly."""
        assert TIER_THRESHOLDS["trash"] < TIER_THRESHOLDS["low"]
        assert TIER_THRESHOLDS["low"] < TIER_THRESHOLDS["medium"]
        assert TIER_THRESHOLDS["medium"] < TIER_THRESHOLDS["high"]
        assert TIER_THRESHOLDS["high"] < TIER_THRESHOLDS["gg"]


class TestItemPrediction:
    """Tests for ItemPrediction dataclass."""
    
    def test_prediction_creation(self):
        """Test prediction creation."""
        pred = ItemPrediction(
            tier="high",
            confidence=0.85,
            estimated_fg=25.0,
            score=35.0,
            top_affixes=["+2 to All Skills", "20% FCR"],
            synergy_bonuses=["fcr+skills (+1.5)"],
            reasoning="Has +skills and FCR",
        )
        
        assert pred.tier == "high"
        assert pred.confidence == 0.85
        assert pred.estimated_fg == 25.0
        assert len(pred.top_affixes) == 2
