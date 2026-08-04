#!/bin/sh
set -eu

export LILOS_RELEASE="${RENDER_GIT_COMMIT:?RENDER_GIT_COMMIT is required}"

exec python -m apps.scheduler
