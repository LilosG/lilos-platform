"""Location-scope regressions for product readiness."""

import asyncio
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.contracts import (
    BusinessFactDecision,
    BusinessFactPropose,
    EntitlementCreate,
)
from apps.api.app.administration.enums import FactAuthority
from apps.api.app.administration.service import AdministrationService
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.models import LocationProfile, OrganizationProfile


async def _approve_fact(
    session: AsyncSession,
    service: AdministrationService,
    organization_id: UUID,
    actor_id: UUID,
    *,
    fact_key: str,
    value_type: str,
    value: object,
    location_id: UUID | None = None,
) -> UUID:
    proposed = await service.propose_fact(
        session,
        organization_id,
        BusinessFactPropose.model_validate(
            {
                "location_id": location_id,
                "fact_key": fact_key,
                "value_type": value_type,
                "value": value,
                "source": "readiness-scope-test",
                "authority": FactAuthority.CLIENT_APPROVED,
                "change_reason": "Authoritative test fixture",
            }
        ),
        actor_id=actor_id,
        correlation_id="readiness-scope-test",
    )
    approved = await service.decide_fact(
        session,
        organization_id,
        proposed.id,
        BusinessFactDecision(decision="approve"),
        actor_id=actor_id,
        correlation_id="readiness-scope-test",
    )
    return approved.id


async def _create_client(
    session: AsyncSession,
    *,
    suffix: str,
    statuses: tuple[LocationStatus, ...],
) -> tuple[UUID, list[UUID]]:
    organization = Organization(
        name=f"Readiness {suffix}",
        slug=f"readiness-{suffix}",
        organization_type=OrganizationType.CLIENT,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(organization)
    await session.flush()
    session.add(OrganizationProfile(organization_id=organization.id, version=1))
    locations: list[Location] = []
    for index, status in enumerate(statuses):
        locations.append(
            Location(
                organization_id=organization.id,
                name=f"Location {index + 1}",
                slug=f"location-{index + 1}",
                location_type=LocationType.PHYSICAL,
                status=status,
                timezone="UTC",
                country_code="US",
                address_line_1=f"{index + 1} Test Street",
                city="Test City",
                region="CA",
                postal_code=f"9000{index}",
                is_primary=index == 0,
                version=1,
            )
        )
    session.add_all(locations)
    await session.flush()
    return organization.id, [location.id for location in locations]


def test_readiness_evaluates_facts_and_profiles_at_entitled_location_scope(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_readiness_scope(administration_session_factory))


async def _readiness_scope(factory: async_sessionmaker[AsyncSession]) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    async with factory() as session, session.begin():
        session.add(
            UserProfile(
                id=actor_id,
                auth_user_id=uuid4(),
                email="readiness@example.invalid",
                display_name="Readiness Operator",
                status=UserStatus.ACTIVE,
                version=1,
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="readiness-scope-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="readiness-scope-test")

        organization_wide, wide_locations = await _create_client(
            session,
            suffix="wide",
            statuses=(LocationStatus.ACTIVE, LocationStatus.ACTIVE),
        )
        await service.create_entitlement(
            session,
            organization_wide,
            EntitlementCreate(product_key="seo", source="test", reason="Organization-wide"),
            actor_id=actor_id,
            correlation_id="readiness-scope-test",
        )
        name_revision = await _approve_fact(
            session,
            service,
            organization_wide,
            actor_id,
            fact_key="business.name",
            value_type="string",
            value="Organization Wide",
        )
        first_address_revision = await _approve_fact(
            session,
            service,
            organization_wide,
            actor_id,
            location_id=wide_locations[0],
            fact_key="business.address",
            value_type="object",
            value={"address_line_1": "1 Main Street"},
        )
        session.add_all(
            [
                LocationProfile(
                    organization_id=organization_wide,
                    location_id=location_id,
                    version=1,
                )
                for location_id in wide_locations
            ]
        )
        await session.flush()

        unresolved = await service.readiness(session, organization_wide, "seo")
        assert unresolved.selected_location_ids == ()
        assert "BUSINESS_FACT_UNRESOLVED" in {
            finding.code for finding in unresolved.blocking_requirements
        }

        second_address_revision = await _approve_fact(
            session,
            service,
            organization_wide,
            actor_id,
            location_id=wide_locations[1],
            fact_key="business.address",
            value_type="object",
            value={"address_line_1": "2 Main Street"},
        )
        resolved = await service.readiness(session, organization_wide, "seo")
        resolved_codes = {finding.code for finding in resolved.blocking_requirements}
        assert "BUSINESS_FACT_UNRESOLVED" not in resolved_codes
        assert "LOCATION_PROFILE_MISSING" not in resolved_codes
        assert set(resolved.fact_versions) == {
            name_revision,
            first_address_revision,
            second_address_revision,
        }

        restricted, restricted_locations = await _create_client(
            session,
            suffix="restricted",
            statuses=(LocationStatus.ACTIVE, LocationStatus.ACTIVE),
        )
        await service.create_entitlement(
            session,
            restricted,
            EntitlementCreate(
                product_key="seo",
                source="test",
                reason="First location only",
                location_ids=(restricted_locations[0],),
            ),
            actor_id=actor_id,
            correlation_id="readiness-scope-test",
        )
        await _approve_fact(
            session,
            service,
            restricted,
            actor_id,
            fact_key="business.name",
            value_type="string",
            value="Restricted",
        )
        await _approve_fact(
            session,
            service,
            restricted,
            actor_id,
            location_id=restricted_locations[0],
            fact_key="business.address",
            value_type="object",
            value={"address_line_1": "3 Main Street"},
        )
        session.add(
            LocationProfile(
                organization_id=restricted,
                location_id=restricted_locations[0],
                version=1,
            )
        )
        await session.flush()
        restricted_result = await service.readiness(session, restricted, "seo")
        restricted_codes = {finding.code for finding in restricted_result.blocking_requirements}
        assert restricted_result.selected_location_ids == (restricted_locations[0],)
        assert "BUSINESS_FACT_UNRESOLVED" not in restricted_codes
        assert "LOCATION_PROFILE_MISSING" not in restricted_codes

        historical, historical_locations = await _create_client(
            session,
            suffix="historical",
            statuses=(LocationStatus.ACTIVE, LocationStatus.CLOSED_PERMANENTLY),
        )
        await service.create_entitlement(
            session,
            historical,
            EntitlementCreate(product_key="seo", source="test", reason="Current locations"),
            actor_id=actor_id,
            correlation_id="readiness-scope-test",
        )
        await _approve_fact(
            session,
            service,
            historical,
            actor_id,
            fact_key="business.name",
            value_type="string",
            value="Historical",
        )
        await _approve_fact(
            session,
            service,
            historical,
            actor_id,
            location_id=historical_locations[0],
            fact_key="business.address",
            value_type="object",
            value={"address_line_1": "4 Main Street"},
        )
        session.add(
            LocationProfile(
                organization_id=historical,
                location_id=historical_locations[0],
                version=1,
            )
        )
        await session.flush()
        historical_result = await service.readiness(session, historical, "seo")
        historical_codes = {finding.code for finding in historical_result.blocking_requirements}
        assert "BUSINESS_FACT_UNRESOLVED" not in historical_codes
        assert "LOCATION_PROFILE_MISSING" not in historical_codes

        terminal, terminal_locations = await _create_client(
            session,
            suffix="terminal",
            statuses=(LocationStatus.CLOSED_PERMANENTLY,),
        )
        await service.create_entitlement(
            session,
            terminal,
            EntitlementCreate(
                product_key="seo",
                source="test",
                reason="Explicit historical location",
                location_ids=(terminal_locations[0],),
            ),
            actor_id=actor_id,
            correlation_id="readiness-scope-test",
        )
        terminal_result = await service.readiness(session, terminal, "seo")
        assert terminal_result.selected_location_ids == (terminal_locations[0],)
        assert "LOCATION_NOT_OPERATIONAL" in {
            finding.code for finding in terminal_result.blocking_requirements
        }

        missing_profile, missing_profile_locations = await _create_client(
            session,
            suffix="missing-profile",
            statuses=(LocationStatus.ACTIVE,),
        )
        await service.create_entitlement(
            session,
            missing_profile,
            EntitlementCreate(product_key="seo", source="test", reason="Missing profile"),
            actor_id=actor_id,
            correlation_id="readiness-scope-test",
        )
        await _approve_fact(
            session,
            service,
            missing_profile,
            actor_id,
            fact_key="business.name",
            value_type="string",
            value="Missing Profile",
        )
        await _approve_fact(
            session,
            service,
            missing_profile,
            actor_id,
            location_id=missing_profile_locations[0],
            fact_key="business.address",
            value_type="object",
            value={"address_line_1": "5 Main Street"},
        )
        missing_profile_result = await service.readiness(session, missing_profile, "seo")
        missing_profile_codes = {
            finding.code for finding in missing_profile_result.blocking_requirements
        }
        assert "BUSINESS_FACT_UNRESOLVED" not in missing_profile_codes
        assert "LOCATION_PROFILE_MISSING" in missing_profile_codes
