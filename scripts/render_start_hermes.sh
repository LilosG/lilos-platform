#!/bin/sh
set -eu

export HERMES_HOME="${HERMES_HOME:-/opt/data}"
export HOME="/opt/data"
export PATH="/command:/package/admin/s6/command:/opt/hermes/bin:/opt/hermes/.venv/bin:/opt/data/.local/bin:${PATH}"

# LILOs keeps the desired production inference model in the Blueprint's
# HERMES_INFERENCE_MODEL setting. Hermes v2026.8.3 reads HERMES_MODEL as the
# process-level model override, so bridge the governed LILOs setting explicitly
# unless an operator has already supplied the native Hermes override.
if [ -z "${HERMES_MODEL:-}" ] && [ -n "${HERMES_INFERENCE_MODEL:-}" ]; then
    export HERMES_MODEL="$HERMES_INFERENCE_MODEL"
fi

echo "[lilos-hermes] Render bootstrap starting"
echo "[lilos-hermes] Model override: ${HERMES_MODEL:-<config>}"
/opt/hermes/docker/stage2-hook.sh
echo "[lilos-hermes] Bootstrap complete; starting foreground gateway"

exec /opt/hermes/docker/main-wrapper.sh "$@"
