"""References a bound agent run has already been given, recorded as observed at start.

A bound run is handed a specific opportunity, content item or SEO decision. Hermes
should not have to re-read what LILOs already bound it to before it may cite that
evidence. Everything here is derived by LILOs from persisted, organization-scoped
records; model prose never contributes a reference. Anything not derived here still
has to be observed through a tool call.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.growth.models import GrowthAction
from apps.api.app.products.content.evidence import (
    reference_strings,
)
from apps.api.app.products.content.evidence import (
    seo_opportunity_evidence_references as seo_evidence,
)
from apps.api.app.products.content.models import ContentBrief, ContentItem, ContentOpportunity
from apps.api.app.products.seo.models import SEORecommendationRevision

MAX_BOUND_REFERENCES = 200


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


async def _revision_references(
    session: AsyncSession, organization_id: UUID, revision_id: UUID
) -> list[str]:
    revision = await session.scalar(
        select(SEORecommendationRevision).where(
            SEORecommendationRevision.organization_id == organization_id,
            SEORecommendationRevision.id == revision_id,
        )
    )
    if revision is None:
        return []
    references = [f"seo-recommendation:{revision.id}"]
    references += reference_strings(revision.evidence_references)
    references += await seo_evidence(session, organization_id, revision.opportunity_id)
    return references


async def _content_opportunity_references(
    session: AsyncSession, organization_id: UUID, opportunity_id: UUID
) -> list[str]:
    opportunity = await session.scalar(
        select(ContentOpportunity).where(
            ContentOpportunity.organization_id == organization_id,
            ContentOpportunity.id == opportunity_id,
        )
    )
    if opportunity is None:
        return []
    references = [f"content-opportunity:{opportunity.id}"]
    prefix, _, raw = (opportunity.source_reference or "").partition(":")
    source_id = _uuid(raw)
    if prefix == "seo-opportunity" and source_id is not None:
        references += await seo_evidence(session, organization_id, source_id)
    items = list(
        await session.scalars(
            select(ContentItem).where(
                ContentItem.organization_id == organization_id,
                ContentItem.opportunity_id == opportunity.id,
            )
        )
    )
    for item in items:
        references.append(f"content-item:{item.id}")
        brief = await session.scalar(
            select(ContentBrief)
            .where(
                ContentBrief.organization_id == organization_id,
                ContentBrief.content_item_id == item.id,
                ContentBrief.status == "ready",
            )
            .order_by(ContentBrief.revision_number.desc())
            .limit(1)
        )
        if brief is not None:
            references.append(f"content-brief:{brief.id}")
            references += reference_strings(brief.source_evidence_references)
    return references


async def _growth_action_references(
    session: AsyncSession, organization_id: UUID, action_id: UUID
) -> list[str]:
    action = await session.scalar(
        select(GrowthAction).where(
            GrowthAction.organization_id == organization_id, GrowthAction.id == action_id
        )
    )
    if action is None:
        return []
    references = [f"growth-action:{action.id}"]
    for reference in reference_strings(action.evidence_references):
        references.append(reference)
        prefix, _, raw = reference.partition(":")
        referenced_id = _uuid(raw)
        if referenced_id is None:
            continue
        if prefix == "seo-recommendation":
            references += await _revision_references(session, organization_id, referenced_id)
        elif prefix == "seo-opportunity":
            references += await seo_evidence(session, organization_id, referenced_id)
    content_opportunity = await session.scalar(
        select(ContentOpportunity).where(
            ContentOpportunity.organization_id == organization_id,
            ContentOpportunity.source_reference == f"growth-action:{action.id}",
        )
    )
    if content_opportunity is not None:
        references += await _content_opportunity_references(
            session, organization_id, content_opportunity.id
        )
    return references


async def bound_source_references(
    session: AsyncSession, organization_id: UUID, input_document: dict[str, Any]
) -> list[str]:
    """Return the references a run bound by ``input_document`` may cite without re-reading."""
    references: list[str] = []
    bound_opportunity = input_document.get("seo_opportunity_id")
    if isinstance(bound_opportunity, str) and (opportunity_id := _uuid(bound_opportunity)):
        references += await seo_evidence(session, organization_id, opportunity_id)
    context = input_document.get("context_reference")
    if isinstance(context, str):
        prefix, _, raw = context.partition(":")
        bound_id = _uuid(raw)
        if bound_id is not None:
            if prefix == "seo-opportunity":
                references += await seo_evidence(session, organization_id, bound_id)
            elif prefix == "seo-recommendation":
                references += await _revision_references(session, organization_id, bound_id)
            elif prefix == "content-opportunity":
                references += await _content_opportunity_references(
                    session, organization_id, bound_id
                )
            elif prefix == "growth-action":
                references += await _growth_action_references(session, organization_id, bound_id)
    return list(dict.fromkeys(references))[:MAX_BOUND_REFERENCES]
