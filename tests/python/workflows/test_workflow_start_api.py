"""Production-capable shared workflow-start route, idempotency, and isolation tests."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
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
from apps.api.app.execution.errors import (
    WorkflowRunNotAvailableError,
    WorkflowRunNotFoundError,
    WorkflowRunTypeMismatchError,
)
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.main import create_app
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


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
        key_id="workflow-start-test-key",
    )


def run_db[T](postgresql_test_url: str, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def scenario() -> T:
        engine = create_async_engine(postgresql_test_url)
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                return await work(session)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


HEADERS = {"Authorization": "Bearer fabricated.token"}


class WorkflowClientContext:
    def __init__(
        self,
        client: TestClient,
        verifier: FakeVerifier,
        no_permission_claims: VerifiedProviderClaims,
        ids: dict[str, UUID],
    ) -> None:
        self.client = client
        self.verifier = verifier
        self.no_permission_claims = no_permission_claims
        self.ids = ids


@pytest.fixture
def workflow_client(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[WorkflowClientContext, None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, VerifiedProviderClaims, dict[str, UUID]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with workflows_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="workflow-start-api-catalog")
            organization = Organization(
                name="Workflow Start Test Org",
                slug="workflow-start-test-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_organization = Organization(
                name="Workflow Start Other Org",
                slug="workflow-start-other-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            owner_profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            no_permission_profile = UserProfile(
                auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1
            )
            session.add_all(
                [organization, other_organization, owner_profile, no_permission_profile]
            )
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
            other_location = Location(
                organization_id=other_organization.id,
                name="Other Downtown",
                slug="other-downtown",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=True,
                version=1,
            )
            session.add_all([location, other_location])
            await session.flush()

            owner_membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(
                    user_profile_id=owner_profile.id, membership_type=MembershipType.CLIENT
                ),
                correlation_id="workflow-start-api-owner-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                organization.id,
                owner_membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="workflow-start-api-owner-assignment",
            )

            # A membership with no role assignment at all: no permissions granted.
            await access.create_membership(
                session,
                organization.id,
                MembershipCreate(
                    user_profile_id=no_permission_profile.id,
                    membership_type=MembershipType.CLIENT,
                ),
                correlation_id="workflow-start-api-no-permission-member",
            )

            identifiers = {
                "organization": organization.id,
                "other_organization": other_organization.id,
                "location": location.id,
                "other_location": other_location.id,
            }
            return (
                claims(owner_profile.auth_user_id),
                claims(no_permission_profile.auth_user_id),
                identifiers,
            )

    owner_claims, no_permission_claims, identifiers = asyncio.run(populate())
    verifier = FakeVerifier(owner_claims)
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield WorkflowClientContext(client, verifier, no_permission_claims, identifiers)


def _workflow_run_status(postgresql_test_url: str, run_id: UUID) -> str | None:
    async def work(session: AsyncSession) -> str | None:
        run = await session.get(WorkflowRun, run_id)
        return run.status if run else None

    return run_db(postgresql_test_url, work)


@pytest.mark.integration
def test_start_workflow_run_creates_persisted_run(workflow_client: WorkflowClientContext) -> None:
    client, ids = workflow_client.client, workflow_client.ids
    org, location = ids["organization"], ids["location"]

    response = client.post(
        f"/api/v1/organizations/{org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"location_id": str(location), "idempotency_key": "workflow-start-key-001"},
    )
    assert response.status_code == 201, response.text
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["status"] == "queued"
    assert data["product_key"] == "content"
    assert UUID(data["workflow_run_id"])


@pytest.mark.integration
def test_repeat_request_with_same_idempotency_key_is_idempotent(
    workflow_client: WorkflowClientContext,
) -> None:
    client, org = workflow_client.client, workflow_client.ids["organization"]

    first = client.post(
        f"/api/v1/organizations/{org}/workflows/seo.crawl_or_analysis/runs",
        headers=HEADERS,
        json={"idempotency_key": "workflow-start-key-002"},
    )
    second = client.post(
        f"/api/v1/organizations/{org}/workflows/seo.crawl_or_analysis/runs",
        headers=HEADERS,
        json={"idempotency_key": "workflow-start-key-002"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["workflow_run_id"] == second.json()["data"]["workflow_run_id"]


@pytest.mark.integration
def test_unknown_workflow_key_rejected(workflow_client: WorkflowClientContext) -> None:
    client, org = workflow_client.client, workflow_client.ids["organization"]
    response = client.post(
        f"/api/v1/organizations/{org}/workflows/not.a.real.workflow/runs",
        headers=HEADERS,
        json={"idempotency_key": "workflow-start-key-003"},
    )
    assert response.status_code == 404


@pytest.mark.integration
def test_location_from_other_organization_rejected(workflow_client: WorkflowClientContext) -> None:
    client, ids = workflow_client.client, workflow_client.ids
    org, other_location = ids["organization"], ids["other_location"]
    response = client.post(
        f"/api/v1/organizations/{org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"location_id": str(other_location), "idempotency_key": "workflow-start-key-004"},
    )
    assert response.status_code == 404


@pytest.mark.integration
def test_permission_denied_without_workflows_execute(
    workflow_client: WorkflowClientContext,
) -> None:
    client, org = workflow_client.client, workflow_client.ids["organization"]
    previous = workflow_client.verifier.result
    workflow_client.verifier.result = workflow_client.no_permission_claims
    try:
        response = client.post(
            f"/api/v1/organizations/{org}/workflows/content.publish/runs",
            headers=HEADERS,
            json={"idempotency_key": "workflow-start-key-005"},
        )
        assert response.status_code == 403
    finally:
        workflow_client.verifier.result = previous


@pytest.mark.integration
def test_cross_organization_workflow_run_cannot_be_consumed(
    postgresql_test_url: str,
    workflow_client: WorkflowClientContext,
) -> None:
    """Confirms tenant isolation at the two layers where it can be defeated.

    First, starting a run scoped to an organization the caller does not
    belong to is denied by authorization before any row could be produced.
    Second — and this is the layer the workflow_run_id defect actually lived
    in — even a real, persisted run from one organization is rejected by the
    shared consumption contract when resolved under a different
    organization_id, independent of any HTTP-layer authorization check.
    """
    client, ids = workflow_client.client, workflow_client.ids
    org, other_org = ids["organization"], ids["other_organization"]

    other_run = client.post(
        f"/api/v1/organizations/{other_org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"idempotency_key": "workflow-start-key-006"},
    )
    assert other_run.status_code in (403, 404)

    started = client.post(
        f"/api/v1/organizations/{org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"idempotency_key": "workflow-start-key-006b"},
    )
    run_id = UUID(started.json()["data"]["workflow_run_id"])

    async def resolve_cross_tenant(session: AsyncSession) -> None:
        with pytest.raises(WorkflowRunNotFoundError):
            await ExecutionService().resolve_for_consumption(
                session, other_org, run_id, "content.publish"
            )

    run_db(postgresql_test_url, resolve_cross_tenant)


@pytest.mark.integration
def test_wrong_workflow_type_rejected_on_consumption(
    postgresql_test_url: str,
    workflow_client: WorkflowClientContext,
) -> None:
    client, org = workflow_client.client, workflow_client.ids["organization"]

    started = client.post(
        f"/api/v1/organizations/{org}/workflows/seo.crawl_or_analysis/runs",
        headers=HEADERS,
        json={"idempotency_key": "workflow-start-key-007"},
    )
    run_id = UUID(started.json()["data"]["workflow_run_id"])

    async def resolve_wrong_type(session: AsyncSession) -> None:
        with pytest.raises(WorkflowRunTypeMismatchError):
            await ExecutionService().resolve_for_consumption(
                session, org, run_id, "content.publish"
            )

    run_db(postgresql_test_url, resolve_wrong_type)


@pytest.mark.integration
def test_completed_workflow_run_cannot_be_reused(
    postgresql_test_url: str,
    workflow_client: WorkflowClientContext,
) -> None:
    client, org = workflow_client.client, workflow_client.ids["organization"]

    started = client.post(
        f"/api/v1/organizations/{org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"idempotency_key": "workflow-start-key-008"},
    )
    run_id = UUID(started.json()["data"]["workflow_run_id"])

    async def mark_completed(session: AsyncSession) -> None:
        run = await session.get(WorkflowRun, run_id)
        assert run is not None
        run.status = "completed"
        await session.commit()

    run_db(postgresql_test_url, mark_completed)
    assert _workflow_run_status(postgresql_test_url, run_id) == "completed"

    async def resolve_stale(session: AsyncSession) -> None:
        with pytest.raises(WorkflowRunNotAvailableError):
            await ExecutionService().resolve_for_consumption(
                session, org, run_id, "content.publish"
            )

    run_db(postgresql_test_url, resolve_stale)
