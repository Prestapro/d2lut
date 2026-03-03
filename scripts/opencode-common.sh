#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${OPENCODE_COMMON_LOADED:-}" ]]; then
  return 0 2>/dev/null || true
fi
OPENCODE_COMMON_LOADED=1

SCRIPT_VERSION="0.2.0"

print_exit_code_legend() {
  cat <<'EOF'
Exit codes:
  1 - legacy mode (when OPENCODE_LEGACY_EXIT1=1)
  2 - missing required dependency
  3 - missing required file/helper script
  4 - runtime execution/state failure
  5 - invalid or incomplete configuration
EOF
}

exit_with_code() {
  local code="$1"
  if [[ "${OPENCODE_LEGACY_EXIT1:-0}" == "1" ]]; then
    exit 1
  fi
  exit "$code"
}

require_command() {
  local bin="$1"
  local label="${2:-$1}"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "[$label] missing required dependency: $bin" >&2
    exit_with_code 2
  fi
}

require_executable_file() {
  local file_path="$1"
  local label="${2:-script}"
  if [[ ! -x "$file_path" ]]; then
    echo "[$label] missing runner: $file_path" >&2
    exit_with_code 3
  fi
}

assert_pipefail_enabled() {
  local label="${1:-script}"
  if [[ "$-" != *e* ]]; then
    echo "[$label] shell missing 'set -e'" >&2
    exit_with_code 4
  fi
  if ! [[ -o pipefail ]]; then
    echo "[$label] shell missing 'set -o pipefail'" >&2
    exit_with_code 4
  fi
}
