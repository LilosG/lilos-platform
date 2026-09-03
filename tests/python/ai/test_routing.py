"""Shared model-routing contract tests."""

from __future__ import annotations

from apps.api.app.ai.factory import resolve_ai_provider
from apps.api.app.ai.providers import OpenRouterProvider
from apps.api.app.ai.routing import is_dynamic_openrouter_route, resolve_task_model
from apps.api.app.config import EnvironmentName, Settings


def test_task_model_override_beats_default_and_runtime_fallback() -> None:
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "ai_default_model": "default/model",
            "ai_task_model_overrides": '{"agent.seo.operator":"reasoning/model"}',
        }
    )
    assert (
        resolve_task_model(
            "agent.seo.operator", settings, fallback="hermes/runtime-default"
        )
        == "reasoning/model"
    )


def test_task_model_default_beats_runtime_fallback() -> None:
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "ai_default_model": "default/model"}
    )
    assert (
        resolve_task_model("agent.gbp.operator", settings, fallback="hermes/runtime-default")
        == "default/model"
    )


def test_task_model_uses_runtime_fallback_when_platform_default_is_absent() -> None:
    settings = Settings.model_validate({"environment": EnvironmentName.TEST})
    assert (
        resolve_task_model("agent.gbp.operator", settings, fallback="hermes/runtime-default")
        == "hermes/runtime-default"
    )


def test_dynamic_openrouter_route_detection_is_narrow() -> None:
    assert is_dynamic_openrouter_route(None) is True
    assert is_dynamic_openrouter_route("openrouter/auto") is True
    assert is_dynamic_openrouter_route("deepseek/deepseek-v4-flash-0731") is False


def test_openrouter_provider_receives_the_resolved_task_model() -> None:
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "ai_provider": "openrouter",
            "ai_openrouter_api_key": "test-openrouter-key",
            "ai_default_model": "default/model",
            "ai_task_model_overrides": '{"content.draft_revision":"quality/model"}',
        }
    )
    provider = resolve_ai_provider(settings, task_key="content.draft_revision")
    assert isinstance(provider, OpenRouterProvider)
    assert provider._default_model == "quality/model"
