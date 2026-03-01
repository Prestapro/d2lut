"""Tests for the overlay rule engine (LLD/craft detection, rule matching, price adjustments)."""

import pytest
from d2lut.overlay.ocr_parser import ParsedItem, Property
from d2lut.overlay.rule_engine import (
    AdjustedPriceEstimate,
    PricingRule,
    RuleEngine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(
    raw_text: str = "",
    item_name: str | None = None,
    item_type: str | None = None,
    quality: str | None = None,
    base_properties: list[Property] | None = None,
    diagnostic: dict | None = None,
) -> ParsedItem:
    return ParsedItem(
        raw_text=raw_text,
        item_name=item_name,
        item_type=item_type,
        quality=quality,
        base_properties=base_properties or [],
        diagnostic=diagnostic or {},
    )


# ---------------------------------------------------------------------------
# LLD detection
# ---------------------------------------------------------------------------

class TestCheckLLD:
    def test_lld_via_diagnostic_context(self):
        item = _make_item(diagnostic={"lld_context": True})
        engine = RuleEngine()
        assert engine.check_lld(item) is True

    def test_lld_via_keyword_in_raw_text(self):
        item = _make_item(raw_text="3/20/20 SC LLD")
        engine = RuleEngine()
        assert engine.check_lld(item) is True

    def test_lld_via_keyword_in_item_name(self):
        item = _make_item(item_name="LLD Small Charm")
        engine = RuleEngine()
        assert engine.check_lld(item) is True

    def test_lld_sc_property_combo(self):
        props = [
            Property(name="max_damage", value="3"),
            Property(name="ar", value="20"),
            Property(name="life", value="20"),
        ]
        item = _make_item(item_type="small charm", base_properties=props)
        engine = RuleEngine()
        assert engine.check_lld(item) is True

    def test_lld_low_req_level(self):
        props = [Property(name="req_level", value="18")]
        item = _make_item(base_properties=props)
        engine = RuleEngine()
        assert engine.check_lld(item) is True

    def test_not_lld_normal_item(self):
        item = _make_item(raw_text="Shako Unique Helm", item_type="helm")
        engine = RuleEngine()
        assert engine.check_lld(item) is False

    def test_not_lld_high_req_level(self):
        props = [Property(name="req_level", value="67")]
        item = _make_item(base_properties=props)
        engine = RuleEngine()
        assert engine.check_lld(item) is False


# ---------------------------------------------------------------------------
# Craft detection
# ---------------------------------------------------------------------------

class TestCheckCraft:
    def test_craft_via_quality(self):
        item = _make_item(quality="crafted")
        engine = RuleEngine()
        assert engine.check_craft(item) is True

    def test_craft_via_keyword_blood(self):
        item = _make_item(raw_text="Blood Craft Amulet 2/10")
        engine = RuleEngine()
        assert engine.check_craft(item) is True

    def test_craft_via_keyword_caster(self):
        item = _make_item(raw_text="Caster Amulet 2/10 FCR")
        engine = RuleEngine()
        assert engine.check_craft(item) is True

    def test_craft_via_keyword_safety(self):
        item = _make_item(item_name="Safety Shield")
        engine = RuleEngine()
        assert engine.check_craft(item) is True

    def test_craft_via_keyword_hitpower(self):
        item = _make_item(raw_text="Hit Power Gloves")
        engine = RuleEngine()
        assert engine.check_craft(item) is True

    def test_not_craft_normal_item(self):
        item = _make_item(raw_text="Shako Unique Helm", quality="unique")
        engine = RuleEngine()
        assert engine.check_craft(item) is False


# ---------------------------------------------------------------------------
# Rule matching and get_relevant_rules
# ---------------------------------------------------------------------------

class TestGetRelevantRules:
    def test_lld_rule_matches_lld_item(self):
        engine = RuleEngine()
        rule = PricingRule(
            rule_id="lld_premium",
            rule_type="lld",
            conditions={},
            adjustment_type="multiplier",
            adjustment_value=1.5,
            priority=10,
        )
        engine.add_rule(rule)
        item = _make_item(diagnostic={"lld_context": True})
        matched = engine.get_relevant_rules(item)
        assert len(matched) == 1
        assert matched[0].rule_id == "lld_premium"

    def test_lld_rule_skips_non_lld_item(self):
        engine = RuleEngine()
        rule = PricingRule(
            rule_id="lld_premium",
            rule_type="lld",
            conditions={},
            adjustment_type="multiplier",
            adjustment_value=1.5,
        )
        engine.add_rule(rule)
        item = _make_item(raw_text="Shako", item_type="helm")
        assert engine.get_relevant_rules(item) == []

    def test_craft_rule_matches_craft_item(self):
        engine = RuleEngine()
        rule = PricingRule(
            rule_id="craft_boost",
            rule_type="craft",
            conditions={},
            adjustment_type="percentage",
            adjustment_value=20,
        )
        engine.add_rule(rule)
        item = _make_item(quality="crafted")
        matched = engine.get_relevant_rules(item)
        assert len(matched) == 1

    def test_disabled_rule_skipped(self):
        engine = RuleEngine()
        rule = PricingRule(
            rule_id="disabled_rule",
            rule_type="lld",
            conditions={},
            adjustment_type="flat",
            adjustment_value=100,
            enabled=False,
        )
        engine.add_rule(rule)
        item = _make_item(diagnostic={"lld_context": True})
        assert engine.get_relevant_rules(item) == []

    def test_priority_ordering(self):
        engine = RuleEngine()
        engine.add_rule(PricingRule(
            rule_id="low_prio", rule_type="lld", conditions={},
            adjustment_type="flat", adjustment_value=10, priority=1,
        ))
        engine.add_rule(PricingRule(
            rule_id="high_prio", rule_type="lld", conditions={},
            adjustment_type="flat", adjustment_value=50, priority=10,
        ))
        item = _make_item(diagnostic={"lld_context": True})
        matched = engine.get_relevant_rules(item)
        assert [r.rule_id for r in matched] == ["high_prio", "low_prio"]

    def test_condition_quality_filter(self):
        engine = RuleEngine()
        engine.add_rule(PricingRule(
            rule_id="rare_only", rule_type="custom", conditions={"quality": "rare"},
            adjustment_type="flat", adjustment_value=50,
        ))
        assert engine.get_relevant_rules(_make_item(quality="rare")) != []
        assert engine.get_relevant_rules(_make_item(quality="unique")) == []

    def test_condition_item_type_filter(self):
        engine = RuleEngine()
        engine.add_rule(PricingRule(
            rule_id="charm_rule", rule_type="custom",
            conditions={"item_type": "charm"},
            adjustment_type="flat", adjustment_value=10,
        ))
        assert engine.get_relevant_rules(_make_item(item_type="small charm")) != []
        assert engine.get_relevant_rules(_make_item(item_type="helm")) == []

    def test_condition_required_properties(self):
        engine = RuleEngine()
        engine.add_rule(PricingRule(
            rule_id="needs_fcr", rule_type="custom",
            conditions={"required_properties": ["fcr"]},
            adjustment_type="percentage", adjustment_value=10,
        ))
        with_fcr = _make_item(base_properties=[Property(name="fcr", value="20")])
        without_fcr = _make_item(base_properties=[Property(name="ias", value="20")])
        assert engine.get_relevant_rules(with_fcr) != []
        assert engine.get_relevant_rules(without_fcr) == []

    def test_condition_keyword(self):
        engine = RuleEngine()
        engine.add_rule(PricingRule(
            rule_id="eth_bonus", rule_type="custom",
            conditions={"keyword": "ethereal"},
            adjustment_type="multiplier", adjustment_value=1.3,
        ))
        assert engine.get_relevant_rules(_make_item(raw_text="Ethereal Thresher")) != []
        assert engine.get_relevant_rules(_make_item(raw_text="Thresher")) == []


# ---------------------------------------------------------------------------
# Rule add / remove
# ---------------------------------------------------------------------------

class TestRuleManagement:
    def test_add_and_remove(self):
        engine = RuleEngine()
        rule = PricingRule(
            rule_id="tmp", rule_type="custom", conditions={},
            adjustment_type="flat", adjustment_value=0,
        )
        engine.add_rule(rule)
        assert engine.remove_rule("tmp") is True
        assert engine.remove_rule("tmp") is False  # already gone


# ---------------------------------------------------------------------------
# Price adjustment calculations
# ---------------------------------------------------------------------------

class TestApplyRules:
    def test_multiplier_adjustment(self):
        engine = RuleEngine()
        engine.add_rule(PricingRule(
            rule_id="lld_mult", rule_type="lld", conditions={},
            adjustment_type="multiplier", adjustment_value=1.5,
        ))
        item = _make_item(diagnostic={"lld_context": True})
        result = engine.apply_rules(item, 100.0)
        assert result.original_estimate_fg == 100.0
        assert result.adjusted_estimate_fg == pytest.approx(150.0)
        assert "lld_mult" in result.rules_applied

    def test_flat_adjustment(self):
        engine = RuleEngine()
        engine.add_rule(PricingRule(
            rule_id="craft_flat", rule_type="craft", conditions={},
            adjustment_type="flat", adjustment_value=200,
        ))
        item = _make_item(quality="crafted")
        result = engine.apply_rules(item, 50.0)
        assert result.adjusted_estimate_fg == pytest.approx(250.0)

    def test_percentage_adjustment(self):
        engine = RuleEngine()
        engine.add_rule(PricingRule(
            rule_id="pct_rule", rule_type="craft", conditions={},
            adjustment_type="percentage", adjustment_value=20,
        ))
        item = _make_item(quality="crafted")
        result = engine.apply_rules(item, 100.0)
        assert result.adjusted_estimate_fg == pytest.approx(120.0)

    def test_no_matching_rules(self):
        engine = RuleEngine()
        item = _make_item(raw_text="Shako", quality="unique")
        result = engine.apply_rules(item, 500.0)
        assert result.adjusted_estimate_fg == 500.0
        assert result.rules_applied == []
        assert result.adjustment_reason == "no adjustment"

    def test_multiple_rules_applied_in_priority_order(self):
        engine = RuleEngine()
        # Higher priority first: multiply by 2
        engine.add_rule(PricingRule(
            rule_id="mult_first", rule_type="lld", conditions={},
            adjustment_type="multiplier", adjustment_value=2.0, priority=10,
        ))
        # Then add flat 50
        engine.add_rule(PricingRule(
            rule_id="flat_second", rule_type="lld", conditions={},
            adjustment_type="flat", adjustment_value=50, priority=5,
        ))
        item = _make_item(diagnostic={"lld_context": True})
        result = engine.apply_rules(item, 100.0)
        # 100 * 2 = 200, then 200 + 50 = 250
        assert result.adjusted_estimate_fg == pytest.approx(250.0)
        assert result.rules_applied == ["mult_first", "flat_second"]

    def test_unknown_adjustment_type_is_noop(self):
        engine = RuleEngine()
        engine.add_rule(PricingRule(
            rule_id="bad_type", rule_type="custom", conditions={},
            adjustment_type="unknown_type", adjustment_value=999,
        ))
        item = _make_item()
        result = engine.apply_rules(item, 100.0)
        assert result.adjusted_estimate_fg == 100.0
        assert result.rules_applied == []
