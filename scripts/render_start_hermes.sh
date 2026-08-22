#!/bin/sh
set -eu

export HERMES_HOME="${HERMES_HOME:-/opt/data}"
export HOME="/opt/data"
export PATH="/command:/package/admin/s6/command:/opt/hermes/bin:/opt/hermes/.venv/bin:/opt/data/.local/bin:${PATH}"

echo "[lilos-hermes] Render bootstrap starting"
/opt/hermes/docker/stage2-hook.sh

# The OpenAI-compatible gateway reads its default inference route from the
# persisted Hermes config, not from the one-shot HERMES_INFERENCE_MODEL flag.
# Enforce the governed LILOs production route on every boot so a stale model
# selection on the persistent disk cannot silently send work to another model.
if [ -n "${HERMES_INFERENCE_MODEL:-}" ]; then
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set model.default "$HERMES_INFERENCE_MODEL"
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set model.provider openrouter
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set model.base_url https://openrouter.ai/api/v1
    echo "[lilos-hermes] Gateway model: $HERMES_INFERENCE_MODEL via openrouter"
fi

echo "[lilos-hermes] Bootstrap complete; starting foreground gateway"
exec /opt/hermes/docker/main-wrapper.sh "$@"
