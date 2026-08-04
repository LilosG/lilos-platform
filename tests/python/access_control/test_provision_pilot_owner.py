"""Integration tests for the idempotent pilot-owner provisioning script."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.enums import MembershipStatus
from apps.api.app.access_control.models import MembershipRoleAssignment, OrganizationMembership
from apps.api.app.authentication.models import UserProfile
from apps.api.app.industries.contracts import IndustryCreate
from apps.api.app.industries.service import IndustryService
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from scripts import provision_pilot_owner

# All async work per test runs inside one asyncio.run() call. access_session_factory's
# engine binds its pooled connections to the event loop active when first used;
# spanning multiple asyncio.run() calls (multiple loops) against that same engine
# breaks connection cleanup, independent of the script under test.


async def _seed_catalog(access_session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with access_session_factory.begin() as session:
        await AccessCatalogSeeder().seed(session, correlation_id="test-catalog-seed")


async def _seed_industry(
    access_session_factory: async_sessionmaker[AsyncSession], key: str
) -> None:
    async with access_session_factory.begin() as session:
        await IndustryService().create(
            session,
            IndustryCreate(key=key, name=key.replace("_", " ").title()),
            correlation_id="test-industry-seed",
        )


async def _inspect(
    access_session_factory: async_sessionmaker[AsyncSession], auth_user_id: object, slug: str
) -> tuple[Organization, OrganizationMembership, list[MembershipRoleAssignment], UserProfile]:
    async with access_session_factory() as session:
        profile = (
            await session.scalars(
                select(UserProfile).where(UserProfile.auth_user_id == auth_user_id)
            )
        ).one()
        organization = (
            await session.scalars(select(Organization).where(Organization.slug == slug))
        ).one()
        membership = (
            await session.scalars(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == organization.id
                )
            )
        ).one()
        assignments = list(
            await session.scalars(
                select(MembershipRoleAssignment).where(
                    MembershipRoleAssignment.membership_id == membership.id
                )
            )
        )
        return organization, membership, assignments, profile


@pytest.mark.integration
def test_provision_creates_all_records_and_is_idempotent(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    auth_user_id = uuid4()
    slug = f"pilot-{uuid4().hex[:8]}"
    monkeypatch.setenv("PILOT_OWNER_AUTH_USER_ID", str(auth_user_id))
    monkeypatch.setenv("PILOT_ORGANIZATION_NAME", "Pilot Test Org")
    monkeypatch.setenv("PILOT_ORGANIZATION_SLUG", slug)
    monkeypatch.setenv("PILOT_INDUSTRY_KEY", "general_local_business")
    monkeypatch.setenv("PILOT_OWNER_EMAIL", "pilot-owner@example.invalid")

    async def scenario() -> tuple[
        tuple[Organization, OrganizationMembership, list[MembershipRoleAssignment], UserProfile],
        tuple[Organization, OrganizationMembership, list[MembershipRoleAssignment], UserProfile],
    ]:
        await _seed_catalog(access_session_factory)
        await _seed_industry(access_session_factory, "general_local_business")

        await provision_pilot_owner.provision()
        first = await _inspect(access_session_factory, auth_user_id, slug)

        # Re-running with identical inputs must not create duplicate records.
        await provision_pilot_owner.provision()
        second = await _inspect(access_session_factory, auth_user_id, slug)
        return first, second

    (
        (organization, membership, assignments, profile),
        (
            organization_again,
            membership_again,
            assignments_again,
            _,
        ),
    ) = asyncio.run(scenario())

    assert organization.status is OrganizationStatus.ACTIVE
    assert membership.status is MembershipStatus.ACTIVE
    assert len(assignments) == 1
    assert profile.email == "pilot-owner@example.invalid"
    assert organization_again.id == organization.id
    assert membership_again.id == membership.id
    assert len(assignments_again) == 1


@pytest.mark.integration
def test_missing_required_environment_variable_blocks(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.delenv("PILOT_OWNER_AUTH_USER_ID", raising=False)
    monkeypatch.setenv("PILOT_ORGANIZATION_NAME", "Pilot Test Org")
    monkeypatch.setenv("PILOT_ORGANIZATION_SLUG", f"pilot-{uuid4().hex[:8]}")

    with pytest.raises(SystemExit, match="PILOT_OWNER_AUTH_USER_ID"):
        asyncio.run(provision_pilot_owner.provision())


@pytest.mark.integration
def test_client_organization_without_industry_key_blocks(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    monkeypatch.delenv("PILOT_INDUSTRY_KEY", raising=False)
    monkeypatch.setenv("PILOT_OWNER_AUTH_USER_ID", str(uuid4()))
    monkeypatch.setenv("PILOT_ORGANIZATION_NAME", "Pilot Test Org")
    monkeypatch.setenv("PILOT_ORGANIZATION_SLUG", f"pilot-{uuid4().hex[:8]}")

    with pytest.raises(SystemExit, match="requires PILOT_INDUSTRY_KEY"):
        asyncio.run(provision_pilot_owner.provision())


@pytest.mark.integration
def test_unseeded_owner_role_blocks_without_creating_partial_state(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    monkeypatch.setenv("LILOS_DATABASE_URL", postgresql_test_url)
    auth_user_id = uuid4()
    slug = f"pilot-{uuid4().hex[:8]}"
    monkeypatch.setenv("PILOT_OWNER_AUTH_USER_ID", str(auth_user_id))
    monkeypatch.setenv("PILOT_ORGANIZATION_NAME", "Pilot Test Org")
    monkeypatch.setenv("PILOT_ORGANIZATION_SLUG", slug)
    monkeypatch.setenv("PILOT_INDUSTRY_KEY", "general_local_business")

    async def scenario() -> tuple[bool, bool]:
        await _seed_industry(access_session_factory, "general_local_business")
        raised = False
        try:
            await provision_pilot_owner.provision()
        except SystemExit as error:
            raised = "organization_owner role is not seeded" in str(error)
        async with access_session_factory() as session:
            exists = (
                await session.scalar(select(Organization).where(Organization.slug == slug))
            ) is not None
        return raised, exists

    raised, organization_exists = asyncio.run(scenario())
    assert raised is True
    assert organization_exists is False
