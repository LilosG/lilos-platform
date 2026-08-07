# ruff: noqa: E501
"""Integrated Phase 4 governance, isolation, resolution, and audit tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.contracts import (
    BusinessFactDecision,
    BusinessFactPropose,
    ChecklistComplete,
    ChecklistItemCreate,
    ConfigurationCreate,
    EntitlementCreate,
    FeatureFlagCreate,
    OffboardingCreate,
    OffboardingTransition,
    PolicyCreate,
    RuntimeControlCreate,
    ServiceAssignmentCreate,
    ServiceCreate,
    ServiceUpdate,
)
from apps.api.app.administration.enums import (
    ChecklistSeverity,
    ConfigurationScope,
    ControlState,
    FactAuthority,
    OffboardingStatus,
    PolicyCategory,
)
from apps.api.app.administration.errors import (
    AdministrationConflictError,
    AdministrationNotFoundError,
    CatalogMismatchError,
)
from apps.api.app.administration.models import BusinessFactRevision, Product, ServiceDefinition
from apps.api.app.administration.service import AdministrationService
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.models import LocationProfile, OrganizationProfile


def test_phase4_governed_domain_end_to_end(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_exercise(administration_session_factory))


async def _exercise(factory: async_sessionmaker[AsyncSession]) -> None:
    domain = AdministrationService()
    actor_id = uuid4()
    org_a, org_b, location_a = uuid4(), uuid4(), uuid4()
    async with factory() as session, session.begin():
        actor = UserProfile(
            id=actor_id,
            auth_user_id=uuid4(),
            email="operator@example.invalid",
            display_name="Operator",
            status=UserStatus.ACTIVE,
            version=1,
        )
        session.add_all(
            [
                actor,
                Organization(
                    id=org_a,
                    name="Example A",
                    slug="example-a",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
                Organization(
                    id=org_b,
                    name="Example B",
                    slug="example-b",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        location = Location(
            id=location_a,
            organization_id=org_a,
            name="Virtual A",
            slug="virtual-a",
            location_type=LocationType.VIRTUAL,
            status=LocationStatus.ACTIVE,
            timezone="UTC",
            country_code="US",
            website_url="https://example.invalid",
            is_primary=True,
            version=1,
        )
        session.add_all(
            [
                location,
                OrganizationProfile(organization_id=org_a, brand_name="Example", version=1),
                LocationProfile(
                    organization_id=org_a,
                    location_id=location_a,
                    local_description="Local",
                    version=1,
                ),
            ]
        )
        await session.flush()
        access_seed = await AccessCatalogSeeder().seed(session, correlation_id="phase4-test")
        admin_seed = await AdministrationCatalogSeeder().seed(session, correlation_id="phase4-test")
        assert access_seed.permissions_created >= 19
        assert (admin_seed.products_created, admin_seed.configuration_definitions_created) == (7, 7)
    async with factory() as session, session.begin():
        assert await AdministrationCatalogSeeder().seed(
            session, correlation_id="phase4-test"
        ) == type(admin_seed)(0, 0)
        savepoint = await session.begin_nested()
        session.add(
            Product(
                key="unexpected",
                name="Unexpected",
                description="Catalog mismatch fixture.",
                owning_module="fixture",
                current_product_version="1.0",
                status="registered",
                required_capabilities=[],
                required_configuration_keys=[],
                required_business_fact_keys=[],
                required_integrations=[],
                requires_organization_profile=False,
                requires_location_profile=False,
                requires_approval_policy=False,
                runtime_control_namespace="fixture",
                version=1,
            )
        )
        await session.flush()
        with pytest.raises(CatalogMismatchError):
            await AdministrationCatalogSeeder().seed(session, correlation_id="phase4-test")
        await savepoint.rollback()
        service = await domain.create_service(
            session,
            org_a,
            ServiceCreate(
                key="electrical-repair", name="Electrical Repair", description="Governed offering"
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        service = await domain.update_service(
            session,
            org_a,
            service.id,
            ServiceUpdate(
                name="Electrical Repair", description="Updated offering", expected_version=1
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        assert service.version == 2
        assignment = await domain.assign_service(
            session,
            org_a,
            ServiceAssignmentCreate(
                service_id=service.id, scope_type="location", location_id=location_a
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        assert [
            item.id for item in await domain.effective_services(session, org_a, location_a)
        ] == [service.id]
        with pytest.raises(AdministrationNotFoundError):
            await domain.assign_service(
                session,
                org_b,
                ServiceAssignmentCreate(service_id=service.id, scope_type="organization"),
                actor_id=actor_id,
                correlation_id="phase4-test",
            )
        fact = await domain.propose_fact(
            session,
            org_a,
            BusinessFactPropose(
                fact_key="business.name",
                value_type="string",
                value="Example A",
                source="client approval",
                authority=FactAuthority.CLIENT_APPROVED,
                change_reason="Initial approved identity",
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        fact = await domain.decide_fact(
            session,
            org_a,
            fact.id,
            BusinessFactDecision(decision="approve"),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        assert fact.status == "active"
        resolved = await domain.resolve_fact(session, org_a, "business.name")
        assert (resolved.state, resolved.value, resolved.revision) == ("resolved", "Example A", 1)
        imported = await domain.propose_fact(
            session,
            org_a,
            BusinessFactPropose(
                fact_key="business.name",
                value_type="string",
                value="Unverified Import",
                source="import",
                authority=FactAuthority.IMPORTED,
                change_reason="Imported candidate",
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        assert (
            await domain.resolve_fact(session, org_a, "business.name")
        ).selected_revision_id == fact.id
        assert imported.status == "proposed"
        configuration = await domain.create_configuration(
            session,
            org_a,
            ConfigurationCreate(
                definition_key="seo.general",
                scope_type=ConfigurationScope.ORGANIZATION,
                document={"enabled_features": ["audit"]},
                change_reason="Initial SEO configuration",
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        configuration = await domain.approve_configuration(
            session, org_a, configuration.id, actor_id=actor_id, correlation_id="phase4-test"
        )
        resolved_configuration = await domain.resolve_configuration(
            session, org_a, "seo.general", product_key="seo"
        )
        assert resolved_configuration.valid and resolved_configuration.value == {
            "enabled_features": ["audit"]
        }
        assert [source.layer for source in resolved_configuration.sources] == [
            "platform",
            "organization",
        ]
        policy = await domain.create_policy(
            session,
            org_a,
            PolicyCreate(
                policy_key="publishing.approval",
                category=PolicyCategory.APPROVAL,
                schema_version=1,
                scope_type=ConfigurationScope.ORGANIZATION,
                document={
                    "action_type": "publish",
                    "required_approver_permission": "business_facts.approve",
                    "minimum_approvals": 1,
                    "self_approval_allowed": False,
                    "material_edit_invalidates": True,
                },
                change_reason="Require controlled publishing",
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        policy = await domain.approve_policy(
            session, org_a, policy.id, actor_id=actor_id, correlation_id="phase4-test"
        )
        assert policy.status == "active"
        entitlement = await domain.create_entitlement(
            session,
            org_a,
            EntitlementCreate(
                product_key="seo",
                source="internal",
                reason="Contract approved",
                location_ids=(location_a,),
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        readiness = await domain.readiness(session, org_a, "seo")
        assert not readiness.ready and readiness.entitlement_version == entitlement.version
        # SEO's self-contained crawl requires NO external integration, so a
        # connection requirement must NOT block it.  The real blocker here is
        # the unresolved business fact.
        codes = {item.code for item in readiness.blocking_requirements}
        assert "CONNECTION_REQUIRED" not in codes
        assert "BUSINESS_FACT_UNRESOLVED" in codes
        flag = await domain.create_flag(
            session,
            org_a,
            FeatureFlagCreate(
                flag_key="seo.experimental",
                scope_type="organization",
                enabled=True,
                purpose="Controlled test",
                risk_class="low",
                review_at=datetime.now(UTC) + timedelta(days=30),
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        assert (await domain.resolve_flag(session, org_a, "seo.experimental")).id == flag.id  # type: ignore[union-attr]
        control = await domain.create_control(
            session,
            org_a,
            RuntimeControlCreate(
                capability="product.seo",
                scope_type=ConfigurationScope.ORGANIZATION,
                control_state=ControlState.PAUSED,
                reason="Maintenance",
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        control_resolution = await domain.resolve_control(
            session, org_a, "product.seo", product_key="seo"
        )
        assert (
            not control_resolution.allowed and control_resolution.winning_control_id == control.id
        )
        checklist = await domain.create_checklist_item(
            session,
            org_a,
            ChecklistItemCreate(
                item_key="business.verify",
                category="business_facts",
                severity=ChecklistSeverity.BLOCKER,
                remediation="Verify the record",
                required_permission="business_facts.approve",
            ),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        assert not (await domain.onboarding(session, org_a)).complete
        checklist = await domain.complete_checklist_item(
            session,
            org_a,
            checklist.id,
            ChecklistComplete(evidence="Verified against signed client record", expected_version=1),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        assert checklist.version == 2 and (await domain.onboarding(session, org_a)).complete
        plan = await domain.create_offboarding(
            session,
            org_a,
            OffboardingCreate(reason="Controlled contract end"),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        plan = await domain.transition_offboarding(
            session,
            org_a,
            plan.id,
            OffboardingTransition(target_status=OffboardingStatus.IN_PROGRESS, expected_version=1),
            actor_id=actor_id,
            correlation_id="phase4-test",
        )
        with pytest.raises(AdministrationConflictError):
            await domain.transition_offboarding(
                session,
                org_a,
                plan.id,
                OffboardingTransition(
                    target_status=OffboardingStatus.COMPLETED, expected_version=2
                ),
                actor_id=actor_id,
                correlation_id="phase4-test",
            )
        assert assignment.organization_id == org_a
    async with factory() as session:
        audit_count = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.organization_id == org_a)
        )
        assert (audit_count or 0) >= 14
        stored = await session.scalar(
            select(BusinessFactRevision).where(BusinessFactRevision.id == fact.id)
        )
        assert stored and stored.value == "Example A"
        assert await session.scalar(select(func.count()).select_from(Product)) == 7
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ServiceDefinition)
                .where(ServiceDefinition.organization_id == org_b)
            )
            == 0
        )
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(
                    text(
                        "UPDATE business_fact_revisions SET value='\"tampered\"'::jsonb WHERE id=:id"
                    ),
                    {"id": fact.id},
                )
