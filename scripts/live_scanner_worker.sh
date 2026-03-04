#!/bin/sh
set -eu

INTERVAL_SEC="${LIVE_SCANNER_INTERVAL_SEC:-1800}"
RETRY_MAX="${LIVE_SCANNER_RETRY_MAX:-3}"
RETRY_BACKOFF_SEC="${LIVE_SCANNER_RETRY_BACKOFF_SEC:-20}"
HEARTBEAT_FILE="${LIVE_SCANNER_HEARTBEAT_FILE:-/tmp/live-scanner.heartbeat}"

scanner_command() {
  if [ -n "${LIVE_SCANNER_COMMAND:-}" ]; then
    printf '%s' "$LIVE_SCANNER_COMMAND"
    return
  fi

  if command -v bun >/dev/null 2>&1; then
    printf '%s' "bun run cron:live-refresh"
    return
  fi

  printf '%s' "node scripts/live_refresh_d2jsp.js"
}

run_once() {
  cmd="$(scanner_command)"
  attempt=1
  while [ "$attempt" -le "$RETRY_MAX" ]; do
    if sh -c "$cmd"; then
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
