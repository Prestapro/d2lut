"""Tests for rule engine DB persistence and default rules."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from d2lut.overlay.rule_engine import (
    PricingRule,
    RuleEngine,
    load_default_rules,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_db(path: str | Path) -> None:
    """Create a fresh DB with the pricing_rules table."""
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


def _insert_rule(path: str | Path, rule_id: str, rule_type: str,
                 conditions: dict, adj_type: str, adj_value: float,
                 priority: int = 0, enabled: int = 1) -> None:
    con = sqlite3.connect(str(path))
    con.execute(
        "INSERT INTO pricing_rules "
        "(rule_id, rule_type, conditions_json, adjustment_type, "
        "adjustment_value, priority, enabled) VALUES (?,?,?,?,?,?,?)",
        (rule_id, rule_type, json.dumps(conditions), adj_type,
         adj_value, priority, enabled),
    )
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Tests: load_rules_from_db
# ---------------------------------------------------------------------------

class TestLoadRulesFromDB:
    def test_loads_enabled_rules(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _create_db(db)
        _insert_rule(db, "r1", "lld", {}, "multiplier", 1.5, priority=10)
        _insert_rule(db, "r2", "craft", {}, "flat", 50.0, priority=5)

        engine = RuleEngine()
        count = engine.load_rules_from_db(db)

        assert count == 2
        ids = [r.rule_id for r in engine._rules]
        assert "r1" in ids
        assert "r2" in ids

    def test_skips_disabled_rules(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _create_db(db)
        _insert_rule(db, "r1", "lld", {}, "multiplier", 1.5, enabled=1)
        _insert_rule(db, "r2", "craft", {}, "flat", 50.0, enabled=0)

        engine = RuleEngine()
        count = engine.load_rules_from_db(db)

        assert count == 1
        assert engine._rules[0].rule_id == "r1"

    def test_replaces_existing_rules(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _create_db(db)
        _insert_rule(db, "r1", "lld", {}, "multiplier", 1.5)

        engine = RuleEngine()
        engine.add_rule(PricingRule("old", "custom", {}, "flat", 10.0))
        assert len(engine._rules) == 1

        engine.load_rules_from_db(db)
        assert len(engine._rules) == 1
        assert engine._rules[0].rule_id == "r1"

    def test_loads_conditions_json(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _create_db(db)
        conds = {"keyword": "ethereal", "quality": "unique"}
        _insert_rule(db, "r1", "affix", conds, "multiplier", 1.3)

        engine = RuleEngine()
        engine.load_rules_from_db(db)

        assert engine._rules[0].conditions == conds

    def test_empty_table(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        _create_db(db)

        engine = RuleEngine()
        count = engine.load_rules_from_db(db)

        assert count == 0
        assert engine._rules == []


# ---------------------------------------------------------------------------
# Tests: save_rules_to_db
# ---------------------------------------------------------------------------

class TestSaveRulesToDB:
    def test_save_and_reload(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"

        engine = RuleEngine()
        for rule in load_default_rules():
            engine.add_rule(rule)
        written = engine.save_rules_to_db(db)
        assert written == 3

        engine2 = RuleEngine()
        loaded = engine2.load_rules_from_db(db)
        assert loaded == 3

        ids = {r.rule_id for r in engine2._rules}
        assert ids == {"default_lld_premium", "default_craft_boost",
                       "default_ethereal_premium"}

    def test_upsert_existing_rule(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"

        engine = RuleEngine()
        engine.add_rule(PricingRule("r1", "lld", {}, "multiplier", 1.5))
        engine.save_rules_to_db(db)

        # Change the value and save again
        engine._rules[0] = PricingRule("r1", "lld", {}, "multiplier", 2.0)
        engine.save_rules_to_db(db)

        engine2 = RuleEngine()
        engine2.load_rules_from_db(db)
        assert engine2._rules[0].adjustment_value == pytest.approx(2.0)

    def test_creates_table_if_missing(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        # Don't call _create_db — save_rules_to_db should create the table
        engine = RuleEngine()
        engine.add_rule(PricingRule("r1", "lld", {}, "multiplier", 1.5))
        written = engine.save_rules_to_db(db)
        assert written == 1

        engine2 = RuleEngine()
        engine2.load_rules_from_db(db)
        assert len(engine2._rules) == 1

    def test_preserves_conditions_json(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        conds = {"keyword": "ethereal", "required_properties": ["ed"]}

        engine = RuleEngine()
        engine.add_rule(PricingRule("r1", "affix", conds, "multiplier", 1.3))
        engine.save_rules_to_db(db)

        engine2 = RuleEngine()
        engine2.load_rules_from_db(db)
        assert engine2._rules[0].conditions == conds


# ---------------------------------------------------------------------------
# Tests: load_default_rules
# ---------------------------------------------------------------------------

class TestLoadDefaultRules:
    def test_returns_three_rules(self) -> None:
        rules = load_default_rules()
        assert len(rules) == 3

    def test_lld_premium_rule(self) -> None:
        rules = {r.rule_id: r for r in load_default_rules()}
        lld = rules["default_lld_premium"]
        assert lld.rule_type == "lld"
        assert lld.adjustment_type == "multiplier"
        assert lld.adjustment_value == pytest.approx(1.5)
        assert lld.enabled is True

    def test_craft_boost_rule(self) -> None:
        rules = {r.rule_id: r for r in load_default_rules()}
        craft = rules["default_craft_boost"]
        assert craft.rule_type == "craft"
        assert craft.adjustment_type == "flat"
        assert craft.adjustment_value == pytest.approx(50.0)
        assert craft.enabled is True

    def test_ethereal_premium_rule(self) -> None:
        rules = {r.rule_id: r for r in load_default_rules()}
        eth = rules["default_ethereal_premium"]
        assert eth.rule_type == "affix"
        assert eth.adjustment_type == "multiplier"
        assert eth.adjustment_value == pytest.approx(1.3)
        assert eth.conditions == {"keyword": "ethereal"}
        assert eth.enabled is True

    def test_all_rules_have_unique_ids(self) -> None:
        rules = load_default_rules()
        ids = [r.rule_id for r in rules]
        assert len(ids) == len(set(ids))

    def test_default_rules_configurable_via_db(self, tmp_path: Path) -> None:
        """Default rules can be saved to DB, reloaded, and used."""
        db = tmp_path / "test.db"
        engine = RuleEngine()
        for rule in load_default_rules():
            engine.add_rule(rule)
        engine.save_rules_to_db(db)

        engine2 = RuleEngine()
        engine2.load_rules_from_db(db)
        assert len(engine2._rules) == 3
