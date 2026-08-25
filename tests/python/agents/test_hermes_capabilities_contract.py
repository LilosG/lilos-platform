"""Regression coverage for Hermes v2026.8.19 capability metadata."""

import asyncio
from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest

from apps.api.app.agents.hermes_client import (
    REQUIRED_FEATURES,
    REQUIRED_LILOS_TOOLS,
    HermesRunsClient,
    HermesRuntimeError,
)


def _pinned_capabilities() -> dict[str, object]:
    features: dict[str, object] = {name: True for name in REQUIRED_FEATURES}
    features.update(
        {
            "session_continuity_header": "X-Hermes-Session-Id",
            "session_key_header": "X-Hermes-Session-Key",
            "cors": False,
        }
    )
    return {
        "object": "hermes.api_server.capabilities",
        "platform": "hermes-agent",
        "model": "hermes-agent",
        "runtime": {
            "mode": "server_agent",
            "tool_execution": "server",
            "split_runtime": False,
        },
        "features": features,
        "endpoints": {
            "runs": {"method": "POST", "path": "/v1/runs"},
            "run_status": {"method": "GET", "path": "/v1/runs/{run_id}"},
            "run_events": {"method": "GET", "path": "/v1/runs/{run_id}/events"},
            "run_approval": {"method": "POST", "path": "/v1/runs/{run_id}/approval"},
            "run_steer": {"method": "POST", "path": "/v1/runs/{run_id}/steer"},
            "run_stop": {"method": "POST", "path": "/v1/runs/{run_id}/stop"},
        },
    }


def _handler(payload: dict[str, object]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/detailed":
            return httpx.Response(200, json={"status": "ready", "version": "0.20.5"})
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json=payload)
        if request.url.path == "/v1/toolsets":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "name": "lilos",
                            "enabled": True,
                            "tools": sorted(REQUIRED_LILOS_TOOLS),
                        }
                    ]
                },
            )
        raise AssertionError(request.url.path)

    return handler


def test_pinned_hermes_metadata_is_accepted_without_exposing_non_boolean_controls() -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(_handler(_pinned_capabilities()))
        ) as http:
            client = HermesRunsClient(
                "lilos-hermes:8642",
                "test-hermes-key",
                timeout_seconds=5,
                client=http,
            )
            capabilities = await client.capabilities()

        assert capabilities.missing_required == ()
        assert capabilities.features["run_steer"] is True
        assert capabilities.features["run_stop"] is True
        assert "session_continuity_header" not in capabilities.features
        assert "session_key_header" not in capabilities.features

    asyncio.run(scenario())


def test_required_feature_must_still_be_boolean() -> None:
    payload = _pinned_capabilities()
    features = dict(cast(dict[str, Any], payload["features"]))
    features["run_steer"] = "true"
    payload["features"] = features

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(_handler(payload))) as http:
            client = HermesRunsClient(
                "lilos-hermes:8642",
                "test-hermes-key",
                timeout_seconds=5,
                client=http,
            )
            with pytest.raises(HermesRuntimeError) as exc:
                await client.capabilities()

        assert exc.value.safe_code == "HERMES_CAPABILITIES_INVALID"

    asyncio.run(scenario())
