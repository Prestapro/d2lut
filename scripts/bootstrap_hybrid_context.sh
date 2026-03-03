#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
FALLBACK_ENV_FILE="/Users/alex/Desktop/antid/.env"

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#${line%%[![:space:]]*}}"
    line="${line%${line##*[![:space:]]}}"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" == *"="* ]] || continue

    local key="${line%%=*}"
    local value="${line#*=}"

    key="${key%${key##*[![:space:]]}}"
    value="${value#${value%%[![:space:]]*}}"
    value="${value%${value##*[![:space:]]}}"

    if [[ "$value" =~ ^\".*\"$ || "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi

    export "$key=$value"
  done < "$file"
}

load_env_file "$ENV_FILE"
load_env_file "$FALLBACK_ENV_FILE"

if [[ -z "${VOYAGE_API_KEY:-}" && -n "${VOYAGEAI_TOKEN:-}" ]]; then
  export VOYAGE_API_KEY="$VOYAGEAI_TOKEN"
fi

echo "[1/4] Configure CocoIndex MCP"
bash "$ROOT_DIR/scripts/setup_cocoindex_mcp.sh"

echo "[2/4] Install and configure CodexFi memory layer"
MEMORY_ARGS=(install --no-tui)

if [[ -n "${VOYAGE_API_KEY:-}" ]]; then
  MEMORY_ARGS+=(--voyage-key "$VOYAGE_API_KEY")
fi

if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  MEMORY_ARGS+=(--google-key "$GEMINI_API_KEY")
elif [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  MEMORY_ARGS+=(--anthropic-key "$ANTHROPIC_API_KEY")
elif [[ -n "${XAI_API_KEY:-}" ]]; then
  MEMORY_ARGS+=(--xai-key "$XAI_API_KEY")
fi

if command -v codexfi >/dev/null 2>&1; then
  codexfi "${MEMORY_ARGS[@]}"
else
  bunx codexfi "${MEMORY_ARGS[@]}"
fi

echo "[3/4] Validate memory health"
if command -v codexfi >/dev/null 2>&1; then
  codexfi status
else
  bunx codexfi status
fi

echo "[4/4] Optional end-to-end smoke check"
if [[ "${OPENCODE_MEMORY_SMOKE:-0}" == "1" ]]; then
  SMOKE_MODEL="${OPENCODE_MEMORY_SMOKE_MODEL:-opencode/minimax-m2.5-free}"
  opencode run -m "$SMOKE_MODEL" "Reply with exactly: codexfi smoke test ok" >/dev/null
  if command -v codexfi >/dev/null 2>&1; then
    codexfi status
  else
    bunx codexfi status
  fi
  echo "Smoke check passed."
else
  echo "Skipped. Set OPENCODE_MEMORY_SMOKE=1 to run a live request smoke check."
fi

echo "Done."
