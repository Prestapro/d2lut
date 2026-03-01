"""Machine Learning classifier for Rare/Magic item valuation.

When rules don't apply (rare items, crafted items, magic items with
complex affix combinations), ML can estimate value tier based on
learned patterns from historical data.

Features:
- Item type encoding
- Affix combination encoding
- Stat synergy scoring
- Level requirement normalization
- Tier classification (trash/low/medium/high/gg)
"""

from __future__ import annotations

import json
import math
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

# Item type categories for encoding
ITEM_TYPES = {
    # Weapons
    "sword": 1, "axe": 2, "mace": 3, "hammer": 4, "dagger": 5,
    "spear": 6, "polearm": 7, "bow": 8, "crossbow": 9, "javelin": 10,
    "orb": 11, "wand": 12, "staff": 13, "claw": 14,
    
    # Armor
    "helm": 20, "armor": 21, "shield": 22, "gloves": 23, "boots": 24, "belt": 25,
    
    # Jewelry
    "ring": 30, "amulet": 31,
    
    # Charms
    "small_charm": 40, "large_charm": 41, "grand_charm": 42,
    
    # Jewels
    "jewel": 50,
    
    # Other
    "circlet": 60, "tiara": 61, "coronet": 62, "diadem": 63,
    "other": 0,
}

# Affix importance weights for value
AFFIX_WEIGHTS = {
    # Prefixes (high value)
    "+2_skills": 5.0,
    "+1_skills": 3.0,
    "+2_sorceress": 4.5,
    "+2_paladin": 4.5,
    "+2_necromancer": 4.0,
    "+2_barbarian": 3.5,
    "+2_amazon": 3.5,
    "+2_assassin": 3.5,
    "+2_druid": 3.0,
    "+2_tree_skills": 2.5,  # +2 to specific tree
    
    # Damage prefixes
    "ed%": 2.5,  # Enhanced damage
    "max_damage": 1.5,
    "min_damage": 1.0,
    
    # Defense prefixes
    "def%": 1.5,
    "def": 0.5,
    
    # Resistances
    "all_res": 3.0,
    "single_res": 1.0,
    "cold_res": 1.2,
    "light_res": 1.5,
    "fire_res": 1.0,
    "poison_res": 0.8,
    
    # Attributes
    "str": 1.5,
    "dex": 1.5,
    "vit": 1.8,
    "ene": 0.8,
    "all_attributes": 2.0,
    
    # Life/Mana
    "life": 2.0,
    "mana": 1.2,
    "life_after_kill": 0.5,
    "mana_after_kill": 0.3,
    
    # Combat stats
    "fcr": 3.5,  # Faster cast rate
    "fhr": 1.8,  # Faster hit recovery
    "fbr": 1.2,  # Faster block rate
    "ias": 3.0,  # Increased attack speed
    "frw": 1.5,  # Faster run/walk
    
    # Damage reduction
    "dr%": 2.5,  # Damage reduce %
    "mdr": 1.0,  # Magic damage reduce
    "dr": 0.8,   # Damage reduce flat
    
    # Leech
    "ll": 2.0,  # Life leech
    "ml": 1.5,  # Mana leech
    
    # Other valuable stats
    "cb": 2.5,  # Crushing blow
    "ds": 1.8,  # Deadly strike
    "ow": 1.5,  # Open wounds
    "mf": 1.2,  # Magic find
    "gf": 0.5,  # Gold find
    
    # Suffixes
    "ar": 1.0,  # Attack rating
    "ar_per_level": 1.5,
    "life_per_level": 1.8,
    "mana_per_level": 1.0,
    
    # Skill bonuses
    "skill_tree": 2.5,  # + to skill tree
    "oskill": 3.0,  # + to any skill
    
    # Negative/penalty
    "req_minus": 2.0,  # -requirements
    "durability": 0.1,
    "repair": 0.2,
}

# Synergy bonuses - certain stat combinations are worth more than sum of parts
SYNERGY_BONUSES = {
    # Caster synergy
    frozenset(["fcr", "+2_skills"]): 1.5,
    frozenset(["fcr", "mana"]): 1.2,
    frozenset(["fcr", "all_res"]): 1.3,
    
    # Melee synergy
    frozenset(["ias", "ll"]): 1.4,
    frozenset(["ias", "ed%"]): 1.5,
    frozenset(["cb", "ds"]): 1.3,
    frozenset(["ll", "ml"]): 1.2,
    
    # Defensive synergy
    frozenset(["dr%", "all_res"]): 1.4,
    frozenset(["dr%", "vit"]): 1.2,
    frozenset(["fhr", "all_res"]): 1.2,
    
    # Attribute synergy
    frozenset(["str", "dex"]): 1.1,
    frozenset(["str", "life"]): 1.2,
    frozenset(["dex", "ar"]): 1.3,
    
    # Skill synergy
    frozenset(["+2_skills", "fcr"]): 1.6,
    frozenset(["+2_skills", "all_res"]): 1.4,
    frozenset(["+2_skills", "str"]): 1.3,
    
    # Charm synergy
    frozenset(["max_damage", "ar", "life"]): 2.0,
    frozenset(["fhr", "all_res"]): 1.5,
    
    # Ring/Amulet synergy
    frozenset(["fcr", "str", "mana"]): 1.5,
    frozenset(["fcr", "life", "mana"]): 1.4,
    frozenset(["+2_skills", "fcr", "life"]): 1.8,
}

# Tier thresholds
TIER_THRESHOLDS = {
    "trash": 0,
    "low": 5,
    "medium": 15,
    "high": 30,
    "gg": 50,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ItemFeatures:
    """Extracted features for ML classification."""
    
    item_type_encoded: int = 0
    quality_encoded: int = 0
    affix_count: int = 0
    total_affix_weight: float = 0.0
    max_affix_weight: float = 0.0
    avg_affix_weight: float = 0.0
    has_plus_skills: bool = False
    has_fcr: bool = False
    has_ias: bool = False
    has_ll: bool = False
    has_all_res: bool = False
    has_dr: bool = False
    has_mf: bool = False
    total_life: float = 0.0
    total_mana: float = 0.0
    total_str: float = 0.0
    total_dex: float = 0.0
    total_res: float = 0.0
    total_fcr: float = 0.0
    total_ias: float = 0.0
    total_mf: float = 0.0
    req_level_normalized: float = 0.0
    is_lld_relevant: bool = False
    synergy_score: float = 0.0
    score: float = 0.0
    
    def to_vector(self) -> list[float]:
        """Convert to feature vector for ML model."""
        return [
            self.item_type_encoded / 100.0,
            self.quality_encoded / 10.0,
            self.affix_count / 10.0,
            self.total_affix_weight / 50.0,
            self.max_affix_weight / 10.0,
            self.avg_affix_weight / 5.0,
            float(self.has_plus_skills),
            float(self.has_fcr),
            float(self.has_ias),
            float(self.has_ll),
            float(self.has_all_res),
            float(self.has_dr),
            float(self.has_mf),
            self.total_life / 100.0,
            self.total_mana / 100.0,
            self.total_str / 50.0,
            self.total_dex / 50.0,
            self.total_res / 100.0,
            self.total_fcr / 20.0,
            self.total_ias / 20.0,
            self.total_mf / 50.0,
            self.req_level_normalized,
            float(self.is_lld_relevant),
            self.synergy_score / 5.0,
        ]


@dataclass
class ItemPrediction:
    """ML prediction result for an item."""
    
    tier: str
    confidence: float
    estimated_fg: float
    score: float
    top_affixes: list[str]
    synergy_bonuses: list[str]
    reasoning: str


# ---------------------------------------------------------------------------
# Feature extractor
# ---------------------------------------------------------------------------

class FeatureExtractor:
    """Extract ML features from parsed items."""
    
    def __init__(self):
        self.affix_weights = AFFIX_WEIGHTS.copy()
        self.synergy_bonuses = SYNERGY_BONUSES.copy()
    
    def extract_features(
        self,
        item_type: str,
        quality: str,
        affixes: list[dict],
        req_level: int | None = None,
    ) -> ItemFeatures:
        """Extract features from an item."""
        
        features = ItemFeatures()
        
        # Encode item type
        item_type_lower = item_type.lower().replace(" ", "_")
        features.item_type_encoded = ITEM_TYPES.get(item_type_lower, 0)
        
        if features.item_type_encoded == 0:
            for key, val in ITEM_TYPES.items():
                if key in item_type_lower or item_type_lower in key:
                    features.item_type_encoded = val
                    break
        
        # Encode quality
        quality_lower = quality.lower()
        if quality_lower == "rare":
            features.quality_encoded = 1
        elif quality_lower == "magic":
            features.quality_encoded = 2
        elif quality_lower == "crafted":
            features.quality_encoded = 3
        
        # Process affixes
        affix_names = []
        for affix in affixes:
            affix_name = affix.get("name", "").lower()
            affix_value = affix.get("value", 0)
            
            affix_key = self._normalize_affix_name(affix_name)
            affix_names.append(affix_key)
            
            weight = self.affix_weights.get(affix_key, 0.5)
            features.total_affix_weight += weight
            features.max_affix_weight = max(features.max_affix_weight, weight)
            
            if "skill" in affix_key:
                features.has_plus_skills = True
            if affix_key == "fcr":
                features.has_fcr = True
                features.total_fcr += affix_value
            if affix_key == "ias":
                features.has_ias = True
                features.total_ias += affix_value
            if affix_key == "ll":
                features.has_ll = True
            if affix_key == "all_res":
                features.has_all_res = True
                features.total_res += affix_value
            if affix_key in ("dr%", "dr"):
                features.has_dr = True
            if affix_key == "mf":
                features.has_mf = True
                features.total_mf += affix_value
            if affix_key == "life":
                features.total_life += affix_value
            elif affix_key == "mana":
                features.total_mana += affix_value
            elif affix_key == "str":
                features.total_str += affix_value
            elif affix_key == "dex":
                features.total_dex += affix_value
            elif affix_key in ("all_res", "single_res", "cold_res", "light_res", "fire_res", "poison_res"):
                features.total_res += affix_value
        
        features.affix_count = len(affixes)
        if features.affix_count > 0:
            features.avg_affix_weight = features.total_affix_weight / features.affix_count
        
        if req_level is not None:
            features.req_level_normalized = req_level / 99.0
            features.is_lld_relevant = req_level <= 30
        
        features.synergy_score = self._calculate_synergy(affix_names)
        features.score = features.total_affix_weight + features.synergy_score
        
        return features
    
    def _normalize_affix_name(self, name: str) -> str:
        """Normalize affix name to match weight dictionary."""
        name = name.lower().strip()
        
        # Check for +skills first (most specific patterns)
        if "+2 to all skills" in name or "+2 to all character skills" in name:
            return "+2_skills"
        if "+1 to all skills" in name or "+1 to all character skills" in name:
            return "+1_skills"
        if "+2 to sorceress" in name:
            return "+2_sorceress"
        if "+2 to paladin" in name:
            return "+2_paladin"
        if "+2 to necromancer" in name:
                return "+2_necromancer"
        if "+2 to barbarian" in name:
            return "+2_barbarian"
        if "+2 to amazon" in name:
            return "+2_amazon"
        if "+2 to assassin" in name:
            return "+2_assassin"
        if "+2 to druid" in name:
            return "+2_druid"
        if "to skills" in name or "+skills" in name:
            return "+1_skills"  # Generic +skills
        
        # Combat stats
        if "faster cast rate" in name or "fcr" in name:
            return "fcr"
        if "faster hit recovery" in name or "fhr" in name:
            return "fhr"
        if "faster run" in name or "faster walk" in name or "frw" in name:
            return "frw"
        if "increased attack speed" in name or "ias" in name:
            return "ias"
        
        # Leech (check before generic ll/ml)
        if "life leech" in name or "life stolen" in name:
            return "ll"
        if "mana leech" in name or "mana stolen" in name:
            return "ml"
        
        # Resistances
        if "all resistances" in name or "all res" in name:
            return "all_res"
        if "cold resist" in name:
            return "cold_res"
        if "lightning resist" in name:
            return "light_res"
        if "fire resist" in name:
            return "fire_res"
        if "poison resist" in name:
            return "poison_res"
        if "resist" in name:
            return "single_res"
        
        # Attributes
        if "to all attributes" in name:
            return "all_attributes"
        if "to strength" in name or name == "strength":
            return "str"
        if "to dexterity" in name or name == "dexterity":
            return "dex"
        if "to vitality" in name or name == "vitality":
            return "vit"
        if "to energy" in name or name == "energy":
            return "ene"
        
        # Life/Mana
        if "to life" in name:
            return "life"
        if "to mana" in name:
            return "mana"
        
        # Damage
        if "enhanced damage" in name or "ed%" in name:
            return "ed%"
        if "max damage" in name or "maximum damage" in name:
            return "max_damage"
        if "min damage" in name or "minimum damage" in name:
            return "min_damage"
        
        # Defense
        if "enhanced defense" in name:
            return "def%"
        
        # Combat
        if "crushing blow" in name:
            return "cb"
        if "deadly strike" in name:
            return "ds"
        if "open wounds" in name:
            return "ow"
        if "magic find" in name:
            return "mf"
        
        # Damage reduction
        if "damage reduced by" in name or "dr%" in name:
            return "dr%"
        
        # Attack rating
        if "attack rating" in name:
            return "ar"
        
        # -requirements
        if "requirements" in name and "-" in name:
            return "req_minus"
        
        return name
    
    def _calculate_synergy(self, affix_names: list[str]) -> float:
        """Calculate synergy bonus for affix combinations."""
        synergy_score = 0.0
        affix_set = set(affix_names)
        
        for synergy_combo, bonus in self.synergy_bonuses.items():
            if synergy_combo.issubset(affix_set):
                synergy_score += bonus
        
        return synergy_score


# ---------------------------------------------------------------------------
# ML Classifier
# ---------------------------------------------------------------------------

class ItemValueClassifier:
    """ML-based classifier for rare/magic item valuation."""
    
    def __init__(self, model_path: str | Path | None = None):
        self.feature_extractor = FeatureExtractor()
        self._model = None
        self._model_path = Path(model_path) if model_path else None
        
        if self._model_path and self._model_path.exists():
            self._load_model()
    
    def _load_model(self) -> bool:
        try:
            with open(self._model_path, "rb") as f:
                self._model = pickle.load(f)
            return True
        except Exception:
            return False
    
    def _save_model(self) -> bool:
        if not self._model or not self._model_path:
            return False
        
        try:
            self._model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._model_path, "wb") as f:
                pickle.dump(self._model, f)
            return True
        except Exception:
            return False
    
    def predict(
        self,
        item_type: str,
        quality: str,
        affixes: list[dict],
        req_level: int | None = None,
    ) -> ItemPrediction:
        """Predict value tier for an item."""
        
        features = self.feature_extractor.extract_features(
            item_type=item_type,
            quality=quality,
            affixes=affixes,
            req_level=req_level,
        )
        
        feature_vector = features.to_vector()
        
        if self._model is not None:
            prediction = self._model.predict([feature_vector])[0]
            confidence = 0.8
        else:
            prediction, confidence = self._rule_based_predict(features)
        
        tier = self._score_to_tier(features.score)
        estimated_fg = self._estimate_fg(features, tier)
        
        top_affixes = [
            a.get("name", "") for a in sorted(affixes, key=lambda x: self._affix_value(x), reverse=True)[:3]
        ]
        
        synergy_bonuses = self._get_synergy_bonuses(affixes)
        reasoning = self._generate_reasoning(tier, features, top_affixes, synergy_bonuses)
        
        return ItemPrediction(
            tier=tier,
            confidence=confidence,
            estimated_fg=estimated_fg,
            score=features.score,
            top_affixes=top_affixes,
            synergy_bonuses=synergy_bonuses,
            reasoning=reasoning,
        )
    
    def _rule_based_predict(self, features: ItemFeatures) -> tuple[int, float]:
        score = features.score
        
        if score >= TIER_THRESHOLDS["gg"]:
            return 4, 0.9
        elif score >= TIER_THRESHOLDS["high"]:
            return 3, 0.85
        elif score >= TIER_THRESHOLDS["medium"]:
            return 2, 0.75
        elif score >= TIER_THRESHOLDS["low"]:
            return 1, 0.7
        else:
            return 0, 0.6
    
    def _score_to_tier(self, score: float) -> str:
        if score >= TIER_THRESHOLDS["gg"]:
            return "gg"
        elif score >= TIER_THRESHOLDS["high"]:
            return "high"
        elif score >= TIER_THRESHOLDS["medium"]:
            return "medium"
        elif score >= TIER_THRESHOLDS["low"]:
            return "low"
        else:
            return "trash"
    
    def _estimate_fg(self, features: ItemFeatures, tier: str) -> float:
        base_values = {
            "gg": 50.0,
            "high": 20.0,
            "medium": 5.0,
            "low": 1.0,
            "trash": 0.1,
        }
        
        base = base_values.get(tier, 0.1)
        
        type_multipliers = {
            30: 1.5,  # Ring
            31: 1.8,  # Amulet
            50: 1.2,  # Jewel
            40: 1.3,  # Small Charm
            42: 1.1,  # Grand Charm
        }
        
        mult = type_multipliers.get(features.item_type_encoded, 1.0)
        
        if features.is_lld_relevant:
            mult *= 1.3
        
        synergy_mult = 1 + (features.synergy_score * 0.1)
        
        return base * mult * synergy_mult
    
    def _affix_value(self, affix: dict) -> float:
        name = affix.get("name", "").lower()
        key = self.feature_extractor._normalize_affix_name(name)
        return self.feature_extractor.affix_weights.get(key, 0.5)
    
    def _get_synergy_bonuses(self, affixes: list[dict]) -> list[str]:
        affix_names = [
            self.feature_extractor._normalize_affix_name(a.get("name", "").lower())
            for a in affixes
        ]
        affix_set = set(affix_names)
        
        bonuses = []
        for combo, value in SYNERGY_BONUSES.items():
            if combo.issubset(affix_set):
                combo_str = "+".join(sorted(combo))
                bonuses.append(f"{combo_str} ({value:+.1f})")
        
        return bonuses
    
    def _generate_reasoning(
        self,
        tier: str,
        features: ItemFeatures,
        top_affixes: list[str],
        synergy_bonuses: list[str],
    ) -> str:
        parts = [f"Predicted tier: {tier.upper()}"]
        
        if features.has_plus_skills:
            parts.append("Has +skills - high value")
        if features.has_fcr:
            parts.append(f"FCR {features.total_fcr:.0f}% - caster demand")
        if features.has_ias:
            parts.append(f"IAS {features.total_ias:.0f}% - melee demand")
        if features.has_all_res:
            parts.append("All res - defensive value")
        if features.has_dr:
            parts.append("Damage reduction - tank value")
        if features.is_lld_relevant:
            parts.append("LLD relevant - niche market premium")
        
        if synergy_bonuses:
            parts.append(f"Synergies: {', '.join(synergy_bonuses[:3])}")
        
        parts.append(f"Overall score: {features.score:.1f}")
        
        return " | ".join(parts)
    
    def train(self, training_data: list[dict], labels: list[int]) -> float:
        """Train the classifier on labeled data."""
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score
            import numpy as np
        except ImportError:
            return 0.0
        
        X = []
        for item in training_data:
            features = self.feature_extractor.extract_features(
                item_type=item.get("item_type", "other"),
                quality=item.get("quality", "rare"),
                affixes=item.get("affixes", []),
                req_level=item.get("req_level"),
            )
            X.append(features.to_vector())
        
        X = np.array(X)
        y = np.array(labels)
        
        self._model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
        )
        
        self._model.fit(X, y)
        self._save_model()
        
        scores = cross_val_score(self._model, X, y, cv=5)
        return scores.mean()


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def classify_item(
    item_type: str,
    quality: str,
    affixes: list[dict],
    req_level: int | None = None,
    model_path: str | None = None,
) -> ItemPrediction:
    """Classify a single item and predict its value tier."""
    classifier = ItemValueClassifier(model_path=model_path)
    return classifier.predict(
        item_type=item_type,
        quality=quality,
        affixes=affixes,
        req_level=req_level,
    )


def classify_from_parsed_item(parsed_item: Any, model_path: str | None = None) -> ItemPrediction:
    """Classify from a ParsedItem object."""
    item_type = getattr(parsed_item, "item_type", "other")
    quality = getattr(parsed_item, "quality", "rare")
    req_level = None
    
    affixes = []
    for prop in getattr(parsed_item, "base_properties", []):
        affixes.append({
            "name": getattr(prop, "name", ""),
            "value": getattr(prop, "value", 0),
        })
        
        if "req" in getattr(prop, "name", "").lower():
            try:
                req_level = int(getattr(prop, "value", 0))
            except (ValueError, TypeError):
                pass
    
    return classify_item(
        item_type=item_type,
        quality=quality,
        affixes=affixes,
        req_level=req_level,
        model_path=model_path,
    )
