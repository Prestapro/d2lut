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

VOYAGE_KEY="${VOYAGE_API_KEY:-${VOYAGEAI_TOKEN:-}}"

MCP_ARGS=(
  mcp add cocoindex-code
  --env "COCOINDEX_CODE_ROOT_PATH=$ROOT_DIR"
)

if [[ -n "$VOYAGE_KEY" ]]; then
  MCP_ARGS+=(
    --env "COCOINDEX_CODE_EMBEDDING_MODEL=voyage/voyage-code-3"
    --env "VOYAGE_API_KEY=$VOYAGE_KEY"
  )
  echo "Configuring cocoindex-code with Voyage embeddings"
else
  echo "VOYAGE_API_KEY not found. Configuring cocoindex-code with default embeddings"
fi

MCP_ARGS+=(
  --
  uvx
  --prerelease=explicit
  --with
  "cocoindex>=1.0.0a22"
  cocoindex-code@latest
)

codex "${MCP_ARGS[@]}"

echo "cocoindex-code MCP configured for: $ROOT_DIR"
