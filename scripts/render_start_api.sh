#!/bin/sh
set -eu

export LILOS_RELEASE="${RENDER_GIT_COMMIT:?RENDER_GIT_COMMIT is required}"

exec python -m uvicorn apps.api.app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-10000}"
