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

# AI Gateway tasks that are single-shot text generation, not agent work.
#
# These cannot be served by the Hermes agent runtime. Hermes answers a
# /v1/chat/completions call by running a tool-using agent loop, and every LILOs
# tool it reaches for is refused by our own bridge with
# "Hermes session is not bound to an active LILOs run" — an AI Gateway request
# has no AgentRun row to bind to (apps/api/app/agents/tools.py: bound_run). The
# loop then burns iterations against a denied toolset until the client timeout
# fires, which is what surfaced in the UI as "Hermes agent request timed out"
# on every Generate AI draft.
#
# Genuine agent work does not come through here: it goes through the agents
# module, which creates the AgentRun first and therefore satisfies the bridge.
DIRECT_GENERATION_TASK_KEYS: frozenset[str] = frozenset(
    {
        "reviews.response_draft",
        "content.draft_revision",
        "gbp.generate_post",
    }
)


def resolve_task_provider_key(task_key: str | None, settings: Settings) -> str:
    """Return the provider key that should serve one AI Gateway task.

    Precedence: an explicit per-task override, then the automatic redirect of
    direct-generation tasks away from the agent runtime, then the configured
    default provider.
    """
    overrides = settings.ai_task_provider_map()
    if task_key and task_key in overrides:
        return overrides[task_key]

    configured = settings.ai_provider.strip().lower()
    if (
        configured == "hermes"
        and task_key in DIRECT_GENERATION_TASK_KEYS
        and settings.ai_openrouter_api_key
    ):
        # Deliberate override of an operator setting, because honouring it here
        # guarantees failure rather than governance. Recorded on the execution
        # as the provider actually used, never silently.
        return "openrouter"
    return configured


def unservable_direct_generation(task_key: str | None, settings: Settings) -> bool:
    """True when this task is routed somewhere that cannot possibly serve it.

    Reached when the agent runtime is the configured provider for a
    single-shot generation task and no direct-inference provider is
    credentialed to take over. The request would be accepted and then hang
    until the client timeout, reported to the operator as "timed out" with no
    indication that it can never succeed. Failing immediately and naming the
    missing credential is the honest behaviour.
    """
    if task_key not in DIRECT_GENERATION_TASK_KEYS:
        return False
    if task_key in settings.ai_task_provider_map():
        # An operator asked for this explicitly; respect it.
        return False
    return settings.ai_provider.strip().lower() == "hermes" and not settings.ai_openrouter_api_key


def resolve_ai_provider(
    settings: Settings | None = None, *, task_key: str | None = None
) -> AIProvider:
    """Return the configured AI provider for the current environment.

    - ``deterministic`` → ``DeterministicAIProvider`` (local/test only)
    - ``openrouter`` → ``OpenRouterProvider`` (raw model inference)
    - ``hermes`` → ``HermesAgentProvider`` (governed agent runtime)
    - In production, ``deterministic`` is rejected (fail-closed).

    ``task_key`` selects the provider per task where the two are not
    interchangeable; see ``resolve_task_provider_key``.
    """
    if settings is None:
        settings = Settings()

    if unservable_direct_generation(task_key, settings):
        raise AIProviderConfigurationError(
            f"Task '{task_key}' is single-shot text generation and cannot run on the "
            "Hermes agent runtime: an AI Gateway request has no agent run for its "
            "tools to bind to, so the request would hang until it timed out. Set "
            "LILOS_OPENROUTER_API_KEY so direct generation can be served, or set "
            "LILOS_AI_TASK_PROVIDER_OVERRIDES to route this task deliberately."
        )

    provider_key = resolve_task_provider_key(task_key, settings)

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
        f"Unknown AI provider '{provider_key}'. Supported values: "
        "deterministic, openrouter, hermes."
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
        provider_resolver=lambda task_key: resolve_ai_provider(settings, task_key=task_key),
        task_model_overrides=settings.ai_task_model_map(),
        default_model=settings.ai_default_model,
        global_max_output_tokens=settings.ai_max_output_tokens,
        global_max_cost_microunits=settings.ai_maximum_cost_microunits,
    )
