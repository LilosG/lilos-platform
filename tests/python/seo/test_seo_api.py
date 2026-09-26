"""Production-capable SEO route, crawl, audit, and isolation tests."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import pytest
from authorization.fixtures import add_effective_product_entitlement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.administration.models import ProductEntitlement
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.main import create_app
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.seo.models import (
    SEOCrawlPageObservation,
    SEOCrawlRun,
    SEOImplementationTask,
    SEOInternalLinkObservation,
    SEOOpportunity,
    SEOOutcome,
    SEOPage,
    SEORecommendationRevision,
    SEOWebsite,
)
from apps.api.app.products.seo.service import SEOService

GOOD_PAGE_HTML = (
    "<html><head><title>Downtown Services</title>"
    '<meta name="description" content="We serve the downtown area.">'
    '<link rel="canonical" href="https://example.test/"></head>'
    "<body><h1>Welcome</h1></body></html>"
)
BROKEN_PAGE_HTML = "<html><head></head><body>No title, no meta, no h1.</body></html>"


def mock_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/broken":
        return httpx.Response(200, text=BROKEN_PAGE_HTML, headers={"content-type": "text/html"})
    return httpx.Response(200, text=GOOD_PAGE_HTML, headers={"content-type": "text/html"})


def mock_http_client_factory() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))


def execute_crawl_directly(
    session_factory: async_sessionmaker[AsyncSession],
    org_id: UUID,
    crawl_run_id: UUID,
) -> None:
    """Simulate the background worker executing an enqueued crawl."""

    async def _run() -> None:
        seo_service = SEOService(http_client_factory=mock_http_client_factory)
        async with session_factory.begin() as session:
            await seo_service.execute_crawl(
                session, org_id, crawl_run_id, correlation_id="seo-test-worker"
            )

    asyncio.run(_run())


class FakeVerifier:
    def __init__(self, claims: VerifiedProviderClaims) -> None:
        self.result: VerifiedProviderClaims | Exception = claims

    async def verify(self, token: str) -> VerifiedProviderClaims:
        del token
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def claims(
    subject: UUID, assurance: AssuranceLevel = AssuranceLevel.AAL2
) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=subject,
        session_id=uuid4(),
        assurance_level=assurance,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        algorithm="ES256",
        key_id="seo-test-key",
    )


HEADERS = {"Authorization": "Bearer fabricated.token"}


def test_opportunity_scope_is_in_query_before_limit_without_database() -> None:
    async def scenario() -> None:
        organization_id, location_id, website_id = uuid4(), uuid4(), uuid4()
        statement_sql: list[str] = []

        class FakeSession:
            async def scalars(self, statement: Any) -> list[object]:
                statement_sql.append(str(statement))
                return [SimpleNamespace(id=uuid4()) for _ in range(3)]

        rows, has_more = await SEOService().list_opportunities(
            cast(Any, FakeSession()),
            organization_id,
            website_id=website_id,
            status_filter="identified",
            location_scope=(location_id, None),
            limit=2,
            offset=1,
        )
        assert len(rows) == 2 and has_more is True
        query = statement_sql[0]
        assert "seo_opportunities.organization_id =" in query
        assert "seo_opportunities.website_id =" in query
        assert "seo_opportunities.status =" in query
        assert "seo_opportunities.location_id IN" in query
        assert "seo_opportunities.location_id IS NULL" in query
        assert query.index("seo_opportunities.location_id IN") < query.index("LIMIT")
        assert "ORDER BY seo_opportunities.priority_score DESC, seo_opportunities.id ASC" in query
        assert "OFFSET" in query

    asyncio.run(scenario())


@pytest.mark.integration
def test_opportunity_location_scope_precedes_pagination_and_preserves_filters(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, ids = seo_client

    async def scenario() -> None:
        organization_id = ids["organization"]
        other_organization_id = ids["other_organization"]
        location_id = ids["location"]
        async with seo_session_factory.begin() as session:
            other_location = Location(
                organization_id=organization_id,
                name="Uptown",
                slug="uptown",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://uptown.example.invalid",
                is_primary=False,
                version=1,
            )
            session.add(other_location)
            await session.flush()
            websites = [
                SEOWebsite(
                    organization_id=org,
                    location_id=loc,
                    key=key,
                    name=key,
                    canonical_origin=f"https://{key}.example.invalid",
                    status="active",
                    ownership_status="verified",
                    version=1,
                )
                for org, loc, key in (
                    (organization_id, location_id, "downtown"),
                    (organization_id, other_location.id, "uptown"),
                    (organization_id, None, "organization"),
                    (other_organization_id, None, "foreign"),
                )
            ]
            session.add_all(websites)
            await session.flush()
            opportunities = [
                SEOOpportunity(
                    organization_id=org,
                    location_id=loc,
                    website_id=website.id,
                    page_id=None,
                    opportunity_type="test_issue",
                    deduplication_key=f"packet-0a-{score}-{uuid4().hex}",
                    active_marker="active",
                    evidence={},
                    source_versions=["crawl.v1"],
                    score_version=1,
                    priority_score=score,
                    score_explanation={},
                    status=status,
                    version=1,
                )
                for org, loc, website, score, status in (
                    (organization_id, other_location.id, websites[1], 99, "identified"),
                    (organization_id, other_location.id, websites[1], 98, "identified"),
                    (organization_id, location_id, websites[0], 70, "identified"),
                    (organization_id, location_id, websites[0], 65, "rejected"),
                    (organization_id, location_id, websites[0], 60, "identified"),
                    (organization_id, None, websites[2], 50, "identified"),
                    (other_organization_id, None, websites[3], 100, "identified"),
                )
            ]
            session.add_all(opportunities)
            await session.flush()

            service = SEOService()
            first, has_more = await service.list_opportunities(
                session, organization_id, location_scope=(location_id, None), limit=2
            )
            assert [row.priority_score for row in first] == [70, 65]
            assert has_more is True
            second, has_more = await service.list_opportunities(
                session, organization_id, location_scope=(location_id, None), limit=2, offset=2
            )
            assert [row.priority_score for row in second] == [60, 50]
            assert has_more is False
            website_rows, has_more = await service.list_opportunities(
                session,
                organization_id,
                website_id=websites[0].id,
                status_filter="identified",
                location_scope=(location_id, None),
                limit=2,
            )
            assert [row.priority_score for row in website_rows] == [70, 60]
            assert has_more is False
            unscoped, _ = await service.list_opportunities(session, organization_id, limit=10)
            assert len(unscoped) == 6
            assert all(row.organization_id == organization_id for row in unscoped)

    asyncio.run(scenario())


@pytest.fixture
def seo_client(
    postgresql_test_url: str,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with seo_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="seo-api-catalog")
            organization = Organization(
                name="SEO Test Org",
                slug="seo-test-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_organization = Organization(
                name="SEO Other Org",
                slug="seo-other-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            session.add_all([organization, other_organization, profile])
            await session.flush()
            await add_effective_product_entitlement(
                session,
                organization.id,
                "seo",
                correlation_id="seo-api-entitlement",
            )

            location = Location(
                organization_id=organization.id,
                name="Downtown",
                slug="downtown",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=True,
                version=1,
            )
            session.add(location)
            await session.flush()

            membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="seo-api-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="seo-api-owner",
            )

            provider = Provider(
                key="google_search_console",
                name="Google Search Console",
                status="active",
                capabilities=["seo.read"],
            )
            session.add(provider)
            await session.flush()
            connection = IntegrationConnection(
                organization_id=organization.id,
                provider_id=provider.id,
                external_account_reference="sc-domain:example.test",
                status="connected",
            )
            session.add(connection)
            await session.flush()

            workflow_definition = WorkflowDefinition(
                key="seo.crawl_or_analysis", name="Crawl or analyze SEO website", owner="seo"
            )
            session.add(workflow_definition)
            await session.flush()
            workflow_version = WorkflowVersion(
                definition_id=workflow_definition.id,
                version=1,
                status="approved",
                input_schema={},
                output_schema={},
                step_specification=[],
                retry_policy={},
                timeout_seconds=60,
            )
            session.add(workflow_version)
            await session.flush()
            workflow_run = WorkflowRun(
                organization_id=organization.id,
                location_id=location.id,
                workflow_version_id=workflow_version.id,
                product_key="seo",
                trigger_type="manual",
                idempotency_key="seo-test-workflow-run-001",
                request_hash="deterministic-request-hash",
                input_document={},
                correlation_id="seo-test-workflow",
            )
            session.add(workflow_run)
            await session.flush()
            workflow_run_2 = WorkflowRun(
                organization_id=organization.id,
                location_id=location.id,
                workflow_version_id=workflow_version.id,
                product_key="seo",
                trigger_type="manual",
                idempotency_key="seo-test-workflow-run-002",
                request_hash="deterministic-request-hash-2",
                input_document={},
                correlation_id="seo-test-workflow",
            )
            session.add(workflow_run_2)
            await session.flush()

            identifiers = {
                "organization": organization.id,
                "other_organization": other_organization.id,
                "location": location.id,
                "assigned_subject": profile.auth_user_id,
                "connection": connection.id,
                "workflow_run": workflow_run.id,
                "workflow_run_2": workflow_run_2.id,
            }
            return claims(profile.auth_user_id), identifiers

    verified, identifiers = asyncio.run(populate())
    verifier = FakeVerifier(verified)
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    monkeypatch.setattr(
        "apps.api.app.routes.seo.service",
        SEOService(http_client_factory=mock_http_client_factory),
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, identifiers


@pytest.mark.integration
def test_website_crawl_generates_opportunities_and_landing_page_gaps(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org, location = ids["organization"], ids["location"]
    base = f"/api/v1/organizations/{org}/seo"

    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(location),
            "key": "primary",
            "name": "Example Site",
            "canonical_origin": "https://example.test",
        },
    )
    assert website.status_code == 201, website.text
    website_id = website.json()["data"]["id"]
    assert website.json()["data"]["status"] == "pending_verification"

    crawl = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run"]),
            "seed_paths": ["/", "/broken"],
            "max_pages": 2,
            "idempotency_key": "seo-crawl-key-001",
        },
    )
    assert crawl.status_code == 202, crawl.text
    assert crawl.json()["data"]["status"] == "queued"
    assert "opportunities_created" not in crawl.json()["data"]
    crawl_run_id = UUID(crawl.json()["data"]["id"])

    execute_crawl_directly(seo_session_factory, org, crawl_run_id)

    crawl_run = client.get(f"{base}/crawl-runs/{crawl_run_id}", headers=HEADERS)
    assert crawl_run.status_code == 200
    assert crawl_run.json()["data"]["status"] == "success"
    assert crawl_run.json()["data"]["safe_result"]["pages_crawled"] == 2

    listing = client.get(f"{base}/opportunities", headers=HEADERS)
    assert listing.status_code == 200
    assert listing.headers["Cache-Control"] == "no-store"
    opportunities = listing.json()["data"]
    assert len(opportunities) > 0
    assert {"missing_title", "missing_meta_description", "missing_h1"} & {
        item["opportunity_type"] for item in opportunities
    }

    summary = client.get(f"{base}/summary", headers=HEADERS)
    assert summary.status_code == 200
    assert summary.json()["data"]["website_count"] == 1
    assert summary.json()["data"]["crawl_run_count"] == 1
    assert sum(summary.json()["data"]["by_status"].values()) == len(opportunities)

    gaps = client.get(f"{base}/websites/{website_id}/landing-page-gaps", headers=HEADERS)
    assert gaps.status_code == 200
    assert any(gap["location_id"] == str(location) for gap in gaps.json()["data"])

    audit = client.get(f"{base}/websites/{website_id}/audit", headers=HEADERS)
    assert audit.status_code == 200
    event_types = {event["event_type"] for event in audit.json()["data"]}
    assert {"seo.website.created", "seo.crawl.success"} <= event_types


@pytest.mark.integration
def test_page_intelligence_link_reconciliation_and_scope(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/seo"
    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(ids["location"]),
            "key": "links",
            "name": "Links",
            "canonical_origin": "https://example.test",
        },
    )
    assert website.status_code == 201, website.text
    website_id = UUID(website.json()["data"]["id"])
    crawl = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run"]),
            "seed_paths": ["/target"],
            "max_pages": 2,
            "concurrency": 2,
            "crawl_delay_seconds": 0.1,
            "idempotency_key": "link-run",
        },
    )
    assert crawl.status_code == 202, crawl.text
    run_id = UUID(crawl.json()["data"]["id"])

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/target":
            await asyncio.sleep(0.2)
            html = (
                "<html><head><title>Target</title></head><body><h1>Target</h1>"
                '<a href="/">Back to source</a></body></html>'
            )
        else:
            html = (
                "<html><head><title>Source</title></head><body><h1>Source</h1>"
                '<a href="/target" rel="nofollow">Target <strong>page</strong></a>'
                '<a href="/target" rel="nofollow">Target <em>page</em></a>'
                '<a href="/target?x=1">Parameterized</a>'
                '<a href="/missing">Missing</a>'
                '<a href="https://foreign.test/out">Foreign</a>'
                "</body></html>"
            )
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    async def run_crawl() -> tuple[UUID, UUID]:
        seo = SEOService(
            http_client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        async with seo_session_factory.begin() as session:
            result, _ = await seo.execute_crawl(session, org, run_id, correlation_id="link-test")
            assert result.status == "success"
            assert result.safe_result["internal_link_evidence_status"] == "available"
        async with seo_session_factory() as session:
            source = await session.scalar(
                select(SEOPage).where(
                    SEOPage.organization_id == org,
                    SEOPage.website_id == website_id,
                    SEOPage.normalized_url == "https://example.test/",
                )
            )
            target = await session.scalar(
                select(SEOPage).where(
                    SEOPage.organization_id == org,
                    SEOPage.website_id == website_id,
                    SEOPage.normalized_url == "https://example.test/target",
                )
            )
            assert source is not None and target is not None
            assert source.observed_at is not None and target.observed_at is not None
            assert source.observed_at < target.observed_at
            edges = list(
                await session.scalars(
                    select(SEOInternalLinkObservation).where(
                        SEOInternalLinkObservation.organization_id == org,
                        SEOInternalLinkObservation.crawl_run_id == run_id,
                    )
                )
            )
            assert len(edges) == 4
            mapped = [edge for edge in edges if edge.normalized_target_url.endswith("/target")]
            assert len(mapped) == 1 and mapped[0].target_page_id == target.id
            assert mapped[0].occurrence_count == 2
            assert mapped[0].nofollow and mapped[0].anchor_text == "Target page"
            assert all(
                edge.target_page_id is None
                for edge in edges
                if edge.normalized_target_url.endswith(("/missing", "/target?x=1"))
            )
            assert any(
                edge.source_page_id == target.id and edge.target_page_id == source.id
                for edge in edges
            )
            return source.id, target.id

    source_id, target_id = asyncio.run(run_crawl())
    execute_crawl_directly(seo_session_factory, org, run_id)
    response = client.get(
        f"{base}/websites/{website_id}/pages/{source_id}/intelligence", headers=HEADERS
    )
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert (
        client.get(f"{base}/websites/{website_id}/pages/{source_id}/intelligence").status_code
        == 401
    )
    data = response.json()["data"]
    assert data["version"] == "page_intelligence.v1"
    assert data["internal_links"]["mapped_outbound_count"] == 1
    assert data["internal_links"]["unresolved_outbound_count"] == 2
    assert data["internal_links"]["source_page_observed"] is True
    assert data["internal_links"]["source_link_evidence_available"] is True
    assert data["internal_links"]["crawl_run_id"] == str(run_id)
    assert data["change"]["state"] == "first_observation"
    assert data["content"]["knowledge"]["items"]
    assert data["content"]["business_relationship_availability"] == "unavailable"
    assert data["workflow"]["opportunities"]["items"]
    assert "priority_score" not in str(data["workflow"])
    target_response = client.get(
        f"{base}/websites/{website_id}/pages/{target_id}/intelligence", headers=HEADERS
    )
    assert target_response.status_code == 200, target_response.text
    assert target_response.json()["data"]["internal_links"]["mapped_inbound_count"] == 1
    assert target_response.json()["data"]["internal_links"]["mapped_outbound_count"] == 1

    async def mark_partial() -> None:
        async with seo_session_factory.begin() as session:
            item = await session.get(SEOCrawlRun, run_id)
            assert item is not None
            item.status = "partial"
            item.safe_result = {
                **item.safe_result,
                "internal_link_evidence_status": "partial",
                "internal_link_evidence_limitation": "Crawl coverage was partial.",
            }

    asyncio.run(mark_partial())
    partial_response = client.get(
        f"{base}/websites/{website_id}/pages/{source_id}/intelligence", headers=HEADERS
    )
    assert partial_response.status_code == 200
    assert partial_response.json()["data"]["internal_links"]["availability"] == "partial"
    assert partial_response.json()["data"]["internal_links"]["run_status"] == "partial"
    wrong_org = client.get(
        f"/api/v1/organizations/{ids['other_organization']}/seo/websites/"
        f"{website_id}/pages/{source_id}/intelligence",
        headers=HEADERS,
    )
    assert wrong_org.status_code in (403, 404)
    wrong_website = client.get(
        f"{base}/websites/{uuid4()}/pages/{source_id}/intelligence", headers=HEADERS
    )
    assert wrong_website.status_code == 404

    later_crawl = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run_2"]),
            "seed_paths": ["/"],
            "max_pages": 1,
            "idempotency_key": "link-run-later",
        },
    )
    assert later_crawl.status_code == 202, later_crawl.text
    later_id = UUID(later_crawl.json()["data"]["id"])
    execute_crawl_directly(seo_session_factory, org, later_id)
    later_response = client.get(
        f"{base}/websites/{website_id}/pages/{source_id}/intelligence", headers=HEADERS
    )
    assert later_response.status_code == 200, later_response.text
    later_data = later_response.json()["data"]
    assert later_data["internal_links"]["crawl_run_id"] == str(later_id)
    assert later_data["internal_links"]["source_page_observed"] is True
    assert later_data["internal_links"]["source_link_evidence_available"] is True
    assert later_data["internal_links"]["mapped_outbound_count"] == 0
    assert later_data["internal_links"]["unresolved_outbound_count"] == 0
    assert later_data["internal_links"]["outbound"]["items"] == []
    assert later_data["internal_links"]["pages_crawled"] == 1
    assert later_data["internal_links"]["pages_queued"] is not None
    assert later_data["internal_links"]["pages_skipped"] is not None
    absent_response = client.get(
        f"{base}/websites/{website_id}/pages/{target_id}/intelligence", headers=HEADERS
    )
    assert absent_response.status_code == 200, absent_response.text
    absent_graph = absent_response.json()["data"]["internal_links"]
    assert absent_graph["crawl_run_id"] == str(later_id)
    assert absent_graph["availability"] == "partial"
    assert absent_graph["source_page_observed"] is False
    assert absent_graph["source_link_evidence_available"] is False
    assert absent_graph["mapped_outbound_count"] is None
    assert absent_graph["unresolved_outbound_count"] is None
    assert absent_graph["outbound"]["items"] == []
    assert "did not observe this page as a source" in absent_graph["limitation"]
    assert later_data["change"]["state"] == "changed"
    assert "content_hash" in later_data["change"]["fields"]

    async def remove_source_success_marker() -> None:
        async with seo_session_factory.begin() as session:
            item = await session.get(SEOCrawlRun, later_id)
            assert item is not None
            item.safe_result = {
                key: value
                for key, value in item.safe_result.items()
                if key != "internal_link_evidence_successful_source_urls"
            }

    asyncio.run(remove_source_success_marker())
    unmarked_response = client.get(
        f"{base}/websites/{website_id}/pages/{source_id}/intelligence", headers=HEADERS
    )
    assert unmarked_response.status_code == 200
    unmarked_graph = unmarked_response.json()["data"]["internal_links"]
    assert unmarked_graph["source_page_observed"] is True
    assert unmarked_graph["source_link_evidence_available"] is False
    assert unmarked_graph["availability"] == "partial"
    assert unmarked_graph["mapped_outbound_count"] is None
    assert unmarked_graph["unresolved_outbound_count"] is None
    assert "no per-source link-evidence success marker" in unmarked_graph["limitation"]

    async def verify_history() -> None:
        async with seo_session_factory.begin() as session:
            old_count = await session.scalar(
                select(func.count())
                .select_from(SEOInternalLinkObservation)
                .where(
                    SEOInternalLinkObservation.organization_id == org,
                    SEOInternalLinkObservation.crawl_run_id == run_id,
                )
            )
            assert old_count == 4
            runs = list(
                await session.scalars(
                    select(SEOCrawlRun).where(
                        SEOCrawlRun.organization_id == org,
                        SEOCrawlRun.id.in_((run_id, later_id)),
                    )
                )
            )
            for item in runs:
                item.safe_result = {
                    key: value
                    for key, value in item.safe_result.items()
                    if not key.startswith("internal_link_evidence_")
                }

    asyncio.run(verify_history())
    legacy_response = client.get(
        f"{base}/websites/{website_id}/pages/{source_id}/intelligence", headers=HEADERS
    )
    assert legacy_response.status_code == 200
    assert legacy_response.json()["data"]["internal_links"]["availability"] == "unavailable"
    assert legacy_response.json()["data"]["internal_links"]["outbound"]["items"] == []

    original_knowledge_id = data["content"]["knowledge"]["items"][0]["id"]

    async def remap_location() -> None:
        async with seo_session_factory.begin() as session:
            replacement = Location(
                organization_id=org,
                name="Replacement",
                slug="replacement",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.test",
                is_primary=False,
                version=1,
            )
            session.add(replacement)
            await session.flush()
            item = await session.get(SEOWebsite, website_id)
            assert item is not None
            item.location_id = replacement.id

    asyncio.run(remap_location())
    remapped = client.get(
        f"{base}/websites/{website_id}/pages/{source_id}/intelligence", headers=HEADERS
    )
    assert remapped.status_code == 200, remapped.text
    assert original_knowledge_id in {
        item["id"] for item in remapped.json()["data"]["content"]["knowledge"]["items"]
    }

    async def suspend_entitlement() -> None:
        async with seo_session_factory.begin() as session:
            entitlement = await session.scalar(
                select(ProductEntitlement).where(
                    ProductEntitlement.organization_id == org,
                )
            )
            assert entitlement is not None
            entitlement.status = "suspended"

    asyncio.run(suspend_entitlement())
    denied = client.get(
        f"{base}/websites/{website_id}/pages/{source_id}/intelligence", headers=HEADERS
    )
    assert denied.status_code == 403


@pytest.mark.integration
def test_link_persistence_failure_keeps_other_edges_reconciled(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/seo"
    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(ids["location"]),
            "key": "partial-links",
            "name": "Partial links",
            "canonical_origin": "https://example.test",
        },
    )
    assert website.status_code == 201, website.text
    website_id = UUID(website.json()["data"]["id"])
    crawl = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run"]),
            "seed_paths": ["/target"],
            "max_pages": 2,
            "concurrency": 2,
            "crawl_delay_seconds": 0.1,
            "idempotency_key": "partial-link-persistence",
        },
    )
    assert crawl.status_code == 202, crawl.text
    run_id = UUID(crawl.json()["data"]["id"])

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/target":
            await asyncio.sleep(0.2)
            html = '<html><body><a href="/">Return</a></body></html>'
        else:
            html = '<html><body><a href="/target">Target</a></body></html>'
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    async def execute() -> tuple[UUID, UUID]:
        seo = SEOService(
            http_client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        async with seo_session_factory.begin() as session:
            original_execute = session.execute
            failed = False

            async def execute_with_one_link_failure(
                statement: Any, *args: Any, **kwargs: Any
            ) -> Any:
                nonlocal failed
                if (
                    not failed
                    and getattr(statement, "is_insert", False)
                    and getattr(getattr(statement, "table", None), "name", None)
                    == "seo_internal_link_observations"
                ):
                    failed = True
                    raise RuntimeError("simulated one-page link persistence failure")
                return await original_execute(statement, *args, **kwargs)

            session.execute = execute_with_one_link_failure  # type: ignore[method-assign]
            result, _ = await seo.execute_crawl(session, org, run_id, correlation_id="partial-link")
            assert failed
            assert result.status == "success"
            assert result.safe_result["internal_link_evidence_status"] == "partial"
            assert result.safe_result["internal_link_evidence_count"] == 1
            assert result.safe_result["internal_link_evidence_reconciled_count"] == 1
            assert result.safe_result["internal_link_evidence_failure_count"] == 1
            assert result.safe_result["internal_link_evidence_successful_source_urls"] == [
                "https://example.test/target"
            ]
        async with seo_session_factory() as session:
            source = await session.scalar(
                select(SEOPage).where(
                    SEOPage.website_id == website_id,
                    SEOPage.normalized_url == "https://example.test/",
                )
            )
            target = await session.scalar(
                select(SEOPage).where(
                    SEOPage.website_id == website_id,
                    SEOPage.normalized_url == "https://example.test/target",
                )
            )
            assert source is not None and target is not None
            edge = await session.scalar(
                select(SEOInternalLinkObservation).where(
                    SEOInternalLinkObservation.organization_id == org,
                    SEOInternalLinkObservation.crawl_run_id == run_id,
                )
            )
            assert edge is not None and edge.source_page_id == target.id
            assert edge.target_page_id == source.id and edge.mapping_state == "mapped"
            return source.id, target.id

    source_id, target_id = asyncio.run(execute())
    response = client.get(
        f"{base}/websites/{website_id}/pages/{target_id}/intelligence", headers=HEADERS
    )
    assert response.status_code == 200, response.text
    graph = response.json()["data"]["internal_links"]
    assert graph["availability"] == "partial"
    assert graph["source_page_observed"] is True
    assert graph["source_link_evidence_available"] is True
    assert graph["mapped_outbound_count"] == 1
    assert graph["outbound"]["items"][0]["target_page_id"] == str(source_id)
    failed_response = client.get(
        f"{base}/websites/{website_id}/pages/{source_id}/intelligence", headers=HEADERS
    )
    assert failed_response.status_code == 200, failed_response.text
    failed_graph = failed_response.json()["data"]["internal_links"]
    assert failed_graph["availability"] == "partial"
    assert failed_graph["source_page_observed"] is True
    assert failed_graph["source_link_evidence_available"] is False
    assert failed_graph["mapped_outbound_count"] is None
    assert failed_graph["unresolved_outbound_count"] is None
    assert failed_graph["outbound"]["items"] == []
    assert failed_graph["mapped_inbound_count"] == 1
    assert "was not successfully persisted" in failed_graph["limitation"]


@pytest.mark.integration
def test_link_reconciliation_failure_keeps_persisted_evidence_count(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/seo"
    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(ids["location"]),
            "key": "reconcile-failure",
            "name": "Reconcile failure",
            "canonical_origin": "https://example.test",
        },
    )
    assert website.status_code == 201, website.text
    website_id = UUID(website.json()["data"]["id"])
    crawl = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run"]),
            "seed_paths": ["/"],
            "max_pages": 1,
            "idempotency_key": "reconciliation-failure",
        },
    )
    assert crawl.status_code == 202, crawl.text
    run_id = UUID(crawl.json()["data"]["id"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='<html><body><a href="/missing">Missing</a></body></html>',
            headers={"content-type": "text/html"},
        )

    async def fail_resolver(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated reconciliation failure")

    monkeypatch.setattr("apps.api.app.products.seo.service.PageResolver.load", fail_resolver)

    async def execute() -> UUID:
        seo = SEOService(
            http_client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        async with seo_session_factory.begin() as session:
            run, _ = await seo.execute_crawl(session, org, run_id, correlation_id="reconcile-fail")
            assert run.status == "success"
            assert run.safe_result["internal_link_evidence_status"] == "partial"
            assert run.safe_result["internal_link_evidence_count"] == 1
            assert run.safe_result["internal_link_evidence_reconciled_count"] == 0
            assert run.safe_result["internal_link_evidence_failure_count"] == 1
        async with seo_session_factory() as session:
            edge = await session.scalar(
                select(SEOInternalLinkObservation).where(
                    SEOInternalLinkObservation.organization_id == org,
                    SEOInternalLinkObservation.crawl_run_id == run_id,
                )
            )
            assert edge is not None and edge.mapping_state == "unknown"
            return edge.source_page_id

    page_id = asyncio.run(execute())
    response = client.get(
        f"{base}/websites/{website_id}/pages/{page_id}/intelligence", headers=HEADERS
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["internal_links"]["availability"] == "partial"


@pytest.mark.integration
def test_page_intelligence_workflow_descendants_survive_parent_limits(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/seo"
    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(ids["location"]),
            "key": "workflow-bounds",
            "name": "Workflow bounds",
            "canonical_origin": "https://example.test",
        },
    )
    assert website.status_code == 201, website.text
    website_id = UUID(website.json()["data"]["id"])

    async def populate() -> tuple[UUID, UUID, UUID, UUID, UUID]:
        async with seo_session_factory.begin() as session:
            page = SEOPage(
                organization_id=org,
                website_id=website_id,
                normalized_url="https://example.test/workflow",
                observed_url="https://example.test/workflow",
                normalization_reasons=[],
                robots_directives=[],
                internal_links=[],
                external_links=[],
                structured_data_present=False,
                indexability="indexable",
                technical_issues=[],
                quality_status="clean",
            )
            session.add(page)
            await session.flush()
            now = datetime.now(UTC)
            opportunities = [
                SEOOpportunity(
                    organization_id=org,
                    location_id=ids["location"],
                    website_id=website_id,
                    page_id=page.id,
                    opportunity_type="test_evidence",
                    deduplication_key=f"workflow-limit-{uuid4().hex}",
                    active_marker="active",
                    evidence={},
                    source_versions=[],
                    score_version=1,
                    priority_score=1,
                    score_explanation={},
                    status="identified",
                    version=1,
                    created_at=now + timedelta(seconds=i),
                )
                for i in range(51)
            ]
            session.add_all(opportunities)
            await session.flush()
            revisions = [
                SEORecommendationRevision(
                    organization_id=org,
                    opportunity_id=opportunities[0].id,
                    revision_number=i + 1,
                    proposed_action="Inspect evidence",
                    evidence_references=[],
                    expected_result_hypothesis="Unknown",
                    risk="low",
                    effort="low",
                    status="draft",
                    created_at=now + timedelta(seconds=i),
                )
                for i in range(51)
            ]
            session.add_all(revisions)
            await session.flush()
            tasks = [
                SEOImplementationTask(
                    organization_id=org,
                    recommendation_revision_id=revisions[0].id,
                    workflow_run_id=ids["workflow_run"],
                    target_type="page",
                    target_reference=page.normalized_url,
                    status="pending",
                    created_at=now + timedelta(seconds=i),
                )
                for i in range(51)
            ]
            session.add_all(tasks)
            await session.flush()
            outcome = SEOOutcome(
                organization_id=org,
                implementation_task_id=tasks[0].id,
                baseline_start=now,
                baseline_end=now + timedelta(days=1),
                measurement_start=now + timedelta(days=1),
                measurement_end=now + timedelta(days=2),
                classification="insufficient_evidence",
                metrics={},
                limitations=[],
            )
            session.add(outcome)
            await session.flush()
            return page.id, opportunities[0].id, revisions[0].id, tasks[0].id, outcome.id

    page_id, oldest_opportunity, oldest_revision, oldest_task, outcome_id = asyncio.run(populate())
    response = client.get(
        f"{base}/websites/{website_id}/pages/{page_id}/intelligence", headers=HEADERS
    )
    assert response.status_code == 200, response.text
    workflow = response.json()["data"]["workflow"]
    assert all(
        workflow[key]["has_more"] is True for key in ("opportunities", "recommendations", "tasks")
    )
    assert str(oldest_opportunity) not in {
        item["id"] for item in workflow["opportunities"]["items"]
    }
    assert str(oldest_revision) not in {item["id"] for item in workflow["recommendations"]["items"]}
    assert str(oldest_task) not in {item["id"] for item in workflow["tasks"]["items"]}
    assert workflow["outcomes"]["has_more"] is False
    assert [item["id"] for item in workflow["outcomes"]["items"]] == [str(outcome_id)]


@pytest.mark.integration
def test_concurrent_crawl_fetches_serialize_shared_session_persistence(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/seo"
    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(ids["location"]),
            "key": "concurrent",
            "name": "Concurrent site",
            "canonical_origin": "https://example.test",
        },
    )
    assert website.status_code == 201, website.text
    website_id = UUID(website.json()["data"]["id"])
    crawl = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run"]),
            "seed_paths": ["/broken"],
            "max_pages": 2,
            "concurrency": 2,
            "crawl_delay_seconds": 0.1,
            "idempotency_key": "concurrent-persistence-test",
        },
    )
    assert crawl.status_code == 202, crawl.text
    crawl_run_id = UUID(crawl.json()["data"]["id"])

    class ConcurrentFetchTransport(httpx.AsyncBaseTransport):
        def __init__(self) -> None:
            self.page_requests = 0
            self.both_pages_requested = asyncio.Event()

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            if request.url.path in ("/", "/broken"):
                self.page_requests += 1
                if self.page_requests == 2:
                    self.both_pages_requested.set()
                await asyncio.wait_for(self.both_pages_requested.wait(), timeout=5)
            return mock_handler(request)

    async def scenario() -> None:
        transport = ConcurrentFetchTransport()
        seo_service = SEOService(http_client_factory=lambda: httpx.AsyncClient(transport=transport))
        active_page_writes = 0
        max_active_page_writes = 0
        async with seo_session_factory.begin() as session:
            original_execute = session.execute

            async def delayed_execute(statement: Any, *args: Any, **kwargs: Any) -> Any:
                nonlocal active_page_writes, max_active_page_writes
                if getattr(getattr(statement, "table", None), "name", None) != "seo_pages":
                    return await original_execute(statement, *args, **kwargs)
                active_page_writes += 1
                max_active_page_writes = max(max_active_page_writes, active_page_writes)
                try:
                    await asyncio.sleep(0.05)
                    return await original_execute(statement, *args, **kwargs)
                finally:
                    active_page_writes -= 1

            session.execute = delayed_execute  # type: ignore[method-assign]
            run, _ = await seo_service.execute_crawl(
                session, org, crawl_run_id, correlation_id="concurrent-persistence-test"
            )
            assert run.status == "success", run.stop_reason
            assert run.safe_result["page_failures"] == []

        assert transport.page_requests == 2
        assert max_active_page_writes == 1
        async with seo_session_factory() as session:
            pages = (
                await session.scalars(
                    select(SEOPage).where(
                        SEOPage.organization_id == org, SEOPage.website_id == website_id
                    )
                )
            ).all()
            observations = (
                await session.scalars(
                    select(SEOCrawlPageObservation).where(
                        SEOCrawlPageObservation.organization_id == org,
                        SEOCrawlPageObservation.website_id == website_id,
                        SEOCrawlPageObservation.crawl_run_id == crawl_run_id,
                    )
                )
            ).all()
            assert {page.normalized_url for page in pages} == {
                "https://example.test/",
                "https://example.test/broken",
            }
            assert {item.normalized_url: item.title for item in observations} == {
                "https://example.test/": "Downtown Services",
                "https://example.test/broken": None,
            }

    asyncio.run(scenario())


@pytest.mark.integration
def test_recommendation_approval_execution_and_outcome_flow(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org, location = ids["organization"], ids["location"]
    base = f"/api/v1/organizations/{org}/seo"

    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(location),
            "key": "primary",
            "name": "Example Site",
            "canonical_origin": "https://example.test",
        },
    )
    website_id = website.json()["data"]["id"]

    crawl = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run"]),
            "seed_paths": ["/broken"],
            "max_pages": 2,
            "idempotency_key": "seo-crawl-key-002",
        },
    )
    assert crawl.status_code == 202, crawl.text
    crawl_run_id = UUID(crawl.json()["data"]["id"])
    execute_crawl_directly(seo_session_factory, org, crawl_run_id)

    opportunities = client.get(f"{base}/opportunities", headers=HEADERS).json()["data"]
    opportunity_id = opportunities[0]["id"]

    recommendation = client.post(
        f"{base}/opportunities/{opportunity_id}/recommendations",
        headers=HEADERS,
        json={
            "proposed_action": "Add a descriptive title tag.",
            "evidence_references": ["crawl-run"],
            "expected_result_hypothesis": "Improved click-through rate from search results.",
            "risk": "low",
            "effort": "low",
        },
    )
    assert recommendation.status_code == 201, recommendation.text
    revision_id = recommendation.json()["data"]["id"]
    assert recommendation.json()["data"]["status"] == "awaiting_approval"

    decision = client.post(
        f"{base}/recommendations/{revision_id}/decision", headers=HEADERS, json={"approve": True}
    )
    assert decision.status_code == 200
    assert decision.json()["data"]["status"] == "approved"

    task = client.post(
        f"{base}/recommendations/{revision_id}/tasks",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run_2"]),
            "target_type": "page_title",
            "target_reference": "https://example.test/broken",
        },
    )
    assert task.status_code == 201, task.text
    task_id = task.json()["data"]["id"]
    assert task.json()["data"]["status"] == "pending"

    verify = client.post(
        f"{base}/tasks/{task_id}/verify",
        headers=HEADERS,
        json={"verification_evidence": {"title_present": True}},
    )
    assert verify.status_code == 200
    assert verify.json()["data"]["status"] == "verified"

    now = datetime.now(UTC)
    outcome = client.post(
        f"{base}/tasks/{task_id}/outcome",
        headers=HEADERS,
        json={
            "baseline_start": (now - timedelta(days=14)).isoformat(),
            "baseline_end": (now - timedelta(days=7)).isoformat(),
            "measurement_start": (now - timedelta(days=7)).isoformat(),
            "measurement_end": now.isoformat(),
            "classification": "improved",
            "metrics": {"clicks_delta": 12},
            "limitations": ["short_measurement_window"],
        },
    )
    assert outcome.status_code == 201, outcome.text
    assert outcome.json()["data"]["classification"] == "improved"


@pytest.mark.integration
def test_search_property_requires_connected_connection(
    seo_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = seo_client
    org, location, connection = ids["organization"], ids["location"], ids["connection"]
    base = f"/api/v1/organizations/{org}/seo"

    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(location),
            "key": "primary",
            "name": "Example Site",
            "canonical_origin": "https://example.test",
        },
    )
    website_id = website.json()["data"]["id"]

    unconfigured = client.post(
        f"{base}/websites/{website_id}/search-properties",
        headers=HEADERS,
        json={
            "connection_id": str(uuid4()),
            "external_property_id": "sc-domain:example.test",
            "property_type": "domain",
        },
    )
    assert unconfigured.status_code == 409

    configured = client.post(
        f"{base}/websites/{website_id}/search-properties",
        headers=HEADERS,
        json={
            "connection_id": str(connection),
            "external_property_id": "sc-domain:example.test",
            "property_type": "domain",
        },
    )
    assert configured.status_code == 201, configured.text

    listing = client.get(f"{base}/websites/{website_id}/search-properties", headers=HEADERS)
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 1


@pytest.mark.integration
def test_cross_tenant_website_detail_is_not_found(
    seo_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = seo_client
    other_org = ids["other_organization"]
    response = client.get(
        f"/api/v1/organizations/{other_org}/seo/websites/{uuid4()}", headers=HEADERS
    )
    assert response.status_code in (403, 404)


@pytest.mark.integration
def test_idempotent_crawl_no_duplicate_rows(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org, location = ids["organization"], ids["location"]
    base = f"/api/v1/organizations/{org}/seo"

    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(location),
            "key": "primary",
            "name": "Example Site",
            "canonical_origin": "https://example.test",
        },
    )
    assert website.status_code == 201, website.text
    website_id = UUID(website.json()["data"]["id"])

    payload = {
        "workflow_run_id": str(ids["workflow_run"]),
        "seed_paths": ["/", "/broken"],
        "max_pages": 2,
    }

    first = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={**payload, "idempotency_key": "idem-crawl-001"},
    )
    assert first.status_code == 202, first.text
    first_run_id = UUID(first.json()["data"]["id"])

    second = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run_2"]),
            "seed_paths": ["/", "/broken"],
            "max_pages": 2,
            "idempotency_key": "idem-crawl-002",
        },
    )
    assert second.status_code == 202, second.text
    second_run_id = UUID(second.json()["data"]["id"])

    execute_crawl_directly(seo_session_factory, org, first_run_id)
    execute_crawl_directly(seo_session_factory, org, second_run_id)

    async def counts() -> tuple[int, int, int, int]:
        async with seo_session_factory() as session:
            total_pages = await session.scalar(
                select(func.count()).select_from(SEOPage).where(SEOPage.website_id == website_id)
            )
            unique_urls = await session.scalar(
                select(func.count(func.distinct(SEOPage.normalized_url))).where(
                    SEOPage.website_id == website_id
                )
            )
            active_opps = await session.scalar(
                select(func.count())
                .select_from(SEOOpportunity)
                .where(
                    SEOOpportunity.organization_id == org,
                    SEOOpportunity.active_marker == "active",
                )
            )
            unique_opp_keys = await session.scalar(
                select(func.count(func.distinct(SEOOpportunity.deduplication_key))).where(
                    SEOOpportunity.organization_id == org,
                    SEOOpportunity.active_marker == "active",
                )
            )
            return (
                int(total_pages or 0),
                int(unique_urls or 0),
                int(active_opps or 0),
                int(unique_opp_keys or 0),
            )

    total_pages, unique_urls, active_opps, unique_opp_keys = asyncio.run(counts())
    assert total_pages == 2
    assert total_pages == unique_urls
    assert active_opps == 3
    assert active_opps == unique_opp_keys


@pytest.mark.integration
def test_crawl_run_pages_preserve_historical_evidence(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org, location = ids["organization"], ids["location"]
    base = f"/api/v1/organizations/{org}/seo"
    website_response = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(location),
            "key": "primary",
            "name": "Historical site",
            "canonical_origin": "https://example.test",
        },
    )
    assert website_response.status_code == 201
    website_id = website_response.json()["data"]["id"]

    def queue(idempotency_key: str) -> UUID:
        async def make_workflow() -> UUID:
            async with seo_session_factory.begin() as session:
                template = await session.get(WorkflowRun, ids["workflow_run"])
                assert template is not None
                workflow = WorkflowRun(
                    organization_id=org,
                    location_id=location,
                    workflow_version_id=template.workflow_version_id,
                    product_key="seo",
                    trigger_type="manual",
                    idempotency_key=f"workflow-{idempotency_key}",
                    request_hash="history-test",
                    input_document={},
                    correlation_id="history-test",
                )
                session.add(workflow)
                await session.flush()
                return workflow.id

        workflow_id = asyncio.run(make_workflow())
        response = client.post(
            f"{base}/websites/{website_id}/crawl",
            headers=HEADERS,
            json={
                "workflow_run_id": str(workflow_id),
                "max_pages": 1,
                "idempotency_key": idempotency_key,
            },
        )
        assert response.status_code == 202, response.text
        return UUID(response.json()["data"]["id"])

    def execute(run_id: UUID, title: str) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text=f"<html><head><title>{title}</title></head><body><h1>{title}</h1></body></html>",
                headers={"content-type": "text/html"},
            )

        async def run() -> None:
            seo_service = SEOService(
                http_client_factory=lambda: httpx.AsyncClient(
                    transport=httpx.MockTransport(handler)
                )
            )
            async with seo_session_factory.begin() as session:
                await seo_service.execute_crawl(session, org, run_id, correlation_id="history-test")
                # Terminal retry must retain the one observation for this run.
                await seo_service.execute_crawl(
                    session, org, run_id, correlation_id="history-retry"
                )

        asyncio.run(run())

    legacy_id = queue("legacy-history")

    async def mark_legacy() -> None:
        async with seo_session_factory.begin() as session:
            legacy_run = await session.get(SEOCrawlRun, legacy_id)
            assert legacy_run is not None
            legacy_run.safe_result = {}

    asyncio.run(mark_legacy())
    # Pre-capability shape: no marker and no historical observations.
    first_id = queue("history-a")
    execute(first_id, "Historical A")
    second_id = queue("history-b")
    execute(second_id, "Historical B")

    zero_id = queue("history-zero")

    def disallow_all(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        raise AssertionError("robots exclusion should prevent page fetches")

    async def execute_zero() -> None:
        seo_service = SEOService(
            http_client_factory=lambda: httpx.AsyncClient(
                transport=httpx.MockTransport(disallow_all)
            )
        )
        async with seo_session_factory.begin() as session:
            await seo_service.execute_crawl(session, org, zero_id, correlation_id="zero-test")

    asyncio.run(execute_zero())

    first = client.get(f"{base}/crawl-runs/{first_id}/pages", headers=HEADERS)
    second = client.get(f"{base}/crawl-runs/{second_id}/pages", headers=HEADERS)
    legacy = client.get(f"{base}/crawl-runs/{legacy_id}/pages", headers=HEADERS)
    zero = client.get(f"{base}/crawl-runs/{zero_id}/pages", headers=HEADERS)
    assert first.status_code == second.status_code == legacy.status_code == zero.status_code == 200
    assert first.json()["meta"]["evidence_status"] == "available"
    assert second.json()["meta"]["evidence_status"] == "available"
    assert [row["title"] for row in first.json()["data"]] == ["Historical A"]
    assert [row["title"] for row in second.json()["data"]] == ["Historical B"]
    assert legacy.json()["data"] == []
    assert legacy.json()["meta"]["evidence_status"] == "unavailable_legacy_run"
    assert zero.json()["data"] == []
    assert zero.json()["meta"]["evidence_status"] == "available"

    async def verify_inventory() -> None:
        async with seo_session_factory() as session:
            page = await session.scalar(
                select(SEOPage).where(
                    SEOPage.organization_id == org, SEOPage.website_id == UUID(website_id)
                )
            )
            assert page is not None and page.title == "Historical B"
            for run_id in (first_id, second_id):
                count = await session.scalar(
                    select(func.count())
                    .select_from(SEOCrawlPageObservation)
                    .where(
                        SEOCrawlPageObservation.organization_id == org,
                        SEOCrawlPageObservation.crawl_run_id == run_id,
                    )
                )
                assert count == 1

    asyncio.run(verify_inventory())


@pytest.mark.integration
def test_cross_tenant_crawl_run_and_pages_not_found(
    seo_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = seo_client
    org, location = ids["organization"], ids["location"]
    other_org = ids["other_organization"]
    base = f"/api/v1/organizations/{org}/seo"

    website = client.post(
        f"{base}/websites",
        headers=HEADERS,
        json={
            "location_id": str(location),
            "key": "primary",
            "name": "Example Site",
            "canonical_origin": "https://example.test",
        },
    )
    website_id = website.json()["data"]["id"]

    crawl = client.post(
        f"{base}/websites/{website_id}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run"]),
            "seed_paths": ["/broken"],
            "max_pages": 1,
            "idempotency_key": "tenant-crawl-001",
        },
    )
    assert crawl.status_code == 202, crawl.text
    crawl_run_id = crawl.json()["data"]["id"]

    other_base = f"/api/v1/organizations/{other_org}/seo"
    run_resp = client.get(f"{other_base}/crawl-runs/{crawl_run_id}", headers=HEADERS)
    assert run_resp.status_code in (403, 404)

    pages_resp = client.get(f"{other_base}/crawl-runs/{crawl_run_id}/pages", headers=HEADERS)
    assert pages_resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# SC9D — over-length content truncated, over-length URL skipped, crawl survives
# ---------------------------------------------------------------------------


OVERLONG_TITLE = "This is an absurdly long title " * 200  # ~6200 chars
OVERLONG_META = "This is an absurdly long meta description " * 200  # ~7000 chars
OVERLONG_H1 = "This is an absurdly long h1 heading " * 200  # ~6000 chars

_OVERLONG_HTML = (
    f"<html><head><title>{OVERLONG_TITLE}</title>"
    f'<meta name="description" content="{OVERLONG_META}">'
    f'<link rel="canonical" href="https://example.test/">'
    "</head><body>"
    f"<h1>{OVERLONG_H1}</h1>"
    '<a href="/ok-page">OK</a>'
    "</body></html>"
)


@pytest.mark.integration
def test_crawl_survives_overlength_content_and_truncates_with_marker(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Regression: over-length title, meta_description, and h1 must not abort the
    crawl. Values are truncated at ingest with an explicit marker and the crawl
    completes successfully. This test would fail on the current main branch
    (StringDataRightTruncationError on insert into seo_pages)."""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ok-page":
            return httpx.Response(
                200,
                text=GOOD_PAGE_HTML,
                headers={"content-type": "text/html"},
                request=request,
            )
        return httpx.Response(
            200, text=_OVERLONG_HTML, headers={"content-type": "text/html"}, request=request
        )

    def custom_http_client_factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    async def _run() -> None:
        seo_service = SEOService(http_client_factory=custom_http_client_factory)

        async with seo_session_factory.begin() as session:
            org = Organization(
                name="SC9D Org",
                slug="sc9d-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(org)
            await session.flush()

            website = SEOWebsite(
                organization_id=org.id,
                key="sc9d-site",
                name="SC9D Site",
                canonical_origin="https://example.test",
                status="active",
                ownership_status="verified",
                version=1,
            )
            session.add(website)
            await session.flush()

            workflow_def = WorkflowDefinition(key="sc9d.crawl", name="SC9D Crawl", owner="seo")
            session.add(workflow_def)
            await session.flush()
            workflow_ver = WorkflowVersion(
                definition_id=workflow_def.id,
                version=1,
                status="approved",
                input_schema={},
                output_schema={},
                step_specification=[],
                retry_policy={},
                timeout_seconds=60,
            )
            session.add(workflow_ver)
            await session.flush()
            workflow_run = WorkflowRun(
                organization_id=org.id,
                workflow_version_id=workflow_ver.id,
                product_key="seo",
                trigger_type="manual",
                idempotency_key="sc9d-crawl-001",
                request_hash="sc9d-hash",
                input_document={},
                correlation_id="sc9d-test",
            )
            session.add(workflow_run)
            await session.flush()

            crawl_run = SEOCrawlRun(
                organization_id=org.id,
                website_id=website.id,
                workflow_run_id=workflow_run.id,
                idempotency_key="sc9d-crawl-001",
                status="queued",
                max_pages=3,
                safe_result={},
            )
            session.add(crawl_run)
            await session.flush()

            org_id = org.id
            website_id = website.id
            crawl_run_id = crawl_run.id

        async with seo_session_factory.begin() as session:
            crawl_run_ret, _ = await seo_service.execute_crawl(
                session, org_id, crawl_run_id, correlation_id="sc9d-test"
            )

            assert crawl_run_ret.status == "success", (
                f"expected success, got {crawl_run_ret.status}: {crawl_run_ret.stop_reason}"
            )

            page_row = await session.scalar(
                select(SEOPage).where(
                    SEOPage.organization_id == org_id,
                    SEOPage.website_id == website_id,
                    SEOPage.normalized_url == "https://example.test/",
                )
            )
            assert page_row is not None, "overlong landing page must be persisted"

            assert page_row.title is not None
            assert len(page_row.title) == 2000
            assert page_row.title.endswith("…[truncated]")
            assert "title_truncated" in page_row.technical_issues

            assert page_row.meta_description is not None
            assert len(page_row.meta_description) == 2000
            assert page_row.meta_description.endswith("…[truncated]")
            assert "meta_description_truncated" in page_row.technical_issues

            assert page_row.h1 is not None
            assert len(page_row.h1) == 2000
            assert page_row.h1.endswith("…[truncated]")
            assert "h1_truncated" in page_row.technical_issues

            assert len(crawl_run_ret.safe_result["page_failures"]) == 0  # type: ignore[arg-type]

    asyncio.run(_run())
