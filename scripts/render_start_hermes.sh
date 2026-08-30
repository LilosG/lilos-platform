#!/bin/sh
set -eu

export HERMES_HOME="${HERMES_HOME:-/opt/data}"
export HOME="/opt/data"
export PATH="/command:/package/admin/s6/command:/opt/hermes/bin:/opt/hermes/.venv/bin:/opt/data/.local/bin:${PATH}"

echo "[lilos-hermes] Render bootstrap starting"
/opt/hermes/docker/stage2-hook.sh

if [ -z "${API_SERVER_KEY:-}" ]; then
    echo "API_SERVER_KEY is required" >&2
    exit 1
fi
if [ -z "${HERMES_INFERENCE_PROVIDER:-}" ] || [ -z "${HERMES_INFERENCE_MODEL:-}" ]; then
    echo "HERMES_INFERENCE_PROVIDER and HERMES_INFERENCE_MODEL are required" >&2
    exit 1
fi
if [ "${HERMES_INFERENCE_PROVIDER}" = "openrouter" ] && [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "OPENROUTER_API_KEY is required for the governed provider route" >&2
    exit 1
fi
if [ -z "${LILOS_TOOL_BASE_URL:-}" ] || [ -z "${LILOS_TOOL_API_KEY:-}" ]; then
    echo "LILOS_TOOL_BASE_URL and LILOS_TOOL_API_KEY are required" >&2
    exit 1
fi

# The OpenAI-compatible gateway reads its default inference route from the
# persisted Hermes config, not from the one-shot HERMES_INFERENCE_MODEL flag.
# Enforce the governed LILOs production route on every boot so a stale model
# selection on the persistent disk cannot silently send work to another model.
if [ -n "${HERMES_INFERENCE_MODEL:-}" ]; then
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set model.default "$HERMES_INFERENCE_MODEL"
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set model.provider "$HERMES_INFERENCE_PROVIDER"
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set model.base_url https://openrouter.ai/api/v1
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set platform_toolsets.api_server '["lilos","no_mcp"]'
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set agent.disabled_toolsets '["bfl"]'
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set sessions.auto_prune true
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set sessions.retention_days 30

    # Auxiliary tasks (vision, context compression) run their own inference
    # outside the AI Gateway, so the platform's cost ceiling does not bound
    # them. Left at the default "auto" chain the runtime probed Nous on every
    # call -- unauthenticated here -- logged the failure, marked it unhealthy
    # for 60s, and then fell through to a PAID OpenRouter model, warning that
    # it "may incur real spend". Pin the provider so it stops probing an
    # account we do not have, and restrict the fallback to free SKUs so no
    # auxiliary call can spend outside a governed budget.
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.free_only true
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.vision.provider openrouter
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.compression.provider openrouter
    echo "[lilos-hermes] Gateway model: $HERMES_INFERENCE_MODEL via $HERMES_INFERENCE_PROVIDER; toolset: lilos"
    echo "[lilos-hermes] Auxiliary inference: openrouter, free SKUs only"
fi

echo "[lilos-hermes] Bootstrap complete; starting foreground gateway"
exec /opt/hermes/docker/main-wrapper.sh "$@"
