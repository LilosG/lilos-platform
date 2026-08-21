"""AI provider factory — resolves the configured provider for the current environment.

Fail-closed: in production, the deterministic provider is rejected unless
explicitly configured. This prevents the test fixture from silently serving
production traffic.
"""

from __future__ import annotations

from apps.api.app.ai.errors import AIProviderConfigurationError
from apps.api.app.ai.gateway import AIGateway, AIProvider, DeterministicAIProvider
from apps.api.app.ai.hermes import HermesAgentProvider
from apps.api.app.ai.providers import OpenRouterProvider
from apps.api.app.config import Settings


def resolve_ai_provider(settings: Settings | None = None) -> AIProvider:
    """Return the configured AI provider for the current environment.

    - ``deterministic`` → ``DeterministicAIProvider`` (local/test only)
    - ``openrouter`` → ``OpenRouterProvider`` (raw model inference)
    - ``hermes`` → ``HermesAgentProvider`` (governed agent runtime)
    - In production, ``deterministic`` is rejected (fail-closed).
    """
    if settings is None:
        settings = Settings()

    provider_key = settings.ai_provider.strip().lower()

    if provider_key == "deterministic":
        if settings.environment.value == "production":
            raise AIProviderConfigurationError(
                "Deterministic AI provider is not permitted in production. "
                "Set LILOS_AI_PROVIDER=hermes or openrouter and configure its credentials."
            )
        return DeterministicAIProvider()

    if provider_key == "openrouter":
        api_key = settings.ai_openrouter_api_key
        if not api_key:
            raise AIProviderConfigurationError(
                "OpenRouter API key is required when LILOS_AI_PROVIDER=openrouter. "
                "Set LILOS_OPENROUTER_API_KEY in the environment."
            )
        return OpenRouterProvider(
            api_key=api_key,
            base_url=settings.ai_openrouter_base_url,
            timeout_seconds=settings.ai_timeout_seconds,
            max_output_tokens=settings.ai_max_output_tokens,
            default_model=settings.ai_default_model,
        )

    if provider_key == "hermes":
        api_key = settings.ai_hermes_api_key
        base_url = settings.ai_hermes_base_url
        if not api_key or not base_url:
            raise AIProviderConfigurationError(
                "Hermes runtime URL and API key are required when "
                "LILOS_AI_PROVIDER=hermes. Configure LILOS_HERMES_BASE_URL "
                "and LILOS_HERMES_API_KEY."
            )
        return HermesAgentProvider(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=settings.ai_hermes_timeout_seconds,
            max_output_tokens=settings.ai_max_output_tokens,
            model=settings.ai_hermes_model,
        )

    raise AIProviderConfigurationError(
        f"Unknown AI provider '{provider_key}'. Supported values: deterministic, openrouter, hermes."
    )


def build_ai_gateway(settings: Settings | None = None) -> AIGateway:
    """Build a fully configured AIGateway from environment settings.

    The provider is resolved lazily on first execution so that platform
    startup is independent of AI provider configuration. A missing or
    misconfigured provider raises ``AIProviderConfigurationError`` at
    execution time, not at import.
    """
    if settings is None:
        settings = Settings()

    return AIGateway(
        provider_factory=lambda: resolve_ai_provider(settings),
        task_model_overrides=settings.ai_task_model_map(),
        default_model=settings.ai_default_model,
        global_max_output_tokens=settings.ai_max_output_tokens,
        global_max_cost_microunits=settings.ai_maximum_cost_microunits,
    )
