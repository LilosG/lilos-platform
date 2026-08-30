"""Hermes Agent provider contract tests with no network calls."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import httpx
import pytest

from apps.api.app.ai.errors import AIProviderConfigurationError, AIProviderError
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
        organization_id=uuid4(),
        location_id=uuid4(),
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
    assert "hermes-secret-key" not in json.dumps(output)


@pytest.mark.anyio
async def test_hermes_sessions_are_tenant_scoped_without_exposing_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _fake_http(
        monkeypatch,
        FakeResponse(
            {
                "choices": [{"message": {"content": '{"draft": "Scoped"}'}}],
                "usage": {},
            }
        ),
    )
    provider = HermesAgentProvider(
        api_key="hermes-secret-key",
        base_url="lilos-hermes:8642",
    )
    first_org = uuid4()
    second_org = uuid4()
    for organization_id in (first_org, second_org):
        await provider.generate(
            organization_id=organization_id,
            location_id=None,
            task_key="content.draft_revision",
            input_document={"audience": "local"},
            maximum_tokens=100,
        )

    first_session = client.calls[0]["headers"]["X-Hermes-Session-Key"]
    second_session = client.calls[1]["headers"]["X-Hermes-Session-Key"]
    assert first_session != second_session
    assert str(first_org) not in first_session
    assert str(second_org) not in second_session


@pytest.mark.anyio
async def test_hermes_rejects_secret_bearing_output_with_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "hermes-secret-key"
    _fake_http(
        monkeypatch,
        FakeResponse(
            {"choices": [{"message": {"content": json.dumps({"draft": f"unsafe {secret}"})}}]}
        ),
    )
    provider = HermesAgentProvider(api_key=secret, base_url="lilos-hermes:8642")

    with pytest.raises(AIProviderError) as exc:
        await provider.generate(
            organization_id=uuid4(),
            location_id=None,
            task_key="content.draft_revision",
            input_document={},
            maximum_tokens=100,
        )

    assert secret not in exc.value.safe_message


@pytest.mark.anyio
async def test_hermes_timeout_becomes_governed_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TimeoutClient(FakeClient):
        async def post(self, url: str, **kwargs: Any) -> FakeResponse:
            raise httpx.TimeoutException("private runtime timeout")

    monkeypatch.setattr(
        "apps.api.app.ai.hermes.httpx.AsyncClient",
        lambda *args, **kwargs: TimeoutClient(FakeResponse({})),
    )
    provider = HermesAgentProvider(api_key="hermes-secret-key", base_url="lilos-hermes:8642")

    with pytest.raises(AIProviderError) as exc:
        await provider.generate(
            organization_id=uuid4(),
            location_id=None,
            task_key="content.draft_revision",
            input_document={},
            maximum_tokens=100,
        )

    assert exc.value.category == "provider"
    assert "timeout" not in str(exc.value).lower() or "timed out" in str(exc.value).lower()


@pytest.mark.anyio
async def test_hermes_prose_output_is_used_as_the_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent runtime cannot be sent response_format, so it answers in prose.

    Rejecting that answer is what surfaced as "Hermes agent returned content
    that is not valid JSON" on a review reply the model had written correctly.
    """
    reply = "Thank you for the detailed feedback — we have shared it with our team."
    _fake_http(
        monkeypatch,
        FakeResponse({"choices": [{"message": {"content": reply}}]}),
    )
    provider = HermesAgentProvider(api_key="hermes-secret-key", base_url="lilos-hermes:8642")

    output = await provider.generate(
        organization_id=uuid4(),
        location_id=None,
        task_key="content.draft_revision",
        input_document={},
        maximum_tokens=100,
    )

    assert output["draft"] == reply
    assert output["requires_human_review"] is True


@pytest.mark.anyio
async def test_hermes_truncated_json_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A half-written object is truncation, and its fragments are not a draft."""
    _fake_http(
        monkeypatch,
        FakeResponse({"choices": [{"message": {"content": '{"draft": "Thank you'}}]}),
    )
    provider = HermesAgentProvider(api_key="hermes-secret-key", base_url="lilos-hermes:8642")

    with pytest.raises(AIProviderError) as exc:
        await provider.generate(
            organization_id=uuid4(),
            location_id=None,
            task_key="content.draft_revision",
            input_document={},
            maximum_tokens=100,
        )

    assert exc.value.category == "provider"


def test_factory_resolves_hermes_provider() -> None:
    settings = Settings(
        ai_provider="hermes",
        ai_hermes_base_url="lilos-hermes:8642",
        ai_hermes_api_key="hermes-secret-key",
    )

    provider = resolve_ai_provider(settings)

    assert isinstance(provider, HermesAgentProvider)


def test_factory_fails_closed_when_production_hermes_config_is_missing() -> None:
    settings = Settings.model_validate(
        {
            "environment": "production",
            "release": "pr39-hermes-contract",
            "telemetry_export_endpoint": "https://telemetry.example.invalid",
            "ai_provider": "hermes",
        }
    )

    with pytest.raises(AIProviderConfigurationError):
        resolve_ai_provider(settings)
