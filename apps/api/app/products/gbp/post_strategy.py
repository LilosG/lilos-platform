"""Content strategy policy for diversified Google Business Profile post generation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.ai.gateway import AIGateway, AIGatewayRequest
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.products.gbp.post_generation import TASK_KEY, GBPPostGenerationService
from apps.api.app.products.reviews.models import Review, ReviewRevision

GOOGLE_REVIEW_SOURCE = "google_review"
SERVICE_KNOWLEDGE_SOURCE = "service_knowledge"
REVIEW_ARCHETYPE = "review_social_proof"
TOPIC_ARCHETYPE = "business_topic_spotlight"


class GBPPostDiversityGateway(AIGateway):
    """Decorate the governed AI gateway with GBP-specific editorial strategy."""

    def __init__(self, delegate: AIGateway) -> None:
        self._delegate = delegate

    async def execute(self, request: AIGatewayRequest) -> dict[str, Any]:
        if request.task_key != TASK_KEY:
            return await self._delegate.execute(request)

        input_document = dict(request.input_document)
        source_type = str(input_document.get("source_type") or "").strip()
        archetype = (
            REVIEW_ARCHETYPE if source_type == GOOGLE_REVIEW_SOURCE else TOPIC_ARCHETYPE
        )
        base_instructions = str(input_document.get("instructions") or "").strip()
        strategy_instructions = self.strategy_instructions(source_type)
        input_document["post_archetype"] = archetype
        input_document["instructions"] = " ".join(
            part for part in (base_instructions, strategy_instructions) if part
        )
        return await self._delegate.execute(replace(request, input_document=input_document))

    @staticmethod
    def strategy_instructions(source_type: str) -> str:
        """Return editorial constraints that preserve variety without inventing claims."""
        if source_type == GOOGLE_REVIEW_SOURCE:
            return (
                "Treat the customer review as supporting evidence, not as a mandatory narrative "
                "frame. Lead with the relevant dish, service, occasion, atmosphere, or customer "
                "need that the evidence supports. Do not begin with 'one guest', 'a guest', "
                "'one customer', 'a customer', 'one reviewer', 'a reviewer', 'a recent review', "
                "or equivalent review-attribution phrasing. If social proof is useful, weave it "
                "in after the opening and vary its placement and wording. Compare against the "
                "recent posts provided and avoid repeating their opening construction, angle, "
                "CTA language, or story structure."
            )
        return (
            "Use the selected business topic as the primary angle. Vary the opening, structure, "
            "and CTA language against the recent posts provided. Prefer a concrete customer need, "
            "occasion, menu/service feature, local relevance, or experience angle supported by "
            "the supplied business facts and website knowledge. Do not manufacture testimonial "
            "language or imply that a guest said something."
        )


class StrategicGBPPostGenerationService(GBPPostGenerationService):
    """Apply source-mix and editorial-diversity policy around the base generator.

    Explicitly selected reviews remain authoritative. Automated runs instead balance
    review-derived social proof with business/topic posts from approved facts, the GBP
    profile, and website knowledge. This prevents a healthy review backlog from turning
    the entire GBP feed into repeated testimonial narratives.
    """

    def __init__(self) -> None:
        super().__init__()
        self.ai_gateway = GBPPostDiversityGateway(self.ai_gateway)

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        revision, execution, asset = await super().generate(*args, **kwargs)
        output_document = dict(execution.output_document or {})
        source_type = str(output_document.get("source_type") or "").strip()
        output_document["post_archetype"] = (
            REVIEW_ARCHETYPE if source_type == GOOGLE_REVIEW_SOURCE else TOPIC_ARCHETYPE
        )
        execution.output_document = output_document
        return revision, execution, asset

    async def _resolve_optional_source_review(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
    ) -> tuple[Review, ReviewRevision] | None:
        candidate = await super()._resolve_optional_source_review(
            session, organization_id, location_id
        )
        if candidate is None:
            return None

        recent_source_types = await self._recent_source_types(
            session, organization_id, location_id
        )
        selected_source_type = self.select_automated_source_type(
            recent_source_types,
            review_available=True,
        )
        return candidate if selected_source_type == GOOGLE_REVIEW_SOURCE else None

    @staticmethod
    async def _recent_source_types(
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        *,
        window: int = 8,
    ) -> list[str]:
        rows = list(
            await session.scalars(
                select(AIExecution.output_document)
                .join(AITaskDefinition, AITaskDefinition.id == AIExecution.task_definition_id)
                .where(
                    AIExecution.organization_id == organization_id,
                    AIExecution.location_id == location_id,
                    AIExecution.status == "completed",
                    AITaskDefinition.key == TASK_KEY,
                )
                .order_by(AIExecution.created_at.desc())
                .limit(window)
            )
        )
        source_types: list[str] = []
        for document in rows:
            inferred = StrategicGBPPostGenerationService.infer_source_type(document or {})
            if inferred is not None:
                source_types.append(inferred)
        return source_types

    @staticmethod
    def infer_source_type(document: dict[str, Any]) -> str | None:
        """Read current and legacy execution provenance into one source vocabulary."""
        explicit = str(document.get("source_type") or "").strip()
        if explicit in {GOOGLE_REVIEW_SOURCE, SERVICE_KNOWLEDGE_SOURCE}:
            return explicit
        if str(document.get("source_review_id") or "").strip():
            return GOOGLE_REVIEW_SOURCE
        if str(document.get("source_service_topic") or "").strip():
            return SERVICE_KNOWLEDGE_SOURCE
        return None

    @staticmethod
    def select_automated_source_type(
        recent_source_types: list[str],
        *,
        review_available: bool,
    ) -> str:
        """Choose a balanced source deterministically for an automated post.

        A review is never required simply because one is available. New histories begin
        with business knowledge, consecutive review-derived posts are prohibited, and the
        recent window is kept at or below a 50% review share whenever business knowledge
        is available. Explicit review requests bypass this method in the base generator.
        """
        if not review_available:
            return SERVICE_KNOWLEDGE_SOURCE

        normalized = [
            source_type
            for source_type in recent_source_types[:8]
            if source_type in {GOOGLE_REVIEW_SOURCE, SERVICE_KNOWLEDGE_SOURCE}
        ]
        if not normalized:
            return SERVICE_KNOWLEDGE_SOURCE
        if normalized[0] == GOOGLE_REVIEW_SOURCE:
            return SERVICE_KNOWLEDGE_SOURCE

        review_count = normalized.count(GOOGLE_REVIEW_SOURCE)
        service_count = normalized.count(SERVICE_KNOWLEDGE_SOURCE)
        if review_count >= service_count:
            return SERVICE_KNOWLEDGE_SOURCE
        return GOOGLE_REVIEW_SOURCE
