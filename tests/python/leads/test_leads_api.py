"""Production-capable Leads route, audit, notification, consent, and isolation tests."""

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
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.main import create_app
from apps.api.app.notifications.models import NotificationEvent
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.leads.models import LeadSource


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
        key_id="leads-test-key",
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


HEADERS = {"Authorization": "Bearer fabricated.token"}


@pytest.fixture
def leads_client(
    postgresql_test_url: str,
    leads_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with leads_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="leads-api-catalog")
            organization = Organization(
                name="Leads Test Org",
                slug="leads-test-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_organization = Organization(
                name="Leads Other Org",
                slug="leads-other-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            other_profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            session.add_all([organization, other_organization, profile, other_profile])
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
                correlation_id="leads-api-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="leads-api-owner",
            )
            await access.create_membership(
                session,
                other_organization.id,
                MembershipCreate(
                    user_profile_id=other_profile.id,
                    membership_type=MembershipType.CLIENT,
                ),
                correlation_id="leads-api-other-member",
            )

            source = LeadSource(
                organization_id=organization.id,
                location_id=location.id,
                key="website_form",
                source_type="web_form",
                name="Website contact form",
                status="active",
                consent_capabilities=["transactional_email", "transactional_sms"],
                raw_payload_retention_policy="leads.raw_payload.default",
                version=1,
            )
            session.add(source)
            await session.flush()

            workflow_definition = WorkflowDefinition(
                key="leads.send_communication", name="Send lead communication", owner="leads"
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
                product_key="leads",
                trigger_type="manual",
                idempotency_key="leads-test-workflow-run-001",
                request_hash="deterministic-request-hash",
                input_document={},
                correlation_id="leads-test-workflow",
            )
            session.add(workflow_run)
            await session.flush()

            identifiers = {
                "organization": organization.id,
                "other_organization": other_organization.id,
                "location": location.id,
                "assigned_subject": profile.auth_user_id,
                "profile": profile.id,
                "other_profile": other_profile.id,
                "source": source.id,
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


def _intake(
    client: TestClient,
    ids: dict[str, UUID],
    *,
    external_submission_id: str,
    first_name: str,
    last_name: str = "Doe",
    email: str | None,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/organizations/{ids['organization']}/leads/intake",
        headers=HEADERS,
        json={
            "source_id": str(ids["source"]),
            "external_submission_id": external_submission_id,
            "location_id": str(ids["location"]),
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "message": "Please contact me about service.",
            "received_at": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json()["data"])


@pytest.mark.integration
def test_intake_dedup_list_filters_search_and_pagination(
    leads_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = leads_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/leads"

    first = _intake(
        client, ids, external_submission_id="lead-1", first_name="Jane", email="person@example.com"
    )
    second = _intake(
        client, ids, external_submission_id="lead-2", first_name="John", email="person@example.com"
    )
    assert first["status"] == "new"
    assert second["status"] == "duplicate"

    listing = client.get(base, headers=HEADERS)
    assert listing.status_code == 200
    assert listing.headers["Cache-Control"] == "no-store"
    assert len(listing.json()["data"]) == 2

    duplicates = client.get(f"{base}?status_filter=duplicate", headers=HEADERS)
    assert duplicates.status_code == 200
    assert len(duplicates.json()["data"]) == 1

    searched = client.get(f"{base}?search=jane", headers=HEADERS)
    assert searched.status_code == 200
    assert len(searched.json()["data"]) == 1

    paged = client.get(f"{base}?limit=1&offset=0", headers=HEADERS)
    assert paged.status_code == 200
    assert len(paged.json()["data"]) == 1
    assert paged.json()["pagination"]["has_more"] is True

    summary = client.get(f"{base}/summary", headers=HEADERS)
    assert summary.status_code == 200
    assert summary.json()["data"]["by_status"]["new"] == 1
    assert summary.json()["data"]["by_status"]["duplicate"] == 1

    performance = client.get(f"{base}/sources/performance", headers=HEADERS)
    assert performance.status_code == 200
    assert performance.json()["data"][0]["lead_count"] == 2


@pytest.mark.integration
def test_assignment_status_notes_tasks_and_conversion_flow(
    postgresql_test_url: str,
    leads_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = leads_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/leads"
    lead = _intake(
        client,
        ids,
        external_submission_id="lead-assign",
        first_name="Alex",
        email="alex@example.com",
    )
    lead_id = lead["lead_id"]

    assign = client.post(
        f"{base}/{lead_id}/assign",
        headers=HEADERS,
        json={"assigned_to_user_id": str(ids["profile"])},
    )
    assert assign.status_code == 200
    assert assign.json()["data"]["status"] == "assigned"
    assert assign.json()["data"]["assigned_to_user_id"] == str(ids["profile"])
    assert _notification_event_exists(postgresql_test_url, org, "leads.lead.assigned") is True

    cross_tenant_assign = client.post(
        f"{base}/{lead_id}/assign",
        headers=HEADERS,
        json={"assigned_to_user_id": str(ids["other_profile"])},
    )
    assert cross_tenant_assign.status_code == 404
    assert cross_tenant_assign.json()["error"]["code"] == "LEAD_ASSIGNEE_NOT_FOUND"

    acknowledged = client.post(
        f"{base}/{lead_id}/status", headers=HEADERS, json={"to_status": "acknowledged"}
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["data"]["acknowledged_at"] is not None

    attempted = client.post(
        f"{base}/{lead_id}/status", headers=HEADERS, json={"to_status": "contact_attempted"}
    )
    assert attempted.status_code == 200
    assert attempted.json()["data"]["first_outbound_attempt_at"] is not None
    assert attempted.json()["data"]["first_human_contact_at"] is None

    before_contact_summary = client.get(f"{base}/summary", headers=HEADERS)
    assert before_contact_summary.status_code == 200
    assert before_contact_summary.json()["data"]["average_speed_to_lead_seconds"] is None

    contacted = client.post(
        f"{base}/{lead_id}/status", headers=HEADERS, json={"to_status": "contacted"}
    )
    assert contacted.status_code == 200
    assert contacted.json()["data"]["first_human_contact_at"] is not None

    note = client.post(
        f"{base}/{lead_id}/notes", headers=HEADERS, json={"body": "Called, left voicemail."}
    )
    assert note.status_code == 201
    notes = client.get(f"{base}/{lead_id}/notes", headers=HEADERS)
    assert len(notes.json()["data"]) == 1

    task = client.post(
        f"{base}/{lead_id}/tasks",
        headers=HEADERS,
        json={"title": "Follow up tomorrow", "due_at": datetime.now(UTC).isoformat()},
    )
    assert task.status_code == 201
    task_id = task.json()["data"]["id"]
    tasks = client.get(f"{base}/{lead_id}/tasks", headers=HEADERS)
    assert tasks.json()["data"][0]["status"] == "open"

    complete = client.post(f"{base}/{lead_id}/tasks/{task_id}/complete", headers=HEADERS)
    assert complete.status_code == 200
    assert complete.json()["data"]["status"] == "completed"

    convert = client.post(
        f"{base}/{lead_id}/convert", headers=HEADERS, json={"converted_value_cents": 50000}
    )
    assert convert.status_code == 200
    assert convert.json()["data"]["status"] == "converted"
    assert convert.json()["data"]["converted_value_cents"] == 50000
    assert _notification_event_exists(postgresql_test_url, org, "leads.lead.converted") is True

    audit = client.get(f"{base}/{lead_id}/audit", headers=HEADERS)
    assert audit.status_code == 200
    event_types = {item["event_type"] for item in audit.json()["data"]}
    assert {
        "leads.lead.intaken",
        "leads.lead.assigned",
        "leads.lead.status_changed",
        "leads.note.added",
        "leads.task.created",
        "leads.task.completed",
    } <= event_types


@pytest.mark.integration
def test_consent_withdrawal_suppresses_communication(
    leads_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = leads_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/leads"
    lead = _intake(
        client,
        ids,
        external_submission_id="lead-consent",
        first_name="Sam",
        email="sam@example.com",
    )
    lead_id = lead["lead_id"]

    grant = client.post(
        f"{base}/{lead_id}/consents",
        headers=HEADERS,
        json={
            "channel": "sms",
            "consent_type": "transactional_sms",
            "status": "granted",
            "source": "web_form",
            "disclosure_version": "v1",
            "evidence_reference": "form-hash-1",
            "captured_at": datetime.now(UTC).isoformat(),
        },
    )
    assert grant.status_code == 201

    planned = client.post(
        f"{base}/{lead_id}/communications",
        headers=HEADERS,
        json={
            "channel": "sms",
            "consent_type": "transactional_sms",
            "message_reference": "template-1",
            "workflow_run_id": str(ids["workflow_run"]),
            "idempotency_key": "comm-key-1",
        },
    )
    assert planned.status_code == 202
    assert planned.json()["data"]["status"] == "planned"

    withdraw = client.post(
        f"{base}/{lead_id}/consents",
        headers=HEADERS,
        json={
            "channel": "sms",
            "consent_type": "transactional_sms",
            "status": "withdrawn",
            "source": "web_form",
            "disclosure_version": "v1",
            "evidence_reference": "form-hash-2",
            "captured_at": (datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
        },
    )
    assert withdraw.status_code == 201

    communications = client.get(f"{base}/{lead_id}/communications", headers=HEADERS)
    assert communications.status_code == 200
    assert communications.json()["data"][0]["status"] == "cancelled"

    suppressed = client.post(
        f"{base}/{lead_id}/communications",
        headers=HEADERS,
        json={
            "channel": "sms",
            "consent_type": "transactional_sms",
            "message_reference": "template-2",
            "workflow_run_id": str(ids["workflow_run"]),
            "idempotency_key": "comm-key-2",
        },
    )
    assert suppressed.status_code == 202
    assert suppressed.json()["data"]["status"] == "suppressed"

    consents = client.get(f"{base}/{lead_id}/consents", headers=HEADERS)
    assert len(consents.json()["data"]) == 2


@pytest.mark.integration
def test_invalid_status_transition_rejected_after_archive(
    leads_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = leads_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}/leads"
    lead = _intake(
        client,
        ids,
        external_submission_id="lead-archive",
        first_name="Kim",
        email="kim@example.com",
    )
    lead_id = lead["lead_id"]

    archived = client.post(
        f"{base}/{lead_id}/status", headers=HEADERS, json={"to_status": "archived"}
    )
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"

    invalid = client.post(
        f"{base}/{lead_id}/status", headers=HEADERS, json={"to_status": "acknowledged"}
    )
    assert invalid.status_code == 409


@pytest.mark.integration
def test_cross_tenant_lead_detail_is_not_found(
    leads_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = leads_client
    other_org = ids["other_organization"]
    response = client.get(f"/api/v1/organizations/{other_org}/leads/{uuid4()}", headers=HEADERS)
    assert response.status_code in (403, 404)
