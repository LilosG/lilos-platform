# ruff: noqa: E501
"""Transactional Phase 4 mutation services and read-only resolvers."""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.contracts import (
    BusinessFactDecision,
    BusinessFactPropose,
    ChecklistComplete,
    ChecklistItemCreate,
    ConfigurationCreate,
    ConfigurationResolution,
    ControlResolution,
    EntitlementCreate,
    EntitlementTransition,
    FactResolution,
    FeatureFlagCreate,
    OffboardingCreate,
    OffboardingStepComplete,
    OffboardingTransition,
    OnboardingResolution,
    PolicyCreate,
    ProductReadiness,
    ReadinessFinding,
    ResolutionSource,
    RuntimeControlCreate,
    ServiceAssignmentCreate,
    ServiceCreate,
    ServiceUpdate,
)
from apps.api.app.administration.enums import ControlState, FactAuthority
from apps.api.app.administration.errors import (
    AdministrationConflictError,
    AdministrationNotFoundError,
    AdministrationVersionConflictError,
    ReadinessBlockedError,
)
from apps.api.app.administration.models import (
    BusinessFactRevision,
    ConfigurationRevision,
    FeatureFlagRevision,
    OffboardingPlan,
    OffboardingStep,
    OnboardingChecklistItem,
    PolicyRevision,
    ProductEntitlement,
    ProductEntitlementLocation,
    RuntimeControlRevision,
    ServiceAssignment,
    ServiceDefinition,
)
from apps.api.app.administration.repository import (
    AdministrationCatalogRepository,
    ConfigurationRepository,
    EntitlementRepository,
    FactRepository,
    OperationsRepository,
    PolicyRepository,
    ServiceRepository,
)
from apps.api.app.administration.validation import validate_against_definition
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.database.base import utc_now
from apps.api.app.locations.errors import LocationNotFoundError
from apps.api.app.locations.models import Location
from apps.api.app.organizations.errors import OrganizationNotFoundError
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.models import LocationProfile, OrganizationProfile

AUTHORITY_RANK = {
    "client_approved": 600,
    "operator_verified": 500,
    "provider_observed": 400,
    "system_derived": 300,
    "imported": 200,
    "industry_default": 100,
    "ai_suggested": 0,
}
CONTROL_RANK = {"allowed": 0, "degraded": 1, "paused": 2, "disabled": 3}
ENTITLEMENT_TRANSITIONS = {
    "not_enabled": {"setup_required", "archived"},
    "setup_required": {
        "configuration_required",
        "connection_required",
        "ready",
        "suspended",
        "archived",
    },
    "configuration_required": {"connection_required", "ready", "suspended", "archived"},
    "connection_required": {"ready", "suspended", "archived"},
    "ready": {"active", "suspended", "archived"},
    "active": {"paused", "degraded", "suspended", "archived"},
    "paused": {"active", "suspended", "archived"},
    "degraded": {"active", "paused", "suspended", "archived"},
    "suspended": {"setup_required", "archived"},
    "archived": set(),
}
OFFBOARDING_TRANSITIONS = {
    "planned": {"in_progress", "cancelled"},
    "in_progress": {"blocked", "completed", "cancelled"},
    "blocked": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}
OFFBOARDING_STEPS = {
    "products.pause": "Pause or suspend product operations.",
    "entitlements.terminate": "Record entitlement termination requirements.",
    "integrations.disconnect": "Disconnect external integrations in the future integration workflow.",
    "workflows.cancel": "Cancel queued and active workflows in the future workflow engine.",
    "notifications.final": "Prepare required final notifications.",
    "data.export": "Prepare a scoped data export.",
    "retention.confirm": "Confirm retention and legal-hold requirements.",
    "access.remove": "Remove organization access under controlled administration.",
    "audit.finalize": "Confirm final immutable audit evidence.",
}


async def _organization(
    session: AsyncSession, organization_id: UUID, *, lock: bool = False
) -> Organization:
    stmt = select(Organization).where(Organization.id == organization_id)
    item = await session.scalar(stmt.with_for_update() if lock else stmt)
    if item is None:
        raise OrganizationNotFoundError
    return item


async def _location(
    session: AsyncSession, organization_id: UUID, location_id: UUID, *, lock: bool = False
) -> Location:
    stmt = select(Location).where(
        Location.organization_id == organization_id, Location.id == location_id
    )
    item = await session.scalar(stmt.with_for_update() if lock else stmt)
    if item is None:
        raise LocationNotFoundError
    return item


@dataclass(frozen=True, slots=True)
class AdministrationService:
    services: ServiceRepository = field(default_factory=ServiceRepository)
    facts: FactRepository = field(default_factory=FactRepository)
    catalog: AdministrationCatalogRepository = field(
        default_factory=AdministrationCatalogRepository
    )
    entitlements: EntitlementRepository = field(default_factory=EntitlementRepository)
    configurations: ConfigurationRepository = field(default_factory=ConfigurationRepository)
    policies: PolicyRepository = field(default_factory=PolicyRepository)
    operations: OperationsRepository = field(default_factory=OperationsRepository)
    audit: AuditEventService = field(default_factory=AuditEventService)

    async def create_service(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: ServiceCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ServiceDefinition:
        await _organization(session, organization_id, lock=True)
        item = ServiceDefinition(
            organization_id=organization_id,
            key=command.key,
            name=command.name,
            description=command.description,
            status="active",
            version=1,
        )
        try:
            await self.services.add(session, item)
        except IntegrityError:
            raise AdministrationConflictError from None
        await self._audit(
            session,
            organization_id,
            "service.created",
            "service",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "created", "version": 1},
        )
        return item

    async def update_service(
        self,
        session: AsyncSession,
        organization_id: UUID,
        service_id: UUID,
        command: ServiceUpdate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ServiceDefinition:
        await _organization(session, organization_id, lock=True)
        item = await self.services.get(session, organization_id, service_id, lock=True)
        if item is None:
            raise AdministrationNotFoundError
        if item.status != "active" or item.version != command.expected_version:
            raise AdministrationVersionConflictError
        changed = [
            key for key in ("name", "description") if getattr(item, key) != getattr(command, key)
        ]
        item.name, item.description, item.version, item.updated_at = (
            command.name,
            command.description,
            item.version + 1,
            utc_now(),
        )
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "service.updated",
            "service",
            item.id,
            actor_id,
            correlation_id,
            {
                "operation": "updated",
                "version": item.version,
                "changed_fields": cast(list[JsonValue], changed),
            },
        )
        return item

    async def archive_service(
        self,
        session: AsyncSession,
        organization_id: UUID,
        service_id: UUID,
        expected_version: int,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ServiceDefinition:
        await _organization(session, organization_id, lock=True)
        item = await self.services.get(session, organization_id, service_id, lock=True)
        if item is None:
            raise AdministrationNotFoundError
        if item.status != "active" or item.version != expected_version:
            raise AdministrationVersionConflictError
        item.status, item.archived_at, item.version, item.updated_at = (
            "archived",
            utc_now(),
            item.version + 1,
            utc_now(),
        )
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "service.archived",
            "service",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "archived", "version": item.version},
        )
        return item

    async def assign_service(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: ServiceAssignmentCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ServiceAssignment:
        await _organization(session, organization_id, lock=True)
        service = await self.services.get(session, organization_id, command.service_id, lock=True)
        if service is None:
            raise AdministrationNotFoundError
        if service.status != "active":
            raise AdministrationConflictError
        if command.location_id:
            await _location(session, organization_id, command.location_id, lock=True)
        item = ServiceAssignment(
            organization_id=organization_id,
            service_id=service.id,
            scope_type=command.scope_type,
            location_id=command.location_id,
            status="active",
            version=1,
        )
        try:
            await self.services.add(session, item)
        except IntegrityError:
            raise AdministrationConflictError from None
        await self._audit(
            session,
            organization_id,
            "service.assignment_added",
            "service_assignment",
            item.id,
            actor_id,
            correlation_id,
            {
                "operation": "assigned",
                "service_id": str(service.id),
                "location_id": str(command.location_id) if command.location_id else None,
            },
        )
        return item

    async def effective_services(
        self, session: AsyncSession, organization_id: UUID, location_id: UUID | None
    ) -> list[ServiceDefinition]:
        await _organization(session, organization_id)
        if location_id:
            await _location(session, organization_id, location_id)
        assignments = await self.services.list_assignments(session, organization_id, location_id)
        ids = {item.service_id for item in assignments}
        return [
            item
            for item in await self.services.list_services(session, organization_id)
            if item.id in ids and item.status == "active"
        ]

    async def remove_service_assignment(
        self,
        session: AsyncSession,
        organization_id: UUID,
        assignment_id: UUID,
        expected_version: int,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ServiceAssignment:
        await _organization(session, organization_id, lock=True)
        item = await self.services.get_assignment(
            session, organization_id, assignment_id, lock=True
        )
        if item is None:
            raise AdministrationNotFoundError
        if item.status != "active" or item.version != expected_version:
            raise AdministrationVersionConflictError
        item.status, item.version, item.updated_at = "removed", item.version + 1, utc_now()
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "service.assignment_removed",
            "service_assignment",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "removed", "version": item.version},
        )
        return item

    async def propose_fact(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: BusinessFactPropose,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> BusinessFactRevision:
        await _organization(session, organization_id, lock=True)
        if command.location_id:
            await _location(session, organization_id, command.location_id, lock=True)
        identity = command.fact_identity or uuid4()
        history = await self.facts.list_identity(session, organization_id, identity, lock=True)
        if history and (
            history[-1].fact_key != command.fact_key
            or history[-1].location_id != command.location_id
        ):
            raise AdministrationConflictError
        item = BusinessFactRevision(
            organization_id=organization_id,
            location_id=command.location_id,
            fact_identity=identity,
            fact_key=command.fact_key,
            value_type=command.value_type,
            value=deepcopy(command.value),
            source=command.source,
            authority=command.authority,
            status="proposed",
            revision=len(history) + 1,
            effective_from=command.effective_from or utc_now(),
            effective_until=command.effective_until,
            review_at=command.review_at,
            supersedes_id=history[-1].id if history else None,
            proposed_by=actor_id,
            change_reason=command.change_reason,
        )
        try:
            await self.facts.add(session, item)
        except IntegrityError:
            raise AdministrationConflictError from None
        await self._audit(
            session,
            organization_id,
            "business_fact.proposed",
            "business_fact",
            item.id,
            actor_id,
            correlation_id,
            {
                "operation": "proposed",
                "fact_identity": str(identity),
                "revision": item.revision,
                "authority": item.authority,
            },
        )
        return item

    async def decide_fact(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        command: BusinessFactDecision,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> BusinessFactRevision:
        await _organization(session, organization_id, lock=True)
        item = await self.facts.get(session, organization_id, revision_id, lock=True)
        if item is None:
            raise AdministrationNotFoundError
        if item.status not in {"proposed", "pending_approval"}:
            raise AdministrationConflictError
        if command.decision == "approve":
            history = await self.facts.list_identity(
                session, organization_id, item.fact_identity, lock=True
            )
            for previous in history:
                if previous.id != item.id and previous.status == "active":
                    previous.status = "superseded"
            item.status, item.approved_by, item.approved_at = "active", actor_id, utc_now()
        else:
            item.status = "rejected"
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "business_fact.approved" if command.decision == "approve" else "business_fact.rejected",
            "business_fact",
            item.id,
            actor_id,
            correlation_id,
            {
                "operation": command.decision,
                "revision": item.revision,
                "fact_identity": str(item.fact_identity),
            },
        )
        return item

    async def resolve_fact(
        self,
        session: AsyncSession,
        organization_id: UUID,
        key: str,
        *,
        location_id: UUID | None = None,
        at: datetime | None = None,
    ) -> FactResolution:
        await _organization(session, organization_id)
        if location_id:
            await _location(session, organization_id, location_id)
        candidates = await self.facts.candidates(
            session, organization_id, key, at or utc_now(), location_id
        )
        if not candidates:
            return FactResolution(
                fact_key=key,
                state="missing",
                selected_revision_id=None,
                fact_identity=None,
                value=None,
                authority=None,
                revision=None,
                scope=None,
                conflicts=(),
            )
        ranked = sorted(
            candidates,
            key=lambda item: (
                AUTHORITY_RANK[item.authority],
                item.location_id is not None,
                item.revision,
            ),
            reverse=True,
        )
        top_rank = (AUTHORITY_RANK[ranked[0].authority], ranked[0].location_id is not None)
        top = [
            item
            for item in ranked
            if (AUTHORITY_RANK[item.authority], item.location_id is not None) == top_rank
        ]
        distinct = {repr(item.value) for item in top}
        if len(distinct) > 1:
            return FactResolution(
                fact_key=key,
                state="ambiguous",
                selected_revision_id=None,
                fact_identity=None,
                value=None,
                authority=None,
                revision=None,
                scope=None,
                conflicts=tuple(item.id for item in top),
            )
        selected = top[0]
        return FactResolution(
            fact_key=key,
            state="resolved",
            selected_revision_id=selected.id,
            fact_identity=selected.fact_identity,
            value=deepcopy(selected.value),
            authority=FactAuthority(selected.authority),
            revision=selected.revision,
            scope="location" if selected.location_id else "organization",
            conflicts=tuple(item.id for item in ranked[1:] if item.value != selected.value),
        )

    async def create_entitlement(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: EntitlementCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ProductEntitlement:
        await _organization(session, organization_id, lock=True)
        product = await self.catalog.get_product_by_key(session, command.product_key)
        if product is None:
            raise AdministrationNotFoundError
        if (
            command.effective_from
            and command.effective_until
            and command.effective_until <= command.effective_from
        ):
            raise AdministrationConflictError
        for location_id in set(command.location_ids):
            await _location(session, organization_id, location_id, lock=True)
        item = ProductEntitlement(
            organization_id=organization_id,
            product_id=product.id,
            status="setup_required",
            source=command.source,
            reason=command.reason,
            effective_from=command.effective_from or utc_now(),
            effective_until=command.effective_until,
            version=1,
        )
        try:
            await self.entitlements.add(session, item)
            for location_id in sorted(set(command.location_ids), key=str):
                await self.entitlements.add(
                    session,
                    ProductEntitlementLocation(
                        organization_id=organization_id,
                        entitlement_id=item.id,
                        location_id=location_id,
                        status="active",
                        version=1,
                    ),
                )
        except IntegrityError:
            raise AdministrationConflictError from None
        await self._audit(
            session,
            organization_id,
            "product.entitlement_created",
            "product_entitlement",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "created", "product_id": str(product.id), "version": 1},
        )
        return item

    async def transition_entitlement(
        self,
        session: AsyncSession,
        organization_id: UUID,
        entitlement_id: UUID,
        command: EntitlementTransition,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ProductEntitlement:
        await _organization(session, organization_id, lock=True)
        item = await self.entitlements.get(session, organization_id, entitlement_id, lock=True)
        if item is None:
            raise AdministrationNotFoundError
        if item.version != command.expected_version:
            raise AdministrationVersionConflictError
        target = command.target_status.value
        if target not in ENTITLEMENT_TRANSITIONS[item.status]:
            raise AdministrationConflictError
        if target == "active":
            product = next(
                (p for p in await self.catalog.list_products(session) if p.id == item.product_id),
                None,
            )
            if product is None:
                raise AdministrationConflictError
            readiness = await self.readiness(session, organization_id, product.key)
            if not readiness.ready:
                raise ReadinessBlockedError
            item.activated_at = utc_now()
        if target == "archived":
            item.archived_at = utc_now()
        item.status, item.reason, item.version, item.updated_at = (
            target,
            command.reason,
            item.version + 1,
            utc_now(),
        )
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "product.entitlement_changed",
            "product_entitlement",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "transitioned", "resulting_status": target, "version": item.version},
        )
        return item

    async def create_configuration(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: ConfigurationCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ConfigurationRevision:
        await _organization(session, organization_id, lock=True)
        definition = await self.catalog.get_definition(session, command.definition_key)
        if definition is None:
            raise AdministrationNotFoundError
        if command.scope_type.value not in definition.allowed_scopes:
            raise AdministrationConflictError
        location_id, product_id = command.location_id, None
        if location_id:
            await _location(session, organization_id, location_id, lock=True)
        if command.product_key:
            product = await self.catalog.get_product_by_key(session, command.product_key)
            if product is None:
                raise AdministrationNotFoundError
            product_id = product.id
        self._validate_scope(command.scope_type.value, location_id, product_id)
        errors = validate_against_definition(command.document, definition.schema_document)
        identity = command.configuration_identity or uuid4()
        history = await self.configurations.identity(session, organization_id, identity, lock=True)
        if history and (
            history[-1].definition_id != definition.id
            or history[-1].scope_type != command.scope_type.value
            or history[-1].location_id != location_id
            or history[-1].product_id != product_id
        ):
            raise AdministrationConflictError
        item = ConfigurationRevision(
            organization_id=organization_id,
            definition_id=definition.id,
            configuration_identity=identity,
            scope_type=command.scope_type,
            location_id=location_id,
            product_id=product_id,
            document=deepcopy(command.document),
            status="validation_failed" if errors else "draft",
            revision=len(history) + 1,
            effective_from=command.effective_from or utc_now(),
            effective_until=command.effective_until,
            supersedes_id=history[-1].id if history else None,
            created_by=actor_id,
            change_reason=command.change_reason,
        )
        await self.configurations.add(session, item)
        await self._audit(
            session,
            organization_id,
            "configuration.created",
            "configuration_revision",
            item.id,
            actor_id,
            correlation_id,
            {
                "operation": "created",
                "revision": item.revision,
                "validation_errors": cast(list[JsonValue], errors),
            },
        )
        return item

    async def effective_policies(
        self,
        session: AsyncSession,
        organization_id: UUID,
        category: str,
        *,
        product_key: str | None = None,
        at: datetime | None = None,
    ) -> list[PolicyRevision]:
        await _organization(session, organization_id)
        product = (
            await self.catalog.get_product_by_key(session, product_key) if product_key else None
        )
        if product_key and product is None:
            raise AdministrationNotFoundError
        if category not in {"general", "approval", "notification"}:
            raise AdministrationNotFoundError
        return await self.policies.effective(
            session, organization_id, category, at or utc_now(), product.id if product else None
        )

    async def approve_configuration(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ConfigurationRevision:
        item = await self.configurations.get(session, organization_id, revision_id, lock=True)
        if item is None:
            raise AdministrationNotFoundError
        if item.status != "draft":
            raise AdministrationConflictError
        definition = next(
            (d for d in await self.catalog.list_definitions(session) if d.id == item.definition_id),
            None,
        )
        if definition is None or validate_against_definition(
            item.document, definition.schema_document
        ):
            raise AdministrationConflictError
        effective = await self.configurations.effective(
            session,
            organization_id,
            item.definition_id,
            item.effective_from,
            item.location_id,
            item.product_id,
        )
        for previous in effective:
            if (
                previous.id != item.id
                and previous.scope_type == item.scope_type
                and previous.location_id == item.location_id
                and previous.product_id == item.product_id
            ):
                previous.status = "superseded"
        item.status = "scheduled" if item.effective_from > utc_now() else "active"
        item.approved_by = actor_id
        item.approved_at = utc_now()
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "configuration.activated",
            "configuration_revision",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "approved", "revision": item.revision},
        )
        return item

    async def resolve_configuration(
        self,
        session: AsyncSession,
        organization_id: UUID,
        key: str,
        *,
        location_id: UUID | None = None,
        product_key: str | None = None,
        at: datetime | None = None,
    ) -> ConfigurationResolution:
        organization = await _organization(session, organization_id)
        if location_id:
            await _location(session, organization_id, location_id)
        definition = await self.catalog.get_definition(session, key)
        if definition is None:
            raise AdministrationNotFoundError
        product = (
            await self.catalog.get_product_by_key(session, product_key) if product_key else None
        )
        if product_key and product is None:
            raise AdministrationNotFoundError
        resolved_at = at or utc_now()
        value = deepcopy(definition.platform_default)
        sources = [
            ResolutionSource(
                layer="platform",
                record_id=definition.id,
                version=definition.schema_version,
                effective_from=None,
            )
        ]
        industry_key = None
        if organization.industry_id:
            from apps.api.app.industries.models import Industry

            industry = await session.get(Industry, organization.industry_id)
            industry_key = industry.key if industry else None
        if industry_key and industry_key in definition.industry_defaults:
            value = self._merge(
                value, definition.industry_defaults[industry_key], definition.merge_strategy
            )
            sources.append(
                ResolutionSource(
                    layer="industry",
                    record_id=organization.industry_id,
                    version=definition.schema_version,
                    effective_from=None,
                )
            )
        records = await self.configurations.effective(
            session,
            organization_id,
            definition.id,
            resolved_at,
            location_id,
            product.id if product else None,
        )
        precedence = {"organization": 1, "location": 2, "product": 3}
        for item in sorted(
            records, key=lambda row: (precedence[row.scope_type], row.revision, str(row.id))
        ):
            value = self._merge(value, item.document, definition.merge_strategy)
            sources.append(
                ResolutionSource(
                    layer=item.scope_type,
                    record_id=item.id,
                    version=item.revision,
                    effective_from=item.effective_from,
                )
            )
        errors = validate_against_definition(value, definition.schema_document)
        return ConfigurationResolution(
            definition_key=key,
            schema_version=definition.schema_version,
            value=value,
            valid=not errors,
            errors=tuple(errors),
            sources=tuple(sources),
            resolved_at=resolved_at,
        )

    async def create_policy(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: PolicyCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> PolicyRevision:
        await _organization(session, organization_id, lock=True)
        if command.location_id:
            await _location(session, organization_id, command.location_id, lock=True)
        product = (
            await self.catalog.get_product_by_key(session, command.product_key)
            if command.product_key
            else None
        )
        if command.product_key and product is None:
            raise AdministrationNotFoundError
        self._validate_scope(
            command.scope_type.value, command.location_id, product.id if product else None
        )
        identity = command.policy_identity or uuid4()
        history = await self.policies.identity(session, organization_id, identity, lock=True)
        if command.category.value == "approval":
            self._validate_approval_policy(command.document)
        item = PolicyRevision(
            organization_id=organization_id,
            policy_identity=identity,
            policy_key=command.policy_key,
            category=command.category,
            schema_version=command.schema_version,
            scope_type=command.scope_type,
            location_id=command.location_id,
            product_id=product.id if product else None,
            document=deepcopy(command.document),
            status="draft",
            revision=len(history) + 1,
            effective_from=command.effective_from or utc_now(),
            effective_until=command.effective_until,
            change_reason=command.change_reason,
        )
        await self.policies.add(session, item)
        await self._audit(
            session,
            organization_id,
            "policy.created",
            "policy_revision",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "created", "category": item.category, "revision": item.revision},
        )
        return item

    async def approve_policy(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> PolicyRevision:
        item = await self.policies.get(session, organization_id, revision_id, lock=True)
        if item is None:
            raise AdministrationNotFoundError
        if item.status != "draft":
            raise AdministrationConflictError
        history = await self.policies.identity(
            session, organization_id, item.policy_identity, lock=True
        )
        for previous in history:
            if previous.id != item.id and previous.status == "active":
                previous.status = "superseded"
        item.status, item.approved_by, item.approved_at = "active", actor_id, utc_now()
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "policy.activated",
            "policy_revision",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "approved", "category": item.category, "revision": item.revision},
        )
        return item

    async def create_flag(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: FeatureFlagCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> FeatureFlagRevision:
        await _organization(session, organization_id, lock=True)
        if command.location_id:
            await _location(session, organization_id, command.location_id, lock=True)
        if (command.scope_type == "organization") != (command.location_id is None):
            raise AdministrationConflictError
        identity = command.flag_identity or uuid4()
        existing = await session.scalars(
            select(FeatureFlagRevision)
            .where(
                FeatureFlagRevision.organization_id == organization_id,
                FeatureFlagRevision.flag_identity == identity,
            )
            .with_for_update()
        )
        history = list(existing)
        item = FeatureFlagRevision(
            organization_id=organization_id,
            flag_identity=identity,
            flag_key=command.flag_key,
            scope_type=command.scope_type,
            location_id=command.location_id,
            enabled=command.enabled,
            purpose=command.purpose,
            risk_class=command.risk_class,
            effective_from=command.effective_from or utc_now(),
            effective_until=command.effective_until,
            review_at=command.review_at,
            version=len(history) + 1,
        )
        await self.operations.add(session, item)
        await self._audit(
            session,
            organization_id,
            "feature_flag.revised",
            "feature_flag",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "created", "version": item.version},
        )
        return item

    async def resolve_flag(
        self,
        session: AsyncSession,
        organization_id: UUID,
        key: str,
        *,
        location_id: UUID | None = None,
        at: datetime | None = None,
    ) -> FeatureFlagRevision | None:
        await _organization(session, organization_id)
        if location_id:
            await _location(session, organization_id, location_id)
        items = await self.operations.flags(
            session, organization_id, key, at or utc_now(), location_id
        )
        if not items:
            return None
        return sorted(
            items,
            key=lambda item: (item.scope_type == "location", item.version, str(item.id)),
            reverse=True,
        )[0]

    async def create_control(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: RuntimeControlCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> RuntimeControlRevision:
        await _organization(session, organization_id, lock=True)
        if command.location_id:
            await _location(session, organization_id, command.location_id, lock=True)
        product = (
            await self.catalog.get_product_by_key(session, command.product_key)
            if command.product_key
            else None
        )
        if command.product_key and product is None:
            raise AdministrationNotFoundError
        self._validate_scope(
            command.scope_type.value, command.location_id, product.id if product else None
        )
        identity = command.control_identity or uuid4()
        history = list(
            await session.scalars(
                select(RuntimeControlRevision)
                .where(
                    RuntimeControlRevision.organization_id == organization_id,
                    RuntimeControlRevision.control_identity == identity,
                )
                .with_for_update()
            )
        )
        item = RuntimeControlRevision(
            organization_id=organization_id,
            control_identity=identity,
            capability=command.capability,
            scope_type=command.scope_type,
            location_id=command.location_id,
            product_id=product.id if product else None,
            control_state=command.control_state,
            reason=command.reason,
            effective_from=command.effective_from or utc_now(),
            effective_until=command.effective_until,
            version=len(history) + 1,
        )
        await self.operations.add(session, item)
        await self._audit(
            session,
            organization_id,
            "runtime_control.activated",
            "runtime_control",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "created", "state": item.control_state, "version": item.version},
        )
        return item

    async def resolve_control(
        self,
        session: AsyncSession,
        organization_id: UUID,
        capability: str,
        *,
        location_id: UUID | None = None,
        product_key: str | None = None,
        at: datetime | None = None,
    ) -> ControlResolution:
        await _organization(session, organization_id)
        if location_id:
            await _location(session, organization_id, location_id)
        product = (
            await self.catalog.get_product_by_key(session, product_key) if product_key else None
        )
        if product_key and product is None:
            raise AdministrationNotFoundError
        items = await self.operations.controls(
            session,
            organization_id,
            capability,
            at or utc_now(),
            location_id,
            product.id if product else None,
        )
        if not items:
            return ControlResolution(
                capability=capability,
                allowed=True,
                state=ControlState.ALLOWED,
                winning_control_id=None,
                winning_scope=None,
                reason=None,
            )
        winner = sorted(
            items,
            key=lambda item: (
                CONTROL_RANK[item.control_state],
                item.scope_type == "organization",
                item.version,
                str(item.id),
            ),
            reverse=True,
        )[0]
        return ControlResolution(
            capability=capability,
            allowed=winner.control_state == "allowed",
            state=ControlState(winner.control_state),
            winning_control_id=winner.id,
            winning_scope=winner.scope_type,
            reason=winner.reason,
        )

    async def create_checklist_item(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: ChecklistItemCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> OnboardingChecklistItem:
        await _organization(session, organization_id, lock=True)
        if command.location_id:
            await _location(session, organization_id, command.location_id, lock=True)
        product = (
            await self.catalog.get_product_by_key(session, command.product_key)
            if command.product_key
            else None
        )
        if command.product_key and product is None:
            raise AdministrationNotFoundError
        item = OnboardingChecklistItem(
            organization_id=organization_id,
            location_id=command.location_id,
            product_id=product.id if product else None,
            item_key=command.item_key,
            category=command.category,
            status="pending",
            severity=command.severity,
            automated=command.automated,
            remediation=command.remediation,
            required_permission=command.required_permission,
            version=1,
        )
        try:
            await self.operations.add(session, item)
        except IntegrityError:
            raise AdministrationConflictError from None
        await self._audit(
            session,
            organization_id,
            "onboarding.item_created",
            "onboarding_item",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "created", "version": 1},
        )
        return item

    async def complete_checklist_item(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        command: ChecklistComplete,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> OnboardingChecklistItem:
        item = await self.operations.checklist_item(session, organization_id, item_id, lock=True)
        if item is None:
            raise AdministrationNotFoundError
        if item.automated or item.version != command.expected_version or item.status == "completed":
            raise AdministrationVersionConflictError
        (
            item.status,
            item.evidence,
            item.completed_by,
            item.completed_at,
            item.version,
            item.updated_at,
        ) = "completed", command.evidence, actor_id, utc_now(), item.version + 1, utc_now()
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "onboarding.item_completed",
            "onboarding_item",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "completed", "version": item.version},
        )
        return item

    async def onboarding(
        self, session: AsyncSession, organization_id: UUID
    ) -> OnboardingResolution:
        await _organization(session, organization_id)
        items = await self.operations.checklist(session, organization_id)
        blockers = tuple(
            item.id
            for item in items
            if item.severity == "blocker"
            and item.status != "completed"
            and item.status != "not_applicable"
        )
        warnings = tuple(
            item.id
            for item in items
            if item.severity == "warning"
            and item.status != "completed"
            and item.status != "not_applicable"
        )
        return OnboardingResolution(
            organization_id=organization_id,
            complete=not blockers,
            blockers=blockers,
            warnings=warnings,
            evaluated_at=utc_now(),
        )

    async def create_offboarding(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: OffboardingCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> OffboardingPlan:
        await _organization(session, organization_id, lock=True)
        item = OffboardingPlan(
            organization_id=organization_id,
            status="planned",
            reason=command.reason,
            target_date=command.target_date,
            version=1,
        )
        await self.operations.add(session, item)
        for key, requirement in OFFBOARDING_STEPS.items():
            await self.operations.add(
                session,
                OffboardingStep(
                    organization_id=organization_id,
                    plan_id=item.id,
                    step_key=key,
                    category=key.split(".")[0],
                    status="pending",
                    blocking=True,
                    requirement=requirement,
                    version=1,
                ),
            )
        await self._audit(
            session,
            organization_id,
            "offboarding.plan_created",
            "offboarding_plan",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "created", "version": 1},
        )
        return item

    async def transition_offboarding(
        self,
        session: AsyncSession,
        organization_id: UUID,
        plan_id: UUID,
        command: OffboardingTransition,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> OffboardingPlan:
        item = await self.operations.plan(session, organization_id, plan_id, lock=True)
        if item is None:
            raise AdministrationNotFoundError
        if (
            item.version != command.expected_version
            or command.target_status.value not in OFFBOARDING_TRANSITIONS[item.status]
        ):
            raise AdministrationVersionConflictError
        if command.target_status.value == "completed":
            steps = await self.operations.steps(session, organization_id, plan_id)
            if any(
                step.blocking and step.status != "completed" and step.status != "not_applicable"
                for step in steps
            ):
                raise AdministrationConflictError
            item.completed_at = utc_now()
        elif command.target_status.value == "in_progress" and item.started_at is None:
            item.started_at = utc_now()
        elif command.target_status.value == "cancelled":
            item.cancelled_at = utc_now()
        item.status, item.version, item.updated_at = (
            command.target_status.value,
            item.version + 1,
            utc_now(),
        )
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "offboarding.plan_changed",
            "offboarding_plan",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "transitioned", "status": item.status, "version": item.version},
        )
        return item

    async def complete_offboarding_step(
        self,
        session: AsyncSession,
        organization_id: UUID,
        plan_id: UUID,
        step_id: UUID,
        command: OffboardingStepComplete,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> OffboardingStep:
        await _organization(session, organization_id, lock=True)
        plan = await self.operations.plan(session, organization_id, plan_id, lock=True)
        if plan is None:
            raise AdministrationNotFoundError
        if plan.status not in {"planned", "in_progress", "blocked"}:
            raise AdministrationConflictError
        item = await self.operations.step(session, organization_id, plan_id, step_id, lock=True)
        if item is None:
            raise AdministrationNotFoundError
        if item.status == "completed" or item.version != command.expected_version:
            raise AdministrationVersionConflictError
        item.status = "completed"
        item.evidence = command.evidence
        item.completed_by = actor_id
        item.completed_at = utc_now()
        item.version += 1
        item.updated_at = utc_now()
        await session.flush()
        await self._audit(
            session,
            organization_id,
            "offboarding.step_completed",
            "offboarding_step",
            item.id,
            actor_id,
            correlation_id,
            {"operation": "completed", "plan_id": str(plan.id), "version": item.version},
        )
        return item

    async def readiness(
        self, session: AsyncSession, organization_id: UUID, product_key: str
    ) -> ProductReadiness:
        organization = await _organization(session, organization_id)
        product = await self.catalog.get_product_by_key(session, product_key)
        if product is None:
            raise AdministrationNotFoundError
        entitlement = await self.entitlements.get_by_product(session, organization_id, product.id)
        selected = (
            await self.entitlements.locations(session, organization_id, entitlement.id)
            if entitlement
            else []
        )
        findings: list[ReadinessFinding] = []
        config_ids: list[UUID] = []
        fact_ids: list[UUID] = []
        policy_ids: list[UUID] = []
        if entitlement is None or entitlement.status in {"not_enabled", "archived", "suspended"}:
            findings.append(
                ReadinessFinding(
                    code="ENTITLEMENT_NOT_EFFECTIVE",
                    blocking=True,
                    resource_key=product_key,
                    remediation="Create or restore an effective entitlement.",
                )
            )
        if organization.status.value != "active":
            findings.append(
                ReadinessFinding(
                    code="ORGANIZATION_NOT_ACTIVE",
                    blocking=True,
                    resource_key=None,
                    remediation="Complete the organization lifecycle prerequisites.",
                )
            )
        if (
            product.requires_organization_profile
            and await session.scalar(
                select(OrganizationProfile).where(
                    OrganizationProfile.organization_id == organization_id
                )
            )
            is None
        ):
            findings.append(
                ReadinessFinding(
                    code="ORGANIZATION_PROFILE_MISSING",
                    blocking=True,
                    resource_key=None,
                    remediation="Create the organization profile.",
                )
            )
        for selected_location in selected:
            location = await _location(session, organization_id, selected_location.location_id)
            if location.status.value in {"closed_permanently", "archived"}:
                findings.append(
                    ReadinessFinding(
                        code="LOCATION_NOT_OPERATIONAL",
                        blocking=True,
                        resource_key=str(location.id),
                        remediation="Select an eligible location.",
                    )
                )
            if (
                product.requires_location_profile
                and await session.scalar(
                    select(LocationProfile).where(
                        LocationProfile.organization_id == organization_id,
                        LocationProfile.location_id == location.id,
                    )
                )
                is None
            ):
                findings.append(
                    ReadinessFinding(
                        code="LOCATION_PROFILE_MISSING",
                        blocking=True,
                        resource_key=str(location.id),
                        remediation="Create the location profile.",
                    )
                )
        for key in product.required_configuration_keys:
            configuration_resolution = await self.resolve_configuration(
                session, organization_id, key, product_key=product_key
            )
            if not configuration_resolution.valid:
                findings.append(
                    ReadinessFinding(
                        code="CONFIGURATION_INVALID",
                        blocking=True,
                        resource_key=key,
                        remediation="Activate a valid configuration revision.",
                    )
                )
            config_ids.extend(
                source.record_id
                for source in configuration_resolution.sources
                if source.record_id and source.layer not in {"platform", "industry"}
            )
        for key in product.required_business_fact_keys:
            fact_resolution = await self.resolve_fact(session, organization_id, key)
            if fact_resolution.state != "resolved":
                findings.append(
                    ReadinessFinding(
                        code="BUSINESS_FACT_UNRESOLVED",
                        blocking=True,
                        resource_key=key,
                        remediation="Approve one unambiguous current business fact.",
                    )
                )
            elif fact_resolution.selected_revision_id:
                fact_ids.append(fact_resolution.selected_revision_id)
        if product.required_integrations:
            findings.extend(
                ReadinessFinding(
                    code="INTEGRATION_FOUNDATION_DEFERRED",
                    blocking=True,
                    resource_key=key,
                    remediation="Connect the required integration when the integration foundation is available.",
                )
                for key in product.required_integrations
            )
        if product.requires_approval_policy:
            policies = await self.policies.effective(
                session, organization_id, "approval", utc_now(), product.id
            )
            if not policies:
                findings.append(
                    ReadinessFinding(
                        code="APPROVAL_POLICY_MISSING",
                        blocking=True,
                        resource_key=product_key,
                        remediation="Activate an approval policy.",
                    )
                )
            policy_ids.extend(item.id for item in policies)
        control = await self.resolve_control(
            session, organization_id, f"product.{product_key}", product_key=product_key
        )
        if not control.allowed:
            findings.append(
                ReadinessFinding(
                    code="RUNTIME_CONTROL_BLOCKED",
                    blocking=True,
                    resource_key=product_key,
                    remediation="Resolve the winning runtime control.",
                )
            )
        onboarding = await self.onboarding(session, organization_id)
        if onboarding.blockers:
            findings.append(
                ReadinessFinding(
                    code="ONBOARDING_BLOCKED",
                    blocking=True,
                    resource_key=None,
                    remediation="Complete blocking onboarding requirements.",
                )
            )
        ready = not any(item.blocking for item in findings)
        return ProductReadiness(
            ready=ready,
            readiness_state="ready"
            if ready
            else ("not_entitled" if entitlement is None else "blocked"),
            product_key=product_key,
            organization_id=organization_id,
            selected_location_ids=tuple(item.location_id for item in selected),
            entitlement_version=entitlement.version if entitlement else None,
            configuration_versions=tuple(config_ids),
            fact_versions=tuple(fact_ids),
            policy_versions=tuple(policy_ids),
            blocking_requirements=tuple(item for item in findings if item.blocking),
            warnings=tuple(item for item in findings if not item.blocking),
            evaluated_at=utc_now(),
        )

    async def _audit(
        self,
        session: AsyncSession,
        organization_id: UUID,
        event_type: str,
        resource_type: str,
        resource_id: UUID,
        actor_id: UUID,
        correlation_id: str,
        metadata: dict[str, JsonValue],
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event_type,
                action=event_type,
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER,
                actor_id=actor_id,
                organization_id=organization_id,
                product_key="platform",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary="Governed shared-administration mutation completed.",
                metadata=metadata,
            ),
        )

    @staticmethod
    def _validate_scope(scope: str, location_id: UUID | None, product_id: UUID | None) -> None:
        valid = (
            (scope == "organization" and location_id is None and product_id is None)
            or (scope == "location" and location_id is not None and product_id is None)
            or (scope == "product" and product_id is not None)
        )
        if not valid:
            raise AdministrationConflictError

    @staticmethod
    def _merge(current: object, incoming: object, strategy: str) -> object:
        if strategy == "replace":
            return deepcopy(incoming)
        if strategy == "object_merge":
            if not isinstance(current, dict) or not isinstance(incoming, dict):
                raise AdministrationConflictError
            object_result: dict[object, object] = deepcopy(current)
            object_result.update(deepcopy(incoming))
            return object_result
        if strategy == "append_unique":
            if not isinstance(current, list) or not isinstance(incoming, list):
                raise AdministrationConflictError
            list_result: list[object] = deepcopy(current)
            for item in incoming:
                if item not in list_result:
                    list_result.append(deepcopy(item))
            return list_result
        raise AdministrationConflictError

    @staticmethod
    def _validate_approval_policy(document: dict[str, object]) -> None:
        required = {
            "action_type",
            "required_approver_permission",
            "minimum_approvals",
            "self_approval_allowed",
            "material_edit_invalidates",
        }
        if (
            not required.issubset(document)
            or not isinstance(document["minimum_approvals"], int)
            or int(document["minimum_approvals"]) < 1
        ):
            raise AdministrationConflictError
