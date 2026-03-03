#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage: test-opencode-exit-codes.sh

Runs smoke tests validating opencode helper script exit-code behavior.
EOF
  exit 0
fi

if [[ "${1:-}" == "--version" || "${1:-}" == "-v" ]]; then
  echo "test-opencode-exit-codes.sh 0.2.0"
  exit 0
fi

assert_exit_code() {
  local expected="$1"
  local name="$2"
  shift 2

  set +e
  "$@" >/dev/null 2>&1
  local code=$?
  set -e

  if [[ "$code" -ne "$expected" ]]; then
    echo "[FAIL] $name expected exit $expected, got $code" >&2
    return 1
  fi

  echo "[PASS] $name returned exit $expected"
}

run_expect_exit_1() {
  local name="$1"
  local env_path="$2"
  shift 2

  set +e
  PATH="$env_path" OPENCODE_LEGACY_EXIT1=1 "$@" >/dev/null 2>&1
  local code=$?
  set -e

  if [[ "$code" -ne 1 ]]; then
    echo "[FAIL] $name expected exit 1, got $code" >&2
    return 1
  fi

  echo "[PASS] $name returned exit 1"
}

run_expect_exit_1 \
  "opencode-lf legacy fallback" \
  "/bin" \
  bash "$ROOT_DIR/scripts/opencode-lf" run --help

run_expect_exit_1 \
  "opencode-guard legacy fallback" \
  "/bin" \
  bash "$ROOT_DIR/scripts/opencode-guard"

run_expect_exit_1 \
  "opencode-run-json legacy fallback" \
  "/bin" \
  bash "$ROOT_DIR/scripts/opencode-run-json"

assert_exit_code 2 \
  "opencode-run-json missing dependency" \
  env PATH="/bin:/usr/bin" OPENCODE_LEGACY_EXIT1=0 bash "$ROOT_DIR/scripts/opencode-run-json"

assert_exit_code 2 \
  "opencode-lf missing dependency" \
  env PATH="/bin:/usr/bin" OPENCODE_LEGACY_EXIT1=0 bash "$ROOT_DIR/scripts/opencode-lf" run --help

mkdir -p "$TEST_TMP/guard/scripts"
cp "$ROOT_DIR/scripts/opencode-guard" "$TEST_TMP/guard/scripts/opencode-guard"
cp "$ROOT_DIR/scripts/opencode-common.sh" "$TEST_TMP/guard/scripts/opencode-common.sh"
assert_exit_code 3 \
  "opencode-guard missing runner" \
  env PATH="/bin:/usr/bin" OPENCODE_LEGACY_EXIT1=0 bash "$TEST_TMP/guard/scripts/opencode-guard"

mkdir -p "$TEST_TMP/runtime/scripts" "$TEST_TMP/runtime/bin"
cp "$ROOT_DIR/scripts/opencode-run-json" "$TEST_TMP/runtime/scripts/opencode-run-json"
cp "$ROOT_DIR/scripts/opencode-common.sh" "$TEST_TMP/runtime/scripts/opencode-common.sh"
cat > "$TEST_TMP/runtime/scripts/opencode-lf" <<'EOF'
#!/usr/bin/env bash
exit 4
EOF
chmod +x "$TEST_TMP/runtime/scripts/opencode-lf"
cat > "$TEST_TMP/runtime/bin/opencode" <<'EOF'
#!/usr/bin/env bash
echo "fake-opencode"
EOF
chmod +x "$TEST_TMP/runtime/bin/opencode"
assert_exit_code 4 \
  "opencode-run-json runtime failure" \
  env PATH="$TEST_TMP/runtime/bin:/bin:/usr/bin" OPENCODE_LEGACY_EXIT1=0 HOME="$TEST_TMP/runtime/home" bash "$TEST_TMP/runtime/scripts/opencode-run-json"

mkdir -p "$TEST_TMP/config/scripts" "$TEST_TMP/config/bin"
cp "$ROOT_DIR/scripts/opencode-lf" "$TEST_TMP/config/scripts/opencode-lf"
cp "$ROOT_DIR/scripts/opencode-common.sh" "$TEST_TMP/config/scripts/opencode-common.sh"
cat > "$TEST_TMP/config/.env" <<'EOF'
LANGFUSE_BASE_URL="https://cloud.langfuse.com"
EOF
cat > "$TEST_TMP/config/bin/opencode" <<'EOF'
#!/usr/bin/env bash
echo "fake-opencode"
EOF
chmod +x "$TEST_TMP/config/bin/opencode"
assert_exit_code 5 \
  "opencode-lf invalid config" \
  env PATH="$TEST_TMP/config/bin:/bin:/usr/bin" OPENCODE_LEGACY_EXIT1=0 bash "$TEST_TMP/config/scripts/opencode-lf" run --help

echo "All exit-code checks passed."
