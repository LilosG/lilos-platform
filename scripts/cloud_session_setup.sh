#!/usr/bin/env bash
# Prepare a Claude Code cloud session for LILOs work. Idempotent; safe to re-run.
#
# Installs dependencies exactly as CI does, and starts a disposable local PostgreSQL
# (whatever server version the container provides; CI runs PostgreSQL 17 and stays the
# authority) with a database whose name contains "test". Never touches Supabase.
#
# Usage:  source scripts/cloud_session_setup.sh
# (sourcing exports LILOS_TEST_DATABASE_URL into the current shell)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Node dependencies (npm ci)"
npm ci --no-audit --no-fund

echo "==> Python dependencies (uv sync --locked)"
uv sync --locked

PGBIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1 || true)"
if [ -z "${PGBIN}" ]; then
  echo "==> No PostgreSQL server binaries found; skipping local test database."
  echo "    CI runs the full Python suite. Do not point tests at Supabase."
  return 0 2>/dev/null || exit 0
fi

PGDATA="${LILOS_CLOUD_PGDATA:-$HOME/.lilos-test-pg}"
PGPORT="${LILOS_CLOUD_PGPORT:-5432}"
PGUSER_NAME="lilos_test"
PGDB_NAME="lilos_test"

echo "==> Local test PostgreSQL ($("${PGBIN}/postgres" --version)) on 127.0.0.1:${PGPORT}"
if [ ! -d "${PGDATA}" ]; then
  # The server refuses to run as root, so run it as an unprivileged user when needed.
  if [ "$(id -u)" = "0" ]; then
    id lilos_pg >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash lilos_pg
    PGDATA="/home/lilos_pg/pgdata"
    RUN_AS="runuser -u lilos_pg --"
  else
    RUN_AS=""
  fi
  ${RUN_AS} "${PGBIN}/initdb" -D "${PGDATA}" -U postgres --auth=trust >/dev/null
else
  RUN_AS=""
  if [ "$(id -u)" = "0" ]; then
    PGDATA="/home/lilos_pg/pgdata"
    RUN_AS="runuser -u lilos_pg --"
  fi
fi

if ! "${PGBIN}/pg_isready" -h 127.0.0.1 -p "${PGPORT}" >/dev/null 2>&1; then
  ${RUN_AS} "${PGBIN}/pg_ctl" -D "${PGDATA}" -o "-p ${PGPORT} -c listen_addresses=127.0.0.1 -c unix_socket_directories=${PGDATA}" \
    -l "${PGDATA}/server.log" -w start >/dev/null
fi

if ! "${PGBIN}/pg_isready" -h 127.0.0.1 -p "${PGPORT}" >/dev/null 2>&1; then
  echo "ERROR: local PostgreSQL did not start; see ${PGDATA}/server.log" >&2
  return 1 2>/dev/null || exit 1
fi

psql -h 127.0.0.1 -p "${PGPORT}" -U postgres -tAc \
  "SELECT 1 FROM pg_roles WHERE rolname='${PGUSER_NAME}'" | grep -q 1 \
  || psql -h 127.0.0.1 -p "${PGPORT}" -U postgres -qc \
    "CREATE ROLE ${PGUSER_NAME} LOGIN SUPERUSER PASSWORD '${PGUSER_NAME}'"
psql -h 127.0.0.1 -p "${PGPORT}" -U postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='${PGDB_NAME}'" | grep -q 1 \
  || psql -h 127.0.0.1 -p "${PGPORT}" -U postgres -qc \
    "CREATE DATABASE ${PGDB_NAME} OWNER ${PGUSER_NAME}"

# The container's preinstalled Chromium may be a different build than the repo's Playwright
# expects; apps/console/playwright.config.ts launches this path when the variable is set.
if [ -z "${PLAYWRIGHT_CHROMIUM_EXECUTABLE:-}" ] && [ -x /opt/pw-browsers/chromium ]; then
  export PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium
  echo "==> Console browser tests will use ${PLAYWRIGHT_CHROMIUM_EXECUTABLE}"
fi

export LILOS_TEST_DATABASE_URL="postgresql+asyncpg://${PGUSER_NAME}:${PGUSER_NAME}@127.0.0.1:${PGPORT}/${PGDB_NAME}"
echo "==> Ready. LILOS_TEST_DATABASE_URL=${LILOS_TEST_DATABASE_URL}"
