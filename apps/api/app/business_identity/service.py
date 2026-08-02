"""Deterministic, transaction-local business-identity composition."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.business_identity.contracts import (
    IndustryIdentity,
    LocationBusinessIdentity,
    LocationIdentity,
    LocationProfileIdentity,
    OrganizationBusinessIdentity,
    OrganizationIdentity,
    OrganizationProfileIdentity,
    ResolvedCallToAction,
    ScalarSource,
)
from apps.api.app.industries.repository import IndustryRepository
from apps.api.app.locations.errors import LocationNotFoundError
from apps.api.app.locations.repository import LocationRepository
from apps.api.app.organizations.errors import OrganizationNotFoundError
from apps.api.app.organizations.repository import OrganizationRepository
from apps.api.app.profiles.repository import (
    LocationProfileRepository,
    OrganizationProfileRepository,
)


@dataclass(frozen=True, slots=True)
class BusinessIdentityService:
    """Compose current authoritative records without persistence or mutation."""

    organizations: OrganizationRepository = field(default_factory=OrganizationRepository)
    locations: LocationRepository = field(default_factory=LocationRepository)
    industries: IndustryRepository = field(default_factory=IndustryRepository)
    organization_profiles: OrganizationProfileRepository = field(
        default_factory=OrganizationProfileRepository
    )
    location_profiles: LocationProfileRepository = field(default_factory=LocationProfileRepository)

    async def resolve_organization(
        self, session: AsyncSession, organization_id: UUID
    ) -> OrganizationBusinessIdentity:
        organization = await self.organizations.get_by_id(session, organization_id)
        if organization is None:
            raise OrganizationNotFoundError
        industry = (
            await self.industries.get_by_id(session, organization.industry_id)
            if organization.industry_id is not None
            else None
        )
        profile = await self.organization_profiles.get_for_organization(session, organization_id)
        return OrganizationBusinessIdentity(
            organization=OrganizationIdentity.model_validate(organization),
            industry=IndustryIdentity.model_validate(industry) if industry is not None else None,
            organization_profile=(
                OrganizationProfileIdentity.model_validate(profile) if profile is not None else None
            ),
            has_industry=industry is not None,
            has_organization_profile=profile is not None,
        )

    async def resolve_location(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
    ) -> LocationBusinessIdentity:
        organization_identity = await self.resolve_organization(session, organization_id)
        location = await self.locations.get_by_id(session, organization_id, location_id)
        if location is None:
            raise LocationNotFoundError
        location_profile = await self.location_profiles.get_for_location(
            session, organization_id, location_id
        )
        resolved_call_to_action = _resolve_call_to_action(
            organization_identity.organization_profile,
            (
                LocationProfileIdentity.model_validate(location_profile)
                if location_profile is not None
                else None
            ),
        )
        location_profile_identity = (
            LocationProfileIdentity.model_validate(location_profile)
            if location_profile is not None
            else None
        )
        return LocationBusinessIdentity(
            **organization_identity.model_dump(),
            location=LocationIdentity.model_validate(location),
            location_profile=location_profile_identity,
            has_location_profile=location_profile_identity is not None,
            resolved_call_to_action=resolved_call_to_action,
        )


def _resolve_call_to_action(
    organization_profile: OrganizationProfileIdentity | None,
    location_profile: LocationProfileIdentity | None,
) -> ResolvedCallToAction:
    if location_profile is not None and location_profile.call_to_action_override is not None:
        return ResolvedCallToAction(
            value=location_profile.call_to_action_override,
            source=ScalarSource.LOCATION_PROFILE,
        )
    if organization_profile is not None and organization_profile.default_call_to_action is not None:
        return ResolvedCallToAction(
            value=organization_profile.default_call_to_action,
            source=ScalarSource.ORGANIZATION_PROFILE,
        )
    return ResolvedCallToAction(value=None, source=ScalarSource.NONE)
