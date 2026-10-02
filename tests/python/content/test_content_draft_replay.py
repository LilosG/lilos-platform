"""Replay of the production `content.draft_revision` shape that failed 2026-09-29 to 2026-10-01.

Coco Maya's ready `existing_page` brief for /brunch failed eight times with
CONTENT_GENERATION_EXCEPTION: its SEO opportunity was `query_only` (no attributed page) and the
brief named a crawled page, which `ContentSEOTargetUnresolvedError` rejected (worker log,
2026-10-01 17:00). Replayed here through the real handler and schema, for that shape and for
an opportunity with an attributed page.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.execution.handlers import _handle_content_draft_revision
from apps.api.app.execution.service import ExecutionService
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentOpportunity,
    ContentRevision,
)
from apps.api.app.products.seo.models import SEOOpportunity, SEOPage, SEOWebsite

ORIGIN = "https://inlovewiththecoco.com"


async def _seed(
    session: AsyncSession, *, target_reference: str, attributed: bool = True
) -> tuple[UUID, UUID, UUID, UUID]:
    org = Organization(
        name="Draft replay",
        slug=f"draft-replay-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    user = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
    session.add_all([org, user])
    await session.flush()
    location = Location(
        organization_id=org.id,
        name="Little Italy",
        slug="little-italy",
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        website_url=ORIGIN,
        is_primary=True,
        version=1,
    )
    session.add(location)
    await session.flush()
    # The production brief carried five active facts: some organization-wide, some scoped to
    # the item's location.
    fact_ids: list[str] = []
    for key, value, scope in (
        ("business.name", "Coco Maya", None),
        ("business.website", ORIGIN, None),
        ("brand.approved_claims", "American restaurant and cocktail bar", None),
        ("business.address", "1660 India St, San Diego, CA 92101", location.id),
        ("business.hours", "Sun 9am-9pm", location.id),
    ):
        fact = BusinessFactRevision(
            organization_id=org.id,
            location_id=scope,
            fact_identity=uuid4(),
            fact_key=key,
            value_type="string",
            value=value,
            source="client_input",
            authority="client_approved",
            status="active",
            revision=1,
            proposed_by=user.id,
            approved_by=user.id,
            approved_at=datetime.now(UTC),
            change_reason="replay",
        )
        session.add(fact)
        await session.flush()
        fact_ids.append(str(fact.id))
    website = SEOWebsite(
        organization_id=org.id,
        location_id=None,
        key="primary",
        name="Primary",
        canonical_origin=ORIGIN,
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add(website)
    await session.flush()
    page = SEOPage(
        organization_id=org.id,
        website_id=website.id,
        normalized_url=f"{ORIGIN}/brunch",
        observed_url=f"{ORIGIN}/brunch",
        normalization_reasons=[],
        http_status=200,
        title="Brunch | Coco Maya",
        meta_description="Brunch at Coco Maya.",
        robots_directives=[],
        internal_links=[],
        external_links=[],
        word_count=300,
        indexability="indexable",
        technical_issues=[],
        quality_status="valid",
    )
    session.add(page)
    if not attributed:
        # The production site has the page twice, with and without a trailing slash.
        session.add(
            SEOPage(
                organization_id=org.id,
                website_id=website.id,
                normalized_url=f"{ORIGIN}/brunch/",
                observed_url=f"{ORIGIN}/brunch/",
                normalization_reasons=[],
                http_status=200,
                title="Brunch | Coco Maya",
                meta_description="Brunch at Coco Maya.",
                robots_directives=[],
                internal_links=[],
                external_links=[],
                word_count=300,
                indexability="indexable",
                technical_issues=[],
                quality_status="valid",
            )
        )
    await session.flush()
    opportunity = SEOOpportunity(
        organization_id=org.id,
        location_id=location.id,
        website_id=website.id,
        page_id=page.id if attributed else None,
        opportunity_type="gsc_low_ctr",
        deduplication_key=hashlib.sha256(uuid4().bytes).hexdigest(),
        active_marker="active",
        evidence={"source": "google_search_console", "query": "brunch spots san diego"},
        source_versions=["gsc.v1"],
        score_version=2,
        priority_score=70,
        score_explanation={"score_policy_version": "opportunity_score.v2"},
        status="accepted",
        attribution_state="attributed" if attributed else "query_only",
        version=1,
    )
    session.add(opportunity)
    await session.flush()
    source = f"seo-opportunity:{opportunity.id}"
    content_opportunity = ContentOpportunity(
        organization_id=org.id,
        location_id=location.id,
        product_key="seo",
        target_reference=f"{ORIGIN}/brunch",
        opportunity_type="seo",
        source_type="seo_analysis",
        source_reference=source,
        evidence_document={},
        evidence_hash=uuid4().hex + uuid4().hex,
        priority_score=70,
        status="accepted",
    )
    session.add(content_opportunity)
    await session.flush()
    item = ContentItem(
        organization_id=org.id,
        location_id=location.id,
        opportunity_id=content_opportunity.id,
        content_type="page",
        title="Brunch spots San Diego",
        slug="brunch-spots-san-diego",
        status="brief_ready",
        version=1,
    )
    session.add(item)
    await session.flush()
    brief = ContentBrief(
        organization_id=org.id,
        content_item_id=item.id,
        revision_number=1,
        audience="San Diego-area searchers typing the local list-style query.",
        intent="Optimize the existing canonical /brunch page title tag and meta description.",
        target_kind="existing_page",
        target_reference=target_reference,
        approved_fact_revision_ids=fact_ids,
        required_claims=["Brunch is served daily."],
        prohibited_claims=[],
        required_local_references=["Little Italy"],
        source_evidence_references=[source],
        validation_requirements={},
        status="ready",
    )
    session.add(brief)
    await session.flush()
    run = await ExecutionService().start_named(
        session,
        org.id,
        "content.draft_revision",
        f"draft-replay-{uuid4().hex}",
        input_document={},
        correlation_id="draft-replay",
        enqueue_job=False,
    )
    return org.id, item.id, brief.id, run.id


@pytest.mark.integration
@pytest.mark.anyio
@pytest.mark.parametrize(
    ("target", "attributed"),
    [
        (f"{ORIGIN}/brunch", True),
        ("/brunch", True),
        # The production shape: a query-only opportunity whose brief names a crawled page.
        (f"{ORIGIN}/brunch", False),
    ],
)
async def test_ready_existing_page_brief_drafts_a_revision(
    content_session_factory: async_sessionmaker[AsyncSession], target: str, attributed: bool
) -> None:
    async with content_session_factory.begin() as session:
        org_id, item_id, brief_id, run_id = await _seed(
            session, target_reference=target, attributed=attributed
        )

    async with content_session_factory() as session:
        outcome = await _handle_content_draft_revision(
            session,
            organization_id=org_id,
            location_id=None,
            input_document={
                "item_id": str(item_id),
                "brief_id": str(brief_id),
                "idempotency_key": f"draft-{uuid4().hex}",
                "user_id": None,
            },
            correlation_id="draft-replay",
            workflow_run_id=run_id,
        )
        await session.commit()

    assert outcome.result == "succeeded", outcome.safe_error
    async with content_session_factory() as session:
        revision = await session.scalar(
            select(ContentRevision).where(ContentRevision.content_item_id == item_id)
        )
        item = await session.get(ContentItem, item_id)
        assert revision is not None and item is not None
        assert revision.status == "awaiting_editorial"
        assert item.status == "reviewing"
