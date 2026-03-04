#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "${ROOT_DIR}"

TMP_DB="$(mktemp /tmp/d2lut-selfcheck.XXXXXX.db)"
trap 'rm -f "${TMP_DB}"' EXIT

export DATABASE_URL="file:${TMP_DB}"

python3 mini-services/bridge.py --action selfcheck >/tmp/d2lut-bridge-selfcheck.json

python3 - <<'PY'
import json
from pathlib import Path

report = json.loads(Path('/tmp/d2lut-bridge-selfcheck.json').read_text(encoding='utf-8'))
required = ['d2lutAvailable', 'filterBuilderAvailable', 'dbExists', 'dbReadable']
missing = [k for k in required if k not in report]
if missing:
    raise SystemExit(f"bridge selfcheck missing keys: {missing}")
if not report.get('d2lutAvailable'):
    raise SystemExit('bridge selfcheck: d2lut package unavailable')
if not report.get('filterBuilderAvailable'):
    raise SystemExit('bridge selfcheck: FilterBuilder unavailable')
if not report.get('dbExists') or not report.get('dbReadable'):
    raise SystemExit('bridge selfcheck: db not readable')
PY

python3 - <<'PY'
from pathlib import Path

dockerfile = Path('Dockerfile').read_text(encoding='utf-8')
compose = Path('docker-compose.yml').read_text(encoding='utf-8')

docker_checks = [
    'python3 -m pip install --no-cache-dir -e ./d2lut requests',
]
compose_checks = [
    'live-scanner:',
    'LIVE_SCANNER_INTERVAL_SEC',
    'LIVE_SCANNER_RETRY_MAX',
    'LIVE_SCANNER_RETRY_BACKOFF_SEC',
    'LIVE_SCANNER_HEARTBEAT_FILE',
    'healthcheck:',
    'scripts/live_scanner_worker.sh',
    'scripts/live_scanner_healthcheck.py',
]

for token in docker_checks:
    if token not in dockerfile:
        raise SystemExit(f'Dockerfile check failed: {token}')

for token in compose_checks:
    if token not in compose:
        raise SystemExit(f'docker-compose check failed: {token}')
PY

echo "Runtime wiring checks passed"
