"""Authenticated client for Hermes' native run lifecycle."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from apps.api.app.ai.hermes_endpoint import normalize_hermes_base_url

REQUIRED_FEATURES = frozenset(
    {
        "run_submission",
        "run_status",
        "run_events_sse",
        "run_stop",
        "run_steer",
        "run_approval_response",
        "tool_progress_events",
        "approval_events",
    }
)
REQUIRED_ENDPOINTS = {
    "runs": ("POST", "/v1/runs"),
    "run_status": ("GET", "/v1/runs/{run_id}"),
    "run_events": ("GET", "/v1/runs/{run_id}/events"),
    "run_approval": ("POST", "/v1/runs/{run_id}/approval"),
    "run_steer": ("POST", "/v1/runs/{run_id}/steer"),
    "run_stop": ("POST", "/v1/runs/{run_id}/stop"),
}
REQUIRED_LILOS_TOOLS = frozenset(
    {
        "read_client_business_facts",
        "read_website_knowledge",
        "read_gbp_state",
        "read_gbp_recent_posts",
        "read_gsc_evidence",
        "read_ga4_evidence",
        "read_reviews_state",
        "read_content_inventory",
        "read_cross_product_summary",
        "run_site_crawl",
        "analyze_seo_opportunities",
        "create_seo_recommendation_proposal",
        "create_content_proposal",
        "create_content_brief",
        "generate_content_draft_proposal",
        "generate_gbp_post_proposal",
        "create_gbp_optimization_proposal",
        "draft_review_response_proposal",
        "inspect_workflow",
        "submit_for_approval",
    }
)


class HermesRuntimeError(RuntimeError):
    def __init__(self, safe_code: str, message: str) -> None:
        self.safe_code = safe_code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class HermesCapabilities:
    runtime_version: str
    model: str
    features: dict[str, bool]
    endpoints: dict[str, object]
    runtime: dict[str, object]
    sanctioned_tools: tuple[str, ...]
    raw: dict[str, object]

    @property
    def missing_required(self) -> tuple[str, ...]:
        return tuple(sorted(name for name in REQUIRED_FEATURES if not self.features.get(name)))

    def supports(self, feature: str) -> bool:
        return bool(self.features.get(feature))


class HermesRunsClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        try:
            self._base_url = normalize_hermes_base_url(base_url)
        except ValueError as exc:
            raise HermesRuntimeError(
                "HERMES_CONFIGURATION_INVALID", "Hermes base URL is invalid"
            ) from exc
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._client = client

    def _headers(self, session_key: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"}
        if session_key:
            headers["X-Hermes-Session-Key"] = session_key
        return headers

    async def _request(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers(),
                json=json_body,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise HermesRuntimeError("HERMES_PROTOCOL_INVALID", "Hermes returned invalid JSON")
            return payload
        except HermesRuntimeError:
            raise
        except httpx.TimeoutException as exc:
            raise HermesRuntimeError("HERMES_TIMEOUT", "Hermes request timed out") from exc
        except httpx.HTTPStatusError as exc:
            code = (
                "HERMES_AUTH_FAILED"
                if exc.response.status_code in {401, 403}
                else "HERMES_HTTP_ERROR"
            )
            raise HermesRuntimeError(
                code, f"Hermes request failed with {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HermesRuntimeError("HERMES_UNAVAILABLE", "Hermes runtime unavailable") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def capabilities(self) -> HermesCapabilities:
        health = await self._request("GET", "/health/detailed")
        payload = await self._request("GET", "/v1/capabilities")
        toolsets_payload = await self._request("GET", "/v1/toolsets")
        features = payload.get("features")
        runtime = payload.get("runtime")
        endpoints = payload.get("endpoints")
        if (
            not isinstance(features, dict)
            or not isinstance(runtime, dict)
            or not isinstance(endpoints, dict)
        ):
            raise HermesRuntimeError(
                "HERMES_CAPABILITIES_INVALID", "Hermes capabilities are invalid"
            )
        invalid_required_features = tuple(
            sorted(
                name
                for name in REQUIRED_FEATURES
                if not isinstance(features.get(name), bool)
            )
        )
        if invalid_required_features:
            raise HermesRuntimeError(
                "HERMES_CAPABILITIES_INVALID",
                "Hermes required feature values must be boolean",
            )
        for endpoint_name, (required_method, required_path) in REQUIRED_ENDPOINTS.items():
            endpoint = endpoints.get(endpoint_name)
            if not isinstance(endpoint, dict) or (endpoint.get("method"), endpoint.get("path")) != (
                required_method,
                required_path,
            ):
                raise HermesRuntimeError(
                    "HERMES_CAPABILITIES_INVALID",
                    f"Hermes endpoint contract is invalid: {endpoint_name}",
                )
        toolset_rows = toolsets_payload.get("data")
        if not isinstance(toolset_rows, list):
            raise HermesRuntimeError(
                "HERMES_TOOLSET_INVALID", "Hermes toolset projection is invalid"
            )
        enabled_toolsets = [
            item for item in toolset_rows if isinstance(item, dict) and item.get("enabled") is True
        ]
        enabled_names = {str(item.get("name")) for item in enabled_toolsets}
        lilos_toolset = next(
            (item for item in enabled_toolsets if item.get("name") == "lilos"), None
        )
        lilos_tools = lilos_toolset.get("tools") if isinstance(lilos_toolset, dict) else None
        if enabled_names != {"lilos"} or not isinstance(lilos_tools, list):
            raise HermesRuntimeError(
                "HERMES_TOOLSET_UNSAFE", "Hermes sanctioned toolset is unavailable or unsafe"
            )
        normalized_tools = tuple(sorted(str(item) for item in lilos_tools))
        if normalized_tools != tuple(sorted(REQUIRED_LILOS_TOOLS)):
            raise HermesRuntimeError(
                "HERMES_TOOLSET_MISMATCH", "Hermes sanctioned tool contract does not match LILOs"
            )
        normalized = {
            str(key): value for key, value in features.items() if isinstance(value, bool)
        }
        capabilities = HermesCapabilities(
            runtime_version=str(health.get("version") or "unknown"),
            model=str(payload.get("model") or "unknown"),
            features=normalized,
            endpoints=dict(endpoints),
            runtime=dict(runtime),
            sanctioned_tools=normalized_tools,
            raw=payload,
        )
        if capabilities.runtime.get("tool_execution") != "server":
            raise HermesRuntimeError(
                "HERMES_RUNTIME_UNSAFE", "Hermes server-side tool execution is unavailable"
            )
        if (
            capabilities.runtime.get("mode") != "server_agent"
            or capabilities.runtime.get("split_runtime") is not False
        ):
            raise HermesRuntimeError(
                "HERMES_RUNTIME_UNSAFE", "Hermes native server-agent runtime is unavailable"
            )
        return capabilities

    async def create_run(
        self,
        *,
        objective: str,
        instructions: str,
        hermes_session_id: str,
        session_key: str,
        model: str,
    ) -> str:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                f"{self._base_url}/v1/runs",
                headers=self._headers(session_key),
                json={
                    "input": objective,
                    "instructions": instructions,
                    "session_id": hermes_session_id,
                    "model": model,
                },
            )
            response.raise_for_status()
            payload = response.json()
            run_id = payload.get("run_id") if isinstance(payload, dict) else None
            if not isinstance(run_id, str) or not run_id.startswith("run_"):
                raise HermesRuntimeError("HERMES_PROTOCOL_INVALID", "Hermes run id missing")
            return run_id
        except HermesRuntimeError:
            raise
        except httpx.TimeoutException as exc:
            raise HermesRuntimeError("HERMES_TIMEOUT", "Hermes run creation timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise HermesRuntimeError(
                "HERMES_RUN_REJECTED", f"Hermes rejected run creation ({exc.response.status_code})"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HermesRuntimeError("HERMES_UNAVAILABLE", "Hermes runtime unavailable") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def get_run(self, hermes_run_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/runs/{hermes_run_id}")

    async def delete_session(self, hermes_session_id: str) -> None:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.delete(
                f"{self._base_url}/api/sessions/{hermes_session_id}",
                headers=self._headers(),
            )
            if response.status_code != 404:
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HermesRuntimeError("HERMES_TIMEOUT", "Hermes session reset timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise HermesRuntimeError(
                "HERMES_SESSION_RESET_FAILED",
                f"Hermes rejected session reset ({exc.response.status_code})",
            ) from exc
        except httpx.HTTPError as exc:
            raise HermesRuntimeError(
                "HERMES_UNAVAILABLE", "Hermes session reset is unavailable"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

    async def steer(self, hermes_run_id: str, text: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/v1/runs/{hermes_run_id}/steer", json_body={"input": text}
        )

    async def stop(self, hermes_run_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/v1/runs/{hermes_run_id}/stop", json_body={})

    async def approve(self, hermes_run_id: str, choice: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/v1/runs/{hermes_run_id}/approval", json_body={"choice": choice}
        )

    async def stream_events(self, hermes_run_id: str) -> AsyncIterator[dict[str, Any]]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=None)
        try:
            async with client.stream(
                "GET",
                f"{self._base_url}/v1/runs/{hermes_run_id}/events",
                headers={**self._headers(), "Accept": "text/event-stream"},
                timeout=httpx.Timeout(self._timeout, read=None),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        payload = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        yield payload
        except httpx.HTTPError as exc:
            raise HermesRuntimeError(
                "HERMES_EVENT_STREAM_FAILED", "Hermes event stream failed"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()
