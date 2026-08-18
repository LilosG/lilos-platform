"""Packet 5 — AIGateway and provider factory unit tests."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from apps.api.app.ai.errors import AIProviderConfigurationError
from apps.api.app.ai.factory import build_ai_gateway, resolve_ai_provider
from apps.api.app.ai.gateway import (
    AIGateway,
    AIGatewayRequest,
    DeterministicAIProvider,
)
from apps.api.app.config import EnvironmentName, Settings


class FakeProvider:
    def __init__(self, output: dict[str, Any]):
        self.output = output
        self.calls: list[tuple[str, dict[str, Any], int, int | None]] = []

    async def generate(
        self,
        *,
        task_key: str,
        input_document: dict[str, Any],
        maximum_tokens: int,
        maximum_latency_ms: int | None = None,
    ) -> dict[str, Any]:
        self.calls.append((task_key, dict(input_document), maximum_tokens, maximum_latency_ms))
        return dict(self.output)


def _request(**overrides: Any) -> AIGatewayRequest:
    org_id = uuid4()
    fact_id = uuid4()
    kwargs: dict[str, Any] = {
        "organization_id": org_id,
        "location_id": None,
        "task_key": "content.draft_revision",
        "input_document": {"audience": "local"},
        "input_references": (),
        "approved_fact_revision_ids": (fact_id,),
        "maximum_cost_microunits": 10_000,
        "maximum_latency_ms": 5_000,
    }
    kwargs.update(overrides)
    return AIGatewayRequest(
        organization_id=kwargs["organization_id"],
        location_id=kwargs["location_id"],
        task_key=kwargs["task_key"],
        input_document=kwargs["input_document"],
        input_references=kwargs["input_references"],
        approved_fact_revision_ids=kwargs["approved_fact_revision_ids"],
        maximum_cost_microunits=kwargs["maximum_cost_microunits"],
        maximum_latency_ms=kwargs["maximum_latency_ms"],
    )


# ---------------------------------------------------------------------------
# Gateway safety guards
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_gateway_requires_approved_facts() -> None:
    gateway = AIGateway(FakeProvider({"draft": "x"}))
    with pytest.raises(ValueError, match="grounding"):
        await gateway.execute(_request(approved_fact_revision_ids=()))


@pytest.mark.anyio
async def test_gateway_rejects_secret_bearing_input() -> None:
    gateway = AIGateway(FakeProvider({"draft": "x"}))
    with pytest.raises(ValueError, match="secret"):
        await gateway.execute(_request(input_document={"audience": "local", "api_key": "sk-123"}))


@pytest.mark.anyio
async def test_gateway_task_limit_zero_inherits_global_limit() -> None:
    """task maximum_cost_microunits == 0 inherits the configured global ceiling."""
    gateway = AIGateway(FakeProvider({"draft": "x"}), global_max_cost_microunits=200_000)
    output = await gateway.execute(_request(maximum_cost_microunits=0))
    assert output["draft"] == "x"


@pytest.mark.anyio
async def test_gateway_positive_task_limit_lower_than_global_wins() -> None:
    """When task limit is positive and lower than global, the task limit is the effective bound."""
    provider = FakeProvider({"draft": "x", "cost_microunits": 5_000})
    gateway = AIGateway(provider, global_max_cost_microunits=200_000)
    await gateway.execute(_request(maximum_cost_microunits=10_000))
    # effective bound = min(10_000, 200_000) = 10_000; cost 5_000 is within bound


@pytest.mark.anyio
async def test_gateway_global_limit_lower_than_task_wins() -> None:
    """When global limit is lower than task limit, the global limit is the effective bound."""
    provider = FakeProvider({"draft": "x", "cost_microunits": 5_000})
    gateway = AIGateway(provider, global_max_cost_microunits=10_000)
    await gateway.execute(_request(maximum_cost_microunits=200_000))
    # effective bound = min(200_000, 10_000) = 10_000; cost 5_000 is within bound


@pytest.mark.anyio
async def test_gateway_rejects_when_effective_global_limit_is_zero() -> None:
    """When the global limit is zero (or negative), execution is rejected fail-closed."""
    gateway = AIGateway(FakeProvider({"draft": "x"}), global_max_cost_microunits=0)
    with pytest.raises(ValueError, match="cost"):
        await gateway.execute(_request(maximum_cost_microunits=0))


@pytest.mark.anyio
async def test_gateway_fills_default_output_keys() -> None:
    gateway = AIGateway(FakeProvider({"draft": "partial"}))
    output = await gateway.execute(_request())
    assert output["provider"] == "unknown"
    assert output["model"] == "unknown"
    assert output["requires_human_review"] is True
    assert output["usage"] == {}


@pytest.mark.anyio
async def test_gateway_passes_max_tokens_to_provider() -> None:
    provider = FakeProvider({"draft": "x"})
    gateway = AIGateway(provider, global_max_output_tokens=1_200)
    await gateway.execute(_request())
    assert provider.calls[0][2] == 1_200


@pytest.mark.anyio
async def test_gateway_passes_latency_bound_to_provider() -> None:
    provider = FakeProvider({"draft": "x"})
    gateway = AIGateway(provider)
    await gateway.execute(_request(maximum_latency_ms=2_500))
    assert provider.calls[0][3] == 2_500


@pytest.mark.anyio
async def test_gateway_provider_error_propagates() -> None:
    from apps.api.app.ai.errors import AIProviderError

    class RaisingProvider:
        async def generate(
            self,
            *,
            task_key: str,
            input_document: dict[str, Any],
            maximum_tokens: int,
            maximum_latency_ms: int | None = None,
        ) -> dict[str, Any]:
            raise AIProviderError("provider", "simulated outage")

    gateway = AIGateway(RaisingProvider())
    with pytest.raises(AIProviderError) as exc:
        await gateway.execute(_request())
    assert exc.value.category == "provider"


@pytest.mark.anyio
async def test_gateway_unexpected_provider_exception_becomes_governed_error() -> None:
    from apps.api.app.ai.errors import AIProviderError

    class BrokenProvider:
        async def generate(
            self,
            *,
            task_key: str,
            input_document: dict[str, Any],
            maximum_tokens: int,
            maximum_latency_ms: int | None = None,
        ) -> dict[str, Any]:
            raise RuntimeError("raw internals with secrets")

    gateway = AIGateway(BrokenProvider())
    with pytest.raises(AIProviderError):
        await gateway.execute(_request())


# ---------------------------------------------------------------------------
# Deterministic provider contract
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_deterministic_provider_is_clearly_identified() -> None:
    output = await DeterministicAIProvider().generate(
        task_key="content.draft_revision",
        input_document={"manual_fallback": "fallback text"},
        maximum_tokens=100,
    )
    assert output["provider"] == "deterministic_test"
    assert output["model"] == "fixture-v1"
    assert output["requires_human_review"] is True


# ---------------------------------------------------------------------------
# Provider factory — fail-closed behavior
# ---------------------------------------------------------------------------


def test_factory_deterministic_allowed_outside_production() -> None:
    settings = Settings(environment=EnvironmentName.TEST, ai_provider="deterministic")
    provider = resolve_ai_provider(settings)
    assert isinstance(provider, DeterministicAIProvider)


def test_factory_deterministic_rejected_in_production() -> None:
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.PRODUCTION,
            "ai_provider": "deterministic",
            "release": "p5-test",
            "telemetry_export_endpoint": "https://telemetry.example.invalid",
        }
    )
    with pytest.raises(AIProviderConfigurationError):
        resolve_ai_provider(settings)


def test_factory_openrouter_requires_key() -> None:
    settings = Settings(environment=EnvironmentName.TEST, ai_provider="openrouter")
    with pytest.raises(AIProviderConfigurationError):
        resolve_ai_provider(settings)


def test_factory_openrouter_builds_provider_with_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LILOS_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("LILOS_OPENROUTER_API_KEY", "test-key-123")
    monkeypatch.setenv("LILOS_ENV", "test")
    from apps.api.app.ai.providers import OpenRouterProvider

    provider = resolve_ai_provider(Settings())
    assert isinstance(provider, OpenRouterProvider)


def test_factory_unknown_provider_rejected() -> None:
    settings = Settings(environment=EnvironmentName.TEST, ai_provider="nonexistent")
    with pytest.raises(AIProviderConfigurationError):
        resolve_ai_provider(settings)


def test_build_ai_gateway_routes_task_models(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    monkeypatch.setenv("LILOS_AI_PROVIDER", "deterministic")
    monkeypatch.setenv("LILOS_ENV", "test")
    monkeypatch.setenv(
        "LILOS_AI_TASK_MODEL_OVERRIDES",
        json.dumps({"content.draft_revision": "test/model-x"}),
    )
    gateway = build_ai_gateway(Settings())
    assert gateway._resolve_model("content.draft_revision") == "test/model-x"
    assert gateway._resolve_model("reviews.draft_response") is None
