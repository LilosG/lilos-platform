"""Time the Command Center portfolio and overview reads on a seeded disposable database.

Seeds production-like volumes (see ``VOLUMES``) for N active organizations, drives the real
FastAPI app with a fabricated verified principal, and reports wall time plus the number of SQL
statements per request. Refuses any database whose name does not contain ``test``.

    LILOS_BENCHMARK_DATABASE_URL=postgresql://user@localhost/lilos_perf_test \
        uv run python -m scripts.benchmark_portfolio --organizations 7
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import event, insert, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.models import Product, ProductEntitlement
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.execution.models import (
    Schedule,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.insights.models import InsightSource, MetricObservation
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.main import create_app
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.platform_admin.models import PlatformAdministrator
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.leads.models import Lead, LeadSource
from apps.api.app.products.seo.models import (
    SEOOpportunity,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.reporting_periods import comparison_window

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Per organization, scaled from production row counts (262k search observations, 6.4k reviews,
# 3k metric observations, 830 workflow runs across 7 organizations).
VOLUMES = {
    "search_observations": 37_000,
    "reviews": 900,
    "metric_observations": 430,
    "workflow_runs": 120,
    "leads": 60,
    "opportunities": 40,
}
NAMES = [
    "Coco Maya",
    "Cococabana",
    "Lilos Growth",
    "Louisiana Purchase",
    "Miss B's Coconut Club",
    "Park 101 Carlsbad",
    "The Lobby Tiki Bar",
    "Extra Client",
    "Another Client",
]
PRODUCTS = ("seo", "insights", "leads", "reviews")


class FakeVerifier:
    def __init__(self, claims: VerifiedProviderClaims) -> None:
        self.claims = claims

    async def verify(self, token: str) -> VerifiedProviderClaims:
        del token
        return self.claims


def claims(subject: UUID) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=subject,
        session_id=uuid4(),
        assurance_level=AssuranceLevel.AAL2,
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        algorithm="ES256",
        key_id="benchmark-key",
    )


async def seed(url: str, organizations: int, scale: float) -> tuple[UUID, list[UUID]]:
    engine = create_async_engine(
        url.replace("postgresql://", "postgresql+asyncpg://", 1), poolclass=NullPool
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    org_ids: list[UUID] = []
    async with factory.begin() as session:
        await AccessCatalogSeeder().seed(session, correlation_id="benchmark")
        await AdministrationCatalogSeeder().seed(session, correlation_id="benchmark")
        await ProviderCatalogSeeder().run(session)
        profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
        session.add(profile)
        await session.flush()
        access = AccessControlService()
        owner = await access.catalog.get_role_by_key(session, "organization_owner")
        assert owner is not None
        products = {
            p.key: p.id
            for p in await session.scalars(select(Product).where(Product.key.in_(PRODUCTS)))
        }
        provider = await session.scalar(
            select(Provider).where(Provider.key == "google_business_profile")
        )
        assert provider is not None
        definition = (await AnalyticsService()._ensure_metric_definitions(session))["ga4.sessions"]
        workflow_definitions = []
        for key in ("gbp.publish_post", "seo.crawl_or_analysis", "reviews.ingest"):
            wd = WorkflowDefinition(key=key, name=key, owner="benchmark")
            session.add(wd)
            await session.flush()
            wv = WorkflowVersion(
                definition_id=wd.id,
                version=1,
                status="approved",
                input_schema={},
                output_schema={},
                step_specification=[],
                retry_policy={},
                timeout_seconds=60,
            )
            session.add(wv)
            await session.flush()
            workflow_definitions.append(wv)
        for index in range(organizations):
            name = NAMES[index % len(NAMES)] + ("" if index < len(NAMES) else f" {index}")
            org = Organization(
                name=name,
                slug=f"bench-{index}-{uuid4().hex[:6]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(org)
            await session.flush()
            org_ids.append(org.id)
            first_location: Location | None = None
            for place in range(1 + index % 2):
                location = Location(
                    organization_id=org.id,
                    name=f"{name} {place}",
                    slug=f"loc-{place}",
                    location_type=LocationType.VIRTUAL,
                    status=LocationStatus.ACTIVE,
                    timezone="UTC",
                    country_code="US",
                    website_url="https://example.invalid",
                    is_primary=place == 0,
                    version=1,
                )
                session.add(location)
                await session.flush()
                first_location = first_location or location
            assert first_location is not None
            membership = await access.create_membership(
                session,
                org.id,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="benchmark-member",
            )
            await access.add_assignment(
                session,
                org.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="benchmark-owner",
            )
            for product_key in PRODUCTS:
                session.add(
                    ProductEntitlement(
                        organization_id=org.id,
                        product_id=products[product_key],
                        status="active",
                        source="benchmark",
                        reason="benchmark",
                        version=1,
                    )
                )
            connection = IntegrationConnection(
                organization_id=org.id,
                location_id=None,
                provider_id=provider.id,
                external_account_reference=f"google-{uuid4().hex[:8]}",
                status="connected" if index != 1 else "reconnect_required",
                granted_capabilities=[],
                version=1,
            )
            session.add(connection)
            await session.flush()
            website = SEOWebsite(
                organization_id=org.id,
                location_id=None,
                key="primary",
                name="Primary site",
                canonical_origin="https://example.invalid/",
                status="active",
                ownership_status="verified",
                version=1,
            )
            session.add(website)
            await session.flush()
            prop = SEOSearchProperty(
                organization_id=org.id,
                website_id=website.id,
                connection_id=connection.id,
                provider="google_search_console",
                external_property_id=f"sc-domain:bench{index}.example",
                property_type="domain",
                mapping_status="mapped",
                freshness_status="fresh",
                last_synced_at=now,
            )
            session.add(prop)
            ga4 = AnalyticsProperty(
                organization_id=org.id,
                connection_id=connection.id,
                website_id=website.id,
                provider="google_analytics",
                external_property_id=f"properties/{1000 + index}",
                property_number=str(1000 + index),
                display_name="GA4",
                mapping_status="mapped",
                freshness_status="fresh",
                last_synced_at=now,
            )
            session.add(ga4)
            source = InsightSource(
                organization_id=org.id,
                key=f"properties/{1000 + index}",
                source_type="analytics_property",
                product_key="insights",
                provider="google_analytics",
                status="active",
                authority_scope="organization",
            )
            session.add(source)
            await session.flush()
            period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            for days in (7, 28, 90):
                start = period_end - timedelta(days=days)
                comp_start, comp_end = comparison_window(start, days)
                for window_start, window_end in ((start, period_end), (comp_start, comp_end)):
                    dims = {"observation_type": "site_summary"}
                    await session.execute(
                        insert(SEOSearchObservation),
                        [
                            {
                                "organization_id": org.id,
                                "search_property_id": prop.id,
                                "website_id": website.id,
                                "page_id": None,
                                "query": None,
                                "date_start": window_start,
                                "date_end": window_end,
                                "dimensions": dims,
                                "dimension_hash": uuid4().hex,
                                "clicks": 1000 + days,
                                "impressions": 30000,
                                "ctr": 0.03,
                                "position": 8.2,
                                "quality_status": "valid",
                                "partial": False,
                            }
                        ],
                    )
                    agg = {"observation_type": "aggregate"}
                    await session.execute(
                        insert(MetricObservation),
                        [
                            {
                                "organization_id": org.id,
                                "website_id": website.id,
                                "location_id": None,
                                "page_id": None,
                                "source_id": source.id,
                                "metric_definition_id": definition.id,
                                "period_start": window_start,
                                "period_end": window_end,
                                "dimensions": agg,
                                "dimension_hash": uuid4().hex,
                                "value": 500 + days,
                                "quality_state": "valid",
                                "completeness": 1,
                                "provenance": {},
                            }
                        ],
                    )
            # Bulk volume the report must NOT read for a summary: daily, top_query, top_page rows.
            bulk = int(VOLUMES["search_observations"] * scale)
            start28 = period_end - timedelta(days=28)
            await session.execute(
                text(
                    """
                    INSERT INTO seo_search_observations (
                      id, organization_id, search_property_id, website_id, query,
                      date_start, date_end, dimensions, dimension_hash, clicks, impressions,
                      ctr, position, quality_status, partial, created_at, updated_at
                    )
                    SELECT gen_random_uuid(), :org, :prop, :site, 'q' || g,
                      :start, :end,
                      jsonb_build_object('observation_type',
                        CASE WHEN g % 3 = 0 THEN 'top_query' WHEN g % 3 = 1 THEN 'top_page'
                             ELSE 'legacy_page' END, 'n', g),
                      md5(random()::text || g::text), (g % 40), (g % 900), 0.04, 9.5,
                      'valid', false, now(), now()
                    FROM generate_series(1, :n) g
                    """
                ),
                {
                    "org": org.id,
                    "prop": prop.id,
                    "site": website.id,
                    "start": start28,
                    "end": period_end,
                    "n": bulk,
                },
            )
            mapping = ProviderResourceMapping(
                organization_id=org.id,
                connection_id=connection.id,
                resource_type="location",
                external_resource_id=f"locations/{index}",
                platform_resource_id=first_location.id,
                status="active",
            )
            session.add(mapping)
            await session.flush()
            n_reviews = int(VOLUMES["reviews"] * scale)
            await session.execute(
                text(
                    """
                    INSERT INTO reviews (
                      id, organization_id, location_id, integration_resource_id,
                      external_review_id, provider, rating, status, review_created_at,
                      created_at, updated_at
                    )
                    SELECT gen_random_uuid(), :org, :loc, :map, 'r' || :tag || g, 'google',
                      1 + (g % 5), 'new', now() - (g || ' hours')::interval, now(), now()
                    FROM generate_series(1, :n) g
                    """
                ),
                {
                    "org": org.id,
                    "loc": first_location.id,
                    "map": mapping.id,
                    "tag": str(index),
                    "n": n_reviews,
                },
            )
            lead_source = LeadSource(
                organization_id=org.id,
                location_id=first_location.id,
                key="website_form",
                source_type="web_form",
                name="Website",
                status="active",
                consent_capabilities=[],
                raw_payload_retention_policy="leads.raw_payload.default",
                version=1,
            )
            session.add(lead_source)
            await session.flush()
            await session.execute(
                insert(Lead),
                [
                    {
                        "organization_id": org.id,
                        "location_id": first_location.id,
                        "source_id": lead_source.id,
                        "status": "new",
                        "received_at": now - timedelta(days=n % 80),
                    }
                    for n in range(int(VOLUMES["leads"] * scale))
                ],
            )
            await session.execute(
                insert(SEOOpportunity),
                [
                    {
                        "organization_id": org.id,
                        "website_id": website.id,
                        "opportunity_type": "ranking_opportunity",
                        "status": "identified" if n % 4 else "archived",
                        "priority_score": n,
                        "deduplication_key": uuid4().hex,
                        "source_versions": [],
                        "score_version": 1,
                        "score_explanation": {},
                        "evidence": {"query": f"q{n}", "impressions": n},
                    }
                    for n in range(int(VOLUMES["opportunities"] * scale))
                ],
            )
            versions = workflow_definitions
            runs = []
            for n in range(int(VOLUMES["workflow_runs"] * scale)):
                runs.append(
                    {
                        "organization_id": org.id,
                        "location_id": first_location.id,
                        "workflow_version_id": versions[n % 3].id,
                        "product_key": "benchmark",
                        "trigger_type": "manual",
                        "idempotency_key": f"bench-{index}-{n}-{uuid4().hex[:6]}",
                        "request_hash": "h",
                        "input_document": {},
                        "correlation_id": "bench",
                        "status": "failed" if n == 0 else "completed",
                        "completed_at": now - timedelta(hours=n),
                    }
                )
            if runs:
                await session.execute(insert(WorkflowRun), runs)
            session.add(
                Schedule(
                    organization_id=org.id,
                    location_id=None,
                    workflow_version_id=versions[1].id,
                    key=f"bench-{index}",
                    cron_expression="0 3 * * *",
                    timezone="UTC",
                    status="active",
                    next_run_at=now + timedelta(hours=12),
                )
            )
        if os.environ.get("BENCHMARK_ADMIN") == "1":
            session.add(PlatformAdministrator(user_profile_id=profile.id))
        subject = profile.auth_user_id
    await engine.dispose()
    return subject, org_ids


def migrate(url: str) -> None:
    os.environ["LILOS_MIGRATION_DATABASE_URL"] = url
    command.upgrade(Config(os.path.join(ROOT, "alembic.ini")), "head")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--organizations", type=int, default=7)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--skip-seed", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("LILOS_BENCHMARK_DATABASE_URL", "")
    if "test" not in urlsplit(url).path.lower():
        sys.exit("LILOS_BENCHMARK_DATABASE_URL must name a database containing 'test'")
    migrate(url)
    if args.skip_seed:
        subject = UUID(os.environ["BENCHMARK_SUBJECT"])
        org_ids: list[UUID] = []
    else:
        subject, org_ids = asyncio.run(seed(url, args.organizations, args.scale))
        print(f"seeded organizations={len(org_ids)} subject={subject}")
    counter = {"statements": 0}

    @event.listens_for(Engine, "before_cursor_execute")
    def count(*_: object) -> None:
        counter["statements"] += 1

    settings = Settings.model_validate({"environment": EnvironmentName.TEST, "database_url": url})
    headers = {"Authorization": "Bearer benchmark.token"}
    results: dict[str, dict[str, float]] = {}
    with TestClient(
        create_app(settings, authentication_verifier=FakeVerifier(claims(subject))),
        raise_server_exceptions=True,
    ) as client:
        targets = {
            "/api/v1/command-center/clients": "clients",
            "/api/v1/command-center/portfolio?days=28": "portfolio",
        }
        first = client.get("/api/v1/command-center/clients", headers=headers).json()["data"]
        if first:
            targets[f"/api/v1/command-center/clients/{first[0]['organization_id']}/overview"] = (
                "overview"
            )
        for path, label in targets.items():
            client.get(path, headers=headers)  # warm the pool and caches
            timings: list[float] = []
            statements = 0
            for _ in range(args.runs):
                counter["statements"] = 0
                started = time.perf_counter()
                response = client.get(path, headers=headers)
                timings.append((time.perf_counter() - started) * 1000)
                statements = counter["statements"]
                assert response.status_code == 200, response.text
            results[label] = {
                "median_ms": round(statistics.median(timings), 1),
                "max_ms": round(max(timings), 1),
                "statements": statements,
                "clients": len(first),
            }
    print("RESULT " + json.dumps(results))


if __name__ == "__main__":
    main()
