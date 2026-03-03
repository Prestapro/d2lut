#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" >/dev/null 2>&1 && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[load-env] missing .env: $ENV_FILE" >&2
  exit 1
fi

python3 - "$ENV_FILE" <<'PY'
import shlex
import sys
from pathlib import Path

env_file = Path(sys.argv[1])

for raw in env_file.read_text(encoding='utf-8', errors='replace').splitlines():
    line = raw.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    key = key.strip()
    value = value.strip()
    if not key:
        continue
    if value[:1] in {'"', "'"} and value[-1:] == value[:1]:
        value = value[1:-1]
    print(f"export {key}={shlex.quote(value)}")
PY
