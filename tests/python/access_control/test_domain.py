"""Membership, invitation, catalog, scope, deny, audit, and isolation tests."""

import asyncio
import base64
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import (
    PERMISSION_CATALOG,
    ROLE_CATALOG,
    ROLE_MAPPINGS,
    AccessCatalogSeeder,
)
from apps.api.app.access_control.contracts import (
    InvitationCreate,
    MembershipCreate,
    PermissionDenyCreate,
    RoleAssignmentCreate,
)
from apps.api.app.access_control.enums import MembershipStatus, MembershipType, ScopeType
from apps.api.app.access_control.errors import (
    CatalogConflictError,
    MembershipConflictError,
    MembershipLifecycleConflictError,
    MembershipNotFoundError,
    MembershipVersionConflictError,
)
from apps.api.app.access_control.models import (
    MembershipPermissionDeny,
    MembershipRoleAssignment,
    OrganizationInvitation,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
)
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.contracts import AuthenticatedPrincipal
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


def organization(slug: str, status: OrganizationStatus = OrganizationStatus.ACTIVE) -> Organization:
    return Organization(
        name=slug.title(),
        slug=slug,
        organization_type=OrganizationType.TEST,
        status=status,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )


def user(email: str = "fabricated@example.invalid") -> UserProfile:
    return UserProfile(auth_user_id=uuid4(), email=email, status=UserStatus.ACTIVE, version=1)


def principal(profile: UserProfile) -> AuthenticatedPrincipal:
    now = datetime.now(UTC)
    return AuthenticatedPrincipal(
        platform_user_id=profile.id,
        auth_user_id=profile.auth_user_id,
        user_status=UserStatus.ACTIVE,
        session_id=uuid4(),
        assurance_level=AssuranceLevel.AAL1,
        token_issued_at=now,
        token_expires_at=now + timedelta(minutes=5),
    )


@pytest.mark.integration
def test_catalog_seed_is_exact_idempotent_audited_and_mismatch_safe(
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        seeder = AccessCatalogSeeder()
        async with access_session_factory.begin() as session:
            first = await seeder.seed(session, correlation_id="catalog-first")
        assert (first.roles_created, first.permissions_created) == (
            len(ROLE_CATALOG),
            len(PERMISSION_CATALOG),
        )
        assert first.mappings_created == sum(len(value) for value in ROLE_MAPPINGS.values())
        async with access_session_factory.begin() as session:
            second = await seeder.seed(session, correlation_id="catalog-second")
        assert second.roles_created == second.permissions_created == second.mappings_created == 0
        async with access_session_factory() as session:
            assert set(await session.scalars(select(Role.key))) == set(ROLE_CATALOG)
            assert set(await session.scalars(select(Permission.key))) == set(PERMISSION_CATALOG)
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.resource_type == "access_catalog")
                )
                == 3
            )
        async with access_session_factory.begin() as session:
            await session.execute(
                update(Role).where(Role.key == "organization_viewer").values(name="Mismatch")
            )
        with pytest.raises(CatalogConflictError):
            async with access_session_factory.begin() as session:
                await seeder.seed(session, correlation_id="catalog-mismatch")
        async with access_session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(Role)) == 5

    asyncio.run(exercise())


@pytest.mark.integration
def test_membership_lifecycle_uniqueness_isolation_immutability_and_rollback(
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = AccessControlService()
        async with access_session_factory.begin() as session:
            first_org, second_org, profile = (
                organization("access-one"),
                organization("access-two"),
                user(),
            )
            session.add_all([first_org, second_org, profile])
            await session.flush()
            first_id, second_id, user_id = first_org.id, second_org.id, profile.id
        async with access_session_factory.begin() as session:
            membership = await service.create_membership(
                session,
                first_id,
                MembershipCreate(user_profile_id=user_id, membership_type=MembershipType.CLIENT),
                correlation_id="member-create",
            )
            membership_id = membership.id
        with pytest.raises(MembershipNotFoundError):
            async with access_session_factory() as session:
                await service.get_membership(session, second_id, membership_id)
        with pytest.raises(MembershipConflictError):
            async with access_session_factory.begin() as session:
                await service.create_membership(
                    session,
                    first_id,
                    MembershipCreate(
                        user_profile_id=user_id, membership_type=MembershipType.SUPPORT
                    ),
                    correlation_id="duplicate",
                )
        async with access_session_factory.begin() as session:
            suspended = await service.transition_membership(
                session,
                first_id,
                membership_id,
                target=MembershipStatus.SUSPENDED,
                expected_version=1,
                correlation_id="suspend",
            )
            assert suspended.version == 2 and suspended.suspended_at is not None
        with pytest.raises(MembershipVersionConflictError):
            async with access_session_factory.begin() as session:
                await service.transition_membership(
                    session,
                    first_id,
                    membership_id,
                    target=MembershipStatus.ACTIVE,
                    expected_version=1,
                    correlation_id="stale",
                )
        async with access_session_factory.begin() as session:
            restored = await service.transition_membership(
                session,
                first_id,
                membership_id,
                target=MembershipStatus.ACTIVE,
                expected_version=2,
                correlation_id="restore",
            )
            assert restored.version == 3 and restored.suspended_at is None
        with pytest.raises(RuntimeError, match="forced"):
            async with access_session_factory.begin() as session:
                await service.transition_membership(
                    session,
                    first_id,
                    membership_id,
                    target=MembershipStatus.REVOKED,
                    expected_version=3,
                    correlation_id="rollback",
                )
                raise RuntimeError("forced")
        with pytest.raises(IntegrityError):
            async with access_session_factory.begin() as session:
                await session.execute(
                    update(OrganizationMembership)
                    .where(OrganizationMembership.id == membership_id)
                    .values(membership_type="support")
                )
        async with access_session_factory.begin() as session:
            revoked = await service.transition_membership(
                session,
                first_id,
                membership_id,
                target=MembershipStatus.REVOKED,
                expected_version=3,
                correlation_id="revoke",
            )
            assert revoked.version == 4
        with pytest.raises(MembershipLifecycleConflictError):
            async with access_session_factory.begin() as session:
                await service.transition_membership(
                    session,
                    first_id,
                    membership_id,
                    target=MembershipStatus.ACTIVE,
                    expected_version=4,
                    correlation_id="terminal",
                )
        with pytest.raises(MembershipConflictError):
            async with access_session_factory.begin() as session:
                await service.create_membership(
                    session,
                    first_id,
                    MembershipCreate(
                        user_profile_id=user_id, membership_type=MembershipType.CLIENT
                    ),
                    correlation_id="reserved",
                )

    asyncio.run(exercise())


@pytest.mark.integration
def test_invitation_hash_acceptance_replay_expiry_and_email_matching(
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = AccessControlService()
        async with access_session_factory.begin() as session:
            org, inviter, invitee = (
                organization("invite-org"),
                user("inviter@example.invalid"),
                user("invitee@example.invalid"),
            )
            session.add_all([org, inviter, invitee])
            await session.flush()
            org_id, inviter_id, invitee_id = org.id, inviter.id, invitee.id
            invitee_principal = principal(invitee)
        async with access_session_factory.begin() as session:
            invitation, token = await service.create_invitation(
                session,
                org_id,
                InvitationCreate(
                    user_profile_id=invitee_id,
                    email=" INVITEE@EXAMPLE.INVALID ",
                    membership_type=MembershipType.CLIENT,
                    invited_by_user_profile_id=inviter_id,
                ),
                correlation_id="invite",
            )
            invitation_id = invitation.id
            assert len(base64.urlsafe_b64decode(token + "=")) == 32
            assert invitation.token_hash == hashlib.sha256(token.encode()).digest()
            assert token.encode() != invitation.token_hash
        async with access_session_factory.begin() as session:
            accepted = await service.accept_invitation(
                session, token, invitee_principal, correlation_id="accept"
            )
            assert accepted.accepted and accepted.membership is not None
            assert accepted.membership.status is MembershipStatus.ACTIVE
        async with access_session_factory.begin() as session:
            replay = await service.accept_invitation(
                session, token, invitee_principal, correlation_id="replay"
            )
            assert not replay.accepted
        async with access_session_factory() as session:
            stored = await session.get(OrganizationInvitation, invitation_id)
            assert stored is not None and stored.status.value == "accepted"
            serialized = str(
                list(
                    await session.scalars(
                        select(AuditEvent).where(AuditEvent.organization_id == org_id)
                    )
                )
            )
            assert (
                token not in serialized
                and hashlib.sha256(token.encode()).hexdigest() not in serialized
            )
        async with access_session_factory.begin() as session:
            expired_user = user("expired@example.invalid")
            session.add(expired_user)
            await session.flush()
            expired_user_id = expired_user.id
            expired_principal = principal(expired_user)
        async with access_session_factory.begin() as session:
            expired_invitation, expired_token = await service.create_invitation(
                session,
                org_id,
                InvitationCreate(
                    user_profile_id=expired_user_id,
                    email="expired@example.invalid",
                    membership_type=MembershipType.CLIENT,
                    invited_by_user_profile_id=inviter_id,
                ),
                correlation_id="expired-invite",
            )
            expired_id = expired_invitation.id
            await session.execute(
                update(OrganizationInvitation)
                .where(OrganizationInvitation.id == expired_id)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        async with access_session_factory.begin() as session:
            outcome = await service.accept_invitation(
                session, expired_token, expired_principal, correlation_id="expire"
            )
            assert not outcome.accepted
        async with access_session_factory() as session:
            expired_stored = await session.get(OrganizationInvitation, expired_id)
            assert expired_stored is not None and expired_stored.status.value == "expired"

    asyncio.run(exercise())


@pytest.mark.integration
def test_scoped_assignments_denies_and_database_tenant_constraints(
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service, seeder = AccessControlService(), AccessCatalogSeeder()
        async with access_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="catalog")
            org_a, org_b, profile = organization("scope-one"), organization("scope-two"), user()
            session.add_all([org_a, org_b, profile])
            await session.flush()
            location_b = Location(
                organization_id=org_b.id,
                name="Other",
                slug="other-location",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.SETUP_REQUIRED,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=False,
                version=1,
            )
            session.add(location_b)
            await session.flush()
            org_a_id, org_b_id, user_id, location_b_id = (
                org_a.id,
                org_b.id,
                profile.id,
                location_b.id,
            )
        async with access_session_factory.begin() as session:
            membership = await service.create_membership(
                session,
                org_a_id,
                MembershipCreate(user_profile_id=user_id, membership_type=MembershipType.INTERNAL),
                correlation_id="member",
            )
            owner = await service.catalog.get_role_by_key(session, "organization_viewer")
            read = await service.catalog.get_permission_by_key(session, "organization.read")
            assert owner is not None and read is not None
            assignment = await service.add_assignment(
                session,
                org_a_id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="assign",
            )
            deny = await service.add_deny(
                session,
                org_a_id,
                membership.id,
                PermissionDenyCreate(permission_id=read.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="deny",
            )
            membership_id, assignment_id, deny_id = membership.id, assignment.id, deny.id
        with pytest.raises(IntegrityError):
            async with access_session_factory.begin() as session:
                session.add(
                    MembershipRoleAssignment(
                        organization_id=org_a_id,
                        membership_id=membership_id,
                        role_id=owner.id,
                        scope_type=ScopeType.LOCATION,
                        location_id=location_b_id,
                    )
                )
                await session.flush()
        async with access_session_factory.begin() as session:
            await service.remove_assignment(
                session, org_a_id, membership_id, assignment_id, correlation_id="remove-assignment"
            )
            await service.remove_deny(
                session, org_a_id, membership_id, deny_id, correlation_id="remove-deny"
            )
        async with access_session_factory() as session:
            assert (
                await session.scalar(select(func.count()).select_from(MembershipRoleAssignment))
                == 0
            )
            assert (
                await session.scalar(select(func.count()).select_from(MembershipPermissionDeny))
                == 0
            )
            assert await session.scalar(select(func.count()).select_from(RolePermission)) == sum(
                len(value) for value in ROLE_MAPPINGS.values()
            )
            assert org_a_id != org_b_id

    asyncio.run(exercise())
