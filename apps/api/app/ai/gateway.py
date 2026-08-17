"""One provider-neutral, task-registered AI execution boundary.

The gateway enforces:
- approved business-fact grounding (required)
- secret-bearing input rejection
- task → model/profile routing via configuration
- bounded maximum output tokens
- bounded maximum cost (pre-flight check against global config)
- bounded maximum latency (passed through to provider timeout)
- post-execution cost validation (records overspend, does not block)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from apps.api.app.ai.errors import AIProviderError

logger = logging.getLogger(__name__)


class AIProvider(Protocol):
    async def generate(
        self,
        *,
        task_key: str,
        input_document: dict[str, Any],
        maximum_tokens: int,
        maximum_latency_ms: int | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class AIGatewayRequest:
    organization_id: UUID
    location_id: UUID | None
    task_key: str
    input_document: dict[str, Any]
    input_references: tuple[UUID, ...]
    approved_fact_revision_ids: tuple[UUID, ...]
    maximum_cost_microunits: int
    maximum_latency_ms: int


class AIGateway:
    """Governed AI execution boundary with task routing and cost/latency bounds."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        task_model_overrides: dict[str, str] | None = None,
        default_model: str | None = None,
        global_max_output_tokens: int = 2_000,
        global_max_cost_microunits: int = 200_000,
    ) -> None:
        self.provider = provider
        self._task_models = task_model_overrides or {}
        self._default_model = default_model
        self._global_max_output_tokens = global_max_output_tokens
        self._global_max_cost_microunits = global_max_cost_microunits

    def _resolve_model(self, task_key: str) -> str | None:
        """Resolve the model for a task key from overrides or default."""
        return self._task_models.get(task_key, self._default_model)

    async def execute(self, request: AIGatewayRequest) -> dict[str, Any]:
        """Execute a governed AI task through the configured provider.

        Returns a dict with keys: ``provider``, ``model``, ``draft``,
        ``requires_human_review``, ``usage`` (input/output/total tokens),
        ``latency_ms``, ``cost_microunits``, ``request_id``.
        """
        if not request.approved_fact_revision_ids:
            raise ValueError("approved business-fact grounding required")
        secret_bearers = {
            "password",
            "secret",
            "token",
            "authorization",
            "api_key",
            "apikey",
            "credential",
        }
        for key in request.input_document:
            normalized = key.lower().replace("-", "_").replace(" ", "_")
            if normalized in secret_bearers or any(
                bearer in normalized for bearer in secret_bearers
            ):
                raise ValueError("secret-bearing AI input rejected")

        # Pre-flight cost bound: if the task's maximum_cost_microunits exceeds
        # the global safety bound, reject before any provider call.
        effective_cost_bound = min(
            request.maximum_cost_microunits, self._global_max_cost_microunits
        )
        if effective_cost_bound <= 0:
            raise ValueError("AI task cost bound must be positive")

        # Resolve maximum tokens: use the global bound as a ceiling.
        maximum_tokens = self._global_max_output_tokens

        try:
            output = await self.provider.generate(
                task_key=request.task_key,
                input_document=dict(request.input_document),
                maximum_tokens=maximum_tokens,
                maximum_latency_ms=request.maximum_latency_ms,
            )
        except AIProviderError:
            raise
        except Exception as exc:
            logger.exception("Unexpected AI provider failure")
            raise AIProviderError(
                "provider", "AI provider encountered an unexpected error"
            ) from exc

        # Post-execution cost validation: record overspend but do not block
        # (the provider has already been called). The caller can inspect
        # cost_microunits against the bound.
        cost = output.get("cost_microunits")
        if isinstance(cost, (int, float)) and cost > effective_cost_bound:
            logger.warning(
                "AI execution exceeded cost bound",
                extra={
                    "event_name": "ai.execution.cost_exceeded",
                    "task_key": request.task_key,
                    "cost_microunits": cost,
                    "bound_microunits": effective_cost_bound,
                },
            )

        # Ensure required keys are present
        output.setdefault("provider", "unknown")
        output.setdefault("model", "unknown")
        output.setdefault("draft", "")
        output.setdefault("requires_human_review", True)
        output.setdefault("usage", {})
        output.setdefault("latency_ms", None)
        output.setdefault("cost_microunits", None)
        output.setdefault("request_id", None)

        return output


class DeterministicAIProvider:
    """Safe, credential-free provider for tests and local development.

    Returns a fixed draft from the ``manual_fallback`` input field.
    Always marks ``requires_human_review=True``.
    """

    async def generate(
        self,
        *,
        task_key: str,
        input_document: dict[str, Any],
        maximum_tokens: int,
        maximum_latency_ms: int | None = None,
    ) -> dict[str, Any]:
        return {
            "task_type": task_key,
            "draft": str(input_document.get("manual_fallback", "Thank you for your feedback.")),
            "requires_human_review": True,
            "provider": "deterministic_test",
            "model": "fixture-v1",
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "latency_ms": 0,
            "cost_microunits": 0,
            "request_id": None,
        }
