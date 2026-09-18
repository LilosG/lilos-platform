#!/bin/sh
set -eu

: "${RENDER_GIT_COMMIT:?RENDER_GIT_COMMIT must be provided by Render}"
export LILOS_RELEASE="${RENDER_GIT_COMMIT}"
export HERMES_HOME="${HERMES_HOME:-/opt/data}"
export HOME="/opt/data"
export PATH="/command:/package/admin/s6/command:/opt/hermes/bin:/opt/hermes/.venv/bin:/opt/data/.local/bin:${PATH}"

echo "[lilos-hermes] Render bootstrap starting"
echo "[lilos-hermes] Platform release: ${LILOS_RELEASE}"

# Inspect the persisted schema directly before Hermes reads it. Calling
# `hermes config get` here loads the stale file and emits the same migration
# warning we are trying to prevent. The persistent disk is runtime state only;
# this script is the authoritative source of its generated settings.
HERMES_CONFIG_FILE="${HERMES_HOME}/config.yaml"
if [ -f "$HERMES_CONFIG_FILE" ]; then
    HERMES_CONFIG_VERSION="$(sed -n 's/^[[:space:]]*_config_version:[[:space:]]*["'\'' ]*\([0-9][0-9]*\).*/\1/p' "$HERMES_CONFIG_FILE" | head -n 1)"
    if [ -z "$HERMES_CONFIG_VERSION" ] || [ "$HERMES_CONFIG_VERSION" -lt 12 ]; then
        HERMES_CONFIG_BACKUP="${HERMES_CONFIG_FILE}.below-floor-$(date -u +%Y%m%dT%H%M%SZ).bak"
        cp "$HERMES_CONFIG_FILE" "$HERMES_CONFIG_BACKUP"
        rm -f "$HERMES_CONFIG_FILE"
        echo "[lilos-hermes] Config schema '${HERMES_CONFIG_VERSION:-unreadable}' is below the v12 support floor; backed up to ${HERMES_CONFIG_BACKUP} and regenerating before Hermes bootstrap"
    fi
fi

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
if [ "${HERMES_INFERENCE_PROVIDER}" = "openrouter" ]; then
    case "$HERMES_AUXILIARY_MODEL" in
        *:free) ;;
        *)
            echo "HERMES_AUXILIARY_MODEL must be an OpenRouter :free SKU; refusing a paid auxiliary route" >&2
            exit 1
            ;;
    esac
    case "$HERMES_AUXILIARY_VISION_MODEL" in
        *:free) ;;
        *)
            echo "HERMES_AUXILIARY_VISION_MODEL must be an OpenRouter :free SKU; refusing a paid auxiliary route" >&2
            exit 1
            ;;
    esac
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

    # `platform_toolsets` is consumed by Hermes' platform resolver but is not a
    # recognized `hermes config set` schema key in the pinned runtime, so the
    # CLI warns and does not give us a reliable fail-closed contract. Write the
    # exact API-server selection into YAML instead. The `no_mcp` sentinel is
    # intentionally preserved to prevent default MCP discovery.
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/python - <<'PY'
from pathlib import Path
import yaml

path = Path("/opt/data/config.yaml")
config = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
if not isinstance(config, dict):
    config = {}
platform_toolsets = config.get("platform_toolsets")
if not isinstance(platform_toolsets, dict):
    platform_toolsets = {}
platform_toolsets["api_server"] = ["lilos", "no_mcp"]
config["platform_toolsets"] = platform_toolsets
path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
PY

    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set agent.disabled_toolsets '["bfl"]'
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set sessions.auto_prune true
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set sessions.retention_days 30

    # Auxiliary work must never escape onto a paid OpenRouter fallback. Pin
    # explicit :free text/compression and vision models, then enable Hermes'
    # native free-only guard as a second fail-closed layer. The startup checks
    # above prevent a future Render env edit from silently reintroducing spend.
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.free_only true
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.openrouter_model "$HERMES_AUXILIARY_MODEL"
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.vision.provider openrouter
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.vision.model "$HERMES_AUXILIARY_VISION_MODEL"
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.compression.provider openrouter
    /command/s6-setuidgid hermes /opt/hermes/.venv/bin/hermes config set auxiliary.compression.model "$HERMES_AUXILIARY_MODEL"
    echo "[lilos-hermes] Gateway model: $HERMES_INFERENCE_MODEL via $HERMES_INFERENCE_PROVIDER; toolset: lilos"
    echo "[lilos-hermes] Auxiliary text/compression: $HERMES_AUXILIARY_MODEL; vision: $HERMES_AUXILIARY_VISION_MODEL via openrouter; free-only enforced"
fi

echo "[lilos-hermes] Bootstrap complete; starting foreground gateway"
exec /opt/hermes/docker/main-wrapper.sh "$@"
