"""Platform-user mapping, lifecycle, audit, rollback, and immutability tests."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.contracts import UserProfileCreate, VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserLifecycleAction, UserStatus
from apps.api.app.authentication.errors import (
    AuthenticationRequiredError,
    UserProfileConflictError,
    UserVersionConflictError,
)
from apps.api.app.authentication.models import UserProfile
from apps.api.app.authentication.service import AuthenticationService, UserAdministrationService


def command(auth_user_id: UUID | None = None) -> UserProfileCreate:
    return UserProfileCreate(
        auth_user_id=auth_user_id or uuid4(),
        email="  FABRICATED@EXAMPLE.INVALID  ",
        display_name="Fabricated User",
    )


def claims(auth_user_id: UUID) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=auth_user_id,
        session_id=uuid4(),
        assurance_level=AssuranceLevel.AAL1,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        algorithm="ES256",
        key_id="test-key",
    )


@pytest.mark.integration
def test_provision_mapping_lifecycle_and_audit_are_atomic(
    authentication_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        admin = UserAdministrationService()
        authentication = AuthenticationService()
        subject = uuid4()
        async with authentication_session_factory.begin() as session:
            profile = await admin.provision(session, command(subject), correlation_id="user-create")
            profile_id = profile.id
            assert profile.email == "fabricated@example.invalid"
            assert profile.status is UserStatus.ACTIVE
            assert profile.version == 1

        async with authentication_session_factory() as session:
            principal = await authentication.authenticate(session, claims(subject))
            assert principal.platform_user_id == profile_id
            assert not hasattr(principal, "organization_id")

        async with authentication_session_factory.begin() as session:
            deactivated = await admin.transition(
                session,
                profile_id,
                action=UserLifecycleAction.DEACTIVATE,
                expected_version=1,
                correlation_id="user-deactivate",
            )
            assert deactivated.version == 2
            assert deactivated.deactivated_at is not None

        async with authentication_session_factory() as session:
            with pytest.raises(AuthenticationRequiredError):
                await authentication.authenticate(session, claims(subject))

        async with authentication_session_factory.begin() as session:
            reactivated = await admin.transition(
                session,
                profile_id,
                action=UserLifecycleAction.REACTIVATE,
                expected_version=2,
                correlation_id="user-reactivate",
            )
            assert reactivated.version == 3
            assert reactivated.deactivated_at is None

        async with authentication_session_factory() as session:
            events = list(
                await session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.resource_id == profile_id)
                    .order_by(AuditEvent.recorded_at)
                )
            )
        assert [event.event_type for event in events] == [
            "platform.user_profile.provisioned",
            "platform.user_profile.deactivate",
            "platform.user_profile.reactivate",
        ]
        serialized = json.dumps([event.event_metadata for event in events])
        assert "fabricated@example.invalid" not in serialized

    asyncio.run(exercise())


@pytest.mark.integration
def test_unknown_duplicate_stale_and_rollback_behaviors(
    authentication_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        admin = UserAdministrationService()
        authentication = AuthenticationService()
        subject = uuid4()
        with pytest.raises(AuthenticationRequiredError):
            async with authentication_session_factory() as session:
                await authentication.authenticate(session, claims(subject))

        async with authentication_session_factory.begin() as session:
            profile = await admin.provision(session, command(subject), correlation_id="created")
            profile_id = profile.id
        with pytest.raises(UserProfileConflictError):
            async with authentication_session_factory.begin() as session:
                await admin.provision(session, command(subject), correlation_id="duplicate")
        with pytest.raises(UserVersionConflictError):
            async with authentication_session_factory.begin() as session:
                await admin.transition(
                    session,
                    profile_id,
                    action=UserLifecycleAction.DEACTIVATE,
                    expected_version=99,
                    correlation_id="stale",
                )
        with pytest.raises(RuntimeError, match="forced rollback"):
            async with authentication_session_factory.begin() as session:
                await admin.transition(
                    session,
                    profile_id,
                    action=UserLifecycleAction.DEACTIVATE,
                    expected_version=1,
                    correlation_id="rollback",
                )
                raise RuntimeError("forced rollback")
        async with authentication_session_factory() as session:
            stored = await admin.get(session, profile_id)
            events = list(
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.resource_id == profile_id)
                )
            )
        assert stored.status is UserStatus.ACTIVE
        assert stored.version == 1
        assert len(events) == 1

    asyncio.run(exercise())


@pytest.mark.integration
def test_subject_is_unique_and_database_immutable(
    authentication_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        subject = uuid4()
        async with authentication_session_factory.begin() as session:
            first = UserProfile(auth_user_id=subject, status=UserStatus.ACTIVE, version=1)
            session.add(first)
            await session.flush()
            first_id = first.id
        with pytest.raises(IntegrityError):
            async with authentication_session_factory.begin() as session:
                session.add(UserProfile(auth_user_id=subject, status=UserStatus.ACTIVE, version=1))
                await session.flush()
        with pytest.raises(IntegrityError):
            async with authentication_session_factory.begin() as session:
                await session.execute(
                    update(UserProfile)
                    .where(UserProfile.id == first_id)
                    .values(auth_user_id=uuid4())
                )

    asyncio.run(exercise())
