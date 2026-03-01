"""Tests for rule management interface (enable/disable, get, priority)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from d2lut.overlay.ocr_parser import ParsedItem, Property
from d2lut.overlay.rule_engine import PricingRule, RuleEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule(rule_id: str, rule_type: str = "custom", priority: int = 0,
          enabled: bool = True, adj_type: str = "flat",
          adj_value: float = 10.0, conditions: dict | None = None) -> PricingRule:
    return PricingRule(
        rule_id=rule_id,
        rule_type=rule_type,
        conditions=conditions or {},
        adjustment_type=adj_type,
        adjustment_value=adj_value,
        priority=priority,
        enabled=enabled,
    )


def _make_item(**kwargs) -> ParsedItem:
    defaults = dict(raw_text="", item_name=None, item_type=None,
                    quality=None, base_properties=[], diagnostic={})
    defaults.update(kwargs)
    return ParsedItem(**defaults)


def _create_db(path: str | Path) -> None:
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE IF NOT EXISTS pricing_rules ("
        "  rule_id TEXT PRIMARY KEY,"
        "  rule_type TEXT NOT NULL,"
        "  conditions_json TEXT NOT NULL,"
        "  adjustment_type TEXT NOT NULL,"
        "  adjustment_value REAL NOT NULL,"
        "  priority INTEGER NOT NULL DEFAULT 0,"
        "  enabled INTEGER NOT NULL DEFAULT 1"
        ")"
    )
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Enable / Disable
# ---------------------------------------------------------------------------

class TestEnableDisable:
    def test_disable_rule(self):
        engine = RuleEngine()
        engine.add_rule(_rule("r1"))
        assert engine.disable_rule("r1") is True
        assert engine.get_rule("r1").enabled is False

    def test_enable_rule(self):
        engine = RuleEngine()
        engine.add_rule(_rule("r1", enabled=False))
        assert engine.enable_rule("r1") is True
        assert engine.get_rule("r1").enabled is True

    def test_disable_nonexistent_returns_false(self):
        engine = RuleEngine()
        assert engine.disable_rule("nope") is False

    def test_enable_nonexistent_returns_false(self):
        engine = RuleEngine()
        assert engine.enable_rule("nope") is False

    def test_toggle_round_trip(self):
        engine = RuleEngine()
        engine.add_rule(_rule("r1"))
        engine.disable_rule("r1")
        assert engine.get_rule("r1").enabled is False
        engine.enable_rule("r1")
        assert engine.get_rule("r1").enabled is True


# ---------------------------------------------------------------------------
# Disabled rules excluded from get_relevant_rules / apply_rules
# ---------------------------------------------------------------------------

class TestDisabledRulesExcluded:
    def test_disabled_rule_not_in_relevant(self):
        engine = RuleEngine()
        engine.add_rule(_rule("r1", rule_type="lld", enabled=False))
        item = _make_item(diagnostic={"lld_context": True})
        assert engine.get_relevant_rules(item) == []

    def test_disabled_rule_not_applied(self):
        engine = RuleEngine()
        engine.add_rule(_rule("r1", rule_type="lld", adj_type="flat",
                              adj_value=100.0, enabled=False))
        item = _make_item(diagnostic={"lld_context": True})
        result = engine.apply_rules(item, 50.0)
        assert result.adjusted_estimate_fg == pytest.approx(50.0)
        assert result.rules_applied == []

    def test_re_enabled_rule_applies_again(self):
        engine = RuleEngine()
        engine.add_rule(_rule("r1", rule_type="lld", adj_type="flat",
                              adj_value=100.0))
        engine.disable_rule("r1")
        item = _make_item(diagnostic={"lld_context": True})
        assert engine.apply_rules(item, 50.0).adjusted_estimate_fg == pytest.approx(50.0)

        engine.enable_rule("r1")
        assert engine.apply_rules(item, 50.0).adjusted_estimate_fg == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# get_rules / get_rule
# ---------------------------------------------------------------------------

class TestGetRules:
    def test_get_rules_sorted_by_priority(self):
        engine = RuleEngine()
        engine.add_rule(_rule("low", priority=1))
        engine.add_rule(_rule("high", priority=10))
        engine.add_rule(_rule("mid", priority=5))
        ids = [r.rule_id for r in engine.get_rules()]
        assert ids == ["high", "mid", "low"]

    def test_get_rules_includes_disabled(self):
        engine = RuleEngine()
        engine.add_rule(_rule("on", enabled=True))
        engine.add_rule(_rule("off", enabled=False))
        ids = {r.rule_id for r in engine.get_rules()}
        assert ids == {"on", "off"}

    def test_get_rules_empty(self):
        engine = RuleEngine()
        assert engine.get_rules() == []

    def test_get_rule_found(self):
        engine = RuleEngine()
        engine.add_rule(_rule("r1", priority=7))
        r = engine.get_rule("r1")
        assert r is not None
        assert r.rule_id == "r1"
        assert r.priority == 7

    def test_get_rule_not_found(self):
        engine = RuleEngine()
        assert engine.get_rule("missing") is None


# ---------------------------------------------------------------------------
# set_rule_priority
# ---------------------------------------------------------------------------

class TestSetRulePriority:
    def test_set_priority(self):
        engine = RuleEngine()
        engine.add_rule(_rule("r1", priority=0))
        assert engine.set_rule_priority("r1", 99) is True
        assert engine.get_rule("r1").priority == 99

    def test_set_priority_nonexistent(self):
        engine = RuleEngine()
        assert engine.set_rule_priority("nope", 5) is False

    def test_priority_affects_apply_order(self):
        engine = RuleEngine()
        # Both match any item (custom type, no conditions)
        engine.add_rule(_rule("mult", adj_type="multiplier", adj_value=2.0, priority=1))
        engine.add_rule(_rule("flat", adj_type="flat", adj_value=50.0, priority=10))
        item = _make_item()
        # flat first (prio 10): 100+50=150, then mult (prio 1): 150*2=300
        result = engine.apply_rules(item, 100.0)
        assert result.adjusted_estimate_fg == pytest.approx(300.0)

        # Swap priorities
        engine.set_rule_priority("mult", 20)
        engine.set_rule_priority("flat", 1)
        # mult first (prio 20): 100*2=200, then flat (prio 1): 200+50=250
        result2 = engine.apply_rules(item, 100.0)
        assert result2.adjusted_estimate_fg == pytest.approx(250.0)


# ---------------------------------------------------------------------------
# Save / load preserves enabled state
# ---------------------------------------------------------------------------

class TestPersistEnabledState:
    def test_save_load_preserves_enabled(self, tmp_path: Path):
        db = tmp_path / "rules.db"
        engine = RuleEngine()
        engine.add_rule(_rule("on", enabled=True, priority=5))
        engine.add_rule(_rule("off", enabled=False, priority=3))
        engine.save_rules_to_db(db)

        engine2 = RuleEngine()
        # load_rules_from_db only loads enabled=1 rows
        engine2.load_rules_from_db(db)
        assert len(engine2._rules) == 1
        assert engine2._rules[0].rule_id == "on"
        assert engine2._rules[0].enabled is True

    def test_disabled_rule_persisted_in_db(self, tmp_path: Path):
        """Disabled rules are written to DB even though load skips them."""
        db = tmp_path / "rules.db"
        engine = RuleEngine()
        engine.add_rule(_rule("off", enabled=False))
        engine.save_rules_to_db(db)

        con = sqlite3.connect(str(db))
        row = con.execute(
            "SELECT enabled FROM pricing_rules WHERE rule_id = ?", ("off",)
        ).fetchone()
        con.close()
        assert row is not None
        assert row[0] == 0


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_existing_rules_work_unchanged(self):
        """Rules created without explicit enabled/priority use defaults."""
        engine = RuleEngine()
        rule = PricingRule(
            rule_id="legacy",
            rule_type="custom",
            conditions={},
            adjustment_type="flat",
            adjustment_value=25.0,
        )
        engine.add_rule(rule)
        assert rule.enabled is True
        assert rule.priority == 0
        item = _make_item()
        result = engine.apply_rules(item, 100.0)
        assert result.adjusted_estimate_fg == pytest.approx(125.0)

    def test_add_remove_still_works(self):
        engine = RuleEngine()
        engine.add_rule(_rule("a"))
        engine.add_rule(_rule("b"))
        assert engine.remove_rule("a") is True
        assert engine.remove_rule("a") is False
        assert len(engine.get_rules()) == 1
