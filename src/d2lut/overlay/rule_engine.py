"""Rule engine for LLD/craft detection and price adjustments.

Provides in-memory rule storage, LLD and craft item detection,
and price adjustment logic (multiplier, flat, percentage).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PricingRule:
    """A single pricing rule definition."""
    rule_id: str
    rule_type: str  # "lld", "craft", "affix", "custom"
    conditions: dict[str, Any]
    adjustment_type: str  # "multiplier", "flat", "percentage"
    adjustment_value: float
    priority: int = 0
    enabled: bool = True


@dataclass
class AdjustedPriceEstimate:
    """Result of applying rules to a base price."""
    original_estimate_fg: float
    adjusted_estimate_fg: float
    rules_applied: list[str]
    adjustment_reason: str


# ---------------------------------------------------------------------------
# LLD detection helpers
# ---------------------------------------------------------------------------

# Small charms with max damage / AR / life combos are classic LLD items.
_LLD_SC_PROPERTIES = {"max_damage", "ar", "life"}

# Items with requirement level at or below this are LLD-relevant.
_LLD_MAX_REQ_LEVEL = 30

_LLD_KEYWORDS = {"lld", "low level duel", "low level dueling", "low lvl duel"}


def _has_property(parsed_item: Any, name: str) -> bool:
    """Check if *parsed_item* has a base property with the given name."""
    for prop in getattr(parsed_item, "base_properties", []):
        if prop.name == name:
            return True
    return False


def _get_property_value(parsed_item: Any, name: str) -> str | None:
    """Return the string value of a base property, or ``None``."""
    for prop in getattr(parsed_item, "base_properties", []):
        if prop.name == name:
            return prop.value
    return None


# ---------------------------------------------------------------------------
# Craft detection helpers
# ---------------------------------------------------------------------------

_CRAFT_TYPES = {
    "blood": {"blood", "blood craft"},
    "caster": {"caster", "caster craft"},
    "hitpower": {"hitpower", "hit power", "hitpower craft", "hit power craft"},
    "safety": {"safety", "safety craft"},
}

_CRAFT_KEYWORDS = set()
for _kws in _CRAFT_TYPES.values():
    _CRAFT_KEYWORDS.update(_kws)
_CRAFT_KEYWORDS.add("craft")
_CRAFT_KEYWORDS.add("crafted")


# ---------------------------------------------------------------------------
# RuleEngine
# ---------------------------------------------------------------------------

class RuleEngine:
    """In-memory rule engine for LLD/craft detection and price adjustments.

    Rules are stored in a list and matched against ``ParsedItem`` objects.
    Adjustment types supported: ``multiplier``, ``flat``, ``percentage``.
    """

    def __init__(self) -> None:
        self._rules: list[PricingRule] = []

    # -- rule management ----------------------------------------------------

    def add_rule(self, rule: PricingRule) -> None:
        """Add a pricing rule."""
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by id. Returns ``True`` if found and removed."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule by id. Returns ``True`` if found."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule by id. Returns ``True`` if found."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = False
                return True
        return False

    def get_rules(self) -> list[PricingRule]:
        """Return all rules sorted by priority (highest first)."""
        return sorted(self._rules, key=lambda r: r.priority, reverse=True)

    def get_rule(self, rule_id: str) -> PricingRule | None:
        """Return a single rule by id, or ``None`` if not found."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def set_rule_priority(self, rule_id: str, priority: int) -> bool:
        """Update a rule's priority. Returns ``True`` if found."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.priority = priority
                return True
        return False

    # -- DB persistence -----------------------------------------------------

    def load_rules_from_db(self, db_path: str | Path) -> int:
        """Load enabled rules from the ``pricing_rules`` table.

        Replaces the current in-memory rule set.  Returns the number of
        rules loaded.
        """
        db_path = str(db_path)
        con = sqlite3.connect(db_path)
        try:
            cur = con.execute(
                "SELECT rule_id, rule_type, conditions_json, "
                "adjustment_type, adjustment_value, priority, enabled "
                "FROM pricing_rules WHERE enabled = 1 "
                "ORDER BY priority DESC"
            )
            loaded: list[PricingRule] = []
            for row in cur.fetchall():
                loaded.append(PricingRule(
                    rule_id=row[0],
                    rule_type=row[1],
                    conditions=json.loads(row[2]),
                    adjustment_type=row[3],
                    adjustment_value=row[4],
                    priority=row[5],
                    enabled=bool(row[6]),
                ))
            self._rules = loaded
            return len(loaded)
        finally:
            con.close()

    def save_rules_to_db(self, db_path: str | Path) -> int:
        """Persist current in-memory rules to the ``pricing_rules`` table.

        Uses INSERT OR REPLACE so existing rows are updated.  Returns the
        number of rules written.
        """
        db_path = str(db_path)
        con = sqlite3.connect(db_path)
        try:
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
            for rule in self._rules:
                con.execute(
                    "INSERT OR REPLACE INTO pricing_rules "
                    "(rule_id, rule_type, conditions_json, "
                    "adjustment_type, adjustment_value, priority, enabled) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        rule.rule_id,
                        rule.rule_type,
                        json.dumps(rule.conditions),
                        rule.adjustment_type,
                        rule.adjustment_value,
                        rule.priority,
                        int(rule.enabled),
                    ),
                )
            con.commit()
            return len(self._rules)
        finally:
            con.close()

    # -- detection ----------------------------------------------------------

    def check_lld(self, parsed_item: Any) -> bool:
        """Return ``True`` if *parsed_item* looks LLD-relevant.

        Heuristics:
        1. ``diagnostic["lld_context"]`` already set by CategoryAwareParser.
        2. Raw text or item name contains LLD keywords.
        3. Small charm with max_damage + AR + life combo.
        4. Item has a ``req_level`` property <= 30.
        """
        diag: dict = getattr(parsed_item, "diagnostic", {}) or {}
        if diag.get("lld_context"):
            return True

        text = " ".join([
            (getattr(parsed_item, "raw_text", "") or ""),
            (getattr(parsed_item, "item_name", "") or ""),
        ]).lower()

        for kw in _LLD_KEYWORDS:
            if kw in text:
                return True

        # Small charm with max_damage/AR/life combo
        item_type = (getattr(parsed_item, "item_type", "") or "").lower()
        if "charm" in item_type or "small charm" in text or "sc" in text.split():
            present = {p.name for p in getattr(parsed_item, "base_properties", [])}
            if _LLD_SC_PROPERTIES.issubset(present):
                return True

        # Low requirement level
        req_val = _get_property_value(parsed_item, "req_level")
        if req_val is not None:
            try:
                if int(req_val) <= _LLD_MAX_REQ_LEVEL:
                    return True
            except (ValueError, TypeError):
                pass

        return False

    def check_craft(self, parsed_item: Any) -> bool:
        """Return ``True`` if *parsed_item* looks like a crafted item.

        Checks quality field, raw text, and item name for craft keywords.
        """
        quality = (getattr(parsed_item, "quality", "") or "").lower()
        if quality == "crafted":
            return True

        text = " ".join([
            (getattr(parsed_item, "raw_text", "") or ""),
            (getattr(parsed_item, "item_name", "") or ""),
        ]).lower()

        for kw in _CRAFT_KEYWORDS:
            if kw in text:
                return True

        return False

    # -- rule lookup --------------------------------------------------------

    def get_relevant_rules(self, parsed_item: Any) -> list[PricingRule]:
        """Return enabled rules whose conditions match *parsed_item*, sorted
        by descending priority."""
        is_lld = self.check_lld(parsed_item)
        is_craft = self.check_craft(parsed_item)

        matched: list[PricingRule] = []
        for rule in self._rules:
            if not rule.enabled:
                continue
            if self._rule_matches(rule, parsed_item, is_lld, is_craft):
                matched.append(rule)

        matched.sort(key=lambda r: r.priority, reverse=True)
        return matched

    # -- price adjustment ---------------------------------------------------

    def apply_rules(self, parsed_item: Any, base_price_fg: float) -> AdjustedPriceEstimate:
        """Apply all matching rules to *base_price_fg* and return the result."""
        rules = self.get_relevant_rules(parsed_item)
        adjusted = base_price_fg
        applied_ids: list[str] = []
        reasons: list[str] = []

        for rule in rules:
            prev = adjusted
            adjusted = self._apply_adjustment(adjusted, rule)
            if adjusted != prev:
                applied_ids.append(rule.rule_id)
                reasons.append(
                    f"{rule.rule_id}: {rule.adjustment_type} "
                    f"{rule.adjustment_value}"
                )

        return AdjustedPriceEstimate(
            original_estimate_fg=base_price_fg,
            adjusted_estimate_fg=adjusted,
            rules_applied=applied_ids,
            adjustment_reason="; ".join(reasons) if reasons else "no adjustment",
        )

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _apply_adjustment(price: float, rule: PricingRule) -> float:
        """Apply a single rule's adjustment to *price*."""
        if rule.adjustment_type == "multiplier":
            return price * rule.adjustment_value
        if rule.adjustment_type == "flat":
            return price + rule.adjustment_value
        if rule.adjustment_type == "percentage":
            return price * (1.0 + rule.adjustment_value / 100.0)
        return price  # unknown type — no-op

    @staticmethod
    def _rule_matches(
        rule: PricingRule,
        parsed_item: Any,
        is_lld: bool,
        is_craft: bool,
    ) -> bool:
        """Check whether *rule* conditions match *parsed_item*."""
        conds = rule.conditions

        # Type-based shortcut
        if rule.rule_type == "lld" and not is_lld:
            return False
        if rule.rule_type == "craft" and not is_craft:
            return False

        # Condition: required quality
        req_quality = conds.get("quality")
        if req_quality is not None:
            item_quality = (getattr(parsed_item, "quality", "") or "").lower()
            if item_quality != req_quality.lower():
                return False

        # Condition: required item_type substring
        req_type = conds.get("item_type")
        if req_type is not None:
            item_type = (getattr(parsed_item, "item_type", "") or "").lower()
            if req_type.lower() not in item_type:
                return False

        # Condition: required properties (all must be present)
        req_props = conds.get("required_properties")
        if req_props:
            for pname in req_props:
                if not _has_property(parsed_item, pname):
                    return False

        # Condition: keyword in raw_text or item_name
        req_keyword = conds.get("keyword")
        if req_keyword is not None:
            text = " ".join([
                (getattr(parsed_item, "raw_text", "") or ""),
                (getattr(parsed_item, "item_name", "") or ""),
            ]).lower()
            if req_keyword.lower() not in text:
                return False

        return True


# ---------------------------------------------------------------------------
# Default rule definitions
# ---------------------------------------------------------------------------

def load_default_rules() -> list[PricingRule]:
    """Return a set of sensible default pricing rules.

    These can be loaded into a :class:`RuleEngine` via ``add_rule`` or
    persisted to the DB via ``save_rules_to_db``.
    """
    return [
        PricingRule(
            rule_id="default_lld_premium",
            rule_type="lld",
            conditions={},
            adjustment_type="multiplier",
            adjustment_value=1.5,
            priority=10,
            enabled=True,
        ),
        PricingRule(
            rule_id="default_craft_boost",
            rule_type="craft",
            conditions={},
            adjustment_type="flat",
            adjustment_value=50.0,
            priority=5,
            enabled=True,
        ),
        PricingRule(
            rule_id="default_ethereal_premium",
            rule_type="affix",
            conditions={"keyword": "ethereal"},
            adjustment_type="multiplier",
            adjustment_value=1.3,
            priority=8,
            enabled=True,
        ),
    ]
