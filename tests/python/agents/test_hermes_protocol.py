import asyncio
import json
from typing import Any, cast

import httpx
import pytest

from apps.api.app.agents.hermes_client import (
    REQUIRED_FEATURES,
    REQUIRED_LILOS_TOOLS,
    HermesRunsClient,
    HermesRuntimeError,
)


def _capabilities() -> dict[str, object]:
    return {
        "model": "hermes-agent",
        "runtime": {"mode": "server_agent", "tool_execution": "server", "split_runtime": False},
        "features": {name: True for name in REQUIRED_FEATURES},
        "endpoints": {
            "runs": {"method": "POST", "path": "/v1/runs"},
            "run_status": {"method": "GET", "path": "/v1/runs/{run_id}"},
            "run_events": {"method": "GET", "path": "/v1/runs/{run_id}/events"},
            "run_approval": {"method": "POST", "path": "/v1/runs/{run_id}/approval"},
            "run_steer": {"method": "POST", "path": "/v1/runs/{run_id}/steer"},
            "run_stop": {"method": "POST", "path": "/v1/runs/{run_id}/stop"},
        },
    }


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("lilos-hermes:8642", "http://lilos-hermes:8642"),
        ("http://lilos-hermes:8642", "http://lilos-hermes:8642"),
        ("https://hermes.example.com/", "https://hermes.example.com"),
    ],
)
def test_render_private_hostport_base_url_normalization(base_url: str, expected: str) -> None:
    client = HermesRunsClient(base_url, "test-hermes-key", timeout_seconds=5)
    assert client._base_url == expected


def test_render_private_hostport_capability_request_uses_http_scheme() -> None:
    observed: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(str(request.url))
        assert request.url.scheme == "http"
        assert request.url.host == "lilos-hermes"
        assert request.url.port == 8642
        if request.url.path == "/health/detailed":
            return httpx.Response(200, json={"status": "ready", "version": "0.20.5"})
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json=_capabilities())
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

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = HermesRunsClient(
                "lilos-hermes:8642",
                "test-hermes-key",
                timeout_seconds=5,
                client=http,
            )
            capabilities = await client.capabilities()
            assert capabilities.missing_required == ()

    asyncio.run(scenario())
    assert observed == [
        "http://lilos-hermes:8642/health/detailed",
        "http://lilos-hermes:8642/v1/capabilities",
        "http://lilos-hermes:8642/v1/toolsets",
    ]


def test_native_runs_capabilities_and_real_steer_transport() -> None:
    observed: list[tuple[str, str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        observed.append((request.method, request.url.path, body))
        assert request.headers["authorization"] == "Bearer test-hermes-key"
        if request.url.path == "/health/detailed":
            return httpx.Response(200, json={"status": "ready", "version": "0.20.5"})
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json=_capabilities())
        if request.url.path == "/v1/toolsets":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "name": "lilos",
                            "enabled": True,
                            "tools": sorted(REQUIRED_LILOS_TOOLS),
                        },
                        {"name": "terminal", "enabled": False, "tools": ["terminal"]},
                    ]
                },
            )
        if request.url.path == "/v1/runs":
            assert isinstance(body, dict)
            assert request.headers["x-hermes-session-key"] == "lilos_mem_scope_a"
            assert body["session_id"] == "lilos_mem_scope_a"
            return httpx.Response(202, json={"run_id": "run_native_1", "status": "started"})
        if request.url.path == "/api/sessions/lilos_mem_scope_a":
            return httpx.Response(200, json={"deleted": True})
        if request.url.path.endswith("/steer"):
            return httpx.Response(200, json={"run_id": "run_native_1", "accepted": True})
        if request.url.path.endswith("/stop"):
            return httpx.Response(200, json={"run_id": "run_native_1", "status": "stopping"})
        if request.url.path.endswith("/approval"):
            return httpx.Response(200, json={"run_id": "run_native_1", "resolved": 1})
        raise AssertionError(request.url.path)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = HermesRunsClient(
                "http://hermes.internal",
                "test-hermes-key",
                timeout_seconds=5,
                client=http,
            )
            capabilities = await client.capabilities()
            assert capabilities.runtime_version == "0.20.5"
            assert capabilities.missing_required == ()
            assert set(capabilities.sanctioned_tools) == REQUIRED_LILOS_TOOLS
            run_id = await client.create_run(
                objective="Analyze evidence",
                instructions="Use sanctioned tools",
                hermes_session_id="lilos_mem_scope_a",
                session_key="lilos_mem_scope_a",
                model="hermes-agent",
            )
            assert run_id == "run_native_1"
            assert (await client.steer(run_id, "Prioritize current evidence"))["accepted"] is True
            await client.approve(run_id, "once")
            await client.stop(run_id)
            await client.delete_session("lilos_mem_scope_a")

    asyncio.run(scenario())

    paths = [path for _method, path, _body in observed]
    assert "/v1/runs/run_native_1/steer" in paths
    assert not any("session.steer" in path for path in paths)


def test_split_or_non_server_agent_runtime_fails_closed() -> None:
    payload = _capabilities()
    payload["runtime"] = {
        "mode": "split",
        "tool_execution": "server",
        "split_runtime": True,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/detailed":
            return httpx.Response(200, json={"status": "ready", "version": "0.20.5"})
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json=payload)
        return httpx.Response(
            200,
            json={
                "data": [{"name": "lilos", "enabled": True, "tools": sorted(REQUIRED_LILOS_TOOLS)}]
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = HermesRunsClient(
                "http://hermes.internal", "test-hermes-key", timeout_seconds=5, client=http
            )
            with pytest.raises(HermesRuntimeError) as exc:
                await client.capabilities()
            assert exc.value.safe_code == "HERMES_RUNTIME_UNSAFE"

    asyncio.run(scenario())


def test_missing_native_steer_capability_fails_closed() -> None:
    payload = _capabilities()
    features = dict(cast(dict[str, Any], payload["features"]))
    features["run_steer"] = False
    payload["features"] = features

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/detailed":
            return httpx.Response(200, json={"status": "ready", "version": "0.20.5"})
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
        return httpx.Response(200, json=payload)

    async def scenario() -> tuple[str, ...]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = HermesRunsClient(
                "http://hermes.internal", "test-hermes-key", timeout_seconds=5, client=http
            )
            capabilities = await client.capabilities()
            return capabilities.missing_required

    missing_required = asyncio.run(scenario())
    assert missing_required == ("run_steer",)


def test_extra_enabled_hermes_toolset_fails_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/detailed":
            return httpx.Response(200, json={"status": "ready", "version": "0.20.5"})
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json=_capabilities())
        return httpx.Response(
            200,
            json={
                "data": [
                    {"name": "lilos", "enabled": True, "tools": sorted(REQUIRED_LILOS_TOOLS)},
                    {"name": "terminal", "enabled": True, "tools": ["terminal"]},
                ]
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = HermesRunsClient(
                "http://hermes.internal", "test-hermes-key", timeout_seconds=5, client=http
            )
            with pytest.raises(HermesRuntimeError) as exc:
                await client.capabilities()
            assert exc.value.safe_code == "HERMES_TOOLSET_UNSAFE"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("mutation", "safe_code"),
    [
        (("features", "run_steer", "true"), "HERMES_CAPABILITIES_INVALID"),
        (
            ("endpoints", "run_steer", {"method": "POST", "path": "/queued-follow-up"}),
            "HERMES_CAPABILITIES_INVALID",
        ),
    ],
)
def test_non_boolean_features_and_wrong_native_endpoint_fail_closed(
    mutation: tuple[str, str, object], safe_code: str
) -> None:
    payload = _capabilities()
    section, key, value = mutation
    mutated = dict(cast(dict[str, Any], payload[section]))
    mutated[key] = value
    payload[section] = mutated

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/detailed":
            return httpx.Response(200, json={"status": "ready", "version": "0.20.5"})
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json=payload)
        return httpx.Response(
            200,
            json={
                "data": [{"name": "lilos", "enabled": True, "tools": sorted(REQUIRED_LILOS_TOOLS)}]
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = HermesRunsClient(
                "http://hermes.internal", "test-hermes-key", timeout_seconds=5, client=http
            )
            with pytest.raises(HermesRuntimeError) as exc:
                await client.capabilities()
            assert exc.value.safe_code == safe_code

    asyncio.run(scenario())
