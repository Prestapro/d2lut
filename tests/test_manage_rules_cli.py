"""Tests for scripts/manage_rules.py CLI tool."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure src is on path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from manage_rules import main, _ensure_table, _load_all_rules_from_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db(tmp_path: Path) -> str:
    """Return a fresh DB path string and ensure the table exists."""
    p = str(tmp_path / "test_rules.db")
    _ensure_table(p)
    return p


def _count_rules(db_path: str) -> int:
    con = sqlite3.connect(db_path)
    try:
        return con.execute("SELECT count(*) FROM pricing_rules").fetchone()[0]
    finally:
        con.close()


def _get_field(db_path: str, rule_id: str, field: str):
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            f"SELECT {field} FROM pricing_rules WHERE rule_id = ?",
            (rule_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestList:
    def test_list_empty(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "list"])
        assert rc == 0
        assert "No rules found" in capsys.readouterr().out

    def test_list_shows_rules(self, tmp_path, capsys):
        db = _db(tmp_path)
        main(["--db", db, "add", "--id", "r1", "--adj-type", "flat",
              "--adj-value", "10", "--priority", "5"])
        rc = main(["--db", db, "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "r1" in out
        assert "flat" in out
        assert "1 rule(s)" in out


# ---------------------------------------------------------------------------
# add + list round trip
# ---------------------------------------------------------------------------

class TestAdd:
    def test_add_and_list(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "add", "--id", "test_rule",
                    "--type", "lld", "--adj-type", "multiplier",
                    "--adj-value", "1.5", "--priority", "10"])
        assert rc == 0
        assert _count_rules(db) == 1

        rules = _load_all_rules_from_db(db)
        r = rules[0]
        assert r.rule_id == "test_rule"
        assert r.rule_type == "lld"
        assert r.adjustment_type == "multiplier"
        assert r.adjustment_value == pytest.approx(1.5)
        assert r.priority == 10
        assert r.enabled is True

    def test_add_with_conditions(self, tmp_path):
        db = _db(tmp_path)
        conds = json.dumps({"keyword": "ethereal"})
        rc = main(["--db", db, "add", "--id", "eth_rule",
                    "--adj-type", "percentage", "--adj-value", "30",
                    "--conditions", conds])
        assert rc == 0
        rules = _load_all_rules_from_db(db)
        assert rules[0].conditions == {"keyword": "ethereal"}

    def test_add_invalid_adj_type(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "add", "--id", "bad",
                    "--adj-type", "bogus", "--adj-value", "10"])
        assert rc == 1
        assert "must be one of" in capsys.readouterr().err

    def test_add_empty_id(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "add", "--id", "",
                    "--adj-type", "flat", "--adj-value", "10"])
        assert rc == 1
        assert "non-empty" in capsys.readouterr().err

    def test_add_invalid_conditions_json(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "add", "--id", "x",
                    "--adj-type", "flat", "--adj-value", "10",
                    "--conditions", "{bad json}"])
        assert rc == 1
        assert "invalid JSON" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

class TestRemove:
    def test_remove_existing(self, tmp_path, capsys):
        db = _db(tmp_path)
        main(["--db", db, "add", "--id", "r1", "--adj-type", "flat",
              "--adj-value", "10"])
        assert _count_rules(db) == 1
        rc = main(["--db", db, "remove", "--id", "r1"])
        assert rc == 0
        assert _count_rules(db) == 0
        assert "Removed" in capsys.readouterr().out

    def test_remove_nonexistent(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "remove", "--id", "nope"])
        assert rc == 1
        assert "not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# enable / disable
# ---------------------------------------------------------------------------

class TestEnableDisable:
    def test_disable_and_enable(self, tmp_path, capsys):
        db = _db(tmp_path)
        main(["--db", db, "add", "--id", "r1", "--adj-type", "flat",
              "--adj-value", "10"])
        assert _get_field(db, "r1", "enabled") == 1

        rc = main(["--db", db, "disable", "--id", "r1"])
        assert rc == 0
        assert _get_field(db, "r1", "enabled") == 0

        rc = main(["--db", db, "enable", "--id", "r1"])
        assert rc == 0
        assert _get_field(db, "r1", "enabled") == 1

    def test_enable_nonexistent(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "enable", "--id", "nope"])
        assert rc == 1
        assert "not found" in capsys.readouterr().err

    def test_disable_nonexistent(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "disable", "--id", "nope"])
        assert rc == 1
        assert "not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# set-priority
# ---------------------------------------------------------------------------

class TestSetPriority:
    def test_set_priority(self, tmp_path, capsys):
        db = _db(tmp_path)
        main(["--db", db, "add", "--id", "r1", "--adj-type", "flat",
              "--adj-value", "10", "--priority", "0"])
        rc = main(["--db", db, "set-priority", "--id", "r1", "--priority", "99"])
        assert rc == 0
        assert _get_field(db, "r1", "priority") == 99

    def test_set_priority_nonexistent(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "set-priority", "--id", "nope", "--priority", "5"])
        assert rc == 1
        assert "not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# load-defaults
# ---------------------------------------------------------------------------

class TestLoadDefaults:
    def test_load_defaults(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "load-defaults"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "default rule(s)" in out
        # Should have at least the 3 defaults from load_default_rules()
        assert _count_rules(db) >= 3


# ---------------------------------------------------------------------------
# export / import round trip
# ---------------------------------------------------------------------------

class TestExportImport:
    def test_export_import_round_trip(self, tmp_path, capsys):
        db = _db(tmp_path)
        # Add two rules
        main(["--db", db, "add", "--id", "r1", "--type", "lld",
              "--adj-type", "multiplier", "--adj-value", "2.0", "--priority", "10"])
        main(["--db", db, "add", "--id", "r2", "--type", "craft",
              "--adj-type", "flat", "--adj-value", "50", "--priority", "5"])

        # Export
        out_file = str(tmp_path / "rules.json")
        rc = main(["--db", db, "export", "--output", out_file])
        assert rc == 0
        assert Path(out_file).exists()

        data = json.loads(Path(out_file).read_text())
        assert len(data) == 2

        # Import into a fresh DB
        db2 = str(tmp_path / "fresh.db")
        _ensure_table(db2)
        rc = main(["--db", db2, "import", "--input", out_file])
        assert rc == 0
        assert _count_rules(db2) == 2

        rules = _load_all_rules_from_db(db2)
        ids = {r.rule_id for r in rules}
        assert ids == {"r1", "r2"}

    def test_import_nonexistent_file(self, tmp_path, capsys):
        db = _db(tmp_path)
        rc = main(["--db", db, "import", "--input", "/no/such/file.json"])
        assert rc == 1
        assert "not found" in capsys.readouterr().err

    def test_import_invalid_json(self, tmp_path, capsys):
        db = _db(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")
        rc = main(["--db", db, "import", "--input", str(bad)])
        assert rc == 1
        assert "invalid JSON" in capsys.readouterr().err

    def test_import_skips_invalid_entries(self, tmp_path, capsys):
        db = _db(tmp_path)
        data = [
            {"rule_id": "good", "adjustment_type": "flat",
             "adjustment_value": 10, "priority": 0},
            {"rule_id": "", "adjustment_type": "flat",
             "adjustment_value": 10},  # empty id
            {"rule_id": "bad_adj", "adjustment_type": "bogus",
             "adjustment_value": 10},  # bad adj type
        ]
        f = tmp_path / "mixed.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        rc = main(["--db", db, "import", "--input", str(f)])
        assert rc == 0
        assert _count_rules(db) == 1
        assert "Imported 1 rule(s)" in capsys.readouterr().out

    def test_export_empty_db(self, tmp_path, capsys):
        db = _db(tmp_path)
        out_file = str(tmp_path / "empty.json")
        rc = main(["--db", db, "export", "--output", out_file])
        assert rc == 0
        data = json.loads(Path(out_file).read_text())
        assert data == []
