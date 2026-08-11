"""GBP normalization, mapping, governed change, publication-intent, and verification service."""

import hashlib
import json
from datetime import UTC, datetime
from typing import TypedDict, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.repository import AuditEventRepository
from apps.api.app.audit.service import AuditEventService
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.integrations.contracts import MappingCreate
from apps.api.app.products.gbp.adapter import SUPPORTED_WRITE_FIELDS
from apps.api.app.products.gbp.contracts import MappingConfirm, ProfileChangeCreate, PublishRequest
from apps.api.app.products.gbp.models import (
    GBPAccount,
    GBPLocation,
    GBPProfileChangeRevision,
    GBPProfileSnapshot,
    GBPPublication,
)


class ProfileHealth(TypedDict):
    healthy: bool
    blockers: list[str]
    warnings: list[str]
    ranking_claim: None


def canonical_hash(value: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def normalize_profile(payload: dict[str, object]) -> dict[str, object]:
    allowed = (
        "name",
        "title",
        "storefrontAddress",
        "serviceArea",
        "regularHours",
        "specialHours",
        "moreHours",
        "profile",
        "phoneNumbers",
        "categories",
        "websiteUri",
        "openInfo",
        "labels",
        "serviceItems",
    )
    return {key: payload[key] for key in allowed if key in payload}


def profile_health(profile: dict[str, object], observed_at: datetime) -> ProfileHealth:
    blockers = []
    warnings = []
    if "title" not in profile:
        blockers.append("business_name_missing")
    if "storefrontAddress" not in profile:
        warnings.append("address_unavailable")
    if "regularHours" not in profile:
        warnings.append("hours_missing")
    if "profile" not in profile:
        warnings.append("description_missing")
    if (datetime.now(UTC) - observed_at).days > 7:
        warnings.append("provider_snapshot_stale")
    return {
        "healthy": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "ranking_claim": None,
    }


class GBPService:
    def __init__(self) -> None:
        self.audit = AuditEventService()
        self.audit_repository = AuditEventRepository()
        self.execution = ExecutionService()
        self.connection = GBPConnectionService()

    async def _audit(
        self,
        session: AsyncSession,
        *,
        event: str,
        organization_id: UUID,
        location_id: UUID | None,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        correlation_id: str,
        summary: str,
        metadata: dict[str, object],
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=location_id,
                product_key="gbp",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    async def confirm_mapping(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        command: MappingConfirm,
        user_id: UUID,
        *,
        correlation_id: str,
    ) -> GBPLocation:
        item = await session.scalar(
            select(GBPLocation)
            .where(
                GBPLocation.organization_id == organization_id, GBPLocation.id == gbp_location_id
            )
            .with_for_update()
        )
        if not item:
            raise LookupError("GBP location not found")
        item.location_id = command.location_id
        item.mapping_status = "confirmed"
        item.write_enabled = command.write_enabled
        resource_mapping = await self.connection.upsert_mapping(
            session,
            organization_id,
            MappingCreate(
                connection_id=item.connection_id,
                external_resource_id=item.external_location_id,
                platform_resource_id=command.location_id,
            ),
            actor_id=user_id,
            correlation_id=correlation_id,
        )
        item.integration_resource_id = resource_mapping.id
        item.confirmed_by_user_id = user_id
        item.confirmed_at = datetime.now(UTC)
        await session.flush()
        await self._audit(
            session,
            event="gbp.location.mapping_confirmed",
            organization_id=organization_id,
            location_id=command.location_id,
            actor_id=user_id,
            resource_type="gbp_location",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary="GBP location mapping confirmed.",
            metadata={"write_enabled": item.write_enabled},
        )
        return item

    async def store_snapshot(
        self,
        session: AsyncSession,
        location: GBPLocation,
        payload: dict[str, object],
        *,
        partial: bool = False,
    ) -> GBPProfileSnapshot:
        normalized = normalize_profile(payload)
        digest = canonical_hash(normalized)
        observed_at = datetime.now(UTC)
        existing = await session.scalar(
            select(GBPProfileSnapshot).where(
                GBPProfileSnapshot.organization_id == location.organization_id,
                GBPProfileSnapshot.gbp_location_id == location.id,
                GBPProfileSnapshot.content_hash == digest,
            )
        )
        location.last_synced_at = observed_at
        if existing:
            await session.flush()
            return existing
        item = GBPProfileSnapshot(
            organization_id=location.organization_id,
            gbp_location_id=location.id,
            normalized_profile=normalized,
            content_hash=digest,
            completeness="partial" if partial else "full",
            observed_at=observed_at,
        )
        session.add(item)
        await session.flush()
        return item

    async def propose(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        gbp_location_id: UUID,
        command: ProfileChangeCreate,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> GBPProfileChangeRevision:
        fields = set(command.desired_fields)
        if not fields or not fields <= SUPPORTED_WRITE_FIELDS:
            raise ValueError("unsupported GBP profile field")
        base = await session.scalar(
            select(GBPProfileSnapshot).where(
                GBPProfileSnapshot.organization_id == organization_id,
                GBPProfileSnapshot.id == command.base_snapshot_id,
                GBPProfileSnapshot.gbp_location_id == gbp_location_id,
            )
        )
        if not base:
            raise LookupError("snapshot not found")
        desired = dict(command.desired_fields)
        diff = {
            key: {"observed": base.normalized_profile.get(key), "desired": value}
            for key, value in sorted(desired.items())
            if base.normalized_profile.get(key) != value
        }
        item = GBPProfileChangeRevision(
            organization_id=organization_id,
            location_id=location_id,
            gbp_location_id=gbp_location_id,
            change_identity=uuid4(),
            revision_number=1,
            base_snapshot_id=base.id,
            desired_fields=desired,
            diff_document=diff,
            fact_revision_ids=[str(x) for x in command.approved_fact_revision_ids],
            status="awaiting_approval",
            risk_level="medium" if "regularHours" in fields else "low",
            content_hash=canonical_hash(desired),
        )
        session.add(item)
        await session.flush()
        await self._audit(
            session,
            event="gbp.change.proposed",
            organization_id=organization_id,
            location_id=location_id,
            actor_id=actor_id,
            resource_type="gbp_profile_change_revision",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary="GBP profile change proposed.",
            metadata={"risk_level": item.risk_level, "fields": sorted(fields)},
        )
        return item

    async def decide(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        user_id: UUID,
        approve: bool,
        *,
        correlation_id: str,
    ) -> GBPProfileChangeRevision:
        item = await session.scalar(
            select(GBPProfileChangeRevision)
            .where(
                GBPProfileChangeRevision.organization_id == organization_id,
                GBPProfileChangeRevision.id == revision_id,
            )
            .with_for_update()
        )
        if not item or item.status != "awaiting_approval":
            raise ValueError("change is not awaiting approval")
        item.status = "approved" if approve else "rejected"
        item.approved_by_user_id = user_id if approve else None
        item.approved_at = datetime.now(UTC) if approve else None
        await session.flush()
        await self._audit(
            session,
            event=f"gbp.change.{item.status}",
            organization_id=organization_id,
            location_id=item.location_id,
            actor_id=user_id,
            resource_type="gbp_profile_change_revision",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary=f"GBP profile change {item.status}.",
            metadata={"status": item.status},
        )
        return item

    async def reserve_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        revision_id: UUID,
        command: PublishRequest,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> GBPPublication:
        existing = await session.scalar(
            select(GBPPublication).where(
                GBPPublication.organization_id == organization_id,
                GBPPublication.idempotency_key == command.idempotency_key,
            )
        )
        if existing:
            return existing
        revision = await session.scalar(
            select(GBPProfileChangeRevision).where(
                GBPProfileChangeRevision.organization_id == organization_id,
                GBPProfileChangeRevision.id == revision_id,
                GBPProfileChangeRevision.location_id == location_id,
                GBPProfileChangeRevision.status == "approved",
            )
        )
        if not revision:
            raise ValueError("current approved revision required")
        workflow_run = await self.execution.resolve_for_consumption(
            session, organization_id, command.workflow_run_id, "gbp.publish_change"
        )
        item = GBPPublication(
            organization_id=organization_id,
            location_id=location_id,
            change_revision_id=revision.id,
            workflow_run_id=workflow_run.id,
            idempotency_key=command.idempotency_key,
            status="reserved",
            update_mask=sorted(revision.desired_fields),
        )
        session.add(item)
        await session.flush()
        workflow_run.input_document = {
            **(workflow_run.input_document or {}),
            "publication_id": str(item.id),
        }
        await self._audit(
            session,
            event="gbp.publication.reserved",
            organization_id=organization_id,
            location_id=location_id,
            actor_id=actor_id,
            resource_type="gbp_publication",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary="GBP publication reserved for dispatch.",
            metadata={"status": item.status, "change_revision_id": str(revision.id)},
        )
        return item

    async def list_accounts(self, session: AsyncSession, organization_id: UUID) -> list[GBPAccount]:
        return list(
            await session.scalars(
                select(GBPAccount)
                .where(GBPAccount.organization_id == organization_id)
                .order_by(GBPAccount.discovered_at.desc())
            )
        )

    async def list_locations(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        mapping_status: str | None = None,
    ) -> list[GBPLocation]:
        statement = select(GBPLocation).where(GBPLocation.organization_id == organization_id)
        if mapping_status is not None:
            statement = statement.where(GBPLocation.mapping_status == mapping_status)
        return list(
            await session.scalars(statement.order_by(GBPLocation.last_discovered_at.desc()))
        )

    async def get_revision(
        self, session: AsyncSession, organization_id: UUID, revision_id: UUID
    ) -> GBPProfileChangeRevision:
        item = await session.scalar(
            select(GBPProfileChangeRevision).where(
                GBPProfileChangeRevision.organization_id == organization_id,
                GBPProfileChangeRevision.id == revision_id,
            )
        )
        if not item:
            raise LookupError("GBP change revision not found")
        return item

    async def list_publications(
        self, session: AsyncSession, organization_id: UUID, location_id: UUID
    ) -> list[GBPPublication]:
        return list(
            await session.scalars(
                select(GBPPublication)
                .where(
                    GBPPublication.organization_id == organization_id,
                    GBPPublication.location_id == location_id,
                )
                .order_by(GBPPublication.created_at.desc())
            )
        )

    async def resource_history(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        resource_type: str,
        resource_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        events = await self.audit_repository.list_for_resource(
            session,
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
        return [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "action": event.action,
                "result": event.result,
                "occurred_at": event.occurred_at,
                "summary": event.summary,
                "actor_type": event.actor_type,
            }
            for event in events
        ]
