"""Backfill GBP capability state from an already-synced provider profile.

Older production locations can have a valid ``GBPProfileSnapshot`` that predates
automatic capability snapshots. The governed operations layer requires a
capability snapshot before it will accept an optimization proposal, so those
locations otherwise fail immediately even though the provider profile is
current and usable.

This module performs a read-only compatibility backfill from persisted provider
truth. It never expands what the adapter can write and never contacts Google.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.gbp.adapter import SUPPORTED_WRITE_FIELDS
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot
from apps.api.app.products.gbp.operations_models import GBPCapabilitySnapshot
from apps.api.app.products.gbp.operations_service import GBPOperationsService


def capability_document_from_profile(profile: dict[str, object]) -> dict[str, object]:
    """Derive provider capabilities without granting unsupported writes."""

    write_keys = {field.split(".", 1)[0] for field in SUPPORTED_WRITE_FIELDS}
    return {
        field: {
            "readable": True,
            "writable": field in write_keys,
            "reason": None,
        }
        for field in profile
        if field != "name"
    }


async def ensure_capability_snapshot_from_profile(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    correlation_id: str,
) -> bool:
    """Ensure one confirmed location has capability state derived from its profile.

    Returns ``True`` when a capability snapshot already exists or a legacy
    location was successfully backfilled. Returns ``False`` when there is not
    enough persisted provider truth to repair safely; the normal operations
    error is then allowed to surface to Hermes.
    """

    if location_id is None:
        return False

    locations = list(
        await session.scalars(
            select(GBPLocation).where(
                GBPLocation.organization_id == organization_id,
                GBPLocation.location_id == location_id,
                GBPLocation.mapping_status == "confirmed",
            )
        )
    )
    if len(locations) != 1:
        return False
    location = locations[0]

    existing = await session.scalar(
        select(GBPCapabilitySnapshot.id)
        .where(
            GBPCapabilitySnapshot.organization_id == organization_id,
            GBPCapabilitySnapshot.gbp_location_id == location.id,
        )
        .limit(1)
    )
    if existing is not None:
        return True

    profile_snapshot = await session.scalar(
        select(GBPProfileSnapshot)
        .where(
            GBPProfileSnapshot.organization_id == organization_id,
            GBPProfileSnapshot.gbp_location_id == location.id,
        )
        .order_by(GBPProfileSnapshot.observed_at.desc())
        .limit(1)
    )
    if profile_snapshot is None:
        return False

    capabilities = capability_document_from_profile(profile_snapshot.normalized_profile)
    if not capabilities:
        return False

    await GBPOperationsService().record_capability_snapshot(
        session,
        organization_id,
        location.id,
        capabilities,
        profile_snapshot.observed_at,
        actor_id=None,
        correlation_id=correlation_id,
    )
    return True
