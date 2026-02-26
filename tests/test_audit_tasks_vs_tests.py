"""Tests for scripts/audit_tasks_vs_tests.py — parsing and audit logic.

Only tests the pure-logic functions (parse_tasks, audit with run_tests=False).
Does NOT invoke pytest subprocess.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure scripts/ is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.audit_tasks_vs_tests import (
    TASK_TEST_MAP,
    audit,
    parse_tasks,
)


# ── parse_tasks ─────────────────────────────────────────────────────

SAMPLE_TASKS_MD = """\
# Implementation Plan

## Completed

- [x] 1. Write bug condition exploration test
  - 8/11 failed
  - _Requirements: 1.1_

- [x] 2. Write preservation property tests
  - 62 tests passing
  - _Requirements: 1.3_

- [x] 3. Fix stash scan presenter regressions
  - Fixed; 17/17 pass
  - _Requirements: 1.1_

## Active sprint

- [x] 6. Runeword kit vs finished detection
  - [x] 6.1 Add kit boolean
  - [x] 6.2 Update props_signature()
  - [x] 6.3 Add kit/finished filter
  - [x] 6.4 Regression test fixtures

- [ ] 7. LLD bucket assignment
  - [ ] 7.1 Add lld_bucket field
  - [ ] 7.2 Extend lldLevel dropdown

- [-] 23. Task audit script
  - _Requirements: 2.1_

- [~] 24. Final checkpoint
"""


def test_parse_tasks_extracts_top_level():
    tasks = parse_tasks(SAMPLE_TASKS_MD)
    assert tasks[1] == "x"
    assert tasks[2] == "x"
    assert tasks[3] == "x"
    assert tasks[6] == "x"
    assert tasks[7] == " "
    assert tasks[23] == "-"
    assert tasks[24] == "~"


def test_parse_tasks_ignores_subtasks():
    """Sub-tasks (6.1, 6.2, …) should not override the top-level marker."""
    tasks = parse_tasks(SAMPLE_TASKS_MD)
    # Task 6 should be 'x' from the top-level line, not from 6.1/6.2/etc.
    assert tasks[6] == "x"
    # Sub-task numbers like 6.1 should not appear as separate keys.
    # (They share the same integer prefix 6.)
    assert 6 in tasks


def test_parse_tasks_empty():
    assert parse_tasks("") == {}
    assert parse_tasks("# No tasks here\nJust text.") == {}


def test_parse_tasks_all_marker_types():
    text = """\
- [x] 1. Done
- [ ] 2. Not done
- [-] 3. In progress
- [~] 4. Partial
"""
    tasks = parse_tasks(text)
    assert tasks == {1: "x", 2: " ", 3: "-", 4: "~"}


# ── audit (no test execution) ──────────────────────────────────────

def test_audit_no_run_marks_skipped():
    tasks = {1: "x", 3: "x", 7: " "}
    results = audit(tasks, run_tests=False)
    for r in results:
        if r["test_file"] is not None:
            assert r["status"] == "skipped"


def test_audit_no_tests_for_unmapped_tasks():
    tasks = {3: "x", 14: " "}  # tasks 3 and 14 have no test file
    results = audit(tasks, run_tests=False)
    for r in results:
        assert r["status"] == "no_tests"
        assert r["test_file"] is None


def test_audit_result_fields():
    tasks = {1: "x"}
    results = audit(tasks, run_tests=False)
    assert len(results) == 1
    r = results[0]
    assert "task" in r
    assert "marker" in r
    assert "test_file" in r
    assert "status" in r
    assert r["task"] == 1
    assert r["marker"] == "x"
    assert r["test_file"] == TASK_TEST_MAP[1]


def test_audit_sorted_by_task_number():
    tasks = {22: "x", 1: "x", 10: " "}
    results = audit(tasks, run_tests=False)
    task_nums = [r["task"] for r in results]
    assert task_nums == sorted(task_nums)


# ── TASK_TEST_MAP sanity ────────────────────────────────────────────

def test_task_test_map_values_are_strings():
    for k, v in TASK_TEST_MAP.items():
        assert isinstance(k, int)
        assert isinstance(v, str)
        assert v.startswith("tests/")
        assert v.endswith(".py")
