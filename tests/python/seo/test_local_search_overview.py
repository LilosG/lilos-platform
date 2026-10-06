"""The Local Search Overview read: insights, technical health and landing-page index status."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.products.seo.models import (
    SEOPage,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)

from .test_seo_api import HEADERS, seo_client

__all__ = ["seo_client"]

END = datetime(2026, 9, 28, tzinfo=UTC)
START = END - timedelta(days=28)
PREVIOUS_START = START - timedelta(days=28)


def observation(
    org: UUID,
    site: UUID,
    prop: UUID,
    kind: str,
    start: datetime,
    end: datetime,
    *,
    clicks: int,
    impressions: int,
    key: str = "",
    page_id: UUID | None = None,
    position: float | None = None,
) -> SEOSearchObservation:
    dimensions: dict[str, object] = {"observation_type": kind}
    if kind == "top_query":
        dimensions["query"] = key
    if kind == "top_page":
        dimensions["page"] = key
    return SEOSearchObservation(
        organization_id=org,
        website_id=site,
        search_property_id=prop,
        page_id=page_id,
        query=key if kind == "top_query" else None,
        date_start=start,
        date_end=end,
        dimensions=dimensions,
        dimension_hash=f"{kind}-{key}-{start.date()}".ljust(64, "0")[:64],
        clicks=clicks,
        impressions=impressions,
        ctr=clicks / impressions if impressions else 0,
        position=position,
        quality_status="valid",
        partial=False,
    )


def page(org: UUID, site: UUID, path: str, **values: object) -> SEOPage:
    return SEOPage(
        organization_id=org,
        website_id=site,
        normalized_url=f"https://example.test{path}",
        observed_url=f"https://example.test{path}",
        normalization_reasons=[],
        http_status=200,
        robots_directives=[],
        internal_links=[],
        external_links=[],
        indexability=values.pop("indexability", "indexable"),
        technical_issues=values.pop("technical_issues", []),
        structured_data_present=values.pop("structured_data_present", False),
        quality_status="valid",
        observed_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


def test_overview_read_carries_insights_technical_health_and_index_status(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/command-center/local-search"

    async def populate() -> UUID:
        async with seo_session_factory.begin() as session:
            google = Provider(
                key="google_business_profile", name="Google", status="active", capabilities=[]
            )
            session.add(google)
            await session.flush()
            connection = IntegrationConnection(
                organization_id=org,
                provider_id=google.id,
                external_account_reference="synthetic-google",
                status="connected",
            )
            site = SEOWebsite(
                organization_id=org,
                location_id=None,
                key="overview",
                name="Overview",
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
                freshness_status="fresh",
                last_synced_at=datetime.now(UTC),
            )
            home = page(org, site.id, "/", indexability="indexable", structured_data_present=True)
            menu = page(org, site.id, "/menu/", technical_issues=["missing_meta_description"])
            thanks = page(org, site.id, "/thanks/", indexability="not_indexable")
            session.add_all([prop, home, menu, thanks])
            await session.flush()
            rows = [
                observation(
                    org, site.id, prop.id, "site_summary", START, END, clicks=300, impressions=6000
                ),
                observation(
                    org,
                    site.id,
                    prop.id,
                    "site_summary",
                    PREVIOUS_START,
                    START,
                    clicks=200,
                    impressions=3000,
                ),
                observation(
                    org,
                    site.id,
                    prop.id,
                    "top_query",
                    START,
                    END,
                    key="brunch near me",
                    clicks=90,
                    impressions=1200,
                    position=9.5,
                ),
                observation(
                    org,
                    site.id,
                    prop.id,
                    "top_query",
                    PREVIOUS_START,
                    START,
                    key="brunch near me",
                    clicks=30,
                    impressions=500,
                    position=12.0,
                ),
                observation(
                    org,
                    site.id,
                    prop.id,
                    "top_page",
                    START,
                    END,
                    key="https://example.test/menu/",
                    clicks=120,
                    impressions=2000,
                    page_id=menu.id,
                ),
                observation(
                    org,
                    site.id,
                    prop.id,
                    "top_page",
                    START,
                    END,
                    key="https://example.test/thanks/",
                    clicks=15,
                    impressions=200,
                    page_id=thanks.id,
                ),
                observation(
                    org,
                    site.id,
                    prop.id,
                    "top_page",
                    START,
                    END,
                    key="https://example.test/old/",
                    clicks=5,
                    impressions=90,
                ),
            ]
            session.add_all(rows)
            return site.id

    site = asyncio.run(populate())
    response = client.get(base + f"?website_id={site}", headers=HEADERS)
    assert response.status_code == 200, response.text
    view = response.json()

    codes = [item["code"] for item in view["insights"]]
    assert codes[0] == "QUERY_GAINING_CLICKS"
    assert "SEARCH_CLICKS_UP" in codes and len(codes) <= 3
    mover = view["insights"][0]
    assert (mover["subject"], mover["current"], mover["previous"]) == ("brunch near me", 90, 30)
    assert mover["link"] == "search_console"
    clicks = next(item for item in view["insights"] if item["code"] == "SEARCH_CLICKS_UP")
    assert (clicks["current"], clicks["previous"]) == (300, 200)
    assert round(clicks["percent_change"]) == 50

    health = view["technical_health"]
    assert health["pages_crawled"] == {"state": "tracked", "value": 3}
    assert health["indexable_pages"]["value"] == 2
    assert health["excluded_pages"]["value"] == 1
    assert health["pages_with_issues"]["value"] == 1
    assert health["structured_data_pages"]["value"] == 1
    # Google's own indexed count is not collected: never a zero.
    assert health["google_indexed_pages"] == {"state": "not_tracked", "value": None}

    status = {
        item["page"].rsplit("/", 2)[-2] or "home": item["index_status"]
        for item in view["search_console"]["top_pages"]
    }
    assert status == {"menu": "indexable", "thanks": "not_indexable", "old": "not_crawled"}


def test_overview_without_data_has_no_insights_and_never_a_zero(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/command-center/local-search"
    empty = client.get(base, headers=HEADERS).json()
    assert empty["insights"] == []
    assert empty["technical_health"] is None

    async def site() -> UUID:
        async with seo_session_factory.begin() as session:
            row = SEOWebsite(
                organization_id=org,
                location_id=None,
                key="bare",
                name="Bare",
                canonical_origin="https://bare.test",
                status="active",
                ownership_status="verified",
                version=1,
            )
            session.add(row)
            await session.flush()
            return row.id

    bare = client.get(base + f"?website_id={asyncio.run(site())}", headers=HEADERS).json()
    assert bare["insights"] == []
    health = bare["technical_health"]
    assert all(
        health[key] == {"state": "not_tracked", "value": None}
        for key in (
            "pages_crawled",
            "indexable_pages",
            "excluded_pages",
            "pages_with_issues",
            "structured_data_pages",
            "google_indexed_pages",
        )
    )
