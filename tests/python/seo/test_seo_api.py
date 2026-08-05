"""Production-capable SEO route, crawl, audit, and isolation tests."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
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
        return httpx.Response(200, text=BROKEN_PAGE_HTML)
    return httpx.Response(200, text=GOOD_PAGE_HTML)


def mock_http_client_factory() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))


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
    assert crawl.json()["data"]["status"] == "completed"
    assert crawl.json()["data"]["safe_result"]["pages_crawled"] == 2
    opportunities = crawl.json()["data"]["opportunities_created"]
    assert len(opportunities) > 0
    assert {"missing_title", "missing_meta_description", "missing_h1"} & {
        item["opportunity_type"] for item in opportunities
    }

    listing = client.get(f"{base}/opportunities", headers=HEADERS)
    assert listing.status_code == 200
    assert listing.headers["Cache-Control"] == "no-store"
    assert len(listing.json()["data"]) == len(opportunities)

    summary = client.get(f"{base}/summary", headers=HEADERS)
    assert summary.status_code == 200
    assert summary.json()["data"]["website_count"] == 1

    gaps = client.get(f"{base}/websites/{website_id}/landing-page-gaps", headers=HEADERS)
    assert gaps.status_code == 200
    assert any(gap["location_id"] == str(location) for gap in gaps.json()["data"])

    audit = client.get(f"{base}/websites/{website_id}/audit", headers=HEADERS)
    assert audit.status_code == 200
    event_types = {event["event_type"] for event in audit.json()["data"]}
    assert {"seo.website.created", "seo.crawl.completed"} <= event_types


@pytest.mark.integration
def test_recommendation_approval_execution_and_outcome_flow(
    seo_client: tuple[TestClient, dict[str, UUID]],
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
            "max_pages": 1,
            "idempotency_key": "seo-crawl-key-002",
        },
    )
    opportunity_id = crawl.json()["data"]["opportunities_created"][0]["id"]

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
