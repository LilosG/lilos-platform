"""First-platform-administrator grant service tests: idempotency and audit."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.errors import UserAccountNotFoundError
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.platform_admin.models import PlatformAdministrator
from apps.api.app.platform_admin.service import PlatformAdministrationService


@pytest.mark.integration
def test_grant_administrator_resolves_by_email_is_idempotent_and_audited(
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = PlatformAdministrationService()
        async with platform_administration_session_factory.begin() as session:
            profile = UserProfile(
                auth_user_id=uuid4(),
                email="mike@lilosgrowth.com",
                status=UserStatus.ACTIVE,
                version=1,
            )
            session.add(profile)
            await session.flush()
            profile_id = profile.id

        async with platform_administration_session_factory.begin() as session:
            with pytest.raises(UserAccountNotFoundError):
                await service.grant_administrator(
                    session,
                    email="nobody-has-signed-in@example.invalid",
                    granted_by_user_profile_id=None,
                    reason="test",
                    source="test",
                    correlation_id="grant-unknown",
                )

        async with platform_administration_session_factory.begin() as session:
            first = await service.grant_administrator(
                session,
                # Case-insensitive resolution: the caller need not match the
                # exact stored casing.
                email="  Mike@LilosGrowth.com  ",
                granted_by_user_profile_id=None,
                reason="First production platform-administrator bootstrap.",
                source="provision_platform_administrator_script",
                correlation_id="grant-first",
            )
            assert first.user_profile_id == profile_id
            assert first.grant_created is True

        async with platform_administration_session_factory() as session:
            grants = list(
                await session.scalars(
                    select(PlatformAdministrator).where(
                        PlatformAdministrator.user_profile_id == profile_id
                    )
                )
            )
            assert len(grants) == 1
            assert grants[0].revoked_at is None

            audit_event = await session.scalar(
                select(AuditEvent).where(AuditEvent.correlation_id == "grant-first")
            )
            assert audit_event is not None
            assert audit_event.event_type == "platform.administrator.granted"
            assert audit_event.actor_type.value == "system"

        # Re-running (e.g. the idempotent bootstrap script rerun) must not
        # create a second grant or a second audit event.
        async with platform_administration_session_factory.begin() as session:
            second = await service.grant_administrator(
                session,
                email="mike@lilosgrowth.com",
                granted_by_user_profile_id=None,
                reason="First production platform-administrator bootstrap.",
                source="provision_platform_administrator_script",
                correlation_id="grant-second",
            )
            assert second.grant_created is False
            assert second.grant_id == first.grant_id

        async with platform_administration_session_factory() as session:
            grants = list(
                await session.scalars(
                    select(PlatformAdministrator).where(
                        PlatformAdministrator.user_profile_id == profile_id
                    )
                )
            )
            assert len(grants) == 1
            second_audit_event = await session.scalar(
                select(AuditEvent).where(AuditEvent.correlation_id == "grant-second")
            )
            assert second_audit_event is None

    asyncio.run(exercise())


@pytest.mark.integration
def test_grant_administrator_then_authorization_dependency_allows_and_revoked_denies(
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """End-to-end: the grant this service creates is exactly what the fixed
    ``require_platform_administrator`` policy checks — no parallel role
    system, no separate authorization path."""
    from datetime import UTC, datetime, timedelta

    from apps.api.app.authentication.contracts import AuthenticatedPrincipal
    from apps.api.app.authentication.enums import AssuranceLevel
    from apps.api.app.authorization.errors import AuthorizationDeniedError
    from apps.api.app.platform_admin.dependencies import require_platform_administrator

    async def exercise() -> None:
        service = PlatformAdministrationService()
        async with platform_administration_session_factory.begin() as session:
            admin_profile = UserProfile(
                auth_user_id=uuid4(),
                email="admin@example.invalid",
                status=UserStatus.ACTIVE,
                version=1,
            )
            other_profile = UserProfile(
                auth_user_id=uuid4(),
                email="other@example.invalid",
                status=UserStatus.ACTIVE,
                version=1,
            )
            session.add_all([admin_profile, other_profile])
            await session.flush()
            admin_id, other_id = admin_profile.id, other_profile.id

        async with platform_administration_session_factory.begin() as session:
            await service.grant_administrator(
                session,
                email="admin@example.invalid",
                granted_by_user_profile_id=None,
                reason="test",
                source="test",
                correlation_id="grant-e2e",
            )

        def principal(user_profile_id: object) -> AuthenticatedPrincipal:
            now = datetime.now(UTC)
            return AuthenticatedPrincipal(
                platform_user_id=user_profile_id,  # type: ignore[arg-type]
                auth_user_id=uuid4(),
                user_status=UserStatus.ACTIVE,
                session_id=uuid4(),
                assurance_level=AssuranceLevel.AAL2,
                token_issued_at=now,
                token_expires_at=now + timedelta(minutes=5),
            )

        policy = require_platform_administrator()

        async with platform_administration_session_factory() as session:
            grant = await policy(principal(admin_id), session)
            assert grant.user_profile_id == admin_id

        async with platform_administration_session_factory() as session:
            with pytest.raises(AuthorizationDeniedError):
                await policy(principal(other_id), session)

    asyncio.run(exercise())
