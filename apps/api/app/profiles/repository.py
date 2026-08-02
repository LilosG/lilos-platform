"""Narrow profile persistence with scoped retrieval and compare-and-swap replacement."""

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.base import utc_now
from apps.api.app.profiles.contracts import LocationProfileReplace, OrganizationProfileReplace
from apps.api.app.profiles.models import LocationProfile, OrganizationProfile

ORGANIZATION_CONTENT_FIELDS = (
    "brand_name",
    "brand_summary",
    "business_description",
    "value_proposition",
    "target_customer",
    "primary_services",
    "approved_claims",
    "prohibited_claims",
    "tone_guidelines",
    "legal_disclaimers",
    "default_call_to_action",
)
LOCATION_CONTENT_FIELDS = (
    "local_description",
    "primary_services",
    "service_area",
    "local_landmarks",
    "local_references",
    "approved_claims",
    "prohibited_claims",
    "tone_overrides",
    "call_to_action_override",
)


@dataclass(frozen=True, slots=True)
class OrganizationProfileRepository:
    async def add(self, session: AsyncSession, profile: OrganizationProfile) -> OrganizationProfile:
        session.add(profile)
        await session.flush()
        return profile

    async def get_for_organization(
        self, session: AsyncSession, organization_id: UUID
    ) -> OrganizationProfile | None:
        return cast(
            OrganizationProfile | None,
            await session.scalar(
                select(OrganizationProfile).where(
                    OrganizationProfile.organization_id == organization_id
                )
            ),
        )

    async def replace(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: OrganizationProfileReplace,
    ) -> OrganizationProfile | None:
        values = {field: getattr(command, field) for field in ORGANIZATION_CONTENT_FIELDS}
        statement = (
            update(OrganizationProfile)
            .where(
                OrganizationProfile.organization_id == organization_id,
                OrganizationProfile.version == command.expected_version,
            )
            .values(**values, version=OrganizationProfile.version + 1, updated_at=utc_now())
            .returning(OrganizationProfile)
        )
        return cast(OrganizationProfile | None, await session.scalar(statement))


@dataclass(frozen=True, slots=True)
class LocationProfileRepository:
    async def add(self, session: AsyncSession, profile: LocationProfile) -> LocationProfile:
        session.add(profile)
        await session.flush()
        return profile

    async def get_for_location(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
    ) -> LocationProfile | None:
        return cast(
            LocationProfile | None,
            await session.scalar(
                select(LocationProfile).where(
                    LocationProfile.organization_id == organization_id,
                    LocationProfile.location_id == location_id,
                )
            ),
        )

    async def replace(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        command: LocationProfileReplace,
    ) -> LocationProfile | None:
        values = {field: getattr(command, field) for field in LOCATION_CONTENT_FIELDS}
        statement = (
            update(LocationProfile)
            .where(
                LocationProfile.organization_id == organization_id,
                LocationProfile.location_id == location_id,
                LocationProfile.version == command.expected_version,
            )
            .values(**values, version=LocationProfile.version + 1, updated_at=utc_now())
            .returning(LocationProfile)
        )
        return cast(LocationProfile | None, await session.scalar(statement))
