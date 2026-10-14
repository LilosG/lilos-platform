# ruff: noqa: F811
"""Platform users, invitation cancellation and system status: authorization, tenant safety,
pagination and the rule that an unreadable component is unknown, never healthy and never 0."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.enums import MembershipType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.execution.models import (
    Job,
    JobAttempt,
    Schedule,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.platform_admin.system_status import SystemStatusService

from .test_api import (  # noqa: F401
    HEADERS,
    FakeVerifier,
    claims,
    platform_administration_client,
)


def _create_organization(client: TestClient, *, slug: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/platform/organizations",
        headers=HEADERS,
        json={
            "name": f"Client {slug}",
            "slug": slug,
            "organization_type": "test",
            "timezone": "UTC",
            "default_currency": "USD",
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json()["data"])


Client = tuple[TestClient, FakeVerifier, dict[str, UUID]]
READ_ROUTES = ("/api/v1/platform/users", "/api/v1/platform/system-status")


@pytest.mark.integration
@pytest.mark.parametrize("path", READ_ROUTES)
def test_only_a_platform_administrator_at_aal2_may_read(
    platform_administration_client: Client, path: str
) -> None:
    client, verifier, ids = platform_administration_client
    assert client.get(path).status_code == 401
    verifier.result = claims(ids["non_admin_subject"])
    assert client.get(path, headers=HEADERS).status_code == 403
    verifier.result = claims(ids["revoked_admin_subject"])
    assert client.get(path, headers=HEADERS).status_code == 403
    verifier.result = claims(ids["admin_subject"], assurance=AssuranceLevel.AAL1)
    denied = client.get(path, headers=HEADERS)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "AUTHORIZATION_DENIED"
    verifier.result = claims(ids["admin_subject"])
    allowed = client.get(path, headers=HEADERS)
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "no-store"


def _run[T](
    factory: async_sessionmaker[AsyncSession], work: Callable[[AsyncSession], Awaitable[T]]
) -> T:
    async def go() -> T:
        async with factory.begin() as session:
            return await work(session)

    return asyncio.run(go())


def _invite(
    factory: async_sessionmaker[AsyncSession], organization_id: object, email: str
) -> tuple[UUID, UUID]:
    """A person with that email who is invited to the client; returns (profile, invitation)."""

    async def work(session: AsyncSession) -> tuple[UUID, UUID]:
        profile = UserProfile(
            auth_user_id=uuid4(), email=email, display_name=email.split("@")[0], version=1
        )
        session.add(profile)
        await session.flush()
        invitation, _token = await AccessControlService().create_invitation_by_email(
            session,
            UUID(str(organization_id)),
            email=email,
            membership_type=MembershipType.CLIENT,
            invited_by_user_profile_id=profile.id,
            correlation_id="test-invite",
        )
        return profile.id, invitation.id

    return _run(factory, work)


@pytest.mark.integration
def test_users_list_shows_people_and_their_clients_and_nothing_else(
    platform_administration_client: Client,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _verifier, _ids = platform_administration_client
    organization = _create_organization(client, slug="users-org")
    profile_id, invitation_id = _invite(
        platform_administration_session_factory, organization["id"], "pat@example.com"
    )

    body = client.get("/api/v1/platform/users", headers=HEADERS).json()["data"]
    person = next(item for item in body["items"] if item["id"] == str(profile_id))

    assert set(person) == {
        "id",
        "display_name",
        "email",
        "status",
        "platform_administrator",
        "access",
        "access_total",
    }
    assert person["email"] == "pat@example.com"
    assert person["platform_administrator"] is False
    assert person["access_total"] == 1
    [access] = person["access"]
    assert access["organization_id"] == organization["id"]
    assert access["organization_name"] == organization["name"]
    assert access["membership_status"] == "invited"
    assert access["invitation"]["id"] == str(invitation_id)
    assert set(access["invitation"]) == {"id", "version", "status", "expires_at"}
    assert "token" not in client.get("/api/v1/platform/users", headers=HEADERS).text
    admin = next(item for item in body["items"] if item["platform_administrator"])
    assert admin["access"] == []
    assert admin["access_total"] == 0


@pytest.mark.integration
def test_users_list_is_paginated_and_stable(
    platform_administration_client: Client,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _verifier, _ids = platform_administration_client

    async def add(session: AsyncSession) -> None:
        session.add_all(
            UserProfile(
                auth_user_id=uuid4(),
                email=f"person{n}@example.com",
                display_name=f"Person {n}",
                status=UserStatus.ACTIVE,
                version=1,
            )
            for n in range(5)
        )

    _run(platform_administration_session_factory, add)
    everyone = client.get("/api/v1/platform/users?limit=100", headers=HEADERS).json()["data"]
    assert everyone["has_more"] is False
    assert everyone["next_offset"] is None

    first = client.get("/api/v1/platform/users?limit=3", headers=HEADERS).json()["data"]
    assert len(first["items"]) == 3
    assert first["has_more"] is True
    assert first["next_offset"] == 3
    second = client.get("/api/v1/platform/users?limit=3&offset=3", headers=HEADERS).json()["data"]
    seen = [item["id"] for item in first["items"] + second["items"]]
    assert seen == [item["id"] for item in everyone["items"]][: len(seen)]
    assert len(set(seen)) == len(seen)
    assert client.get("/api/v1/platform/users?limit=0", headers=HEADERS).status_code == 422
    assert client.get("/api/v1/platform/users?limit=101", headers=HEADERS).status_code == 422


@pytest.mark.integration
def test_a_platform_administrator_cancels_an_invitation_without_a_membership(
    platform_administration_client: Client,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _verifier, _ids = platform_administration_client
    organization = _create_organization(client, slug="cancel-org")
    other = _create_organization(client, slug="other-org")
    profile_id, invitation_id = _invite(
        platform_administration_session_factory, organization["id"], "lee@example.com"
    )
    path = f"/api/v1/platform/organizations/{organization['id']}/invitations/{invitation_id}/cancel"

    # Another client's id never reaches this client's invitation.
    wrong = client.post(
        f"/api/v1/platform/organizations/{other['id']}/invitations/{invitation_id}/cancel",
        headers=HEADERS,
        json={"expected_version": 1},
    )
    assert wrong.status_code == 404
    assert wrong.json()["error"]["code"] == "INVITATION_NOT_FOUND"
    # A stale screen is refused.
    stale = client.post(path, headers=HEADERS, json={"expected_version": 7})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "INVITATION_VERSION_CONFLICT"

    done = client.post(path, headers=HEADERS, json={"expected_version": 1})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "cancelled"
    # Repeating it conflicts instead of acting twice.
    again = client.post(path, headers=HEADERS, json={"expected_version": 1})
    assert again.status_code == 409

    async def audit(session: AsyncSession) -> list[str]:
        rows = await session.execute(
            text("SELECT event_type FROM audit_events WHERE organization_id = :id"),
            {"id": UUID(organization["id"])},
        )
        return [row[0] for row in rows]

    assert "platform.invitation.cancelled" in _run(platform_administration_session_factory, audit)
    after = client.get("/api/v1/platform/users", headers=HEADERS).json()["data"]["items"]
    person = next(item for item in after if item["id"] == str(profile_id))
    assert person["access"] == []


@pytest.mark.integration
def test_cancelling_requires_a_platform_administrator(
    platform_administration_client: Client,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, verifier, ids = platform_administration_client
    organization = _create_organization(client, slug="denied-cancel")
    _profile, invitation_id = _invite(
        platform_administration_session_factory, organization["id"], "kim@example.com"
    )
    path = f"/api/v1/platform/organizations/{organization['id']}/invitations/{invitation_id}/cancel"
    verifier.result = claims(ids["non_admin_subject"])
    assert client.post(path, headers=HEADERS, json={"expected_version": 1}).status_code == 403
    verifier.result = claims(ids["admin_subject"], assurance=AssuranceLevel.AAL1)
    assert client.post(path, headers=HEADERS, json={"expected_version": 1}).status_code == 403


def _seed_machinery(factory: async_sessionmaker[AsyncSession], organization_id: object) -> None:
    org = UUID(str(organization_id))
    now = datetime.now(UTC)

    async def work(session: AsyncSession) -> None:
        definition = WorkflowDefinition(key="test.flow", name="Test", owner="test")
        session.add(definition)
        await session.flush()
        version = WorkflowVersion(
            definition_id=definition.id,
            version=1,
            status="approved",
            input_schema={},
            output_schema={},
            step_specification=[],
            retry_policy={},
            timeout_seconds=60,
        )
        session.add(version)
        await session.flush()

        def run(status: str, age: timedelta) -> WorkflowRun:
            item = WorkflowRun(
                organization_id=org,
                workflow_version_id=version.id,
                status=status,
                trigger_type="manual",
                idempotency_key=uuid4().hex,
                request_hash="0" * 64,
                input_document={},
                correlation_id="seed",
            )
            item.updated_at = now - age
            return item

        recent_failure = run("failed", timedelta(hours=2))
        session.add_all(
            [recent_failure, run("failed", timedelta(hours=30)), run("completed", timedelta())]
        )
        await session.flush()
        for status, attempt_status, category, count in (
            ("dead_lettered", "permanent_failure", None, 2),
            ("dead_lettered", "timed_out", "lease_expired", 1),
            ("dead_lettered", "retryable_failure", None, 1),
            ("completed", "succeeded", None, 3),
        ):
            for _ in range(count):
                job = Job(
                    organization_id=org,
                    workflow_run_id=recent_failure.id,
                    job_type="test",
                    status=status,
                    idempotency_key=uuid4().hex,
                    payload={},
                    attempt_count=1,
                    max_attempts=3,
                )
                session.add(job)
                await session.flush()
                session.add(
                    JobAttempt(
                        organization_id=org,
                        job_id=job.id,
                        attempt_number=1,
                        status=attempt_status,
                        error_category=category,
                        worker_id="w",
                    )
                )
        session.add(
            Job(
                organization_id=org,
                workflow_run_id=recent_failure.id,
                job_type="test",
                status="queued",
                idempotency_key=uuid4().hex,
                payload={},
                available_at=now - timedelta(minutes=40),
            )
        )
        session.add_all(
            [
                Schedule(
                    organization_id=org,
                    workflow_version_id=version.id,
                    key="overdue",
                    cron_expression="* * * * *",
                    timezone="UTC",
                    status="active",
                    next_run_at=now - timedelta(hours=1),
                    last_run_at=now - timedelta(hours=2),
                ),
                Schedule(
                    organization_id=org,
                    workflow_version_id=version.id,
                    key="paused",
                    cron_expression="* * * * *",
                    timezone="UTC",
                    status="paused",
                    next_run_at=now - timedelta(days=3),
                ),
            ]
        )
        provider = Provider(key="gsc", name="GSC", status="active", capabilities=[])
        session.add(provider)
        await session.flush()
        for status in ("degraded", "reconnect_required", "connected", "disconnected"):
            session.add(
                IntegrationConnection(
                    organization_id=org,
                    provider_id=provider.id,
                    status=status,
                    external_account_reference=status,
                )
            )

    _run(factory, work)


@pytest.mark.integration
def test_a_fresh_platform_reports_healthy_with_real_zeros(
    platform_administration_client: Client,
) -> None:
    client, _verifier, _ids = platform_administration_client
    data = client.get("/api/v1/platform/system-status", headers=HEADERS).json()["data"]
    assert data["overall"] == "healthy"
    assert data["database"] == {"status": "healthy"}
    assert data["scheduler"]["active_schedules"] == 0
    assert data["scheduler"]["last_dispatch_at"] is None
    assert data["worker_queue"]["dead_letter_count"] == 0
    assert data["worker_queue"]["dead_letter_groups"] == []
    assert data["failed_runs"]["failed_last_24h"] == 0
    assert data["integrations"]["needing_attention"] == 0


@pytest.mark.integration
def test_system_status_reports_what_the_tables_hold(
    platform_administration_client: Client,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _verifier, _ids = platform_administration_client
    organization = _create_organization(client, slug="status-org")
    _seed_machinery(platform_administration_session_factory, organization["id"])

    data = client.get("/api/v1/platform/system-status", headers=HEADERS).json()["data"]

    assert data["overall"] == "attention"
    assert data["database"]["status"] == "healthy"
    scheduler = data["scheduler"]
    assert scheduler["status"] == "attention"
    assert scheduler["overdue"] is True
    assert scheduler["active_schedules"] == 1  # the paused one is not dispatchable
    assert scheduler["last_dispatch_at"] is not None
    queue = data["worker_queue"]
    assert queue["status"] == "attention"
    assert queue["dead_letter_count"] == 4
    assert {g["reason"]: g["count"] for g in queue["dead_letter_groups"]} == {
        "permanent_failure": 2,
        "retries_exhausted": 1,
        "lease_expired": 1,
    }
    assert queue["backlogged"] is True
    assert queue["oldest_pending_at"] is not None
    assert data["failed_runs"] == {"status": "attention", "failed_last_24h": 1}
    assert data["integrations"] == {"status": "attention", "needing_attention": 2}


@pytest.mark.integration
@pytest.mark.parametrize("settled_status", ["cancelled", "completed"])
def test_a_dead_letter_of_a_run_that_later_settled_is_no_longer_unresolved(
    platform_administration_client: Client,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
    settled_status: str,
) -> None:
    client, _verifier, _ids = platform_administration_client
    organization = _create_organization(client, slug=f"settled-{settled_status}")
    _seed_machinery(platform_administration_session_factory, organization["id"])

    async def settle(session: AsyncSession) -> None:
        await session.execute(
            text(
                "UPDATE workflow_runs SET status = :status "
                "WHERE organization_id = :id AND status = 'failed'"
            ),
            {"id": UUID(organization["id"]), "status": settled_status},
        )

    _run(platform_administration_session_factory, settle)
    queue = client.get("/api/v1/platform/system-status", headers=HEADERS).json()["data"][
        "worker_queue"
    ]
    assert queue["dead_letter_count"] == 0
    assert queue["dead_letter_groups"] == []


@pytest.mark.integration
def test_a_retired_clients_work_is_not_counted_against_the_platform(
    platform_administration_client: Client,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _verifier, _ids = platform_administration_client
    organization = _create_organization(client, slug="retired-org")
    _seed_machinery(platform_administration_session_factory, organization["id"])

    async def retire(session: AsyncSession) -> None:
        await session.execute(
            text("UPDATE organizations SET status='archived', archived_at=now() WHERE id = :id"),
            {"id": UUID(organization["id"])},
        )

    _run(platform_administration_session_factory, retire)
    data = client.get("/api/v1/platform/system-status", headers=HEADERS).json()["data"]
    assert data["scheduler"]["active_schedules"] == 0
    assert data["scheduler"]["overdue"] is False
    assert data["integrations"]["needing_attention"] == 0


@pytest.mark.integration
def test_a_component_that_cannot_be_read_is_unknown_not_healthy_and_not_zero(
    platform_administration_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _verifier, _ids = platform_administration_client

    async def broken(*_args: object, **_kwargs: object) -> object:
        raise SQLAlchemyError("simulated")

    monkeypatch.setattr(SystemStatusService, "_queue", broken)
    data = client.get("/api/v1/platform/system-status", headers=HEADERS).json()["data"]

    assert data["worker_queue"] == {
        "status": "unknown",
        "dead_letter_count": None,
        "dead_letter_groups": [],
        "oldest_pending_at": None,
        "backlogged": None,
    }
    # The others are still read, and one unreadable part keeps the whole from claiming health.
    assert data["scheduler"]["status"] == "healthy"
    assert data["failed_runs"]["failed_last_24h"] == 0
    assert data["overall"] == "unknown"


@pytest.mark.integration
def test_unknown_does_not_hide_a_real_problem(
    platform_administration_client: Client,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _verifier, _ids = platform_administration_client
    organization = _create_organization(client, slug="mixed-org")
    _seed_machinery(platform_administration_session_factory, organization["id"])

    async def broken(*_args: object, **_kwargs: object) -> object:
        raise SQLAlchemyError("simulated")

    monkeypatch.setattr(SystemStatusService, "_integrations", broken)
    data = client.get("/api/v1/platform/system-status", headers=HEADERS).json()["data"]
    assert data["integrations"] == {"status": "unknown", "needing_attention": None}
    assert data["overall"] == "attention"


@pytest.mark.integration
def test_the_organization_cancel_route_refuses_an_administrator_with_no_membership(
    platform_administration_client: Client,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Why the platform route exists: the client-scoped one keys on membership, not on the grant."""
    client, _verifier, _ids = platform_administration_client
    organization = _create_organization(client, slug="member-only")
    _profile, invitation_id = _invite(
        platform_administration_session_factory, organization["id"], "sam@example.com"
    )
    response = client.post(
        f"/api/v1/organizations/{organization['id']}/invitations/{invitation_id}/cancel",
        headers=HEADERS,
        json={"expected_version": 1},
    )
    assert response.status_code == 403
