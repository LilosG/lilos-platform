"""Governed SEO evidence references that back a Content opportunity."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.content.models import ContentOpportunity
from apps.api.app.products.seo.decision import SEOEvidenceInvalidError, resolve_decision
from apps.api.app.products.seo.models import SEOOpportunity

REFERENCE_LIMIT = 500
# Reference kinds that are evidence (as opposed to bookkeeping such as content-item:).
EVIDENCE_PREFIXES = (
    "seo-opportunity:",
    "seo-search-observation:",
    "seo-crawl-observation:",
    "metric-observation:",
)


def reference_strings(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value)[:REFERENCE_LIMIT] for value in values if isinstance(value, str) and value]


async def seo_opportunity_evidence_references(
    session: AsyncSession, organization_id: UUID, opportunity_id: UUID
) -> list[str]:
    """The SEO opportunity reference plus the observations of its governed decision."""
    opportunity = await session.scalar(
        select(SEOOpportunity).where(
            SEOOpportunity.organization_id == organization_id,
            SEOOpportunity.id == opportunity_id,
        )
    )
    if opportunity is None:
        return []
    source_reference = f"seo-opportunity:{opportunity.id}"
    try:
        decision = await resolve_decision(session, organization_id, opportunity, [source_reference])
    except SEOEvidenceInvalidError:
        # An archived or stale opportunity has no governed decision to cite.
        return [source_reference]
    return [source_reference, *reference_strings(decision.get("evidence_references"))]


async def content_opportunity_evidence_references(
    session: AsyncSession, organization_id: UUID, content_opportunity_id: UUID | None
) -> list[str]:
    """Evidence references a brief for this Content opportunity may cite."""
    if content_opportunity_id is None:
        return []
    opportunity = await session.scalar(
        select(ContentOpportunity).where(
            ContentOpportunity.organization_id == organization_id,
            ContentOpportunity.id == content_opportunity_id,
        )
    )
    if opportunity is None:
        return []
    prefix, _, raw = (opportunity.source_reference or "").partition(":")
    if prefix != "seo-opportunity":
        return []
    try:
        seo_id = UUID(raw)
    except ValueError:
        return []
    references = await seo_opportunity_evidence_references(session, organization_id, seo_id)
    return [ref for ref in references if ref.startswith(EVIDENCE_PREFIXES)]
