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
if [ "${HERMES_INFERENCE_PROVIDER}" = "openrouter" ] && { [ -z "${HERMES_AUXILIARY_MODEL:-}" ] || [ -z "${HERMES_AUXILIARY_VISION_MODEL:-}" ]; }; then
    echo "HERMES_AUXILIARY_MODEL and HERMES_AUXILIARY_VISION_MODEL are required for governed auxiliary inference" >&2
    exit 1
fi
if [ -z "${LILOS_TOOL_BASE_URL:-}" ] || [ -z "${LILOS_TOOL_API_KEY:-}" ]; then
    echo "LILOS_TOOL_BASE_URL and LILOS_TOOL_API_KEY are required" >&2
    exit 1
fi

# Hermes stopped auto-migrating configs older than schema v12 (its support
# floor). A below-floor config is left byte-for-byte untouched and the runtime
# continues with defaults deep-merged at read time -- so every setting written
# here lands in the file, is read back under obsolete v11-era key semantics, and
# the current-schema keys silently fall back to their defaults. That is why
# `platform_toolsets.api_server` did not restrict the model to the LILOs
# toolset: it kept Hermes' own bridge tools, and runs wasted iterations calling
# tool_search and tool_call before failing.
#
# The config on this disk was only ever written by this script, so rotating it
# loses nothing: the settings below rebuild it on the current schema. The old
# file is kept beside it rather than deleted, so a hand edit is recoverable.
HERMES_CONFIG_FILE="${HERMES_HOME}/config.yaml"
if [ -f "$HERMES_CONFIG_FILE" ]; then
    HERMES_CONFIG_VERSION="$(/command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config get _config_version 2>/dev/null | tr -dc '0-9')"
    if [ -z "$HERMES_CONFIG_VERSION" ] || [ "$HERMES_CONFIG_VERSION" -lt 12 ]; then
        HERMES_CONFIG_BACKUP="${HERMES_CONFIG_FILE}.below-floor-$(date -u +%Y%m%dT%H%M%SZ).bak"
        cp "$HERMES_CONFIG_FILE" "$HERMES_CONFIG_BACKUP"
        rm -f "$HERMES_CONFIG_FILE"
        echo "[lilos-hermes] Config schema '${HERMES_CONFIG_VERSION:-unreadable}' is below the v12 support floor; backed up to ${HERMES_CONFIG_BACKUP} and regenerating on the current schema"
    fi
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

    # Auxiliary inference is part of the same governed cost policy. Hermes'
    # upstream ``auxiliary.free_only`` switch forces :free SKUs and can reject
    # an otherwise healthy paid route; it is not a quality-aware budget. Pin
    # exact inexpensive models instead. Compression stays on the long-context
    # text model; vision uses a purpose-built multimodal model.
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.free_only false
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.openrouter_model "$HERMES_AUXILIARY_MODEL"
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.vision.provider openrouter
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.vision.model "$HERMES_AUXILIARY_VISION_MODEL"
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.compression.provider openrouter
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.compression.model "$HERMES_AUXILIARY_MODEL"
    echo "[lilos-hermes] Gateway model: $HERMES_INFERENCE_MODEL via $HERMES_INFERENCE_PROVIDER; toolset: lilos"
    echo "[lilos-hermes] Auxiliary text/compression: $HERMES_AUXILIARY_MODEL; vision: $HERMES_AUXILIARY_VISION_MODEL via openrouter; free-only disabled"
fi

echo "[lilos-hermes] Bootstrap complete; starting foreground gateway"
exec /opt/hermes/docker/main-wrapper.sh "$@"
