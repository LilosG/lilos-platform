"""Organization-domain service lifecycle, conflict, and audit tests."""

import asyncio
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.domains.contracts import OrganizationDomainCreate, normalize_domain
from apps.api.app.domains.errors import (
    OrganizationDomainConflictError,
    OrganizationDomainNotFoundError,
    OrganizationDomainPrimaryConflictError,
    OrganizationDomainVersionConflictError,
)
from apps.api.app.domains.service import OrganizationDomainService
from apps.api.app.organizations.errors import OrganizationNotFoundError
from domains.helpers import add_organization


def test_normalize_domain_accepts_bare_host_and_full_url() -> None:
    assert normalize_domain("Example.com") == "example.com"
    assert normalize_domain("https://www.Example.com/path?x=1") == "www.example.com"
    assert normalize_domain("  example.com  ") == "example.com"


def test_domain_create_rejects_malformed_values() -> None:
    with pytest.raises(ValidationError):
        OrganizationDomainCreate(domain="not a domain")
    with pytest.raises(ValidationError):
        OrganizationDomainCreate(domain="localhost")


@pytest.mark.integration
def test_domain_lifecycle_conflicts_and_audit(
    domain_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = OrganizationDomainService()
        async with domain_session_factory.begin() as session:
            organization = await add_organization(session)
            organization_id = organization.id

        async with domain_session_factory.begin() as session:
            primary = await service.create(
                session,
                organization_id,
                OrganizationDomainCreate(domain="example-client.com", is_primary=True),
                correlation_id="domain-primary-created",
            )
            assert primary.is_primary is True
            assert primary.version == 1

        async with domain_session_factory() as session:
            audit_event = await session.scalar(
                select(AuditEvent).where(AuditEvent.correlation_id == "domain-primary-created")
            )
            assert audit_event is not None
            assert audit_event.event_type == "platform.organization_domain.created"

        # Duplicate active domain for the same organization is rejected.
        async with domain_session_factory.begin() as session:
            with pytest.raises(OrganizationDomainConflictError):
                await service.create(
                    session,
                    organization_id,
                    OrganizationDomainCreate(domain="example-client.com"),
                    correlation_id="domain-dup",
                )

        # A second primary domain at create time is rejected.
        async with domain_session_factory.begin() as session:
            with pytest.raises(OrganizationDomainPrimaryConflictError):
                await service.create(
                    session,
                    organization_id,
                    OrganizationDomainCreate(domain="second.example.com", is_primary=True),
                    correlation_id="domain-second-primary",
                )

        async with domain_session_factory.begin() as session:
            secondary = await service.create(
                session,
                organization_id,
                OrganizationDomainCreate(domain="second.example.com"),
                correlation_id="domain-secondary-created",
            )
            secondary_id = secondary.id

        # Switching primary clears the old one atomically.
        async with domain_session_factory.begin() as session:
            new_primary = await service.set_primary(
                session,
                organization_id,
                secondary_id,
                expected_version=1,
                correlation_id="domain-primary-switch",
            )
            assert new_primary.is_primary is True

        async with domain_session_factory() as session:
            domains = await service.list(session, organization_id)
            by_domain = {item.domain: item for item in domains}
            assert by_domain["second.example.com"].is_primary is True
            assert by_domain["example-client.com"].is_primary is False

        # Stale version is rejected.
        async with domain_session_factory.begin() as session:
            with pytest.raises(OrganizationDomainVersionConflictError):
                await service.archive(
                    session,
                    organization_id,
                    secondary_id,
                    expected_version=1,
                    correlation_id="domain-archive-stale",
                )

        async with domain_session_factory.begin() as session:
            archived = await service.archive(
                session,
                organization_id,
                secondary_id,
                expected_version=2,
                correlation_id="domain-archive",
            )
            assert archived.status.value == "archived"
            assert archived.is_primary is False
            assert archived.archived_at is not None

        # Archived domains are history, not active configuration, so they must
        # disappear from the normal organization-domain list.
        async with domain_session_factory() as session:
            domains = await service.list(session, organization_id)
            assert {item.domain for item in domains} == {"example-client.com"}

        # Re-adding the same normalized host restores the archived lifecycle
        # record instead of colliding with its permanent uniqueness constraint.
        async with domain_session_factory.begin() as session:
            reactivated = await service.create(
                session,
                organization_id,
                OrganizationDomainCreate(
                    domain="https://second.example.com/path", is_primary=True
                ),
                correlation_id="domain-reactivated",
            )
            assert reactivated.id == secondary_id
            assert reactivated.status.value == "active"
            assert reactivated.is_primary is True
            assert reactivated.archived_at is None
            assert reactivated.version == 4

        async with domain_session_factory() as session:
            domains = await service.list(session, organization_id)
            by_domain = {item.domain: item for item in domains}
            assert set(by_domain) == {"example-client.com", "second.example.com"}
            assert by_domain["second.example.com"].is_primary is True
            assert by_domain["example-client.com"].is_primary is False
            reactivation_audit = await session.scalar(
                select(AuditEvent).where(AuditEvent.correlation_id == "domain-reactivated")
            )
            assert reactivation_audit is not None
            assert reactivation_audit.event_type == "platform.organization_domain.reactivated"

        async with domain_session_factory.begin() as session:
            with pytest.raises(OrganizationDomainNotFoundError):
                await service.set_primary(
                    session,
                    organization_id,
                    uuid4(),
                    expected_version=1,
                    correlation_id="domain-missing",
                )

        async with domain_session_factory.begin() as session:
            with pytest.raises(OrganizationNotFoundError):
                await service.list(session, UUID(int=0))

    asyncio.run(exercise())
