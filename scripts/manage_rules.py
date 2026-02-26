#!/usr/bin/env python3
"""CLI tool for managing pricing rules in the d2lut overlay system.

Usage examples:
    python scripts/manage_rules.py --db data/cache/d2lut.db list
    python scripts/manage_rules.py --db data/cache/d2lut.db add \
        --id my_rule --type custom --adj-type flat --adj-value 50 --priority 5
    python scripts/manage_rules.py --db data/cache/d2lut.db remove --id my_rule
    python scripts/manage_rules.py --db data/cache/d2lut.db enable --id my_rule
    python scripts/manage_rules.py --db data/cache/d2lut.db disable --id my_rule
    python scripts/manage_rules.py --db data/cache/d2lut.db set-priority --id my_rule --priority 10
    python scripts/manage_rules.py --db data/cache/d2lut.db load-defaults
    python scripts/manage_rules.py --db data/cache/d2lut.db export --output rules.json
    python scripts/manage_rules.py --db data/cache/d2lut.db import --input rules.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Allow running from repo root with PYTHONPATH=src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from d2lut.overlay.rule_engine import PricingRule, RuleEngine, load_default_rules

# Valid adjustment types
VALID_ADJ_TYPES = {"multiplier", "flat", "percentage"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_table(db_path: str) -> None:
    """Create the pricing_rules table if it doesn't exist."""
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
        con.commit()
    finally:
        con.close()


def _load_all_rules_from_db(db_path: str) -> list[PricingRule]:
    """Load ALL rules from DB (including disabled ones)."""
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            "SELECT rule_id, rule_type, conditions_json, "
            "adjustment_type, adjustment_value, priority, enabled "
            "FROM pricing_rules ORDER BY priority DESC"
        )
        rules: list[PricingRule] = []
        for row in cur.fetchall():
            rules.append(PricingRule(
                rule_id=row[0],
                rule_type=row[1],
                conditions=json.loads(row[2]),
                adjustment_type=row[3],
                adjustment_value=row[4],
                priority=row[5],
                enabled=bool(row[6]),
            ))
        return rules
    finally:
        con.close()


def _save_single_rule(db_path: str, rule: PricingRule) -> None:
    """Insert or replace a single rule in the DB."""
    con = sqlite3.connect(db_path)
    try:
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
    finally:
        con.close()


def _update_field(db_path: str, rule_id: str, field: str, value: object) -> bool:
    """Update a single field for a rule. Returns True if row existed."""
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            f"UPDATE pricing_rules SET {field} = ? WHERE rule_id = ?",
            (value, rule_id),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def _delete_rule(db_path: str, rule_id: str) -> bool:
    """Delete a rule by id. Returns True if row existed."""
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            "DELETE FROM pricing_rules WHERE rule_id = ?", (rule_id,)
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def _validate_rule_id(rule_id: str) -> str | None:
    """Return error message if rule_id is invalid, else None."""
    if not rule_id or not rule_id.strip():
        return "rule_id must be non-empty"
    return None


def _validate_adj_type(adj_type: str) -> str | None:
    """Return error message if adjustment_type is invalid, else None."""
    if adj_type not in VALID_ADJ_TYPES:
        return f"adjustment_type must be one of {sorted(VALID_ADJ_TYPES)}, got '{adj_type}'"
    return None


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    _ensure_table(args.db)
    rules = _load_all_rules_from_db(args.db)
    if not rules:
        print("No rules found.")
        return 0
    # Header
    fmt = "{:<25s} {:<10s} {:<12s} {:>10s} {:>8s} {:>8s}"
    print(fmt.format("rule_id", "type", "adj_type", "adj_value", "priority", "enabled"))
    print("-" * 78)
    for r in rules:
        print(fmt.format(
            r.rule_id[:25],
            r.rule_type[:10],
            r.adjustment_type[:12],
            f"{r.adjustment_value:.2f}",
            str(r.priority),
            "yes" if r.enabled else "no",
        ))
    print(f"\n{len(rules)} rule(s) total.")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    err = _validate_rule_id(args.id)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    err = _validate_adj_type(args.adj_type)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    conditions: dict = {}
    if args.conditions:
        try:
            conditions = json.loads(args.conditions)
        except json.JSONDecodeError as exc:
            print(f"Error: invalid JSON for --conditions: {exc}", file=sys.stderr)
            return 1

    rule = PricingRule(
        rule_id=args.id,
        rule_type=args.type,
        conditions=conditions,
        adjustment_type=args.adj_type,
        adjustment_value=args.adj_value,
        priority=args.priority,
        enabled=True,
    )
    _ensure_table(args.db)
    _save_single_rule(args.db, rule)
    print(f"Added rule '{args.id}'.")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    _ensure_table(args.db)
    if _delete_rule(args.db, args.id):
        print(f"Removed rule '{args.id}'.")
        return 0
    print(f"Rule '{args.id}' not found.", file=sys.stderr)
    return 1


def cmd_enable(args: argparse.Namespace) -> int:
    _ensure_table(args.db)
    if _update_field(args.db, args.id, "enabled", 1):
        print(f"Enabled rule '{args.id}'.")
        return 0
    print(f"Rule '{args.id}' not found.", file=sys.stderr)
    return 1


def cmd_disable(args: argparse.Namespace) -> int:
    _ensure_table(args.db)
    if _update_field(args.db, args.id, "enabled", 0):
        print(f"Disabled rule '{args.id}'.")
        return 0
    print(f"Rule '{args.id}' not found.", file=sys.stderr)
    return 1


def cmd_set_priority(args: argparse.Namespace) -> int:
    _ensure_table(args.db)
    if _update_field(args.db, args.id, "priority", args.priority):
        print(f"Set priority of '{args.id}' to {args.priority}.")
        return 0
    print(f"Rule '{args.id}' not found.", file=sys.stderr)
    return 1


def cmd_load_defaults(args: argparse.Namespace) -> int:
    _ensure_table(args.db)
    defaults = load_default_rules()
    for rule in defaults:
        _save_single_rule(args.db, rule)
    print(f"Loaded {len(defaults)} default rule(s).")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    _ensure_table(args.db)
    rules = _load_all_rules_from_db(args.db)
    data = [
        {
            "rule_id": r.rule_id,
            "rule_type": r.rule_type,
            "conditions": r.conditions,
            "adjustment_type": r.adjustment_type,
            "adjustment_value": r.adjustment_value,
            "priority": r.priority,
            "enabled": r.enabled,
        }
        for r in rules
    ]
    out_path = Path(args.output)
    out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(data)} rule(s) to {out_path}.")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Error: file not found: {in_path}", file=sys.stderr)
        return 1
    try:
        data = json.loads(in_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, list):
        print("Error: expected a JSON array of rule objects", file=sys.stderr)
        return 1

    _ensure_table(args.db)
    count = 0
    for entry in data:
        err = _validate_rule_id(entry.get("rule_id", ""))
        if err:
            print(f"Skipping invalid entry: {err}", file=sys.stderr)
            continue
        adj_type = entry.get("adjustment_type", "")
        err = _validate_adj_type(adj_type)
        if err:
            print(f"Skipping '{entry['rule_id']}': {err}", file=sys.stderr)
            continue
        try:
            adj_value = float(entry["adjustment_value"])
        except (KeyError, ValueError, TypeError) as exc:
            print(f"Skipping '{entry['rule_id']}': bad adjustment_value: {exc}",
                  file=sys.stderr)
            continue

        rule = PricingRule(
            rule_id=entry["rule_id"],
            rule_type=entry.get("rule_type", "custom"),
            conditions=entry.get("conditions", {}),
            adjustment_type=adj_type,
            adjustment_value=adj_value,
            priority=int(entry.get("priority", 0)),
            enabled=bool(entry.get("enabled", True)),
        )
        _save_single_rule(args.db, rule)
        count += 1

    print(f"Imported {count} rule(s) from {in_path}.")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage d2lut pricing rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", required=True, help="Path to SQLite database")

    sub = parser.add_subparsers(dest="command", required=True)

    # list
    sub.add_parser("list", help="List all rules")

    # add
    p_add = sub.add_parser("add", help="Add a new rule")
    p_add.add_argument("--id", required=True, help="Rule ID")
    p_add.add_argument("--type", default="custom",
                       help="Rule type (lld, craft, affix, custom)")
    p_add.add_argument("--adj-type", required=True,
                       help="Adjustment type (multiplier, flat, percentage)")
    p_add.add_argument("--adj-value", required=True, type=float,
                       help="Adjustment value (numeric)")
    p_add.add_argument("--priority", type=int, default=0, help="Rule priority")
    p_add.add_argument("--conditions", default=None,
                       help="JSON string of conditions (optional)")

    # remove
    p_rm = sub.add_parser("remove", help="Remove a rule")
    p_rm.add_argument("--id", required=True, help="Rule ID to remove")

    # enable
    p_en = sub.add_parser("enable", help="Enable a rule")
    p_en.add_argument("--id", required=True, help="Rule ID to enable")

    # disable
    p_dis = sub.add_parser("disable", help="Disable a rule")
    p_dis.add_argument("--id", required=True, help="Rule ID to disable")

    # set-priority
    p_pri = sub.add_parser("set-priority", help="Set rule priority")
    p_pri.add_argument("--id", required=True, help="Rule ID")
    p_pri.add_argument("--priority", required=True, type=int, help="New priority")

    # load-defaults
    sub.add_parser("load-defaults", help="Load default rules into DB")

    # export
    p_exp = sub.add_parser("export", help="Export rules to JSON file")
    p_exp.add_argument("--output", required=True, help="Output JSON file path")

    # import
    p_imp = sub.add_parser("import", help="Import rules from JSON file")
    p_imp.add_argument("--input", required=True, help="Input JSON file path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "list": cmd_list,
        "add": cmd_add,
        "remove": cmd_remove,
        "enable": cmd_enable,
        "disable": cmd_disable,
        "set-priority": cmd_set_priority,
        "load-defaults": cmd_load_defaults,
        "export": cmd_export,
        "import": cmd_import,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
