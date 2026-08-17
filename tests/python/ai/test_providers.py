"""Packet 5 — AI provider adapter unit tests (no network, mocked HTTP)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.api.app.ai.errors import AIProviderConfigurationError, AIProviderError
from apps.api.app.ai.providers import OpenRouterProvider


class FakeResponse:
    def __init__(self, status_code: int, body: dict[str, Any] | None = None, text: str = ""):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self) -> dict[str, Any]:
        if self._body is None:
            raise json.JSONDecodeError("no json", self.text, 0)
        return self._body


class FakeClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


def _fake_http(
    monkeypatch: pytest.MonkeyPatch, response: FakeResponse
) -> FakeClient:
    client = FakeClient(response)

    def factory(*args: object, **kwargs: object) -> FakeClient:
        return client

    monkeypatch.setattr("apps.api.app.ai.providers.httpx.AsyncClient", factory)
    return client


def _provider(**overrides: Any) -> OpenRouterProvider:
    return OpenRouterProvider(api_key="test-key", **overrides)


@pytest.mark.anyio
async def test_openrouter_provider_returns_governed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful OpenRouter completion yields a governed output dict."""
    client = _fake_http(
        monkeypatch,
        FakeResponse(
            200,
            {
                "id": "gen-123",
                "model": "deepseek/deepseek-chat",
                "choices": [
                    {"message": {"content": json.dumps({"draft": "Generated draft text"})}}
                ],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 80,
                    "total_tokens": 200,
                },
                "cost": 0.0042,
            },
        ),
    )

    output = await _provider().generate(
        task_key="content.draft_revision",
        input_document={"audience": "local", "intent": "inform"},
        maximum_tokens=500,
    )

    assert output["provider"] == "openrouter"
    assert output["model"] == "deepseek/deepseek-chat"
    assert output["draft"] == "Generated draft text"
    assert output["requires_human_review"] is True
    assert output["usage"]["input_tokens"] == 120
    assert output["usage"]["output_tokens"] == 80
    assert output["usage"]["total_tokens"] == 200
    assert output["cost_microunits"] == 42  # 0.0042 cents * 10,000
    assert output["request_id"] == "gen-123"
    assert output["latency_ms"] is not None
    assert len(client.calls) == 1


@pytest.mark.anyio
async def test_openrouter_provider_never_sends_key_in_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The API key is sent only in the Authorization header, never the body."""
    client = _fake_http(
        monkeypatch,
        FakeResponse(
            200,
            {
                "id": "gen-1",
                "model": "deepseek/deepseek-chat",
                "choices": [{"message": {"content": '{"draft": "text"}'}}],
                "usage": {},
            },
        ),
    )

    await OpenRouterProvider(api_key="sk-secret-key-value").generate(
        task_key="content.draft_revision",
        input_document={},
        maximum_tokens=100,
    )

    call = client.calls[0]
    assert call["headers"]["Authorization"] == "Bearer sk-secret-key-value"
    assert "sk-secret-key-value" not in json.dumps(call["json"])


@pytest.mark.anyio
async def test_openrouter_provider_requires_api_key() -> None:
    with pytest.raises(AIProviderConfigurationError):
        OpenRouterProvider(api_key="   ")


@pytest.mark.anyio
async def test_openrouter_provider_auth_failure_is_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_http(monkeypatch, FakeResponse(401))
    with pytest.raises(AIProviderError) as exc:
        await _provider().generate(
            task_key="content.draft_revision", input_document={}, maximum_tokens=100
        )
    assert exc.value.category == "configuration"
    assert "api" not in exc.value.safe_message.lower() or "key" in exc.value.safe_message.lower()


@pytest.mark.anyio
async def test_openrouter_provider_rate_limit_is_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_http(monkeypatch, FakeResponse(429))
    with pytest.raises(AIProviderError) as exc:
        await _provider().generate(
            task_key="content.draft_revision", input_document={}, maximum_tokens=100
        )
    assert exc.value.category == "provider"
    assert "rate limit" in exc.value.safe_message.lower()


@pytest.mark.anyio
async def test_openrouter_provider_5xx_is_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_http(monkeypatch, FakeResponse(502))
    with pytest.raises(AIProviderError) as exc:
        await _provider().generate(
            task_key="content.draft_revision", input_document={}, maximum_tokens=100
        )
    assert exc.value.category == "provider"


@pytest.mark.anyio
async def test_openrouter_provider_4xx_is_permanent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_http(monkeypatch, FakeResponse(400))
    with pytest.raises(AIProviderError) as exc:
        await _provider().generate(
            task_key="content.draft_revision", input_document={}, maximum_tokens=100
        )
    assert exc.value.category == "permanent"


@pytest.mark.anyio
async def test_openrouter_provider_malformed_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_http(monkeypatch, FakeResponse(200, {"not": "a completion"}))
    with pytest.raises(AIProviderError) as exc:
        await _provider().generate(
            task_key="content.draft_revision", input_document={}, maximum_tokens=100
        )
    assert exc.value.category == "provider"


@pytest.mark.anyio
async def test_openrouter_provider_non_json_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_http(
        monkeypatch,
        FakeResponse(
            200,
            {
                "choices": [{"message": {"content": "plain text, not json"}}],
                "usage": {},
            },
        ),
    )
    with pytest.raises(AIProviderError) as exc:
        await _provider().generate(
            task_key="content.draft_revision", input_document={}, maximum_tokens=100
        )
    assert exc.value.category == "provider"


@pytest.mark.anyio
async def test_openrouter_provider_empty_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_http(
        monkeypatch,
        FakeResponse(
            200,
            {
                "choices": [{"message": {"content": '{"draft": "   "}'}}],
                "usage": {},
            },
        ),
    )
    with pytest.raises(AIProviderError) as exc:
        await _provider().generate(
            task_key="content.draft_revision", input_document={}, maximum_tokens=100
        )
    assert exc.value.category == "provider"


@pytest.mark.anyio
async def test_openrouter_provider_timeout_is_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    def raising_client(*args: object, **kwargs: object) -> FakeClient:
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("apps.api.app.ai.providers.httpx.AsyncClient", raising_client)
    with pytest.raises(AIProviderError) as exc:
        await _provider().generate(
            task_key="content.draft_revision", input_document={}, maximum_tokens=100
        )
    assert exc.value.category == "provider"


@pytest.mark.anyio
async def test_openrouter_provider_connect_error_is_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    def raising_client(*args: object, **kwargs: object) -> FakeClient:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("apps.api.app.ai.providers.httpx.AsyncClient", raising_client)
    with pytest.raises(AIProviderError) as exc:
        await _provider().generate(
            task_key="content.draft_revision", input_document={}, maximum_tokens=100
        )
    assert exc.value.category == "provider"


@pytest.mark.anyio
async def test_openrouter_provider_caps_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """maximum_tokens is capped by the configured max_output_tokens ceiling."""
    client = _fake_http(
        monkeypatch,
        FakeResponse(
            200,
            {
                "id": "gen-1",
                "model": "deepseek/deepseek-chat",
                "choices": [{"message": {"content": '{"draft": "ok"}'}}],
                "usage": {},
            },
        ),
    )

    await _provider(max_output_tokens=100).generate(
        task_key="content.draft_revision",
        input_document={},
        maximum_tokens=10_000,
    )

    assert client.calls[0]["json"]["max_tokens"] == 100


@pytest.mark.anyio
async def test_openrouter_provider_missing_cost_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the provider omits cost, cost_microunits must be None, not fabricated."""
    _fake_http(
        monkeypatch,
        FakeResponse(
            200,
            {
                "id": "gen-1",
                "model": "deepseek/deepseek-chat",
                "choices": [{"message": {"content": '{"draft": "ok"}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            },
        ),
    )

    output = await _provider().generate(
        task_key="content.draft_revision", input_document={}, maximum_tokens=100
    )
    assert output["cost_microunits"] is None


@pytest.mark.anyio
async def test_openrouter_provider_latency_bound_caps_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A task latency bound caps the HTTP client timeout below the configured ceiling."""
    import httpx as httpx_module

    built_clients: list[tuple[Any, ...]] = []

    def recording_client(*args: Any, **kwargs: Any) -> FakeClient:
        built_clients.append((args, kwargs))
        return FakeClient(
            FakeResponse(
                200,
                {
                    "id": "gen-1",
                    "model": "deepseek/deepseek-chat",
                    "choices": [{"message": {"content": '{"draft": "ok"}'}}],
                    "usage": {},
                },
            )
        )

    monkeypatch.setattr(httpx_module, "AsyncClient", recording_client)

    await _provider(timeout_seconds=60.0).generate(
        task_key="content.draft_revision",
        input_document={},
        maximum_tokens=100,
        maximum_latency_ms=3_000,
    )

    kwargs = built_clients[0][1]
    assert kwargs["timeout"] == 3.0  # 3000ms → 3s, capped below 60s ceiling