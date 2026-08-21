"""Hermes Agent provider contract tests with no network calls."""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.api.app.ai.factory import resolve_ai_provider
from apps.api.app.ai.hermes import HermesAgentProvider
from apps.api.app.config import Settings


class FakeResponse:
    def __init__(self, body: dict[str, Any], status_code: int = 200) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict[str, Any]:
        return self._body


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


def _fake_http(monkeypatch: pytest.MonkeyPatch, response: FakeResponse) -> FakeClient:
    client = FakeClient(response)

    def factory(*args: object, **kwargs: object) -> FakeClient:
        return client

    monkeypatch.setattr("apps.api.app.ai.hermes.httpx.AsyncClient", factory)
    return client


@pytest.mark.anyio
async def test_hermes_provider_returns_governed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _fake_http(
        monkeypatch,
        FakeResponse(
            {
                "id": "hermes-response-1",
                "model": "hermes-agent",
                "choices": [{"message": {"content": '```json\n{"draft": "Grounded draft"}\n```'}}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 30,
                    "total_tokens": 130,
                },
            }
        ),
    )
    provider = HermesAgentProvider(
        api_key="hermes-secret-key",
        base_url="lilos-hermes:8642",
    )

    output = await provider.generate(
        task_key="content.draft_revision",
        input_document={"audience": "local", "intent": "inform"},
        maximum_tokens=500,
    )

    assert output["provider"] == "hermes"
    assert output["draft"] == "Grounded draft"
    assert output["requires_human_review"] is True
    assert output["usage"]["total_tokens"] == 130
    assert client.calls[0]["url"] == "http://lilos-hermes:8642/v1/chat/completions"
    assert client.calls[0]["headers"]["Authorization"] == "Bearer hermes-secret-key"
    assert "hermes-secret-key" not in json.dumps(client.calls[0]["json"])


def test_factory_resolves_hermes_provider() -> None:
    settings = Settings(
        ai_provider="hermes",
        ai_hermes_base_url="lilos-hermes:8642",
        ai_hermes_api_key="hermes-secret-key",
    )

    provider = resolve_ai_provider(settings)

    assert isinstance(provider, HermesAgentProvider)
