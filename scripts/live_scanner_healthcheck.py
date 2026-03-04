#!/usr/bin/env python3
"""Healthcheck for live scanner worker heartbeat."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main() -> int:
    heartbeat_path = Path(
        os.getenv("LIVE_SCANNER_HEARTBEAT_FILE", "/tmp/live-scanner.heartbeat")
    )
    max_age = int(os.getenv("LIVE_SCANNER_HEALTH_MAX_AGE", "7200"))

    if not heartbeat_path.exists():
        return 1

    age = time.time() - heartbeat_path.stat().st_mtime
    return 0 if age < max_age else 1


if __name__ == "__main__":
    sys.exit(main())
