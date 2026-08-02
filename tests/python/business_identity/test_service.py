"""Transactional resolution, lifecycle, missing-data, claims, and isolation tests."""

import inspect
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.business_identity.contracts import ScalarSource
from apps.api.app.business_identity.service import BusinessIdentityService
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.location_groups.enums import LocationGroupStatus
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.errors import LocationNotFoundError
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization

from .helpers import (
    add_group_membership,
    add_industry,
    add_location,
    add_location_profile,
    add_organization,
    add_organization_profile,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.integration
async def test_resolves_organization_with_profile_and_active_industry(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        industry = await add_industry(session)
        organization = await add_organization(session, industry_id=industry.id)
        await add_organization_profile(session, organization.id)
        result = await BusinessIdentityService().resolve_organization(session, organization.id)
        assert result.has_industry is result.has_organization_profile is True
        assert result.industry is not None and result.industry.key == industry.key
        assert result.organization_profile is not None
        assert result.organization_profile.primary_services == ("Organization Service",)
        assert result.organization_profile.approved_claims == ("Organization approved",)


@pytest.mark.integration
async def test_missing_profile_and_legacy_missing_industry_are_explicit(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        organization = await add_organization(session)
        result = await BusinessIdentityService().resolve_organization(session, organization.id)
        assert result.industry is None
        assert result.organization_profile is None
        assert result.has_industry is result.has_organization_profile is False


@pytest.mark.integration
@pytest.mark.parametrize("status", list(OrganizationStatus))
async def test_organization_identity_reads_all_lifecycle_states(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
    status: OrganizationStatus,
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        organization = await add_organization(session, status=status)
        result = await BusinessIdentityService().resolve_organization(session, organization.id)
        assert result.organization.status is status


@pytest.mark.integration
async def test_deprecated_assigned_industry_remains_readable(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        industry = await add_industry(session, status=IndustryStatus.DEPRECATED)
        organization = await add_organization(session, industry_id=industry.id)
        result = await BusinessIdentityService().resolve_organization(session, organization.id)
        assert result.industry is not None
        assert result.industry.status is IndustryStatus.DEPRECATED


@pytest.mark.integration
@pytest.mark.parametrize("status", list(LocationStatus))
async def test_location_identity_reads_all_lifecycle_states(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
    status: LocationStatus,
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        organization = await add_organization(session)
        location = await add_location(session, organization.id, status=status)
        result = await BusinessIdentityService().resolve_location(
            session, organization.id, location.id
        )
        assert result.location.status is status


@pytest.mark.integration
async def test_location_context_lists_and_claims_remain_separately_attributable(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        organization = await add_organization(session)
        location = await add_location(session, organization.id)
        await add_organization_profile(session, organization.id)
        await add_location_profile(session, organization.id, location.id)
        result = await BusinessIdentityService().resolve_location(
            session, organization.id, location.id
        )
        assert result.organization_profile is not None
        assert result.location_profile is not None
        assert result.organization_profile.primary_services == ("Organization Service",)
        assert result.location_profile.primary_services == ("Location Service",)
        assert result.organization_profile.approved_claims == ("Organization approved",)
        assert result.location_profile.approved_claims == ("Location approved",)
        assert result.organization_profile.prohibited_claims == ("Organization prohibited",)
        assert result.location_profile.prohibited_claims == ("Location prohibited",)


@pytest.mark.integration
async def test_call_to_action_override_and_fallback_are_traceable(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        organization = await add_organization(session)
        first_location = await add_location(session, organization.id)
        second_location = await add_location(session, organization.id)
        await add_organization_profile(session, organization.id)
        await add_location_profile(session, organization.id, first_location.id)
        await add_location_profile(
            session, organization.id, second_location.id, call_to_action_override=None
        )
        service = BusinessIdentityService()
        overridden = await service.resolve_location(session, organization.id, first_location.id)
        fallback = await service.resolve_location(session, organization.id, second_location.id)
        assert overridden.resolved_call_to_action.value == "Location CTA"
        assert overridden.resolved_call_to_action.source is ScalarSource.LOCATION_PROFILE
        assert fallback.resolved_call_to_action.value == "Organization CTA"
        assert fallback.resolved_call_to_action.source is ScalarSource.ORGANIZATION_PROFILE


@pytest.mark.integration
async def test_missing_profiles_do_not_fabricate_defaults(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        organization = await add_organization(session)
        location = await add_location(session, organization.id)
        result = await BusinessIdentityService().resolve_location(
            session, organization.id, location.id
        )
        assert result.organization_profile is None
        assert result.location_profile is None
        assert result.resolved_call_to_action.value is None
        assert result.resolved_call_to_action.source is ScalarSource.NONE


@pytest.mark.integration
async def test_groups_do_not_enter_business_identity(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        organization = await add_organization(session)
        location = await add_location(session, organization.id)
        await add_group_membership(
            session, organization.id, location.id, status=LocationGroupStatus.ACTIVE
        )
        await add_group_membership(
            session, organization.id, location.id, status=LocationGroupStatus.ARCHIVED
        )
        result = await BusinessIdentityService().resolve_location(
            session, organization.id, location.id
        )
        assert "group" not in result.model_dump_json()


@pytest.mark.integration
async def test_cross_organization_location_is_indistinguishable_from_missing(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        first = await add_organization(session)
        second = await add_organization(session)
        location = await add_location(session, first.id)
        service = BusinessIdentityService()
        with pytest.raises(LocationNotFoundError) as cross:
            await service.resolve_location(session, second.id, location.id)
        with pytest.raises(LocationNotFoundError) as missing:
            await service.resolve_location(session, second.id, uuid4())
        assert type(cross.value) is type(missing.value)


@pytest.mark.integration
async def test_resolution_is_read_only_and_creates_no_persisted_identity(
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with business_identity_session_factory() as session, session.begin():
        organization = await add_organization(session)
        location = await add_location(session, organization.id)
        before = await session.scalar(
            select(Organization.version).where(Organization.id == organization.id)
        )
        await BusinessIdentityService().resolve_location(session, organization.id, location.id)
        await session.flush()
        after = await session.scalar(
            select(Organization.version).where(Organization.id == organization.id)
        )
        assert before == after == 1
        assert not session.new and not session.dirty and not session.deleted
        assert all("business_identity" not in method for method in dir(BusinessIdentityService))
        assert all(
            name in {"resolve_location", "resolve_organization"} or name.startswith("_")
            for name, value in inspect.getmembers(BusinessIdentityService, inspect.isfunction)
        )
