"""Website readiness derived read-model integration tests.

Verifies that WebsiteReadinessService correctly derives tenant-scoped facts
from authoritative records (OrganizationDomain, SEOWebsite, SEOSearchProperty,
AnalyticsProperty, SEOCrawlRun) without fabricating state.
"""

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.domains.enums import OrganizationDomainStatus
from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.insights.website_readiness import WebsiteReadinessService
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.models import SEOCrawlRun, SEOSearchProperty, SEOWebsite


async def make_connection(session: AsyncSession, organization_id: UUID) -> IntegrationConnection:
    """Create a connected Google connection directly (bypassing OAuth)."""
    await ProviderCatalogSeeder().run(session)
    provider = await session.scalar(
        select(Provider).where(Provider.key == "google_business_profile")
    )
    assert provider is not None
    connection = IntegrationConnection(
        organization_id=organization_id,
        location_id=None,
        provider_id=provider.id,
        external_account_reference=f"google-{uuid4().hex[:8]}",
        status="connected",
        granted_capabilities=["https://www.googleapis.com/auth/webmasters.readonly"],
        version=1,
    )
    session.add(connection)
    await session.flush()
    return connection


async def make_organization(session: AsyncSession) -> Organization:
    org = Organization(
        name="Website Readiness Test Org",
        slug=f"wr-test-org-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()
    return org


async def make_domain(
    session: AsyncSession,
    organization_id: UUID,
    domain: str,
    *,
    is_primary: bool = False,
    status: OrganizationDomainStatus = OrganizationDomainStatus.ACTIVE,
    archived_at: datetime | None = None,
) -> OrganizationDomain:
    d = OrganizationDomain(
        organization_id=organization_id,
        domain=domain,
        is_primary=is_primary,
        status=status,
        archived_at=archived_at,
        version=1,
    )
    session.add(d)
    await session.flush()
    return d


async def make_website(
    session: AsyncSession,
    organization_id: UUID,
    canonical_origin: str,
) -> SEOWebsite:
    website = SEOWebsite(
        organization_id=organization_id,
        location_id=None,
        key="primary",
        name="Primary",
        canonical_origin=canonical_origin,
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add(website)
    await session.flush()
    return website


async def make_crawl_run(
    session: AsyncSession,
    organization_id: UUID,
    website_id: UUID,
    *,
    status: str,
    completed_at: datetime | None = None,
) -> SEOCrawlRun:
    """Create a full WorkflowRun FK chain plus a crawl run."""
    wf_def = WorkflowDefinition(
        key=f"crawl.{uuid4().hex[:8]}",
        name="Website Crawl",
        owner="seo",
        status="active",
    )
    session.add(wf_def)
    await session.flush()

    wf_ver = WorkflowVersion(
        definition_id=wf_def.id,
        version=1,
        status="approved",
        input_schema={},
        output_schema={},
        step_specification=[],
        retry_policy={},
        timeout_seconds=300,
    )
    session.add(wf_ver)
    await session.flush()

    wf_run = WorkflowRun(
        organization_id=organization_id,
        workflow_version_id=wf_ver.id,
        status="completed",
        trigger_type="test",
        idempotency_key=f"run-{uuid4().hex[:12]}",
        request_hash="test-hash",
        input_document={},
        correlation_id="crawl-test",
    )
    session.add(wf_run)
    await session.flush()

    crawl = SEOCrawlRun(
        organization_id=organization_id,
        website_id=website_id,
        workflow_run_id=wf_run.id,
        idempotency_key=f"crawl-{uuid4().hex[:12]}",
        status=status,
        max_pages=100,
        safe_result={},
        completed_at=completed_at,
    )
    session.add(crawl)
    await session.flush()
    return crawl


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_no_domains_no_websites(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["canonical_domain_configured"] is False
        assert result["primary_domain"] is None
        assert result["domains"] == []
        assert result["seo_websites"] == []
        assert result["search_console_mapped"] is False
        assert result["search_console_connected"] is False
        assert result["analytics_mapped"] is False
        assert result["analytics_connected"] is False
        assert result["crawl_ready"] is False
        assert result["last_crawl_at"] is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_active_domain_primary(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        await make_domain(
            session, org.id, "example.com", is_primary=True, status=OrganizationDomainStatus.ACTIVE
        )
        await make_domain(
            session, org.id, "other.com", is_primary=False, status=OrganizationDomainStatus.ACTIVE
        )
        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["canonical_domain_configured"] is True
        assert result["primary_domain"] == "example.com"
        assert len(cast(list[dict[str, object]], result["domains"])) == 2


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_archived_domain_not_counted(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        await make_domain(
            session,
            org.id,
            "archived.com",
            is_primary=True,
            status=OrganizationDomainStatus.ARCHIVED,
            archived_at=datetime.now(UTC),
        )
        await make_domain(
            session, org.id, "active.com", is_primary=False, status=OrganizationDomainStatus.ACTIVE
        )
        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["canonical_domain_configured"] is True  # active.com is active
        assert result["primary_domain"] is None  # archived primary is ignored


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_search_console_mapped(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        connection = await make_connection(session, org.id)
        website = await make_website(session, org.id, "https://example.com/")

        sc_prop = SEOSearchProperty(
            organization_id=org.id,
            website_id=website.id,
            connection_id=connection.id,
            provider="google_search_console",
            external_property_id="sc-domain:example.com",
            property_type="domain",
            mapping_status="mapped",
            freshness_status="fresh",
            last_synced_at=datetime.now(UTC),
        )
        session.add(sc_prop)
        await session.flush()

        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["search_console_mapped"] is True
        assert result["search_console_connected"] is True
        assert result["search_console_freshness"] == "fresh"
        assert result["search_console_last_sync"] is not None


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_search_console_not_mapped(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        connection = await make_connection(session, org.id)
        website = await make_website(session, org.id, "https://example.com/")

        sc_prop = SEOSearchProperty(
            organization_id=org.id,
            website_id=website.id,
            connection_id=connection.id,
            provider="google_search_console",
            external_property_id="sc-domain:example.com",
            property_type="domain",
            mapping_status="stale",  # not mapped
            freshness_status="never_synced",
        )
        session.add(sc_prop)
        await session.flush()

        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["search_console_mapped"] is False
        assert result["search_console_connected"] is False


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_analytics_mapped(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        connection = await make_connection(session, org.id)
        website = await make_website(session, org.id, "https://example.com/")

        ga4 = AnalyticsProperty(
            organization_id=org.id,
            connection_id=connection.id,
            website_id=website.id,
            provider="google_analytics",
            external_property_id="properties/123456",
            property_number="123456",
            display_name="Example GA4",
            mapping_status="mapped",
            freshness_status="fresh",
            last_synced_at=datetime.now(UTC),
        )
        session.add(ga4)
        await session.flush()

        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["analytics_mapped"] is True
        assert result["analytics_connected"] is True
        assert result["analytics_freshness"] == "fresh"
        assert result["analytics_last_sync"] is not None


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_tenant_isolation(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify readiness facts are scoped to the requesting organization."""
    async with insights_session_factory.begin() as session:
        org_a = await make_organization(session)
        org_b = await make_organization(session)
        await make_domain(session, org_a.id, "a.example", is_primary=True)
        await make_domain(session, org_b.id, "b.example", is_primary=True)

        service = WebsiteReadinessService()
        result_a = await service.readiness(session, org_a.id)
        result_b = await service.readiness(session, org_b.id)

        assert result_a["primary_domain"] == "a.example"
        assert result_b["primary_domain"] == "b.example"
        domains_a = cast(list[dict[str, object]], result_a["domains"])
        domains_b = cast(list[dict[str, object]], result_b["domains"])
        assert len(domains_a) == 1
        assert len(domains_b) == 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_no_crawl(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        await make_website(session, org.id, "https://example.com/")
        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["crawl_ready"] is False
        assert result["last_crawl_at"] is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_failed_crawl_not_ready(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        website = await make_website(session, org.id, "https://example.com/")
        await make_crawl_run(session, org.id, website.id, status="failed", completed_at=None)
        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["crawl_ready"] is False
        assert result["last_crawl_at"] is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_completed_crawl_ready(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        website = await make_website(session, org.id, "https://example.com/")
        completed_at = datetime.now(UTC) - timedelta(days=1)
        await make_crawl_run(
            session, org.id, website.id, status="completed", completed_at=completed_at
        )
        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["crawl_ready"] is True
        assert result["last_crawl_at"] == completed_at.isoformat()


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_newer_failed_crawl_keeps_completed(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        website = await make_website(session, org.id, "https://example.com/")
        older_completed = datetime.now(UTC) - timedelta(days=2)
        await make_crawl_run(
            session, org.id, website.id, status="completed", completed_at=older_completed
        )
        await make_crawl_run(
            session, org.id, website.id, status="failed", completed_at=datetime.now(UTC)
        )
        service = WebsiteReadinessService()
        result = await service.readiness(session, org.id)
        assert result["crawl_ready"] is True
        assert result["last_crawl_at"] == older_completed.isoformat()


@pytest.mark.integration
@pytest.mark.anyio
async def test_website_readiness_crawl_tenant_isolation(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org_a = await make_organization(session)
        org_b = await make_organization(session)
        await make_website(session, org_a.id, "https://a.example/")
        website_b = await make_website(session, org_b.id, "https://b.example/")

        await make_crawl_run(
            session, org_b.id, website_b.id, status="completed", completed_at=datetime.now(UTC)
        )

        service = WebsiteReadinessService()
        result_a = await service.readiness(session, org_a.id)
        result_b = await service.readiness(session, org_b.id)

        assert result_a["crawl_ready"] is False
        assert result_a["last_crawl_at"] is None
        assert result_b["crawl_ready"] is True
        assert result_b["last_crawl_at"] is not None
