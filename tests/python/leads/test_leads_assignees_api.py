"""Organization-scoped lead-assignee picker endpoint tests.

Verifies the smallest architecture-correct read endpoint that backs the
/leads assignee picker: organization scoping, tenant isolation, the
``leads.assign`` authorization gate, and that only active members with active
user profiles are ever selectable — revoked/suspended/expired memberships and
deactivated users are excluded so stale assignee data can never be offered.
"""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipStatus, MembershipType, ScopeType
from apps.api.app.access_control.models import OrganizationMembership
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.database.base import utc_now
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
        key_id="leads-assignees-test-key",
    )


HEADERS = {"Authorization": "Bearer fabricated.token"}


@pytest.fixture
def assignees_client(
    postgresql_test_url: str,
    leads_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, FakeVerifier, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        access = AccessControlService()
        seeder = AccessCatalogSeeder()
        async with leads_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="leads-assignees-catalog")
            organization = Organization(
                name="Assignees Org",
                slug="assignees-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_organization = Organization(
                name="Assignees Other Org",
                slug="assignees-other-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add_all([organization, other_organization])
            await session.flush()

            viewer = UserProfile(
                auth_user_id=uuid4(),
                email="viewer@example.invalid",
                display_name="Viewer Vera",
                status=UserStatus.ACTIVE,
                version=1,
            )
            owner = UserProfile(
                auth_user_id=uuid4(),
                email="owner@example.invalid",
                display_name="Owner Operator",
                status=UserStatus.ACTIVE,
                version=1,
            )
            teammate = UserProfile(
                auth_user_id=uuid4(),
                email="teammate@example.invalid",
                display_name="Teammate Two",
                status=UserStatus.ACTIVE,
                version=1,
            )
            suspended_user = UserProfile(
                auth_user_id=uuid4(),
                display_name="Suspended Sam",
                status=UserStatus.ACTIVE,
                version=1,
            )
            revoked_user = UserProfile(
                auth_user_id=uuid4(),
                display_name="Revoked Ray",
                status=UserStatus.ACTIVE,
                version=1,
            )
            deactivated_user = UserProfile(
                auth_user_id=uuid4(),
                display_name="Deactivated Dan",
                status=UserStatus.DEACTIVATED,
                deactivated_at=utc_now(),
                version=1,
            )
            cross_tenant_user = UserProfile(
                auth_user_id=uuid4(),
                display_name="Other Org Only",
                status=UserStatus.ACTIVE,
                version=1,
            )
            users = [
                owner,
                teammate,
                viewer,
                suspended_user,
                revoked_user,
                deactivated_user,
                cross_tenant_user,
            ]
            session.add_all(users)
            await session.flush()

            owner_membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(user_profile_id=owner.id, membership_type=MembershipType.CLIENT),
                correlation_id="assignees-owner",
            )
            owner_role = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner_role is not None
            await access.add_assignment(
                session,
                organization.id,
                owner_membership.id,
                RoleAssignmentCreate(role_id=owner_role.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="assignees-owner-role",
            )

            teammate_membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(
                    user_profile_id=teammate.id, membership_type=MembershipType.CLIENT
                ),
                correlation_id="assignees-teammate",
            )
            member_role = await access.catalog.get_role_by_key(session, "organization_member")
            assert member_role is not None
            await access.add_assignment(
                session,
                organization.id,
                teammate_membership.id,
                RoleAssignmentCreate(role_id=member_role.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="assignees-member-role",
            )

            # A read-only operator: ``organization_member`` grants
            # ``leads.read`` but not ``leads.assign`` (see ROLE_MAPPINGS), so
            # the assignees endpoint must deny this caller even though they
            # can read leads. They are still an active member and appear in
            # the picker for the owner.
            viewer_membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(user_profile_id=viewer.id, membership_type=MembershipType.CLIENT),
                correlation_id="assignees-viewer",
            )
            await access.add_assignment(
                session,
                organization.id,
                viewer_membership.id,
                RoleAssignmentCreate(role_id=member_role.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="assignees-viewer-role",
            )

            suspended_membership = OrganizationMembership(
                organization_id=organization.id,
                user_profile_id=suspended_user.id,
                membership_type=MembershipType.CLIENT,
                status=MembershipStatus.ACTIVE,
                activated_at=utc_now(),
                version=1,
            )
            session.add(suspended_membership)
            await session.flush()
            await access.memberships.transition(
                session,
                organization_id=organization.id,
                membership_id=suspended_membership.id,
                expected_status=MembershipStatus.ACTIVE,
                expected_version=1,
                target_status=MembershipStatus.SUSPENDED,
                timestamp=utc_now(),
            )

            revoked_membership = OrganizationMembership(
                organization_id=organization.id,
                user_profile_id=revoked_user.id,
                membership_type=MembershipType.CLIENT,
                status=MembershipStatus.ACTIVE,
                activated_at=utc_now(),
                version=1,
            )
            session.add(revoked_membership)
            await session.flush()
            await access.memberships.transition(
                session,
                organization_id=organization.id,
                membership_id=revoked_membership.id,
                expected_status=MembershipStatus.ACTIVE,
                expected_version=1,
                target_status=MembershipStatus.REVOKED,
                timestamp=utc_now(),
            )

            # Deactivated user still has an ACTIVE membership, but the user
            # profile is DEACTIVATED — they must be excluded from the picker.
            session.add(
                OrganizationMembership(
                    organization_id=organization.id,
                    user_profile_id=deactivated_user.id,
                    membership_type=MembershipType.CLIENT,
                    status=MembershipStatus.ACTIVE,
                    activated_at=utc_now(),
                    version=1,
                )
            )

            # A member of the other organization — must never appear in this
            # organization's assignee list (tenant isolation).
            await access.create_membership(
                session,
                other_organization.id,
                MembershipCreate(
                    user_profile_id=cross_tenant_user.id,
                    membership_type=MembershipType.CLIENT,
                ),
                correlation_id="assignees-cross-tenant",
            )

            identifiers = {
                "organization": organization.id,
                "other_organization": other_organization.id,
                "owner": owner.id,
                "owner_subject": owner.auth_user_id,
                "teammate": teammate.id,
                "viewer": viewer.id,
                "viewer_subject": viewer.auth_user_id,
                "suspended": suspended_user.id,
                "revoked": revoked_user.id,
                "deactivated": deactivated_user.id,
                "cross_tenant": cross_tenant_user.id,
                "owner_membership": owner_membership.id,
            }
            return claims(owner.auth_user_id), identifiers

    verified, identifiers = asyncio.run(populate())
    verifier = FakeVerifier(verified)
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, verifier, identifiers


@pytest.mark.integration
def test_list_assignees_returns_only_active_assignable_teammates(
    assignees_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, _verifier, ids = assignees_client
    response = client.get(
        f"/api/v1/organizations/{ids['organization']}/leads/assignees", headers=HEADERS
    )
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    returned_ids = {row["user_profile_id"] for row in data}
    # The owner, teammate, and viewer are all active members with active
    # user profiles — all three are selectable even though the viewer is the
    # caller (an operator can assign a lead to themselves).
    assert returned_ids == {str(ids["owner"]), str(ids["teammate"]), str(ids["viewer"])}

    by_id = {row["user_profile_id"]: row for row in data}
    owner_row = by_id[str(ids["owner"])]
    assert owner_row["display_name"] == "Owner Operator"
    assert owner_row["membership_status"] == "active"
    assert owner_row["membership_type"] == "client"
    assert "organization_owner" in owner_row["role_keys"]
    teammate_row = by_id[str(ids["teammate"])]
    assert "organization_member" in teammate_row["role_keys"]
    # No row exposes email — the contract intentionally omits it because no
    # public membership contract already discloses it.
    for row in data:
        assert "email" not in row


@pytest.mark.integration
def test_list_assignees_excludes_suspended_revoked_deactivated_and_cross_tenant(
    assignees_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, _verifier, ids = assignees_client
    response = client.get(
        f"/api/v1/organizations/{ids['organization']}/leads/assignees", headers=HEADERS
    )
    assert response.status_code == 200
    returned_ids = {row["user_profile_id"] for row in response.json()["data"]}
    assert str(ids["suspended"]) not in returned_ids
    assert str(ids["revoked"]) not in returned_ids
    assert str(ids["deactivated"]) not in returned_ids
    assert str(ids["cross_tenant"]) not in returned_ids


@pytest.mark.integration
def test_list_assignees_is_tenant_isolated(
    assignees_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, _verifier, ids = assignees_client
    response = client.get(
        f"/api/v1/organizations/{ids['other_organization']}/leads/assignees",
        headers=HEADERS,
    )
    # The caller is not a member of the other organization, so the
    # authorization gate denies before any cross-tenant data is read.
    assert response.status_code == 403


@pytest.mark.integration
def test_list_assignees_requires_leads_assign_permission(
    assignees_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = assignees_client
    # The viewer is an active member but holds only ``organization_member``,
    # which grants ``leads.read`` but not ``leads.assign``. The endpoint must
    # deny them even though they can otherwise read leads for this org.
    verifier.result = claims(ids["viewer_subject"], AssuranceLevel.AAL2)
    response = client.get(
        f"/api/v1/organizations/{ids['organization']}/leads/assignees", headers=HEADERS
    )
    assert response.status_code == 403


@pytest.mark.integration
def test_list_assignees_requires_authentication(
    assignees_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, _verifier, ids = assignees_client
    response = client.get(f"/api/v1/organizations/{ids['organization']}/leads/assignees")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
