#!/bin/sh
set -eu

INTERVAL_SEC="${LIVE_SCANNER_INTERVAL_SEC:-1800}"
RETRY_MAX="${LIVE_SCANNER_RETRY_MAX:-3}"
RETRY_BACKOFF_SEC="${LIVE_SCANNER_RETRY_BACKOFF_SEC:-20}"
HEARTBEAT_FILE="${LIVE_SCANNER_HEARTBEAT_FILE:-/tmp/live-scanner.heartbeat}"

run_once() {
  attempt=1
  while [ "$attempt" -le "$RETRY_MAX" ]; do
    if node scripts/live_refresh_d2jsp.js; then
      date -u +%Y-%m-%dT%H:%M:%SZ > "$HEARTBEAT_FILE"
      return 0
    fi

    if [ "$attempt" -lt "$RETRY_MAX" ]; then
      sleep "$RETRY_BACKOFF_SEC"
    fi
    attempt=$((attempt + 1))
  done

  return 1
}

while true; do
  run_once || true
  sleep "$INTERVAL_SEC"
done
