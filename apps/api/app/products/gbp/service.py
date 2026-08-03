"""GBP normalization, mapping, governed change, publication-intent, and verification service."""

import hashlib
import json
from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.gbp.adapter import SUPPORTED_WRITE_FIELDS
from apps.api.app.products.gbp.contracts import MappingConfirm, ProfileChangeCreate, PublishRequest
from apps.api.app.products.gbp.models import (
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
        "regularHours",
        "profile",
        "phoneNumbers",
        "categories",
        "websiteUri",
        "openInfo",
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
    async def confirm_mapping(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        command: MappingConfirm,
        user_id: UUID,
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
        item.confirmed_by_user_id = user_id
        item.confirmed_at = datetime.now(UTC)
        await session.flush()
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
        existing = await session.scalar(
            select(GBPProfileSnapshot).where(
                GBPProfileSnapshot.organization_id == location.organization_id,
                GBPProfileSnapshot.gbp_location_id == location.id,
                GBPProfileSnapshot.content_hash == digest,
            )
        )
        if existing:
            return existing
        item = GBPProfileSnapshot(
            organization_id=location.organization_id,
            gbp_location_id=location.id,
            normalized_profile=normalized,
            content_hash=digest,
            completeness="partial" if partial else "full",
            observed_at=datetime.now(UTC),
        )
        session.add(item)
        location.last_synced_at = item.observed_at
        await session.flush()
        return item

    async def propose(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        gbp_location_id: UUID,
        command: ProfileChangeCreate,
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
        return item

    async def decide(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        user_id: UUID,
        approve: bool,
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
        return item

    async def reserve_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        revision_id: UUID,
        command: PublishRequest,
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
        item = GBPPublication(
            organization_id=organization_id,
            location_id=location_id,
            change_revision_id=revision.id,
            workflow_run_id=command.workflow_run_id,
            idempotency_key=command.idempotency_key,
            status="reserved",
            update_mask=sorted(revision.desired_fields),
        )
        session.add(item)
        await session.flush()
        return item
