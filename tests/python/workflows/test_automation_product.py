"""Packet 5 — Automation & Agents product-layer acceptance tests.

Covers:
- Workflow-type catalog listing
- Run history (paginated, filterable, per-key path)
- Schedule create / list / update lifecycle
- Schedule authorization (schedules.read vs schedules.manage)
- Workflow key validation (unknown keys rejected)
- Lead communication status semantics (queued, not sent)
- Lead communication idempotency
- Tenant isolation for runs and schedules
"""

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
from apps.api.app.execution.contracts import ScheduleCreate
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
        key_id="p5-test-key",
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


HEADERS = {"Authorization": "Bearer p5.test.token"}


class P5Context:
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
def p5_client(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[P5Context, None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, VerifiedProviderClaims, dict[str, UUID]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with workflows_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="p5-catalog-seed")
            org = Organization(
                name="P5 Test Org",
                slug="p5-test-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_org = Organization(
                name="P5 Other Org",
                slug="p5-other-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            owner = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            no_perm = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            session.add_all([org, other_org, owner, no_perm])
            await session.flush()

            loc = Location(
                organization_id=org.id,
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
            session.add(loc)
            await session.flush()

            owner_mem = await access.create_membership(
                session,
                org.id,
                MembershipCreate(user_profile_id=owner.id, membership_type=MembershipType.CLIENT),
                correlation_id="p5-owner",
            )
            owner_role = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner_role is not None
            await access.add_assignment(
                session,
                org.id,
                owner_mem.id,
                RoleAssignmentCreate(role_id=owner_role.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="p5-owner-assign",
            )
            await access.create_membership(
                session,
                org.id,
                MembershipCreate(user_profile_id=no_perm.id, membership_type=MembershipType.CLIENT),
                correlation_id="p5-no-perm",
            )

            return (
                claims(owner.auth_user_id),
                claims(no_perm.auth_user_id),
                {"organization": org.id, "other_org": other_org.id, "location": loc.id},
            )

    owner_claims, no_perm_claims, ids = asyncio.run(populate())
    verifier = FakeVerifier(owner_claims)
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield P5Context(client, verifier, no_perm_claims, ids)


# ---------------------------------------------------------------------------
# SC5-CATALOG — Workflow type listing
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_list_workflow_types_returns_all_ten(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    resp = client.get(f"/api/v1/organizations/{org}/workflows", headers=HEADERS)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert isinstance(data, list)
    keys = {item["key"] for item in data}
    assert "content.publish" in keys
    assert "content.draft_revision" in keys
    assert "gbp.sync" in keys
    assert "reviews.ingest" in keys
    assert "leads.send_communication" in keys
    assert len(data) == 10, f"Expected 10 workflow types, got {len(data)}"


@pytest.mark.integration
def test_get_single_workflow_type(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    resp = client.get(f"/api/v1/organizations/{org}/workflows/gbp.sync", headers=HEADERS)
    assert resp.status_code == 200, resp.text
    item = resp.json()["data"]
    assert item["key"] == "gbp.sync"
    assert item["product_key"] == "gbp"


@pytest.mark.integration
def test_unknown_workflow_type_404(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    resp = client.get(f"/api/v1/organizations/{org}/workflows/not.a.workflow", headers=HEADERS)
    assert resp.status_code == 404


@pytest.mark.integration
def test_catalog_requires_auth(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    previous = p5_client.verifier.result
    p5_client.verifier.result = p5_client.no_permission_claims
    try:
        resp = client.get(f"/api/v1/organizations/{org}/workflows", headers=HEADERS)
        assert resp.status_code == 403
    finally:
        p5_client.verifier.result = previous


# ---------------------------------------------------------------------------
# SC5-RUN-HISTORY — Run listing
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_list_runs_returns_empty_for_new_org(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    resp = client.get(f"/api/v1/organizations/{org}/workflows/runs", headers=HEADERS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == []


@pytest.mark.integration
def test_list_runs_after_starting_a_workflow(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    client.post(
        f"/api/v1/organizations/{org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"idempotency_key": "p5-run-list-test-001"},
    )
    resp = client.get(f"/api/v1/organizations/{org}/workflows/runs", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    run = data[0]
    assert run["workflow_key"] == "content.publish"
    assert run["status"] == "queued"
    assert run["product_key"] == "content"


@pytest.mark.integration
def test_list_runs_filter_by_workflow_key(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    client.post(
        f"/api/v1/organizations/{org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"idempotency_key": "p5-filter-a"},
    )
    client.post(
        f"/api/v1/organizations/{org}/workflows/seo.crawl_or_analysis/runs",
        headers=HEADERS,
        json={"idempotency_key": "p5-filter-b"},
    )

    resp = client.get(
        f"/api/v1/organizations/{org}/workflows/runs?workflow_key=content.publish",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(r["workflow_key"] == "content.publish" for r in data)


@pytest.mark.integration
def test_list_workflow_key_runs_path(p5_client: P5Context) -> None:
    """Test GET /{workflow_key}/runs returns only runs for that workflow type."""
    client, org = p5_client.client, p5_client.ids["organization"]
    client.post(
        f"/api/v1/organizations/{org}/workflows/gbp.sync/runs",
        headers=HEADERS,
        json={"idempotency_key": "p5-key-runs-a"},
    )
    client.post(
        f"/api/v1/organizations/{org}/workflows/reviews.ingest/runs",
        headers=HEADERS,
        json={"idempotency_key": "p5-key-runs-b"},
    )

    resp = client.get(
        f"/api/v1/organizations/{org}/workflows/gbp.sync/runs",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert all(r["workflow_key"] == "gbp.sync" for r in data)


@pytest.mark.integration
def test_list_workflow_key_runs_unknown_key_returns_empty(p5_client: P5Context) -> None:
    """An unknown workflow key in the run filter returns empty results, not an error."""
    client, org = p5_client.client, p5_client.ids["organization"]
    resp = client.get(
        f"/api/v1/organizations/{org}/workflows/not.real.key/runs",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.integration
def test_get_run_detail(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    started = client.post(
        f"/api/v1/organizations/{org}/workflows/gbp.sync/runs",
        headers=HEADERS,
        json={"idempotency_key": "p5-run-detail"},
    )
    run_id = started.json()["data"]["workflow_run_id"]

    resp = client.get(f"/api/v1/organizations/{org}/workflows/runs/{run_id}", headers=HEADERS)
    assert resp.status_code == 200
    detail = resp.json()["data"]
    assert detail["id"] == run_id
    assert detail["workflow_key"] == "gbp.sync"
    assert isinstance(detail["jobs"], list)
    assert isinstance(detail["latest_attempts"], list)


@pytest.mark.integration
def test_cross_org_run_not_visible(p5_client: P5Context) -> None:
    """A run created in org must not be visible by run_id in another org.
    Either 403 (authorization: no membership in other org) or 404 (run scoped
    to other organization_id, not found) is valid evidence of isolation."""
    client, ids = p5_client.client, p5_client.ids
    org, other_org = ids["organization"], ids["other_org"]

    started = client.post(
        f"/api/v1/organizations/{org}/workflows/content.publish/runs",
        headers=HEADERS,
        json={"idempotency_key": "p5-cross-org"},
    )
    run_id = started.json()["data"]["workflow_run_id"]

    resp = client.get(
        f"/api/v1/organizations/{other_org}/workflows/runs/{run_id}",
        headers=HEADERS,
    )
    assert resp.status_code in (403, 404), (
        f"Expected 403 or 404 for cross-org run access, got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# SC5-SCHEDULES — Schedule lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_list_schedules_empty(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    resp = client.get(f"/api/v1/organizations/{org}/workflows/schedules", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.integration
def test_create_schedule(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    next_run = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    resp = client.post(
        f"/api/v1/organizations/{org}/workflows/schedules",
        headers=HEADERS,
        json={
            "workflow_key": "gbp.sync",
            "key": "p5-test-schedule",
            "cron_expression": "0 8 * * *",
            "timezone": "America/Los_Angeles",
            "next_run_at": next_run,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["key"] == "p5-test-schedule"
    assert data["status"] == "active"
    assert data["cron_expression"] == "0 8 * * *"


@pytest.mark.integration
def test_create_schedule_unknown_workflow_key_rejected(p5_client: P5Context) -> None:
    """Unknown workflow keys must be rejected before any schedule row is created."""
    client, org = p5_client.client, p5_client.ids["organization"]
    next_run = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    resp = client.post(
        f"/api/v1/organizations/{org}/workflows/schedules",
        headers=HEADERS,
        json={
            "workflow_key": "not.a.real.workflow",
            "key": "p5-bad-key",
            "cron_expression": "0 8 * * *",
            "timezone": "UTC",
            "next_run_at": next_run,
        },
    )
    assert resp.status_code == 404, f"Expected 404 for unknown workflow key, got {resp.status_code}"


@pytest.mark.integration
def test_list_schedules_after_create(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    next_run = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    client.post(
        f"/api/v1/organizations/{org}/workflows/schedules",
        headers=HEADERS,
        json={
            "workflow_key": "reviews.ingest",
            "key": "p5-reviews-schedule",
            "cron_expression": "0 */6 * * *",
            "timezone": "UTC",
            "next_run_at": next_run,
        },
    )
    resp = client.get(f"/api/v1/organizations/{org}/workflows/schedules", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    keys = {s["key"] for s in data}
    assert "p5-reviews-schedule" in keys


@pytest.mark.integration
def test_update_schedule_pause(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    next_run = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    created = client.post(
        f"/api/v1/organizations/{org}/workflows/schedules",
        headers=HEADERS,
        json={
            "workflow_key": "gbp.sync",
            "key": "p5-pause-test",
            "cron_expression": "0 12 * * *",
            "timezone": "UTC",
            "next_run_at": next_run,
        },
    )
    sched_id = created.json()["data"]["id"]

    updated = client.patch(
        f"/api/v1/organizations/{org}/workflows/schedules/{sched_id}",
        headers=HEADERS,
        json={"status": "paused"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "paused"

    resumed = client.patch(
        f"/api/v1/organizations/{org}/workflows/schedules/{sched_id}",
        headers=HEADERS,
        json={"status": "active"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["data"]["status"] == "active"


@pytest.mark.integration
def test_schedule_create_requires_schedules_manage(p5_client: P5Context) -> None:
    """A principal with no role assignments (hence no schedules.manage)
    must receive 403 when attempting to create a schedule."""
    client, org = p5_client.client, p5_client.ids["organization"]
    previous = p5_client.verifier.result
    p5_client.verifier.result = p5_client.no_permission_claims
    try:
        next_run = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        resp = client.post(
            f"/api/v1/organizations/{org}/workflows/schedules",
            headers=HEADERS,
            json={
                "workflow_key": "gbp.sync",
                "key": "p5-no-perm",
                "cron_expression": "0 8 * * *",
                "timezone": "UTC",
                "next_run_at": next_run,
            },
        )
        assert resp.status_code == 403
    finally:
        p5_client.verifier.result = previous


@pytest.mark.integration
def test_schedule_update_requires_schedules_manage(p5_client: P5Context) -> None:
    """Updating a schedule requires schedules.manage; a principal without it gets 403."""
    client, org = p5_client.client, p5_client.ids["organization"]
    next_run = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    created = client.post(
        f"/api/v1/organizations/{org}/workflows/schedules",
        headers=HEADERS,
        json={
            "workflow_key": "gbp.sync",
            "key": "p5-auth-test",
            "cron_expression": "0 10 * * *",
            "timezone": "UTC",
            "next_run_at": next_run,
        },
    )
    sched_id = created.json()["data"]["id"]

    previous = p5_client.verifier.result
    p5_client.verifier.result = p5_client.no_permission_claims
    try:
        resp = client.patch(
            f"/api/v1/organizations/{org}/workflows/schedules/{sched_id}",
            headers=HEADERS,
            json={"status": "paused"},
        )
        assert resp.status_code == 403
    finally:
        p5_client.verifier.result = previous


@pytest.mark.integration
def test_update_nonexistent_schedule_404(p5_client: P5Context) -> None:
    client, org = p5_client.client, p5_client.ids["organization"]
    fake_id = uuid4()
    resp = client.patch(
        f"/api/v1/organizations/{org}/workflows/schedules/{fake_id}",
        headers=HEADERS,
        json={"status": "paused"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
def test_schedule_tenant_isolation_service_layer(
    postgresql_test_url: str,
    p5_client: P5Context,
) -> None:
    """A schedule created in one org must not be visible via the service
    layer in another org."""
    org = p5_client.ids["organization"]
    other_org = p5_client.ids["other_org"]

    async def scenario(session: AsyncSession) -> dict[str, object]:
        svc = ExecutionService()
        # Create a schedule in org first (self-contained)
        cmd = ScheduleCreate(
            workflow_key="gbp.sync",
            key="tenant-iso-test",
            cron_expression="0 6 * * *",
            timezone="UTC",
            next_run_at=datetime.now(UTC) + timedelta(days=1),
        )
        await svc.create_schedule(session, org, cmd, correlation_id="tenant-iso")

        schedules = await svc.list_schedules(session, org)
        other_schedules = await svc.list_schedules(session, other_org)
        return {
            "org_count": len(schedules),
            "other_org_count": len(other_schedules),
        }

    result = run_db(postgresql_test_url, scenario)
    org_count: int = result["org_count"]  # type: ignore[assignment]
    other_org_count: int = result["other_org_count"]  # type: ignore[assignment]
    assert org_count >= 1, "Org should see its schedules"
    assert other_org_count == 0, "Other org must not see org's schedules"


# ---------------------------------------------------------------------------
# SC5-LEAD-COMM — Lead communication status semantics
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_lead_communication_handler_sets_queued_not_sent(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Prove the semantic correction: the handler sets status='queued', not 'sent'."""
    from apps.api.app.execution.handlers import _handle_leads_send_communication
    from apps.api.app.execution.models import (
        WorkflowDefinition,
        WorkflowRun,
        WorkflowVersion,
    )
    from apps.api.app.products.leads.models import Lead, LeadCommunication, LeadSource

    async def scenario(session: AsyncSession) -> dict[str, object]:
        org = Organization(
            name="Lead Comm Test",
            slug="lead-comm-test",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        # Create a real WorkflowRun for the FK constraint
        wf_def = WorkflowDefinition(
            key="leads.send_communication",
            name="Send Lead Communication",
            owner="leads",
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
            organization_id=org.id,
            workflow_version_id=wf_ver.id,
            status="queued",
            trigger_type="test",
            idempotency_key=f"p5-lead-comm-run-{uuid4().hex[:12]}",
            request_hash="test-hash",
            input_document={},
            correlation_id="p5-lead-comm-test",
        )
        session.add(wf_run)
        await session.flush()

        source = LeadSource(
            organization_id=org.id,
            key="test-source",
            source_type="form",
            name="Test Form",
            status="active",
            consent_capabilities=[],
            raw_payload_retention_policy="30d",
            version=1,
        )
        session.add(source)
        await session.flush()

        lead = Lead(
            organization_id=org.id,
            source_id=source.id,
            status="new",
            first_name="Test",
            normalized_email="test@example.invalid",
            urgency="routine",
            received_at=datetime.now(UTC),
        )
        session.add(lead)
        await session.flush()

        comm = LeadCommunication(
            organization_id=org.id,
            lead_id=lead.id,
            direction="outbound",
            channel="email",
            status="planned",
            message_reference="test-message-ref",
            workflow_run_id=wf_run.id,
            idempotency_key=f"p5-lead-comm-{uuid4().hex[:12]}",
        )
        session.add(comm)
        await session.flush()

        outcome = await _handle_leads_send_communication(
            session,
            organization_id=org.id,
            location_id=None,
            input_document={"communication_id": str(comm.id)},
            correlation_id="p5-lead-comm-test",
            workflow_run_id=uuid4(),
        )

        await session.refresh(comm)
        return {
            "outcome_result": outcome.result,
            "communication_status": comm.status,
            "sent_at": comm.sent_at,
            "notification_delivery_id": str(comm.notification_delivery_id)
            if comm.notification_delivery_id
            else None,
        }

    result = run_db(postgresql_test_url, scenario)

    assert result["outcome_result"] == "succeeded"
    assert result["communication_status"] == "queued", (
        f"Expected status='queued', got '{result['communication_status']}'. "
        "Communication must not be marked 'sent' until provider dispatch evidence exists."
    )
    assert result["sent_at"] is None, "sent_at should not be set until actual provider dispatch"
    assert result["notification_delivery_id"] is not None, (
        "notification_delivery_id should link to the pending delivery record"
    )


@pytest.mark.integration
def test_lead_communication_idempotent_on_queued_status(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Calling the handler again on an already-queued comm must succeed idempotently."""
    from apps.api.app.execution.handlers import _handle_leads_send_communication
    from apps.api.app.execution.models import (
        WorkflowDefinition,
        WorkflowRun,
        WorkflowVersion,
    )
    from apps.api.app.products.leads.models import Lead, LeadCommunication, LeadSource

    async def scenario(session: AsyncSession) -> dict[str, object]:
        org = Organization(
            name="Lead Idem Test",
            slug="lead-idem-test",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        # Create WorkflowRun for FK constraint
        wf_def = WorkflowDefinition(
            key="leads.send_communication",
            name="Send Lead Communication",
            owner="leads",
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
            organization_id=org.id,
            workflow_version_id=wf_ver.id,
            status="queued",
            trigger_type="test",
            idempotency_key=f"p5-idem-run-{uuid4().hex[:12]}",
            request_hash="test-idem-hash",
            input_document={},
            correlation_id="p5-idem-test",
        )
        session.add(wf_run)
        await session.flush()

        source = LeadSource(
            organization_id=org.id,
            key="test-idem-source",
            source_type="form",
            name="Test Form",
            status="active",
            consent_capabilities=[],
            raw_payload_retention_policy="30d",
            version=1,
        )
        session.add(source)
        await session.flush()
        lead = Lead(
            organization_id=org.id,
            source_id=source.id,
            status="new",
            first_name="Test",
            normalized_email="test@example.invalid",
            urgency="routine",
            received_at=datetime.now(UTC),
        )
        session.add(lead)
        await session.flush()

        comm = LeadCommunication(
            organization_id=org.id,
            lead_id=lead.id,
            direction="outbound",
            channel="email",
            status="planned",
            message_reference="test-idem-ref",
            workflow_run_id=wf_run.id,
            idempotency_key=f"p5-idem-{uuid4().hex[:12]}",
        )
        session.add(comm)
        await session.flush()

        # First call: planned → queued
        outcome1 = await _handle_leads_send_communication(
            session,
            organization_id=org.id,
            location_id=None,
            input_document={"communication_id": str(comm.id)},
            correlation_id="p5-idem-test-1",
            workflow_run_id=uuid4(),
        )
        await session.refresh(comm)
        status1 = comm.status

        # Second call: queued → queued (idempotent)
        outcome2 = await _handle_leads_send_communication(
            session,
            organization_id=org.id,
            location_id=None,
            input_document={"communication_id": str(comm.id)},
            correlation_id="p5-idem-test-2",
            workflow_run_id=uuid4(),
        )
        await session.refresh(comm)
        status2 = comm.status

        # Third call: still queued (idempotent)
        outcome3 = await _handle_leads_send_communication(
            session,
            organization_id=org.id,
            location_id=None,
            input_document={"communication_id": str(comm.id)},
            correlation_id="p5-idem-test-3",
            workflow_run_id=uuid4(),
        )
        await session.refresh(comm)

        return {
            "outcome1": outcome1.result,
            "status1": status1,
            "outcome2": outcome2.result,
            "status2": status2,
            "outcome3": outcome3.result,
            "status3": comm.status,
        }

    result = run_db(postgresql_test_url, scenario)

    assert result["outcome1"] == "succeeded"
    assert result["status1"] == "queued"
    assert result["outcome2"] == "succeeded", (
        f"Expected idempotent success on retry, got '{result['outcome2']}'"
    )
    assert result["status2"] == "queued", (
        f"Status must remain queued on retry, got '{result['status2']}'"
    )
    assert result["outcome3"] == "succeeded"
    assert result["status3"] == "queued"


@pytest.mark.integration
def test_lead_communication_handler_failure_does_not_rollback_outer_transaction(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Notification creation failure must not poison the outer transaction.

    The handler uses a SAVEPOINT / begin_nested() for notification work.
    A failure there must roll back only the nested savepoint, leaving the
    outer transaction clean.  The communication is marked "failed" and
    unrelated durable state in the same session (e.g. a second lead) must
    still be present and the session still usable.

    This test forces a failure inside the savepoint by monkey-patching
    NotificationService.add_delivery to raise an exception, then verifies:
    - The handler returns retryable_failure (NOTIFICATION_CREATE_FAILED)
    - communication.status is "failed"
    - The extra_lead created before the handler call survives
    - The session is still usable after the handler returns
    """
    from unittest.mock import patch

    from apps.api.app.execution.handlers import _handle_leads_send_communication
    from apps.api.app.execution.models import (
        WorkflowDefinition,
        WorkflowRun,
        WorkflowVersion,
    )
    from apps.api.app.notifications.service import NotificationService
    from apps.api.app.products.leads.models import Lead, LeadCommunication, LeadSource

    async def scenario(session: AsyncSession) -> dict[str, object]:
        org = Organization(
            name="Txn Recovery",
            slug="txn-recovery",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        # Create unrelated durable state in the outer transaction BEFORE
        # the handler runs.  This must survive the savepoint failure.
        extra_source = LeadSource(
            organization_id=org.id,
            key="extra-txn-source",
            source_type="form",
            name="Extra Form",
            status="active",
            consent_capabilities=[],
            raw_payload_retention_policy="30d",
            version=1,
        )
        session.add(extra_source)
        await session.flush()

        extra_lead = Lead(
            organization_id=org.id,
            source_id=extra_source.id,
            status="new",
            first_name="Unrelated",
            normalized_email="unrelated@example.invalid",
            urgency="routine",
            received_at=datetime.now(UTC),
        )
        session.add(extra_lead)
        await session.flush()
        extra_lead_id = extra_lead.id

        wf_def = WorkflowDefinition(
            key="leads.send_communication",
            name="Send Lead Communication",
            owner="leads",
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
            organization_id=org.id,
            workflow_version_id=wf_ver.id,
            status="queued",
            trigger_type="test",
            idempotency_key=f"p5-txn-run-{uuid4().hex[:12]}",
            request_hash="test-txn-hash",
            input_document={},
            correlation_id="p5-txn-test",
        )
        session.add(wf_run)
        await session.flush()

        source = LeadSource(
            organization_id=org.id,
            key="test-txn-source",
            source_type="form",
            name="Test Form",
            status="active",
            consent_capabilities=[],
            raw_payload_retention_policy="30d",
            version=1,
        )
        session.add(source)
        await session.flush()

        lead = Lead(
            organization_id=org.id,
            source_id=source.id,
            status="new",
            first_name="Test",
            normalized_email="test@example.invalid",
            urgency="routine",
            received_at=datetime.now(UTC),
        )
        session.add(lead)
        await session.flush()

        comm = LeadCommunication(
            organization_id=org.id,
            lead_id=lead.id,
            direction="outbound",
            channel="email",
            status="planned",
            message_reference="test-txn-ref",
            workflow_run_id=wf_run.id,
            idempotency_key=f"p5-txn-comm-{uuid4().hex[:12]}",
        )
        session.add(comm)
        await session.flush()

        # ── Force notification failure inside the savepoint ────────────
        # Monkey-patch add_delivery to raise; the savepoint will roll back,
        # but the outer transaction must remain clean.

        async def _raise_delivery(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated notification delivery failure")

        with patch.object(NotificationService, "add_delivery", _raise_delivery):
            outcome = await _handle_leads_send_communication(
                session,
                organization_id=org.id,
                location_id=None,
                input_document={"communication_id": str(comm.id)},
                correlation_id="p5-txn-test",
                workflow_run_id=uuid4(),
            )
        await session.refresh(comm)

        # ── Assertions ─────────────────────────────────────────────────

        # 1. Handler reports failure, not poison.
        assert outcome.result == "retryable_failure", (
            f"Expected retryable_failure, got {outcome.result}"
        )
        assert outcome.safe_error == "NOTIFICATION_CREATE_FAILED"

        # 2. Communication marked failed in the outer transaction.
        assert comm.status == "failed", f"Expected comm.status='failed', got '{comm.status}'"

        # 3. Unrelated state must survive the savepoint failure.
        extra = await session.get(Lead, extra_lead_id)
        assert extra is not None, "Unrelated lead must survive savepoint rollback"
        assert extra.first_name == "Unrelated"

        # 4. Session is still usable — we can create new rows after the failure.
        post_fail_lead = Lead(
            organization_id=org.id,
            source_id=source.id,
            status="new",
            first_name="PostFailure",
            normalized_email="post@example.invalid",
            urgency="routine",
            received_at=datetime.now(UTC),
        )
        session.add(post_fail_lead)
        await session.flush()
        assert post_fail_lead.id is not None, (
            "Session must be usable after handler savepoint failure"
        )

        return {
            "outcome_result": outcome.result,
            "safe_error": outcome.safe_error,
            "communication_status": comm.status,
            "extra_lead_survived": extra is not None,
            "session_usable_after_failure": post_fail_lead.id is not None,
        }

    result = run_db(postgresql_test_url, scenario)

    assert result["outcome_result"] == "retryable_failure"
    assert result["safe_error"] == "NOTIFICATION_CREATE_FAILED"
    assert result["communication_status"] == "failed"
    assert result["extra_lead_survived"] is True
    assert result["session_usable_after_failure"] is True


# ---------------------------------------------------------------------------
# SC5-SERVICE — Service-layer operations
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_service_list_workflow_types(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario(session: AsyncSession) -> int:
        svc = ExecutionService()
        items = await svc.list_workflow_types(session)
        assert len(items) == 10
        for item in items:
            assert "key" in item
            assert "display_name" in item
            assert "product_key" in item
        return len(items)

    count = run_db(postgresql_test_url, scenario)
    assert count == 10


@pytest.mark.integration
def test_service_list_runs_empty_for_new_org(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario(session: AsyncSession) -> int:
        org = Organization(
            name="SR Test",
            slug="sr-test",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        svc = ExecutionService()
        runs, total = await svc.list_runs(session, org.id)
        return total

    total = run_db(postgresql_test_url, scenario)
    assert total == 0


@pytest.mark.integration
def test_service_create_and_list_schedule(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario(session: AsyncSession) -> dict[str, object]:
        org = Organization(
            name="Sch Test",
            slug="sch-test",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        svc = ExecutionService()
        next_run = datetime.now(UTC) + timedelta(days=1)
        cmd = ScheduleCreate(
            workflow_key="gbp.sync",
            key="svc-test-schedule",
            cron_expression="0 9 * * *",
            timezone="America/Chicago",
            next_run_at=next_run,
        )
        schedule = await svc.create_schedule(session, org.id, cmd, correlation_id="svc-test")

        schedules = await svc.list_schedules(session, org.id)
        return {
            "created_id": str(schedule.id),
            "count": len(schedules),
            "first_key": schedules[0]["key"] if schedules else None,
        }

    result = run_db(postgresql_test_url, scenario)
    assert result["count"] == 1
    assert result["first_key"] == "svc-test-schedule"
