#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


PATTERNS = {
    "crossover": re.compile(r"CrossOver", re.IGNORECASE),
    "battlenet_mac": re.compile(r"/Applications/Battle\.net\.app", re.IGNORECASE),
    "battlenet_win": re.compile(r"Battle\.net\.exe", re.IGNORECASE),
    "agent": re.compile(r"Agent(?:\.exe)?", re.IGNORECASE),
    "d2r": re.compile(r"(?:\\|/)D2R\.exe\b|Diablo II Resurrected", re.IGNORECASE),
    "wine": re.compile(r"\bwine(?:server|wrapper)?\b", re.IGNORECASE),
}


@dataclass(slots=True)
class ProcessSnapshot:
    timestamp: str
    crossover: bool
    battlenet: bool
    d2r: bool
    agent: bool
    wine: bool
    state: str
    d2r_count: int
    battlenet_count: int


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_ps_lines() -> list[str]:
    proc = subprocess.run(
        ["ps", "-ax", "-o", "pid=,command="],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.rstrip("\n") for line in proc.stdout.splitlines() if line.strip()]


def classify(lines: list[str]) -> ProcessSnapshot:
    counts = {k: 0 for k in PATTERNS}

    for line in lines:
        for key, rx in PATTERNS.items():
            if rx.search(line):
                counts[key] += 1

    has_crossover = counts["crossover"] > 0
    has_battlenet = (counts["battlenet_mac"] + counts["battlenet_win"]) > 0
    has_d2r = counts["d2r"] > 0
    has_agent = counts["agent"] > 0
    has_wine = counts["wine"] > 0

    if has_d2r:
        state = "d2r_running"
    elif has_battlenet and (has_crossover or has_wine):
        state = "d2r_launching_or_launcher_open"
    elif has_battlenet:
        state = "battlenet_open"
    elif has_crossover or has_wine:
        state = "crossover_open"
    else:
        state = "idle"

    return ProcessSnapshot(
        timestamp=now_iso(),
        crossover=has_crossover,
        battlenet=has_battlenet,
        d2r=has_d2r,
        agent=has_agent,
        wine=has_wine,
        state=state,
        d2r_count=counts["d2r"],
        battlenet_count=counts["battlenet_mac"] + counts["battlenet_win"],
    )


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def print_human(snapshot: ProcessSnapshot) -> None:
    print(
        f"{snapshot.timestamp} state={snapshot.state} "
        f"d2r={int(snapshot.d2r)} bn={int(snapshot.battlenet)} "
        f"cx={int(snapshot.crossover)} wine={int(snapshot.wine)} "
        f"agent={int(snapshot.agent)}"
    )


def run_loop(interval: float, log_file: Path, oneshot: bool, emit_heartbeats: bool) -> int:
    prev_state: str | None = None

    while True:
        try:
            lines = get_ps_lines()
            snap = classify(lines)
        except subprocess.CalledProcessError as e:
            err = {"timestamp": now_iso(), "event": "ps_error", "returncode": e.returncode}
            append_jsonl(log_file, err)
            print(json.dumps(err), file=sys.stderr)
            return 1

        changed = snap.state != prev_state
        if changed or emit_heartbeats or oneshot:
            event = {
                "timestamp": snap.timestamp,
                "event": "state_change" if changed else "heartbeat",
                "snapshot": asdict(snap),
            }
            append_jsonl(log_file, event)
            print_human(snap)

        prev_state = snap.state
        if oneshot:
            return 0

        time.sleep(interval)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Monitor CrossOver/Battle.net/D2R process states")
    p.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    p.add_argument(
        "--log-file",
        default="data/cache/process_monitor.jsonl",
        help="JSONL log output path",
    )
    p.add_argument("--oneshot", action="store_true", help="Capture one snapshot and exit")
    p.add_argument(
        "--heartbeats",
        action="store_true",
        help="Write every poll to log, not only state changes",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    return run_loop(
        interval=max(args.interval, 0.2),
        log_file=Path(args.log_file),
        oneshot=args.oneshot,
        emit_heartbeats=args.heartbeats,
    )


if __name__ == "__main__":
    raise SystemExit(main())

