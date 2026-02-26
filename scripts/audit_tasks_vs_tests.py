#!/usr/bin/env python3
"""Task audit: compare tasks.md markers against pytest results.

Parses task completion markers ([x], [ ], [-], [~]) from tasks.md and runs
the associated test file for each task.  Reports:
  - ok          – marked done and tests pass
  - regressed   – marked done but tests fail
  - completable – marked incomplete but tests pass
  - no_tests    – no test file mapped for this task

Exits non-zero when any regressions are detected.

Usage:
    python scripts/audit_tasks_vs_tests.py
    python scripts/audit_tasks_vs_tests.py --tasks-md path/to/tasks.md --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ── task-to-test mapping ────────────────────────────────────────────
# Keys are task numbers (int), values are test file paths relative to repo root.
TASK_TEST_MAP: dict[int, str] = {
    1: "tests/test_bug_condition_exploration.py",
    2: "tests/test_preservation_properties.py",
    4: "tests/test_parser_regression_corpus.py",
    5: "tests/test_req_level_regression.py",
    6: "tests/test_kit_detection.py",
    7: "tests/test_lld_bucket.py",
    8: "tests/test_runeword_roll_extraction.py",
    9: "tests/test_torch_anni_ocr_fold.py",
    10: "tests/test_base_item_parser_v2.py",
    11: "tests/test_jewel_charm_circlet_v2.py",
    15: "tests/test_display_modes.py",
    16: "tests/test_last_seen_freshness.py",
    17: "tests/test_signal_split_columns.py",
    18: "tests/test_saved_filter_presets.py",
    19: "tests/test_modifier_lexicon_integration.py",
    20: "tests/test_ocr_miss_triage.py",
    21: "tests/test_ocr_quality_dashboard.py",
    22: "tests/test_backfill_source_urls.py",
}

# ── tasks.md parser ─────────────────────────────────────────────────
# Matches lines like:  - [x] 6. Runeword kit ...  or  - [x] 6.1 Add kit ...
_TASK_RE = re.compile(
    r"^\s*-\s+\[(?P<marker>[x ~\-])\]\s+(?P<num>\d+)(?:\.\d+)?\b",
)


def parse_tasks(text: str) -> dict[int, str]:
    """Return {task_number: marker} for top-level tasks in *text*.

    Only the first occurrence of each task number is kept (top-level task line).
    Marker values: 'x', ' ', '-', '~'.
    """
    tasks: dict[int, str] = {}
    for line in text.splitlines():
        m = _TASK_RE.match(line)
        if m is None:
            continue
        num = int(m.group("num"))
        marker = m.group("marker")
        # Keep only the first (top-level) entry per task number.
        if num not in tasks:
            tasks[num] = marker
    return tasks


# ── pytest runner ───────────────────────────────────────────────────

def run_test_file(test_path: str, extra_args: list[str] | None = None) -> bool:
    """Run pytest on *test_path*; return True if all tests pass."""
    repo_root = Path(__file__).resolve().parent.parent
    full = repo_root / test_path
    if not full.exists():
        return False

    cmd = [
        sys.executable, "-m", "pytest",
        "--tb=no", "-q",
        str(full),
    ]
    if extra_args:
        cmd.extend(extra_args)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    result = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        timeout=120,
    )
    return result.returncode == 0


# ── audit logic ─────────────────────────────────────────────────────

def audit(
    tasks: dict[int, str],
    *,
    run_tests: bool = True,
    extra_pytest_args: list[str] | None = None,
) -> list[dict]:
    """Compare task markers against test results.

    Returns a list of dicts with keys: task, marker, test_file, status.
    """
    results: list[dict] = []
    for num in sorted(tasks):
        marker = tasks[num]
        test_file = TASK_TEST_MAP.get(num)
        if test_file is None:
            results.append({
                "task": num,
                "marker": marker,
                "test_file": None,
                "status": "no_tests",
            })
            continue

        if run_tests:
            tests_pass = run_test_file(test_file, extra_pytest_args)
        else:
            tests_pass = None

        marked_done = marker == "x"

        if tests_pass is None:
            status = "skipped"
        elif marked_done and not tests_pass:
            status = "regressed"
        elif not marked_done and tests_pass:
            status = "completable"
        elif marked_done and tests_pass:
            status = "ok"
        else:
            # Not done and tests fail — expected.
            status = "pending"

        results.append({
            "task": num,
            "marker": marker,
            "test_file": test_file,
            "status": status,
        })
    return results


# ── output formatters ───────────────────────────────────────────────

_STATUS_SYMBOLS = {
    "ok": "✓",
    "regressed": "✗",
    "completable": "↑",
    "no_tests": "–",
    "pending": "·",
    "skipped": "?",
}


def print_human(results: list[dict]) -> None:
    regressions = [r for r in results if r["status"] == "regressed"]
    completable = [r for r in results if r["status"] == "completable"]

    print("=== Task Audit Report ===\n")
    for r in results:
        sym = _STATUS_SYMBOLS.get(r["status"], "?")
        tf = r["test_file"] or "(no test file)"
        print(f"  {sym} Task {r['task']:>2}  [{r['marker']}]  {r['status']:<12s}  {tf}")

    print()
    if regressions:
        print(f"REGRESSIONS ({len(regressions)}):")
        for r in regressions:
            print(f"  Task {r['task']}: marked [x] but tests FAIL → {r['test_file']}")
    if completable:
        print(f"\nCOMPLETABLE ({len(completable)}):")
        for r in completable:
            print(f"  Task {r['task']}: marked [{r['marker']}] but tests PASS → {r['test_file']}")
    if not regressions and not completable:
        print("No regressions or completable tasks detected.")


def print_json(results: list[dict]) -> None:
    regressions = [r for r in results if r["status"] == "regressed"]
    completable = [r for r in results if r["status"] == "completable"]
    payload = {
        "results": results,
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r["status"] == "ok"),
            "regressed": len(regressions),
            "completable": len(completable),
            "no_tests": sum(1 for r in results if r["status"] == "no_tests"),
            "pending": sum(1 for r in results if r["status"] == "pending"),
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


# ── CLI ─────────────────────────────────────────────────────────────

def main() -> int:
    default_tasks_md = ".kiro/specs/property-table-quality-sprint/tasks.md"

    p = argparse.ArgumentParser(description="Audit tasks.md markers vs pytest results")
    p.add_argument(
        "--tasks-md",
        default=default_tasks_md,
        help=f"Path to tasks.md (default: {default_tasks_md})",
    )
    p.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    p.add_argument(
        "--pytest-args",
        default="",
        help="Additional pytest arguments (space-separated string)",
    )
    p.add_argument(
        "--no-run",
        action="store_true",
        help="Skip running tests (parse tasks.md only)",
    )
    args = p.parse_args()

    tasks_path = Path(args.tasks_md)
    if not tasks_path.exists():
        print(f"ERROR: tasks.md not found: {tasks_path}", file=sys.stderr)
        return 2

    text = tasks_path.read_text(encoding="utf-8")
    tasks = parse_tasks(text)
    if not tasks:
        print("WARNING: no tasks found in tasks.md", file=sys.stderr)
        return 0

    extra = args.pytest_args.split() if args.pytest_args.strip() else None
    results = audit(tasks, run_tests=not args.no_run, extra_pytest_args=extra)

    if args.json_output:
        print_json(results)
    else:
        print_human(results)

    has_regressions = any(r["status"] == "regressed" for r in results)
    return 1 if has_regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
