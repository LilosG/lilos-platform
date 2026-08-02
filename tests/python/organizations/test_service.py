"""Transactional organization service and lifecycle tests."""

import asyncio
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.organizations.contracts import OrganizationCreate
from apps.api.app.organizations.enums import (
    OrganizationLifecycleAction,
    OrganizationStatus,
    OrganizationType,
)
from apps.api.app.organizations.errors import (
    OrganizationSlugConflictError,
    OrganizationTransitionConflictError,
    OrganizationVersionConflictError,
)
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.service import OrganizationService


def command(slug: str = "fabricated-organization") -> OrganizationCreate:
    return OrganizationCreate(
        name="Fabricated Organization",
        slug=slug,
        organization_type=OrganizationType.TEST,
        timezone="America/Los_Angeles",
        default_currency="USD",
        primary_contact_name="Fabricated Contact",
        primary_contact_email="fabricated@example.invalid",
    )


async def all_organizations(
    factory: async_sessionmaker[AsyncSession],
) -> list[Organization]:
    async with factory() as session:
        return list(await session.scalars(select(Organization)))


async def all_audit_events(factory: async_sessionmaker[AsyncSession]) -> list[AuditEvent]:
    async with factory() as session:
        return list(await session.scalars(select(AuditEvent).order_by(AuditEvent.recorded_at)))


@pytest.mark.integration
def test_creation_and_lifecycle_are_audited_atomically(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = OrganizationService()
        async with organization_session_factory.begin() as session:
            organization = await service.create(
                session, command(), correlation_id="organization-create-test"
            )
            organization_id = organization.id

        actions = [
            OrganizationLifecycleAction.START_ONBOARDING,
            OrganizationLifecycleAction.ACTIVATE,
            OrganizationLifecycleAction.PAUSE,
            OrganizationLifecycleAction.RESUME,
            OrganizationLifecycleAction.SUSPEND,
            OrganizationLifecycleAction.ACTIVATE,
            OrganizationLifecycleAction.START_OFFBOARDING,
            OrganizationLifecycleAction.ARCHIVE,
        ]
        expected_version = 1
        for action in actions:
            async with organization_session_factory.begin() as session:
                updated = await service.transition(
                    session,
                    organization_id,
                    action=action,
                    expected_version=expected_version,
                    correlation_id=f"organization-{action.value}-test",
                )
                expected_version += 1
                assert updated.version == expected_version

        organizations = await all_organizations(organization_session_factory)
        events = await all_audit_events(organization_session_factory)
        assert len(organizations) == 1
        assert organizations[0].status is OrganizationStatus.ARCHIVED
        assert organizations[0].archived_at is not None
        assert organizations[0].archived_at.tzinfo is not None
        assert len(events) == 9
        assert all(event.organization_id == organization_id for event in events)
        assert all(event.resource_id == organization_id for event in events)
        assert events[0].correlation_id == "organization-create-test"
        serialized_audit = json.dumps(
            [{"summary": event.summary, "metadata": event.event_metadata} for event in events]
        )
        assert "Fabricated Contact" not in serialized_audit
        assert "fabricated@example.invalid" not in serialized_audit

    asyncio.run(exercise())


@pytest.mark.integration
def test_invalid_stale_duplicate_and_archived_transitions_are_conflicts(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = OrganizationService()
        async with organization_session_factory.begin() as session:
            organization = await service.create(session, command(), correlation_id="create-one")
            organization_id = organization.id

        with pytest.raises(OrganizationSlugConflictError):
            async with organization_session_factory.begin() as session:
                await service.create(session, command(), correlation_id="create-duplicate")

        with pytest.raises(OrganizationTransitionConflictError):
            async with organization_session_factory.begin() as session:
                await service.transition(
                    session,
                    organization_id,
                    action=OrganizationLifecycleAction.PAUSE,
                    expected_version=1,
                    correlation_id="invalid-pause",
                )

        async with organization_session_factory.begin() as session:
            await service.transition(
                session,
                organization_id,
                action=OrganizationLifecycleAction.START_OFFBOARDING,
                expected_version=1,
                correlation_id="offboard",
            )

        with pytest.raises(OrganizationVersionConflictError):
            async with organization_session_factory.begin() as session:
                await service.transition(
                    session,
                    organization_id,
                    action=OrganizationLifecycleAction.ARCHIVE,
                    expected_version=1,
                    correlation_id="stale-archive",
                )

        async with organization_session_factory.begin() as session:
            archived = await service.transition(
                session,
                organization_id,
                action=OrganizationLifecycleAction.ARCHIVE,
                expected_version=2,
                correlation_id="archive",
            )
        assert archived.status is OrganizationStatus.ARCHIVED

        with pytest.raises(OrganizationTransitionConflictError):
            async with organization_session_factory.begin() as session:
                await service.transition(
                    session,
                    organization_id,
                    action=OrganizationLifecycleAction.ACTIVATE,
                    expected_version=3,
                    correlation_id="forbidden-reactivation",
                )

    asyncio.run(exercise())


@pytest.mark.integration
def test_failed_creation_rolls_back_organization_and_audit(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = OrganizationService()
        with pytest.raises(RuntimeError, match="forced owning failure"):
            async with organization_session_factory.begin() as session:
                await service.create(session, command(), correlation_id="rollback-create")
                raise RuntimeError("forced owning failure")

        assert await all_organizations(organization_session_factory) == []
        assert await all_audit_events(organization_session_factory) == []

    asyncio.run(exercise())


@pytest.mark.integration
def test_failed_transition_rolls_back_state_version_and_audit(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = OrganizationService()
        async with organization_session_factory.begin() as session:
            created = await service.create(
                session, command(), correlation_id="create-before-rollback"
            )
            organization_id = created.id

        with pytest.raises(RuntimeError, match="forced transition failure"):
            async with organization_session_factory.begin() as session:
                await service.transition(
                    session,
                    organization_id,
                    action=OrganizationLifecycleAction.START_ONBOARDING,
                    expected_version=1,
                    correlation_id="rollback-transition",
                )
                raise RuntimeError("forced transition failure")

        organizations = await all_organizations(organization_session_factory)
        events = await all_audit_events(organization_session_factory)
        assert organizations[0].status is OrganizationStatus.PROSPECT
        assert organizations[0].version == 1
        assert len(events) == 1
        assert events[0].event_type == "platform.organization.created"

    asyncio.run(exercise())


@pytest.mark.integration
def test_transition_is_isolated_to_the_selected_organization(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = OrganizationService()
        async with organization_session_factory.begin() as session:
            first = await service.create(
                session,
                command("fabricated-isolation-one"),
                correlation_id="isolation-create-one",
            )
            second = await service.create(
                session,
                command("fabricated-isolation-two"),
                correlation_id="isolation-create-two",
            )
            first_id = first.id
            second_id = second.id

        async with organization_session_factory.begin() as session:
            await service.transition(
                session,
                first_id,
                action=OrganizationLifecycleAction.START_ONBOARDING,
                expected_version=1,
                correlation_id="isolation-transition-one",
            )

        async with organization_session_factory() as session:
            stored_first = await service.get(session, first_id)
            stored_second = await service.get(session, second_id)
            second_events = list(
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.organization_id == second_id)
                )
            )

        assert stored_first.status is OrganizationStatus.ONBOARDING
        assert stored_first.version == 2
        assert stored_second.status is OrganizationStatus.PROSPECT
        assert stored_second.version == 1
        assert len(second_events) == 1
        assert second_events[0].event_type == "platform.organization.created"

    asyncio.run(exercise())
