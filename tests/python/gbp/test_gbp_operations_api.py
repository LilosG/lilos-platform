"""Production-capable GBP operations route, audit, notification, and isolation tests."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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
from apps.api.app.notifications.models import NotificationEvent
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation


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
        key_id="gbp-operations-test-key",
    )


def run_db[T](postgresql_test_url: str, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Run one unit of DB work against a fresh, short-lived engine.

    Each call gets its own engine bound to the event loop `asyncio.run` creates
    for this call, then disposes it before returning. This avoids reusing
    asyncpg connections across separate event loops, which breaks connection
    cleanup independent of the code under test.
    """

    async def scenario() -> T:
        engine = create_async_engine(postgresql_test_url)
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                return await work(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


def _notification_event_exists(
    postgresql_test_url: str, organization_id: UUID, event_type: str
) -> bool:
    async def work(session: AsyncSession) -> bool:
        return (
            await session.scalar(
                select(NotificationEvent).where(
                    NotificationEvent.organization_id == organization_id,
                    NotificationEvent.event_type == event_type,
                )
            )
        ) is not None

    return run_db(postgresql_test_url, work)


HEADERS = {"Authorization": "Bearer fabricated.token"}


@pytest.fixture
def gbp_operations_client(
    postgresql_test_url: str,
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with gbp_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="gbp-operations-api-catalog")
            organization = Organization(
                name="GBP Operations Test Org",
                slug="gbp-operations-test-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_organization = Organization(
                name="GBP Operations Other Org",
                slug="gbp-operations-other-org",
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
                correlation_id="gbp-operations-api-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="gbp-operations-api-owner",
            )

            provider = Provider(
                key="google_business_profile",
                name="Google Business Profile",
                status="active",
                capabilities=["profile.read", "profile.write"],
            )
            session.add(provider)
            await session.flush()
            connection = IntegrationConnection(
                organization_id=organization.id,
                provider_id=provider.id,
                external_account_reference="accounts/123",
                status="connected",
            )
            session.add(connection)
            await session.flush()
            gbp_account = GBPAccount(
                organization_id=organization.id,
                connection_id=connection.id,
                external_account_id="accounts/123",
                display_name="Example Business",
                status="discovered",
            )
            session.add(gbp_account)
            await session.flush()
            gbp_location = GBPLocation(
                organization_id=organization.id,
                location_id=location.id,
                connection_id=connection.id,
                account_id=gbp_account.id,
                external_location_id="locations/456",
                business_name="Example Business - Downtown",
                mapping_status="confirmed",
                write_enabled=True,
                confirmed_by_user_id=profile.id,
                confirmed_at=datetime.now(UTC),
            )
            session.add(gbp_location)
            await session.flush()

            workflow_definition = WorkflowDefinition(
                key="gbp.publish_post", name="Publish GBP post", owner="gbp"
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
                product_key="gbp",
                trigger_type="manual",
                idempotency_key="gbp-operations-test-workflow-run-001",
                request_hash="deterministic-request-hash",
                input_document={},
                correlation_id="gbp-operations-test-workflow",
            )
            session.add(workflow_run)
            await session.flush()

            identifiers = {
                "organization": organization.id,
                "other_organization": other_organization.id,
                "location": location.id,
                "assigned_subject": profile.auth_user_id,
                "gbp_location": gbp_location.id,
                "workflow_run": workflow_run.id,
            }
            return claims(profile.auth_user_id), identifiers

    verified, identifiers = asyncio.run(populate())
    verifier = FakeVerifier(verified)
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, identifiers


@pytest.mark.integration
def test_capability_snapshot_change_set_and_completeness_flow(
    postgresql_test_url: str,
    gbp_operations_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = gbp_operations_client
    org, location, gbp_location = ids["organization"], ids["location"], ids["gbp_location"]
    base = f"/api/v1/organizations/{org}/locations/{location}/gbp/operations"

    snapshot = client.post(
        f"{base}/locations/{gbp_location}/capability-snapshots",
        headers=HEADERS,
        json={
            "capabilities": {
                "categories": {"readable": True, "writable": True},
                "special_hours": {"readable": True, "writable": True},
                "q_and_a": {"readable": False, "writable": False, "reason": "not supported"},
            },
            "observed_at": datetime.now(UTC).isoformat(),
        },
    )
    assert snapshot.status_code == 201, snapshot.text
    assert snapshot.headers["Cache-Control"] == "no-store"

    completeness = client.get(f"{base}/locations/{gbp_location}/completeness", headers=HEADERS)
    assert completeness.status_code == 200

    change_set = client.post(
        f"{base}/locations/{gbp_location}/change-sets",
        headers=HEADERS,
        json={
            "capability_key": "categories",
            "field_changes": [{"field": "primary_category", "value": "plumber"}],
            "evidence": {"source": "manual_review"},
            "risk": "low",
            "idempotency_key": "gbp-change-set-key-001",
        },
    )
    assert change_set.status_code == 201, change_set.text
    change_set_id = change_set.json()["data"]["id"]
    assert change_set.json()["data"]["status"] == "awaiting_approval"
    assert (
        _notification_event_exists(postgresql_test_url, org, "gbp.change_set.awaiting_approval")
        is True
    )

    unavailable = client.post(
        f"{base}/locations/{gbp_location}/change-sets",
        headers=HEADERS,
        json={
            "capability_key": "q_and_a",
            "field_changes": [{"field": "answer", "value": "yes"}],
            "idempotency_key": "gbp-change-set-key-002",
        },
    )
    assert unavailable.status_code == 409

    decision = client.post(
        f"{base}/change-sets/{change_set_id}/decision", headers=HEADERS, json={"approve": True}
    )
    assert decision.status_code == 200
    assert decision.json()["data"]["status"] == "approved"

    listing = client.get(f"{base}/locations/{gbp_location}/change-sets", headers=HEADERS)
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 1

    audit = client.get(f"{base}/locations/{gbp_location}/audit", headers=HEADERS)
    assert audit.status_code == 200
    event_types = {event["event_type"] for event in audit.json()["data"]}
    assert {
        "gbp.capability_snapshot.recorded",
        "gbp.change_set.proposed",
        "gbp.change_set.decided",
    } <= event_types


@pytest.mark.integration
def test_special_hours_reject_overlap_and_approve_valid(
    gbp_operations_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = gbp_operations_client
    org, location, gbp_location = ids["organization"], ids["location"], ids["gbp_location"]
    base = f"/api/v1/organizations/{org}/locations/{location}/gbp/operations"

    overlapping = client.post(
        f"{base}/locations/{gbp_location}/special-hours",
        headers=HEADERS,
        json={
            "service_date": "2026-12-25",
            "periods": [
                {"opens": "09:00:00", "closes": "13:00:00"},
                {"opens": "12:00:00", "closes": "17:00:00"},
            ],
            "source": "manual",
        },
    )
    assert overlapping.status_code == 409

    valid = client.post(
        f"{base}/locations/{gbp_location}/special-hours",
        headers=HEADERS,
        json={
            "service_date": "2026-12-25",
            "periods": [{"opens": "09:00:00", "closes": "17:00:00"}],
            "source": "manual",
        },
    )
    assert valid.status_code == 201, valid.text
    special_hours_id = valid.json()["data"]["id"]

    decision = client.post(
        f"{base}/special-hours/{special_hours_id}/decision", headers=HEADERS, json={"approve": True}
    )
    assert decision.status_code == 200
    assert decision.json()["data"]["status"] == "approved"

    listing = client.get(f"{base}/locations/{gbp_location}/special-hours", headers=HEADERS)
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 1


@pytest.mark.integration
def test_media_proposal_and_post_publish_flow(
    gbp_operations_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = gbp_operations_client
    org, location, gbp_location, workflow_run = (
        ids["organization"],
        ids["location"],
        ids["gbp_location"],
        ids["workflow_run"],
    )
    base = f"/api/v1/organizations/{org}/locations/{location}/gbp/operations"

    media = client.post(
        f"{base}/locations/{gbp_location}/media",
        headers=HEADERS,
        json={
            "media_type": "photo",
            "source_reference": "https://example.invalid/photo.jpg",
            "rights_authority": "Business owner upload",
            "idempotency_key": "gbp-media-key-001",
        },
    )
    assert media.status_code == 201, media.text
    assert media.json()["data"]["status"] == "awaiting_approval"

    media_listing = client.get(f"{base}/locations/{gbp_location}/media", headers=HEADERS)
    assert media_listing.status_code == 200
    assert len(media_listing.json()["data"]) == 1

    post = client.post(
        f"{base}/locations/{gbp_location}/posts",
        headers=HEADERS,
        json={"post_type": "standard", "content": "We are open for the holidays!"},
    )
    assert post.status_code == 201, post.text
    revision_id = post.json()["data"]["id"]
    assert post.json()["data"]["status"] == "awaiting_approval"

    decision = client.post(
        f"{base}/posts/{revision_id}/decision", headers=HEADERS, json={"approve": True}
    )
    assert decision.status_code == 200
    assert decision.json()["data"]["status"] == "approved"

    publish = client.post(
        f"{base}/posts/{revision_id}/publish",
        headers=HEADERS,
        json={"workflow_run_id": str(workflow_run), "idempotency_key": "gbp-post-publish-key-001"},
    )
    assert publish.status_code == 202, publish.text
    assert publish.json()["data"]["status"] == "reserved"

    posts_listing = client.get(f"{base}/locations/{gbp_location}/posts", headers=HEADERS)
    assert posts_listing.status_code == 200
    assert len(posts_listing.json()["data"]) == 1


@pytest.mark.integration
def test_suspension_case_report_generates_notification(
    postgresql_test_url: str,
    gbp_operations_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = gbp_operations_client
    org, location, gbp_location = ids["organization"], ids["location"], ids["gbp_location"]
    base = f"/api/v1/organizations/{org}/locations/{location}/gbp/operations"

    report = client.post(
        f"{base}/locations/{gbp_location}/suspension-cases",
        headers=HEADERS,
        json={
            "provider_status": "SUSPENDED",
            "evidence_references": ["support-ticket-123"],
        },
    )
    assert report.status_code == 201, report.text
    assert report.json()["data"]["status"] == "open"
    assert (
        _notification_event_exists(postgresql_test_url, org, "gbp.suspension_case.reported") is True
    )

    listing = client.get(f"{base}/locations/{gbp_location}/suspension-cases", headers=HEADERS)
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 1


@pytest.mark.integration
def test_cross_tenant_change_set_list_is_not_found(
    gbp_operations_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = gbp_operations_client
    other_org, location = ids["other_organization"], ids["location"]
    base = f"/api/v1/organizations/{other_org}/locations/{location}/gbp/operations"
    response = client.get(f"{base}/locations/{uuid4()}/change-sets", headers=HEADERS)
    assert response.status_code in (403, 404)
