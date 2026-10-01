"""Phase 2 projections and atomic canonical dispatch against disposable PostgreSQL."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from authorization.fixtures import add_effective_product_entitlement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.execution.models import Job
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.products.seo.models import SEOSearchObservation, SEOSearchProperty, SEOWebsite

from .test_seo_api import HEADERS, execute_crawl_directly, seo_client

__all__ = ["seo_client"]


def test_search_projection_crawl_dispatch_scope_and_missing_data(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    base = f"/api/v1/organizations/{ids['organization']}"
    empty = client.get(base + "/command-center/local-search", headers=HEADERS)
    assert empty.status_code == 200, empty.text
    assert empty.json()["website_id"] is None
    assert empty.json()["search_console"] is None
    assert empty.json()["analytics"] is None
    assert empty.json()["analytics_availability"] == "permission_required"
    assert empty.json()["profiles"] == []
    website = client.post(
        base + "/seo/websites",
        headers=HEADERS,
        json={
            "key": "phase2",
            "name": "Phase 2",
            "canonical_origin": "https://example.test",
            "location_id": str(ids["location"]),
        },
    ).json()["data"]
    before = client.get(base + "/command-center/local-search", headers=HEADERS)
    assert before.status_code == 200, before.text
    assert before.json()["search_console"]["metrics"] == {}
    assert before.json()["search_console"]["range"] is None
    payload = {"idempotency_key": "phase2-website-check"}
    crawl = client.post(
        base + f"/seo/websites/{website['id']}/check", headers=HEADERS, json=payload
    )
    assert crawl.status_code == 202, crawl.text
    duplicate = client.post(
        base + f"/seo/websites/{website['id']}/check", headers=HEADERS, json=payload
    )
    assert duplicate.status_code == 202, duplicate.text
    assert duplicate.json()["data"]["id"] == crawl.json()["data"]["id"]

    async def jobs() -> None:
        async with seo_session_factory() as session:
            rows = list(
                await session.scalars(select(Job).where(Job.organization_id == ids["organization"]))
            )
            assert len(rows) == 1

    asyncio.run(jobs())
    execute_crawl_directly(
        seo_session_factory, ids["organization"], UUID(crawl.json()["data"]["id"])
    )
    result = client.get(base + "/command-center/local-search", headers=HEADERS)
    assert result.status_code == 200, result.text
    view = result.json()
    assert view["crawls"][0]["status"] == "success"
    assert view["pages"] and view["pages"][0]["observed_at"]
    assert "geographic_rank_grid" in view["unsupported"]
    page = view["pages"][0]
    path = f"/command-center/local-search/websites/{website['id']}/pages/{page['id']}"
    intelligence = client.get(base + path, headers=HEADERS)
    assert intelligence.status_code == 200, intelligence.text
    assert intelligence.json()["identity"]["organization_id"] == str(ids["organization"])
    assert intelligence.json()["crawl"]["availability"] == "observed"
    assert intelligence.json()["gsc"]["availability"] == "unavailable"
    assert intelligence.json()["ga4_organic_landing"]["availability"] == "unavailable"
    for endpoint in ["/command-center/local-search", path]:
        assert client.get(base + endpoint).status_code == 401
        foreign = client.get(
            f"/api/v1/organizations/{ids['other_organization']}" + endpoint, headers=HEADERS
        )
        assert foreign.status_code in {403, 404}
        assert website["id"] not in foreign.text
    assert (
        client.get(
            base + "/command-center/local-search?website_id=" + str(uuid4()), headers=HEADERS
        ).status_code
        == 404
    )
    assert (
        client.get(base + "/command-center/local-search?days=30", headers=HEADERS).status_code
        == 422
    )
    assert (
        client.get(base + "/command-center/local-search?offset=-1", headers=HEADERS).status_code
        == 422
    )


def test_integration_projection_and_stale_gsc_comparison(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}"

    async def populate() -> UUID:
        async with seo_session_factory.begin() as session:
            for product in ["gbp", "insights"]:
                await add_effective_product_entitlement(
                    session, org, product, correlation_id="phase2"
                )
            google = Provider(
                key="google_business_profile", name="Google", status="active", capabilities=[]
            )
            session.add(google)
            await session.flush()
            connection = IntegrationConnection(
                organization_id=org,
                provider_id=google.id,
                external_account_reference="synthetic-google",
                status="reconnect_required",
            )
            site = SEOWebsite(
                organization_id=org,
                location_id=None,
                key="report",
                name="Report",
                canonical_origin="https://example.test",
                status="active",
                ownership_status="verified",
                version=1,
            )
            session.add_all([connection, site])
            await session.flush()
            prop = SEOSearchProperty(
                organization_id=org,
                website_id=site.id,
                connection_id=connection.id,
                provider="google_search_console",
                external_property_id="sc-domain:example.test",
                property_type="domain",
                mapping_status="mapped",
                freshness_status="stale",
                last_synced_at=datetime.now(UTC) - timedelta(days=8),
            )
            session.add(prop)
            await session.flush()
            end = datetime(2026, 9, 28, tzinfo=UTC)
            start = end - timedelta(days=28)
            session.add(
                SEOSearchObservation(
                    organization_id=org,
                    website_id=site.id,
                    search_property_id=prop.id,
                    date_start=start,
                    date_end=end,
                    dimensions={"observation_type": "site_summary"},
                    dimension_hash="a" * 64,
                    clicks=0,
                    impressions=0,
                    ctr=0,
                    position=None,
                    quality_status="zero",
                    partial=False,
                )
            )
            return site.id

    website = asyncio.run(populate())
    integrations = client.get(base + "/command-center/integrations", headers=HEADERS)
    assert integrations.status_code == 200, integrations.text
    data = integrations.json()
    assert data["google"]["connection_status"] == "reconnect_required"
    assert data["search_properties"][0]["freshness_status"] == "stale"
    assert data["search_properties"][0]["website_id"] == str(website)
    assert "access_token" not in integrations.text
    report = client.get(
        base + f"/command-center/local-search?website_id={website}", headers=HEADERS
    )
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["google_status"] == "reconnect_required"
    assert data["search_console"]["freshness"]["status"] == "stale"
    assert data["search_console"]["metrics"]["clicks"]["current"] == 0
    assert data["search_console"]["metrics"]["clicks"]["previous"] is None
    assert data["search_console"]["metrics"]["clicks"]["quality"] == "partial"
    assert data["search_console"]["metrics"]["position"]["current"] is None
    assert data["analytics_scope"] == "organization_all_channels"
    assert client.get(base + "/command-center/integrations").status_code == 401
    assert client.get(
        f"/api/v1/organizations/{ids['other_organization']}/command-center/integrations",
        headers=HEADERS,
    ).status_code in {403, 404}
