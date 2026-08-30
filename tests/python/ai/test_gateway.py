"""Packet 5 — AIGateway and provider factory unit tests."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from apps.api.app.ai.errors import AIProviderConfigurationError
from apps.api.app.ai.factory import (
    build_ai_gateway,
    resolve_ai_provider,
    resolve_task_provider_key,
    unservable_direct_generation,
)
from apps.api.app.ai.gateway import (
    AIGateway,
    AIGatewayRequest,
    DeterministicAIProvider,
)
from apps.api.app.ai.providers import OpenRouterProvider
from apps.api.app.config import EnvironmentName, Settings


class FakeProvider:
    def __init__(self, output: dict[str, Any]):
        self.output = output
        self.calls: list[tuple[str, dict[str, Any], int, int | None]] = []

    async def generate(
        self,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        task_key: str,
        input_document: dict[str, Any],
        maximum_tokens: int,
        maximum_latency_ms: int | None = None,
    ) -> dict[str, Any]:
        del organization_id, location_id
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
async def test_gateway_rejects_nested_secret_bearing_input() -> None:
    gateway = AIGateway(FakeProvider({"draft": "x"}))
    with pytest.raises(ValueError, match="secret"):
        await gateway.execute(
            _request(input_document={"knowledge": [{"authorization_token": "sk-123"}]})
        )


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
            organization_id: UUID,
            location_id: UUID | None,
            task_key: str,
            input_document: dict[str, Any],
            maximum_tokens: int,
            maximum_latency_ms: int | None = None,
        ) -> dict[str, Any]:
            del organization_id, location_id, task_key, input_document, maximum_tokens
            del maximum_latency_ms
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
            organization_id: UUID,
            location_id: UUID | None,
            task_key: str,
            input_document: dict[str, Any],
            maximum_tokens: int,
            maximum_latency_ms: int | None = None,
        ) -> dict[str, Any]:
            del organization_id, location_id, task_key, input_document, maximum_tokens
            del maximum_latency_ms
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


# ---------------------------------------------------------------------------
# Per-task provider routing
# ---------------------------------------------------------------------------


def _hermes_settings(**overrides: Any) -> Settings:
    """Production-shaped settings with both providers credentialed."""
    payload: dict[str, Any] = {
        "environment": EnvironmentName.TEST,
        "ai_provider": "hermes",
        "ai_hermes_base_url": "https://hermes.internal",
        "ai_hermes_api_key": "hermes-key-value",
        "ai_openrouter_api_key": "openrouter-key-value",
    }
    payload.update(overrides)
    return Settings.model_validate(payload)


@pytest.mark.parametrize(
    "task_key",
    ["reviews.response_draft", "content.draft_revision", "gbp.generate_post"],
)
def test_single_shot_generation_never_routes_to_the_agent_runtime(task_key: str) -> None:
    """The agent runtime cannot serve these and would hang until the timeout.

    Hermes answers a chat completion by running a tool loop, and every LILOs
    tool is refused because an AI Gateway request has no AgentRun to bind to.
    Honouring ``ai_provider=hermes`` for these tasks guarantees failure.
    """
    assert resolve_task_provider_key(task_key, _hermes_settings()) == "openrouter"
    assert isinstance(
        resolve_ai_provider(_hermes_settings(), task_key=task_key), OpenRouterProvider
    )


def test_agent_work_still_reaches_the_agent_runtime() -> None:
    # The redirect is narrow: anything outside the direct-generation set keeps
    # the configured provider, so governed agent routing is not weakened.
    settings = _hermes_settings()
    assert resolve_task_provider_key("agents.gbp_operator", settings) == "hermes"
    assert resolve_task_provider_key(None, settings) == "hermes"


def test_an_unservable_task_fails_immediately_instead_of_hanging() -> None:
    # With no direct-inference provider credentialed there is nothing to redirect
    # to, and the agent runtime cannot serve the task. Accepting the request
    # would produce a 120-second hang reported as "timed out"; the operator
    # needs to be told it can never succeed, and what to set.
    settings = _hermes_settings(ai_openrouter_api_key=None)
    assert unservable_direct_generation("reviews.response_draft", settings) is True
    with pytest.raises(AIProviderConfigurationError, match="LILOS_OPENROUTER_API_KEY"):
        resolve_ai_provider(settings, task_key="reviews.response_draft")


def test_an_explicit_override_to_hermes_is_still_honoured() -> None:
    # If an operator deliberately routes a task at the agent runtime, that is
    # their call to make, not ours to veto.
    settings = _hermes_settings(
        ai_openrouter_api_key=None,
        ai_task_provider_overrides='{"reviews.response_draft": "hermes"}',
    )
    assert unservable_direct_generation("reviews.response_draft", settings) is False
    assert resolve_task_provider_key("reviews.response_draft", settings) == "hermes"


def test_agent_tasks_are_unaffected_by_the_servability_check() -> None:
    settings = _hermes_settings(ai_openrouter_api_key=None)
    assert unservable_direct_generation("agents.gbp_operator", settings) is False
    assert unservable_direct_generation(None, settings) is False


def test_an_explicit_per_task_override_beats_the_default_and_the_redirect() -> None:
    settings = _hermes_settings(
        ai_task_provider_overrides='{"reviews.response_draft": "hermes",'
        ' "agents.custom": "openrouter"}'
    )
    assert resolve_task_provider_key("reviews.response_draft", settings) == "hermes"
    assert resolve_task_provider_key("agents.custom", settings) == "openrouter"


def test_a_non_hermes_default_is_left_alone() -> None:
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "ai_provider": "openrouter",
            "ai_openrouter_api_key": "openrouter-key-value",
        }
    )
    assert resolve_task_provider_key("reviews.response_draft", settings) == "openrouter"
    assert resolve_task_provider_key("agents.gbp_operator", settings) == "openrouter"


@pytest.mark.anyio
async def test_the_gateway_resolves_a_provider_per_task_and_caches_it() -> None:
    resolved: list[str | None] = []

    def resolver(task_key: str | None) -> Any:
        resolved.append(task_key)
        return FakeProvider({"draft": "ok", "provider": "openrouter", "model": "m"})

    gateway = AIGateway(provider_resolver=resolver, global_max_cost_microunits=100_000)

    await gateway.execute(_request(task_key="reviews.response_draft"))
    await gateway.execute(_request(task_key="reviews.response_draft"))
    await gateway.execute(_request(task_key="content.draft_revision"))

    # One resolution per distinct task, not per execution: a rebuilt HTTP
    # client on every draft would be a needless cost.
    assert resolved == ["reviews.response_draft", "content.draft_revision"]


@pytest.mark.anyio
async def test_the_recorded_provider_is_the_one_that_actually_ran() -> None:
    # The audit trail must name the provider used, not the one configured,
    # or a redirected task would be attributed to the wrong runtime.
    gateway = AIGateway(
        provider_resolver=lambda _task: FakeProvider(
            {"draft": "ok", "provider": "openrouter", "model": "deepseek/deepseek-v4-flash-0731"}
        )
    )
    result = await gateway.execute(_request(task_key="reviews.response_draft"))
    assert result["provider"] == "openrouter"


def test_a_gateway_with_no_provider_at_all_is_rejected() -> None:
    with pytest.raises(ValueError, match="provider"):
        AIGateway()
