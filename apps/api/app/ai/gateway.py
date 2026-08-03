"""One provider-neutral, task-registered AI execution boundary."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class AIProvider(Protocol):
    async def generate(
        self, *, task_key: str, input_document: dict[str, Any], maximum_tokens: int
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
    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def execute(self, request: AIGatewayRequest) -> dict[str, Any]:
        if not request.approved_fact_revision_ids:
            raise ValueError("approved business-fact grounding required")
        if any(
            key.lower() in {"password", "secret", "token", "authorization"}
            for key in request.input_document
        ):
            raise ValueError("secret-bearing AI input rejected")
        return await self.provider.generate(
            task_key=request.task_key,
            input_document=dict(request.input_document),
            maximum_tokens=2000,
        )


class DeterministicAIProvider:
    async def generate(
        self, *, task_key: str, input_document: dict[str, Any], maximum_tokens: int
    ) -> dict[str, Any]:
        return {
            "task_type": task_key,
            "draft": str(input_document.get("manual_fallback", "Thank you for your feedback.")),
            "requires_human_review": True,
            "provider": "deterministic_test",
            "model": "fixture-v1",
        }
