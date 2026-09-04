"""Convert approved SEO recommendations into governed downstream work.

SEO evidence is analysis until an operator explicitly chooses an action.  This
service creates a real Content opportunity/item/brief and queues the existing
grounded AI draft workflow while preserving the SEO recommendation and evidence
as provenance.  Publication remains behind the Content editorial/client approval
and GitHub verification workflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.execution.service import ExecutionService
from apps.api.app.products.content.contracts import (
    BriefCreate,
    ItemCreate,
    OpportunityCreate,
    OpportunityDecision,
)
from apps.api.app.products.content.service import ContentService
from apps.api.app.products.seo.models import (
    SEOImplementationTask,
    SEOOpportunity,
    SEOPage,
    SEORecommendationRevision,
)

SEOContentAction = Literal["content_article", "content_page", "content_page_optimization"]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return (slug[:200].rstrip("-") or "seo-opportunity")


@dataclass(slots=True)
class SEOActionService:
    content: ContentService = field(default_factory=ContentService)
    execution: ExecutionService = field(default_factory=ExecutionService)

    async def create_content_action(
        self,
        session: AsyncSession,
        organization_id: UUID,
        recommendation_revision_id: UUID,
        *,
        action_type: SEOContentAction,
        actor_id: UUID,
        correlation_id: str,
        title: str | None = None,
        slug: str | None = None,
    ) -> tuple[SEOImplementationTask, UUID, UUID]:
        """Queue a grounded content draft from one approved SEO recommendation."""
        recommendation = await session.scalar(
            select(SEORecommendationRevision).where(
                SEORecommendationRevision.organization_id == organization_id,
                SEORecommendationRevision.id == recommendation_revision_id,
                SEORecommendationRevision.status == "approved",
            )
        )
        if recommendation is None:
            raise LookupError("approved SEO recommendation not found")

        opportunity = await session.scalar(
            select(SEOOpportunity).where(
                SEOOpportunity.organization_id == organization_id,
                SEOOpportunity.id == recommendation.opportunity_id,
                SEOOpportunity.active_marker == "active",
            )
        )
        if opportunity is None:
            raise LookupError("active SEO opportunity not found")

        existing = await session.scalar(
            select(SEOImplementationTask)
            .where(
                SEOImplementationTask.organization_id == organization_id,
                SEOImplementationTask.recommendation_revision_id == recommendation.id,
                SEOImplementationTask.target_type == action_type,
                SEOImplementationTask.status.notin_(("failed", "cancelled")),
            )
            .order_by(SEOImplementationTask.created_at.desc())
            .limit(1)
        )
        if existing is not None:
            reference = existing.target_reference.removeprefix("content-item:")
            try:
                item_id = UUID(reference)
            except ValueError as exc:
                raise RuntimeError("existing SEO action has invalid content reference") from exc
            return existing, item_id, existing.workflow_run_id

        page = (
            await session.scalar(
                select(SEOPage).where(
                    SEOPage.organization_id == organization_id,
                    SEOPage.id == opportunity.page_id,
                )
            )
            if opportunity.page_id is not None
            else None
        )
        target_reference = page.normalized_url if page is not None else f"seo-opportunity:{opportunity.id}"

        fact_rows = list(
            await session.scalars(
                select(BusinessFactRevision)
                .where(
                    BusinessFactRevision.organization_id == organization_id,
                    BusinessFactRevision.status.in_(("approved", "active")),
                    or_(
                        BusinessFactRevision.location_id.is_(None),
                        BusinessFactRevision.location_id == opportunity.location_id,
                    ),
                )
                .order_by(BusinessFactRevision.approved_at.desc().nullslast())
                .limit(100)
            )
        )
        if not fact_rows:
            raise ValueError("approved business facts are required before content execution")
        fact_ids = [row.id for row in fact_rows]

        action_title = (title or recommendation.proposed_action).strip()[:300]
        if not action_title:
            raise ValueError("content action title is required")
        action_slug = _slugify(slug or action_title)
        evidence_references = [str(value) for value in recommendation.evidence_references]
        evidence_references.extend(
            [f"seo-opportunity:{opportunity.id}", f"seo-recommendation:{recommendation.id}"]
        )
        evidence_references = list(dict.fromkeys(evidence_references))[:100]

        content_opportunity = await self.content.create_opportunity(
            session,
            organization_id,
            OpportunityCreate(
                location_id=opportunity.location_id,
                product_key="seo",
                target_reference=target_reference,
                opportunity_type=action_type,
                source_type="seo_recommendation",
                source_reference=f"seo-recommendation:{recommendation.id}",
                evidence_document={
                    "seo_opportunity_id": str(opportunity.id),
                    "seo_recommendation_revision_id": str(recommendation.id),
                    "opportunity_type": opportunity.opportunity_type,
                    "priority_score": opportunity.priority_score,
                    "evidence": opportunity.evidence,
                    "score_explanation": opportunity.score_explanation,
                    "proposed_action": recommendation.proposed_action,
                    "expected_result_hypothesis": recommendation.expected_result_hypothesis,
                    "target_reference": target_reference,
                },
                priority_score=opportunity.priority_score,
            ),
            correlation_id=correlation_id,
        )
        await self.content.decide_opportunity(
            session,
            organization_id,
            content_opportunity.id,
            OpportunityDecision(accept=True),
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

        item = await self.content.create_item(
            session,
            organization_id,
            ItemCreate(
                opportunity_id=content_opportunity.id,
                location_id=opportunity.location_id,
                content_type=action_type,
                title=action_title,
                slug=action_slug,
            ),
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

        brief = await self.content.create_brief(
            session,
            organization_id,
            item.id,
            BriefCreate(
                audience="People whose search intent matches the approved SEO opportunity.",
                intent=recommendation.proposed_action[:500],
                target_reference=target_reference,
                approved_fact_revision_ids=fact_ids,
                required_claims=[],
                prohibited_claims=[
                    "Invented prices, discounts, guarantees, credentials, awards, availability, or service areas.",
                    "Invented or renamed products, services, menu items, locations, people, or offers.",
                    "Keyword stuffing, doorway-page copy, fake FAQs, or unsupported structured-data claims.",
                ],
                required_local_references=[],
                source_evidence_references=evidence_references,
                validation_requirements={
                    "platform": "astro",
                    "best_practices_version": 1,
                    "people_first": True,
                    "single_clear_h1": True,
                    "canonical_entity_names_exact": True,
                    "search_intent_alignment": True,
                    "avoid_cannibalization": True,
                    "internal_links_useful": True,
                    "structured_data_visible_content_only": True,
                    "no_doorway_pages": True,
                    "no_keyword_stuffing": True,
                    "google_and_ai_search_discoverability": True,
                    "requires_human_review": True,
                },
            ),
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

        workflow = await self.execution.start_named(
            session,
            organization_id,
            "content.draft_revision",
            f"seo-action-draft:{recommendation.id}:{action_type}",
            location_id=opportunity.location_id,
            input_document={
                "item_id": str(item.id),
                "brief_id": str(brief.id),
                "idempotency_key": f"seo-draft-{recommendation.id}-{action_type}",
                "user_id": str(actor_id),
                "seo_opportunity_id": str(opportunity.id),
                "seo_recommendation_revision_id": str(recommendation.id),
            },
            correlation_id=correlation_id,
            actor_id=actor_id,
            enqueue_job=True,
        )
        task = SEOImplementationTask(
            organization_id=organization_id,
            recommendation_revision_id=recommendation.id,
            workflow_run_id=workflow.id,
            target_type=action_type,
            target_reference=f"content-item:{item.id}",
            status="pending",
            verification_evidence={
                "content_item_id": str(item.id),
                "content_brief_id": str(brief.id),
                "source_target_reference": target_reference,
            },
        )
        session.add(task)
        await session.flush()
        return task, item.id, workflow.id
