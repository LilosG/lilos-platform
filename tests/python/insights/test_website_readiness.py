"""Website readiness derived read-model integration tests.

Verifies that WebsiteReadinessService correctly derives tenant-scoped facts
from authoritative records (OrganizationDomain, SEOWebsite, SEOSearchProperty,
AnalyticsProperty) without fabricating state.

Crawl readiness scenarios require a WorkflowRun FK chain and are exercised
through browser-level acceptance tests.
"""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.domains.enums import OrganizationDomainStatus
from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.insights.website_readiness import WebsiteReadinessService
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.models import SEOSearchProperty, SEOWebsite


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
