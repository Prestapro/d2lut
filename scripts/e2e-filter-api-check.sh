#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
PORT="${E2E_FILTER_PORT:-3105}"
TMP_DIR="$(mktemp -d /tmp/d2lut-e2e-filter.XXXXXX)"
DB_PATH="${TMP_DIR}/e2e.db"
LOG_FILE="${TMP_DIR}/next.log"
BASE_URL="http://127.0.0.1:${PORT}"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

cd "${ROOT_DIR}"

export DATABASE_URL="file:${DB_PATH}"
export NODE_ENV="production"

npx prisma db push --skip-generate >/dev/null

npm run build >/dev/null

npx next start -p "${PORT}" >"${LOG_FILE}" 2>&1 &
SERVER_PID=$!

for _ in {1..60}; do
  if curl -fsS "${BASE_URL}/api" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "${BASE_URL}/api" >/dev/null 2>&1; then
  echo "Server did not become healthy"
  exit 1
fi

EMPTY_RESPONSE="$(curl -fsS -X POST "${BASE_URL}/api/filter/build" -H 'Content-Type: application/json' -d '{"preset":"default","threshold":0}')"
if [[ "${EMPTY_RESPONSE}" != *"ItemDisplay["* ]]; then
  echo "Empty-DB filter build did not return filter content"
  exit 1
fi

node <<'NODE'
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function main() {
  const low = await prisma.d2Item.create({
    data: {
      variantKey: 'runeword:cta_low',
      name: 'cta_low',
      displayName: 'Call to Arms Low',
      category: 'runeword',
      d2rCode: '7cr',
      priceEstimate: {
        create: {
          priceFg: 20,
          confidence: 'medium',
          nObservations: 2,
        },
      },
    },
  });

  await prisma.d2Item.create({
    data: {
      variantKey: 'runeword:cta_high',
      name: 'cta_high',
      displayName: 'Call to Arms High',
      category: 'runeword',
      d2rCode: '7cr',
      priceEstimate: {
        create: {
          priceFg: 200,
          confidence: 'high',
          nObservations: 9,
        },
      },
    },
  });

  await prisma.d2Item.create({
    data: {
      variantKey: 'runeword:spirit_ok',
      name: 'spirit_ok',
      displayName: 'Spirit',
      category: 'runeword',
      d2rCode: 'xrn',
      priceEstimate: {
        create: {
          priceFg: 10,
          confidence: 'medium',
          nObservations: 5,
        },
      },
    },
  });

  await prisma.$disconnect();
  void low;
}

main().catch(async (error) => {
  console.error(error);
  await prisma.$disconnect();
  process.exit(1);
});
NODE

DEDUPE_RESPONSE="$(curl -fsS -X POST "${BASE_URL}/api/filter/build" -H 'Content-Type: application/json' -d '{"preset":"default","threshold":0,"mode":"db"}')"

COUNT_7CR="$(printf '%s' "${DEDUPE_RESPONSE}" | python3 -c 'import sys; s=sys.stdin.read(); print(s.count("ItemDisplay[7cr]"))')"
if [[ "${COUNT_7CR}" != "1" ]]; then
  echo "Expected exactly one ItemDisplay[7cr], got ${COUNT_7CR}"
  exit 1
fi

if [[ "${DEDUPE_RESPONSE}" != *"Call to Arms High"* ]]; then
  echo "Expected higher-priced duplicate to win in dedupe"
  exit 1
fi

echo "E2E filter API checks passed"
