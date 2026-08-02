"""Industry lifecycle, organization assignment, audit, and rollback tests."""

import asyncio
import json
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.industries.contracts import IndustryCreate
from apps.api.app.industries.enums import IndustryLifecycleAction, IndustryStatus
from apps.api.app.industries.errors import (
    IndustryAssignmentConflictError,
    IndustryKeyConflictError,
    IndustryTransitionConflictError,
    IndustryVersionConflictError,
)
from apps.api.app.industries.service import IndustryService
from apps.api.app.organizations.contracts import OrganizationCreate
from apps.api.app.organizations.enums import (
    OrganizationLifecycleAction,
    OrganizationStatus,
    OrganizationType,
)
from apps.api.app.organizations.errors import OrganizationVersionConflictError
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.service import OrganizationService


def industry_command(key: str = "fabricated_industry") -> IndustryCreate:
    return IndustryCreate(
        key=key,
        name="Fabricated Industry",
        default_configuration={"workflow": {"approval": True}},
        default_risk_policy={"risk": {"threshold": 3}},
        default_content_policy={"content": {"tone": "neutral"}},
    )


def organization_command(
    organization_type: OrganizationType,
    *,
    industry_id: UUID | None = None,
    slug: str = "fabricated_organization",
) -> OrganizationCreate:
    return OrganizationCreate(
        name="Fabricated Organization",
        slug=slug.replace("_", "-"),
        organization_type=organization_type,
        timezone="UTC",
        default_currency="USD",
        industry_id=industry_id,
    )


@pytest.mark.integration
def test_creation_lifecycle_audit_and_terminal_behavior(
    industry_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = IndustryService()
        async with industry_session_factory.begin() as session:
            created = await service.create(
                session, industry_command(), correlation_id="industry-create"
            )
            identifier = created.id
        with pytest.raises(IndustryKeyConflictError):
            async with industry_session_factory.begin() as session:
                await service.create(session, industry_command(), correlation_id="duplicate")
        with pytest.raises(IndustryTransitionConflictError):
            async with industry_session_factory.begin() as session:
                await service.transition(
                    session,
                    identifier,
                    action=IndustryLifecycleAction.ARCHIVE,
                    expected_version=1,
                    correlation_id="direct-archive",
                )
        async with industry_session_factory.begin() as session:
            deprecated = await service.transition(
                session,
                identifier,
                action=IndustryLifecycleAction.DEPRECATE,
                expected_version=1,
                correlation_id="deprecate",
            )
            assert deprecated.status is IndustryStatus.DEPRECATED and deprecated.version == 2
        with pytest.raises(IndustryVersionConflictError):
            async with industry_session_factory.begin() as session:
                await service.transition(
                    session,
                    identifier,
                    action=IndustryLifecycleAction.REACTIVATE,
                    expected_version=1,
                    correlation_id="stale",
                )
        async with industry_session_factory.begin() as session:
            reactivated = await service.transition(
                session,
                identifier,
                action=IndustryLifecycleAction.REACTIVATE,
                expected_version=2,
                correlation_id="reactivate",
            )
            assert reactivated.version == 3
        async with industry_session_factory.begin() as session:
            await service.transition(
                session,
                identifier,
                action=IndustryLifecycleAction.DEPRECATE,
                expected_version=3,
                correlation_id="deprecate-again",
            )
        async with industry_session_factory.begin() as session:
            archived = await service.transition(
                session,
                identifier,
                action=IndustryLifecycleAction.ARCHIVE,
                expected_version=4,
                correlation_id="archive",
            )
            assert archived.archived_at is not None and archived.version == 5
        with pytest.raises(IndustryTransitionConflictError):
            async with industry_session_factory.begin() as session:
                await service.transition(
                    session,
                    identifier,
                    action=IndustryLifecycleAction.REACTIVATE,
                    expected_version=5,
                    correlation_id="terminal",
                )
        async with industry_session_factory() as session:
            events = list(
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.resource_id == identifier)
                )
            )
        assert len(events) == 5
        assert all(event.organization_id is None for event in events)
        serialized = json.dumps([event.event_metadata for event in events])
        assert "workflow" not in serialized
        assert "threshold" not in serialized
        assert "tone" not in serialized

    asyncio.run(exercise())


def test_customer_creation_contract_requires_industry() -> None:
    for organization_type in (
        OrganizationType.CLIENT,
        OrganizationType.PARTNER,
        OrganizationType.DEMO,
    ):
        with pytest.raises(ValidationError):
            organization_command(organization_type)
    for organization_type in (OrganizationType.INTERNAL, OrganizationType.TEST):
        assert organization_command(organization_type).industry_id is None


@pytest.mark.integration
def test_creation_assignment_compatibility_concurrency_and_rollback(
    industry_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        industry_service = IndustryService()
        organization_service = OrganizationService()
        async with industry_session_factory.begin() as session:
            active = await industry_service.create(
                session, industry_command("active_industry"), correlation_id="industry-active"
            )
            deprecated = await industry_service.create(
                session,
                industry_command("deprecated_industry"),
                correlation_id="industry-deprecated",
            )
            active_id, deprecated_id = active.id, deprecated.id
        async with industry_session_factory.begin() as session:
            await industry_service.transition(
                session,
                deprecated_id,
                action=IndustryLifecycleAction.DEPRECATE,
                expected_version=1,
                correlation_id="deprecate-for-assignment",
            )
        for organization_type, suffix in (
            (OrganizationType.CLIENT, "client"),
            (OrganizationType.PARTNER, "partner"),
            (OrganizationType.DEMO, "demo"),
        ):
            async with industry_session_factory.begin() as session:
                created = await organization_service.create(
                    session,
                    organization_command(
                        organization_type,
                        industry_id=active_id,
                        slug=f"fabricated-{suffix}",
                    ),
                    correlation_id=f"create-{suffix}",
                )
                assert created.industry_id == active_id
        for organization_type, suffix in (
            (OrganizationType.INTERNAL, "internal"),
            (OrganizationType.TEST, "test"),
        ):
            async with industry_session_factory.begin() as session:
                created = await organization_service.create(
                    session,
                    organization_command(organization_type, slug=f"fabricated-{suffix}"),
                    correlation_id=f"create-{suffix}",
                )
                assert created.industry_id is None
        async with industry_session_factory.begin() as session:
            legacy = Organization(
                name="Fabricated Legacy Organization",
                slug="fabricated-legacy",
                organization_type=OrganizationType.CLIENT,
                status=OrganizationStatus.PROSPECT,
                timezone="UTC",
                default_currency="USD",
                industry_id=None,
                version=1,
            )
            await organization_service.repository.add(session, legacy)
            legacy_id = legacy.id
        async with industry_session_factory() as session:
            readable = await organization_service.get(session, legacy_id)
            assert readable.industry_id is None and readable.status is OrganizationStatus.PROSPECT
        async with industry_session_factory.begin() as session:
            lifecycle_updated = await organization_service.transition(
                session,
                legacy_id,
                action=OrganizationLifecycleAction.START_ONBOARDING,
                expected_version=1,
                correlation_id="legacy-start-onboarding",
            )
            assert lifecycle_updated.industry_id is None
            assert lifecycle_updated.status is OrganizationStatus.ONBOARDING
            assert lifecycle_updated.version == 2
        with pytest.raises(IndustryAssignmentConflictError):
            async with industry_session_factory.begin() as session:
                await organization_service.set_industry(
                    session,
                    legacy_id,
                    industry_id=deprecated_id,
                    expected_version=2,
                    correlation_id="invalid-assignment",
                )
        async with industry_session_factory.begin() as session:
            await industry_service.transition(
                session,
                deprecated_id,
                action=IndustryLifecycleAction.ARCHIVE,
                expected_version=2,
                correlation_id="archive-for-assignment",
            )
        with pytest.raises(IndustryAssignmentConflictError):
            async with industry_session_factory.begin() as session:
                await organization_service.set_industry(
                    session,
                    legacy_id,
                    industry_id=deprecated_id,
                    expected_version=2,
                    correlation_id="archived-assignment",
                )
        with pytest.raises(RuntimeError, match="forced assignment rollback"):
            async with industry_session_factory.begin() as session:
                await organization_service.set_industry(
                    session,
                    legacy_id,
                    industry_id=active_id,
                    expected_version=2,
                    correlation_id="rolled-back-assignment",
                )
                raise RuntimeError("forced assignment rollback")
        async with industry_session_factory() as session:
            unchanged = await organization_service.get(session, legacy_id)
            rolled_back_event = await session.scalar(
                select(AuditEvent).where(AuditEvent.correlation_id == "rolled-back-assignment")
            )
            assert unchanged.industry_id is None and unchanged.version == 2
            assert rolled_back_event is None
        async with industry_session_factory.begin() as session:
            assigned = await organization_service.set_industry(
                session,
                legacy_id,
                industry_id=active_id,
                expected_version=2,
                correlation_id="assign-industry",
            )
            assert assigned.industry_id == active_id and assigned.version == 3
        with pytest.raises(OrganizationVersionConflictError):
            async with industry_session_factory.begin() as session:
                await organization_service.set_industry(
                    session,
                    legacy_id,
                    industry_id=active_id,
                    expected_version=2,
                    correlation_id="stale-assignment",
                )
        async with industry_session_factory.begin() as session:
            await industry_service.transition(
                session,
                active_id,
                action=IndustryLifecycleAction.DEPRECATE,
                expected_version=1,
                correlation_id="deprecate-assigned-industry",
            )
        async with industry_session_factory() as session:
            still_readable = await organization_service.get(session, legacy_id)
            assert still_readable.industry_id == active_id
        async with industry_session_factory() as session:
            assignment_event = await session.scalar(
                select(AuditEvent).where(AuditEvent.correlation_id == "assign-industry")
            )
            assert assignment_event is not None
            assert assignment_event.organization_id == legacy_id
            assert assignment_event.event_metadata == {
                "industry_id": str(active_id),
                "industry_key": "active_industry",
                "previous_industry_id": None,
                "organization_version": 3,
            }

    asyncio.run(exercise())
