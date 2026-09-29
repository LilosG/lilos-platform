"""Re-evaluation admin command re-runs GSC sync, crawl, and analysis."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.seo.models import SEOCrawlRun, SEOSearchProperty, SEOWebsite
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from scripts.reevaluate_active_websites import reevaluate_active_websites


class FakeSearchConsoleService(SearchConsoleService):
    def __init__(self) -> None:
        super().__init__()
        self.synced_property_ids: list[str] = []

    async def sync_observations(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        search_property_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        days: int = 28,
    ) -> dict[str, object]:
        del session, settings, organization_id, actor_id, correlation_id, days
        self.synced_property_ids.append(str(search_property_id))
        return {"synced": True}


async def _make_organization(session: AsyncSession) -> Organization:
    organization = Organization(
        name="Reevaluate target",
        slug=f"reevaluate-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(organization)
    await session.flush()
    return organization


@pytest.mark.integration
@pytest.mark.anyio
async def test_reevaluate_syncs_mapped_property_and_queues_crawl_for_every_active_website(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization = await _make_organization(session)
        provider = Provider(
            key=f"gsc-reevaluate-{uuid4().hex[:8]}",
            name="Google Search Console",
            status="active",
            capabilities=["search_console.read"],
            manifest_version=1,
        )
        session.add(provider)
        await session.flush()
        connection = IntegrationConnection(
            organization_id=organization.id,
            provider_id=provider.id,
            external_account_reference="reevaluate-gsc",
            status="connected",
            version=1,
        )
        mapped_website = SEOWebsite(
            organization_id=organization.id,
            location_id=None,
            key="mapped",
            name="Mapped site",
            canonical_origin="https://mapped.example.invalid",
            status="active",
            ownership_status="verified",
            version=1,
        )
        unmapped_website = SEOWebsite(
            organization_id=organization.id,
            location_id=None,
            key="unmapped",
            name="Unmapped site",
            canonical_origin="https://unmapped.example.invalid",
            status="active",
            ownership_status="verified",
            version=1,
        )
        paused_website = SEOWebsite(
            organization_id=organization.id,
            location_id=None,
            key="paused",
            name="Paused site",
            canonical_origin="https://paused.example.invalid",
            status="paused",
            ownership_status="verified",
            version=1,
        )
        session.add_all([connection, mapped_website, unmapped_website, paused_website])
        await session.flush()
        search_property = SEOSearchProperty(
            organization_id=organization.id,
            website_id=mapped_website.id,
            connection_id=connection.id,
            provider="google_search_console",
            external_property_id="sc-domain:mapped.example.invalid",
            property_type="domain",
            mapping_status="mapped",
            freshness_status="fresh",
        )
        session.add(search_property)
        await session.flush()
        organization_id = organization.id
        mapped_website_id = mapped_website.id
        unmapped_website_id = unmapped_website.id
        search_property_id = search_property.id

    fake_search_console = FakeSearchConsoleService()
    summary = await reevaluate_active_websites(
        seo_session_factory, Settings(), search_console=fake_search_console
    )

    assert summary.websites == 2
    assert summary.gsc_synced == 1
    assert summary.crawl_analysis_queued == 2
    assert fake_search_console.synced_property_ids == [str(search_property_id)]

    async with seo_session_factory() as session:
        crawl_runs = list(
            await session.scalars(
                select(SEOCrawlRun).where(SEOCrawlRun.organization_id == organization_id)
            )
        )
        assert {run.website_id for run in crawl_runs} == {
            mapped_website_id,
            unmapped_website_id,
        }
        for run in crawl_runs:
            assert run.status == "queued"

        workflow_runs = list(
            await session.scalars(
                select(WorkflowRun).where(WorkflowRun.organization_id == organization_id)
            )
        )
        assert len(workflow_runs) == 2

        jobs = list(
            await session.scalars(select(Job).where(Job.organization_id == organization_id))
        )
        assert len(jobs) == 2
        assert all(job.job_type == "workflow.execute" for job in jobs)


@pytest.mark.integration
@pytest.mark.anyio
async def test_reevaluate_is_safe_to_run_again_without_collision(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A second invocation must not collide with or fail because of the first.

    Each run mints its own idempotency key, mirroring the operator route's
    own idempotency discipline (`SEOService.enqueue_crawl`) rather than
    deduplicating across periodic runs of this command.
    """
    async with seo_session_factory.begin() as session:
        organization = await _make_organization(session)
        website = SEOWebsite(
            organization_id=organization.id,
            location_id=None,
            key="repeatable",
            name="Repeatable site",
            canonical_origin="https://repeatable.example.invalid",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add(website)
        await session.flush()
        organization_id = organization.id

    fake_search_console = FakeSearchConsoleService()
    first = await reevaluate_active_websites(
        seo_session_factory, Settings(), search_console=fake_search_console
    )
    second = await reevaluate_active_websites(
        seo_session_factory, Settings(), search_console=fake_search_console
    )
    assert first.crawl_analysis_queued == 1
    assert second.crawl_analysis_queued == 1

    async with seo_session_factory() as session:
        crawl_runs = list(
            await session.scalars(
                select(SEOCrawlRun).where(SEOCrawlRun.organization_id == organization_id)
            )
        )
        assert len(crawl_runs) == 2
        assert {run.status for run in crawl_runs} == {"queued"}
