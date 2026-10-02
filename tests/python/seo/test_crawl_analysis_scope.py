"""Analysis after a crawl analyzes exactly the crawled website, whatever the run's location."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.execution import operational_extensions
from apps.api.app.execution.contracts import JobOutcome, WorkflowSubmit
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.seo.models import SEOCrawlRun, SEOWebsite
from apps.api.app.products.seo.orchestration import SEOOrchestrationService


async def _organization(session: AsyncSession) -> Organization:
    organization = Organization(
        name="Crawl scope",
        slug=f"crawl-scope-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(organization)
    await session.flush()
    return organization


async def _location(session: AsyncSession, organization_id: UUID, slug: str) -> Location:
    location = Location(
        organization_id=organization_id,
        name=slug,
        slug=slug,
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        website_url=f"https://{slug}.example.invalid",
        is_primary=False,
        version=1,
    )
    session.add(location)
    await session.flush()
    return location


async def _website(
    session: AsyncSession,
    organization_id: UUID,
    location_id: UUID | None,
    key: str,
    status: str = "active",
) -> SEOWebsite:
    website = SEOWebsite(
        organization_id=organization_id,
        location_id=location_id,
        key=key,
        name=key,
        canonical_origin=f"https://{key}.example.invalid",
        status=status,
        ownership_status="unverified",
        version=1,
    )
    session.add(website)
    await session.flush()
    return website


async def _run(
    session: AsyncSession,
    organization_id: UUID,
    location_id: UUID | None,
    *,
    trigger: str = "api",
    input_document: dict[str, object] | None = None,
) -> WorkflowRun:
    execution = ExecutionService()
    version = await execution._resolve_workflow_version(session, "seo.crawl_or_analysis")
    run, _ = await execution.submit(
        session,
        organization_id,
        WorkflowSubmit(
            workflow_version_id=version.id,
            location_id=location_id,
            idempotency_key=f"scope-{uuid4().hex}",
            input_document=input_document or {},
        ),
        "crawl-scope",
        trigger_type=trigger,
        enqueue_job=False,
    )
    return run


def _stub_crawl(monkeypatch: pytest.MonkeyPatch) -> list[UUID]:
    """The network crawl is out of scope: mark the crawl run as a successful 3-page crawl."""
    crawled: list[UUID] = []

    async def crawl(session: AsyncSession, **kwargs: object) -> JobOutcome:
        document = kwargs["input_document"]
        assert isinstance(document, dict)
        crawl_run = await session.get(SEOCrawlRun, UUID(str(document["crawl_run_id"])))
        assert crawl_run is not None
        crawl_run.status = "success"
        crawl_run.safe_result = {"pages_crawled": 3}
        await session.flush()
        crawled.append(crawl_run.website_id)
        return JobOutcome(result="succeeded", result_reference=f"crawl_run:{crawl_run.id}")

    monkeypatch.setattr(operational_extensions, "_handle_seo_crawl", crawl)
    return crawled


@pytest.mark.integration
@pytest.mark.anyio
async def test_analysis_after_crawl_uses_the_crawled_location_website_for_a_run_without_location(
    seo_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    crawled = _stub_crawl(monkeypatch)
    async with seo_session_factory.begin() as session:
        organization = await _organization(session)
        location = await _location(session, organization.id, "downtown")
        website = await _website(
            session, organization.id, location.id, "scoped", "pending_verification"
        )
        run = await _run(session, organization.id, None)
        crawl_run = SEOCrawlRun(
            organization_id=organization.id,
            website_id=website.id,
            workflow_run_id=run.id,
            idempotency_key=f"scope-crawl-{uuid4().hex}",
            status="queued",
            max_pages=10,
            safe_result={},
        )
        session.add(crawl_run)
        await session.flush()

        # The run has no location and the website does: standalone selection finds nothing.
        standalone = await SEOOrchestrationService().analyze(
            session, organization.id, location_id=None, correlation_id="standalone"
        )
        assert standalone["status"] == "no_active_website"

        outcome = await operational_extensions._handle_seo_crawl_and_analysis(
            session,
            organization_id=organization.id,
            location_id=None,
            input_document={"website_id": str(website.id), "crawl_run_id": str(crawl_run.id)},
            correlation_id="crawl-scope",
            workflow_run_id=run.id,
        )

        assert outcome.result == "succeeded", outcome.safe_error
        assert crawled == [website.id]
        assert outcome.result_reference is not None
        assert f"seo-analysis:{website.id}:" in outcome.result_reference


@pytest.mark.integration
@pytest.mark.anyio
async def test_analysis_with_website_id_stays_tenant_and_location_scoped(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization = await _organization(session)
        other_organization = await _organization(session)
        here = await _location(session, organization.id, "here")
        there = await _location(session, organization.id, "there")
        website = await _website(session, organization.id, here.id, "here-site")
        paused = await _website(session, organization.id, None, "paused-site", "paused")
        service = SEOOrchestrationService()

        async def analyze(org: UUID, location: UUID | None, website_id: UUID) -> object:
            result = await service.analyze(
                session,
                org,
                location_id=location,
                correlation_id="scope",
                website_id=website_id,
            )
            return result["status"]

        assert await analyze(other_organization.id, None, website.id) == "no_active_website"
        assert await analyze(organization.id, there.id, website.id) == "no_active_website"
        assert await analyze(organization.id, None, paused.id) == "no_active_website"
        assert await analyze(organization.id, here.id, website.id) != "no_active_website"
        assert await analyze(organization.id, None, website.id) != "no_active_website"


@pytest.mark.integration
@pytest.mark.anyio
async def test_scheduled_run_crawls_and_analyzes_every_active_website_once(
    seo_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    crawled = _stub_crawl(monkeypatch)
    async with seo_session_factory.begin() as session:
        organization = await _organization(session)
        location = await _location(session, organization.id, "uptown")
        first = await _website(session, organization.id, location.id, "first")
        second = await _website(session, organization.id, None, "second")
        await _website(session, organization.id, None, "paused", "paused")
        run = await _run(
            session,
            organization.id,
            None,
            trigger="schedule",
            input_document={"schedule_id": str(uuid4()), "scheduled_for": "2026-10-05T12:00:00Z"},
        )

        async def handle() -> JobOutcome:
            return await operational_extensions._handle_seo_crawl_and_analysis(
                session,
                organization_id=organization.id,
                location_id=None,
                input_document=run.input_document,
                correlation_id="scheduled-crawl",
                workflow_run_id=run.id,
            )

        outcome = await handle()
        assert outcome.result == "succeeded", outcome.safe_error
        assert sorted(crawled) == sorted([first.id, second.id])

        # A retry of the same workflow run reuses the crawl runs rather than starting new ones.
        again = await handle()
        assert again.result == "succeeded", again.safe_error
        from sqlalchemy import func, select

        count = await session.scalar(
            select(func.count())
            .select_from(SEOCrawlRun)
            .where(SEOCrawlRun.workflow_run_id == run.id)
        )
        assert count == 2


@pytest.mark.integration
@pytest.mark.anyio
async def test_scheduled_run_without_an_active_website_fails_with_a_typed_code(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization = await _organization(session)
        run = await _run(
            session,
            organization.id,
            None,
            trigger="schedule",
            input_document={"schedule_id": str(uuid4())},
        )
        outcome = await operational_extensions._handle_seo_crawl_and_analysis(
            session,
            organization_id=organization.id,
            location_id=None,
            input_document=run.input_document,
            correlation_id="scheduled-none",
            workflow_run_id=run.id,
        )
        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "SEO_ACTIVE_WEBSITE_MISSING"
