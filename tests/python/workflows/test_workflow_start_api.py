"""Production-capable shared workflow-start route, idempotency, and isolation tests."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete as sqla_delete
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
from apps.api.app.execution.errors import (
    WorkflowRunNotAvailableError,
    WorkflowRunNotFoundError,
    WorkflowRunTypeMismatchError,
)
from apps.api.app.execution.models import Job, WorkflowRun
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


# ── Hotfix A: reservation-mode regression tests ──────────────────────────


@pytest.mark.integration
def test_api_workflow_reservation_creates_run_without_execution_job(
    postgresql_test_url: str,
    workflow_client: WorkflowClientContext,
) -> None:
    """Prove that the shared workflow-start API creates a WorkflowRun
    without enqueueing a workflow.execute Job, so the product endpoint
    that called resolve_for_consumption owns the run exclusively."""

    client, org = workflow_client.client, workflow_client.ids["organization"]

    response = client.post(
        f"/api/v1/organizations/{org}/workflows/seo.crawl_or_analysis/runs",
        headers=HEADERS,
        json={"idempotency_key": "reservation-no-worker-001"},
    )
    assert response.status_code == 201
    run_id = UUID(response.json()["data"]["workflow_run_id"])

    async def assert_no_job(session: AsyncSession) -> None:
        jobs = (
            (
                await session.execute(
                    select(Job).where(
                        Job.organization_id == org,
                        Job.workflow_run_id == run_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(jobs) == 0

    run_db(postgresql_test_url, assert_no_job)


@pytest.mark.integration
def test_reserved_run_consumable_through_resolve_for_consumption(
    postgresql_test_url: str,
    workflow_client: WorkflowClientContext,
) -> None:
    """A WorkflowRun created via the reservation API (enqueue_job=False)
    remains consumable through resolve_for_consumption without a worker
    having raced ahead."""

    client, org = workflow_client.client, workflow_client.ids["organization"]

    response = client.post(
        f"/api/v1/organizations/{org}/workflows/gbp.publish_change/runs",
        headers=HEADERS,
        json={"idempotency_key": "reservation-consumable-002"},
    )
    run_id = UUID(response.json()["data"]["workflow_run_id"])

    async def consume(session: AsyncSession) -> None:
        run = await ExecutionService().resolve_for_consumption(
            session, org, run_id, "gbp.publish_change"
        )
        assert run.status == "running"
        await session.commit()

    run_db(postgresql_test_url, consume)

    assert _workflow_run_status(postgresql_test_url, run_id) == "running"


@pytest.mark.integration
def test_scheduled_dispatch_still_creates_execution_job(
    postgresql_test_url: str,
    workflow_client: WorkflowClientContext,
) -> None:
    """Schedule-triggered runs (through dispatch_due_schedule → submit)
    must continue enqueueing a workflow.execute Job because the worker
    is the intended consumer."""

    org = workflow_client.ids["organization"]

    async def dispatch(session: AsyncSession) -> None:
        from datetime import UTC

        from apps.api.app.execution.contracts import ScheduleCreate

        now = datetime.now(UTC)
        exec_svc = ExecutionService()
        schedule = await exec_svc.create_schedule(
            session,
            org,
            ScheduleCreate(
                workflow_key="reviews.publish_response",
                key="dispatch-test-schedule",
                cron_expression="0 6 * * *",
                timezone="America/Chicago",
                next_run_at=now,
            ),
            correlation_id="scheduled-dispatch-test",
        )
        await session.flush()
        # Clear pre-existing jobs from other tests or prior runs.
        await session.execute(sqla_delete(Job).where(Job.organization_id == org))
        await session.flush()
        # Advance the schedule so dispatch_due_schedule picks it up.
        schedule.next_run_at = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
        await session.flush()

        run = await exec_svc.dispatch_due_schedule(
            session, correlation_id="scheduled-dispatch-test"
        )
        assert run is not None
        jobs = (
            (
                await session.execute(
                    select(Job).where(
                        Job.organization_id == org,
                        Job.workflow_run_id == run.id,
                        Job.job_type == "workflow.execute",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(jobs) == 1
        await session.commit()

    run_db(postgresql_test_url, dispatch)


@pytest.mark.integration
def test_seo_crawl_can_execute_without_worker_race(
    postgresql_test_url: str,
    workflow_client: WorkflowClientContext,
) -> None:
    """An end-to-end SEO crawl sequence: reserve a run through the API,
    then consume it through resolve_for_consumption (simulating the
    product endpoint). Verifies no worker job exists to race."""

    client, org = (
        workflow_client.client,
        workflow_client.ids["organization"],
    )

    response = client.post(
        f"/api/v1/organizations/{org}/workflows/seo.crawl_or_analysis/runs",
        headers=HEADERS,
        json={"idempotency_key": "seo-e2e-no-worker-003"},
    )
    assert response.status_code == 201
    run_id = UUID(response.json()["data"]["workflow_run_id"])

    async def seo_consume(session: AsyncSession) -> None:
        jobs_before = (
            (
                await session.execute(
                    select(Job).where(
                        Job.organization_id == org,
                        Job.workflow_run_id == run_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(jobs_before) == 0

        run = await ExecutionService().resolve_for_consumption(
            session, org, run_id, "seo.crawl_or_analysis"
        )
        assert run.status == "running"
        assert run.organization_id == org
        assert run.workflow_version_id is not None
        await session.commit()

    run_db(postgresql_test_url, seo_consume)
    assert _workflow_run_status(postgresql_test_url, run_id) == "running"


@pytest.mark.integration
def test_existing_workflow_idempotency_preserved_with_reservation_mode(
    postgresql_test_url: str,
    workflow_client: WorkflowClientContext,
) -> None:
    """Idempotency and tenant-scope contracts remain valid when the
    API runs in reservation (enqueue_job=False) mode."""

    client, org = workflow_client.client, workflow_client.ids["organization"]

    first = client.post(
        f"/api/v1/organizations/{org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"idempotency_key": "idempotent-reservation-004"},
    )
    second = client.post(
        f"/api/v1/organizations/{org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"idempotency_key": "idempotent-reservation-004"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert UUID(first.json()["data"]["workflow_run_id"]) == UUID(
        second.json()["data"]["workflow_run_id"]
    )

    response = client.post(
        f"/api/v1/organizations/{org}/workflows/not.a.real.workflow/runs",
        headers=HEADERS,
        json={"idempotency_key": "unknown-key-reservation-005"},
    )
    assert response.status_code == 404
