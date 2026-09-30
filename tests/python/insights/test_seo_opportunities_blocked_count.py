"""InsightsService.summary separates blocked SEO opportunities from actionable ones.

Overview previously counted every opportunity with an actionable status
(identified/recommended/approved) as "ready to prioritize", including ones
whose evidence never resolved to a page. `opportunities_blocked` isolates
the attribution_state == 'unresolved' subset so the frontend can label them
separately instead of folding them into the actionable count.
"""

import hashlib
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.insights.aggregation_service import InsightsService
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.seo.models import SEOOpportunity, SEOWebsite


async def _make_org(session: AsyncSession) -> Organization:
    org = Organization(
        name="Blocked Count Test",
        slug=f"blocked-count-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()
    return org


def _opportunity(
    org_id: UUID,
    website_id: UUID,
    *,
    opportunity_type: str,
    attribution_state: str,
    status: str = "identified",
) -> SEOOpportunity:
    target = f"{opportunity_type}-{uuid4().hex}"
    return SEOOpportunity(
        organization_id=org_id,
        location_id=None,
        website_id=website_id,
        page_id=None,
        opportunity_type=opportunity_type,
        deduplication_key=hashlib.sha256(target.encode()).hexdigest(),
        active_marker="active",
        evidence={},
        source_versions=["gsc.v1"],
        score_version=2,
        priority_score=50,
        score_explanation={},
        status=status,
        version=1,
        attribution_state=attribution_state,
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_summary_counts_unresolved_opportunities_as_blocked(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await _make_org(session)
        website = SEOWebsite(
            organization_id=org.id,
            location_id=None,
            key="blocked-count",
            name="Blocked count site",
            canonical_origin="https://blocked-count.example.invalid",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add(website)
        await session.flush()
        session.add_all(
            [
                _opportunity(
                    org.id,
                    website.id,
                    opportunity_type="gsc_query_demand",
                    attribution_state="query_only",
                ),
                _opportunity(
                    org.id,
                    website.id,
                    opportunity_type="gsc_striking_distance",
                    attribution_state="unresolved",
                ),
                _opportunity(
                    org.id,
                    website.id,
                    opportunity_type="gsc_low_ctr",
                    attribution_state="unresolved",
                ),
                _opportunity(
                    org.id,
                    website.id,
                    opportunity_type="gsc_low_ctr",
                    attribution_state="unresolved",
                    status="rejected",
                ),
            ]
        )
        org_id = org.id

    async with insights_session_factory() as session:
        summary = await InsightsService().summary(session, org_id)

    seo_summary = cast(dict[str, object], summary["seo"])
    assert seo_summary["opportunities_blocked"] == 2
    assert sum(cast(dict[str, int], seo_summary["opportunities"]).values()) == 4
