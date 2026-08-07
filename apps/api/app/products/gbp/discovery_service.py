"""GBP account, location, and profile discovery via the Google Business Profile API.

Orchestrates the GBPAdapter (real Google HTTP calls) and GBPConnectionService
(token management) to discover, persist, and synchronize provider resources
after an OAuth connection is established.  Every mutation writes a real audit
event through the shared AuditEventService.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.products.gbp.adapter import GBPAdapter, GoogleBusinessProfileAdapter
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation, GBPProfileSnapshot
from apps.api.app.products.gbp.resource_names import normalize_location_name, v1_location_name
from apps.api.app.products.gbp.service import GBPService


@dataclass(slots=True)
class GBPDiscoveryService:
    """Discover GBP accounts/locations and synchronize profiles."""

    adapter: GBPAdapter = field(default_factory=GoogleBusinessProfileAdapter)
    connection: GBPConnectionService = field(default_factory=GBPConnectionService)
    gbp_service: GBPService = field(default_factory=GBPService)
    audit: AuditEventService = field(default_factory=AuditEventService)

    # -- audit helper -------------------------------------------------------

    async def _audit(
        self,
        session: AsyncSession,
        *,
        event: str,
        organization_id: UUID,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        correlation_id: str,
        summary: str,
        metadata: dict[str, object],
        result: AuditResult = AuditResult.SUCCEEDED,
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=result,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                product_key="gbp",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    # -- access token helper ------------------------------------------------

    async def _fresh_token(
        self, session: AsyncSession, settings: Settings, organization_id: UUID
    ) -> str:
        """Return a valid Google access token for this organization's connection."""
        connection = await self.connection.get_connection(session, organization_id)
        return await self.connection.ensure_fresh_token(session, settings, connection)

    # -- discover accounts --------------------------------------------------

    async def discover_accounts(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> list[GBPAccount]:
        """Discover and persist GBP accounts from Google.

        Idempotent: existing accounts (matched by external_account_id +
        connection) are updated; new ones are inserted.  Returns all accounts
        for this organization after the discovery pass.
        """
        token = await self._fresh_token(session, settings, organization_id)
        connection = await self.connection.get_connection(session, organization_id)
        try:
            raw_accounts = await self.adapter.list_accounts(token)
        except Exception as exc:
            await self._audit(
                session,
                event="gbp.discovery.accounts_failed",
                organization_id=organization_id,
                actor_id=actor_id,
                resource_type="integration_connection",
                resource_id=connection.id,
                correlation_id=correlation_id,
                summary="GBP account discovery failed.",
                metadata={"error": str(exc)[:200]},
                result=AuditResult.FAILED,
            )
            raise

        existing_stmt = select(GBPAccount).where(
            GBPAccount.organization_id == organization_id,
            GBPAccount.connection_id == connection.id,
        )
        existing_rows = list(await session.scalars(existing_stmt))
        existing_by_ext: dict[str, GBPAccount] = {
            row.external_account_id: row for row in existing_rows
        }

        seen_ext_ids: set[str] = set()
        for raw in raw_accounts:
            ext_id = str(raw.get("name", "")).removeprefix("accounts/")
            if not ext_id:
                continue
            seen_ext_ids.add(ext_id)
            display_name = str(raw.get("accountName", raw.get("name", ext_id)))
            account_type = str(raw.get("accountType", "")) or None
            now = datetime.now(UTC)

            if ext_id in existing_by_ext:
                acct = existing_by_ext[ext_id]
                acct.display_name = display_name
                acct.account_type = account_type
                acct.freshness_at = now
            else:
                acct = GBPAccount(
                    organization_id=organization_id,
                    connection_id=connection.id,
                    external_account_id=ext_id,
                    display_name=display_name,
                    account_type=account_type,
                    status="discovered",
                    discovered_at=now,
                    freshness_at=now,
                )
                session.add(acct)

        # Mark accounts no longer accessible
        for ext_id, acct in existing_by_ext.items():
            if ext_id not in seen_ext_ids and acct.status == "discovered":
                acct.status = "unavailable"

        await session.flush()

        await self._audit(
            session,
            event="gbp.discovery.accounts_discovered",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary="GBP account discovery completed.",
            metadata={
                "accounts_found": len(raw_accounts),
                "new": len(seen_ext_ids - set(existing_by_ext)),
            },
        )

        # Return all accounts for this org
        return list(
            await session.scalars(
                select(GBPAccount)
                .where(GBPAccount.organization_id == organization_id)
                .order_by(GBPAccount.discovered_at.desc())
            )
        )

    # -- discover locations -------------------------------------------------

    async def discover_locations(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> list[GBPLocation]:
        """Discover and persist GBP locations for all discovered accounts.

        Idempotent: existing locations (matched by external_location_id +
        connection) are updated; new ones are inserted.  Returns all GBP
        locations for this organization after the discovery pass.
        """
        token = await self._fresh_token(session, settings, organization_id)
        connection = await self.connection.get_connection(session, organization_id)

        accounts = list(
            await session.scalars(
                select(GBPAccount).where(
                    GBPAccount.organization_id == organization_id,
                    GBPAccount.connection_id == connection.id,
                    GBPAccount.status.in_(["discovered", "selected"]),
                )
            )
        )
        if not accounts:
            await self._audit(
                session,
                event="gbp.discovery.locations_no_accounts",
                organization_id=organization_id,
                actor_id=actor_id,
                resource_type="integration_connection",
                resource_id=connection.id,
                correlation_id=correlation_id,
                summary="GBP location discovery skipped: no accounts.",
                metadata={},
            )
            return []

        existing_stmt = select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.connection_id == connection.id,
        )
        existing_rows = list(await session.scalars(existing_stmt))
        # Match existing rows by their CANONICAL v1 location name so that rows
        # persisted with a legacy/account-qualified ``external_location_id``
        # (e.g. ``accounts/456/locations/123`` or the bare id ``123``) are
        # reconciled with the canonical ``locations/123`` form rather than
        # duplicated.  This is the safe in-place backfill for production rows
        # created by the broken parser.
        existing_by_ext: dict[str, GBPLocation] = {
            normalize_location_name(row.external_location_id): row for row in existing_rows
        }

        seen_ext_ids: set[str] = set()
        total_raw = 0
        for acct in accounts:
            account_name = f"accounts/{acct.external_account_id}"
            try:
                raw_locations = await self.adapter.list_locations(token, account_name)
            except Exception:
                continue
            total_raw += len(raw_locations)

            for raw in raw_locations:
                loc_name = str(raw.get("name", ""))
                if not loc_name:
                    continue
                # ``accounts.locations.list`` (Business Information v1) returns
                # ``Location.name`` as ``locations/{locationId}``.  Normalize
                # any legacy/account-qualified form to the canonical v1 name.
                ext_id = normalize_location_name(loc_name)
                seen_ext_ids.add(ext_id)
                business_name = str(raw.get("title", raw.get("name", ext_id)))
                now = datetime.now(UTC)

                if ext_id in existing_by_ext:
                    loc = existing_by_ext[ext_id]
                    loc.business_name = business_name
                    loc.last_discovered_at = now
                    # Reconcile the persisted identity to the canonical form so
                    # downstream v1/v4 resource construction is correct.
                    loc.external_location_id = ext_id
                    if loc.mapping_status == "unavailable":
                        loc.mapping_status = "unmapped"
                else:
                    loc = GBPLocation(
                        organization_id=organization_id,
                        connection_id=connection.id,
                        account_id=acct.id,
                        external_location_id=ext_id,
                        business_name=business_name,
                        mapping_status="unmapped",
                        write_enabled=False,
                        last_discovered_at=now,
                    )
                    session.add(loc)
                    existing_by_ext[ext_id] = loc

        # Mark locations no longer accessible
        for ext_id, loc in existing_by_ext.items():
            if ext_id not in seen_ext_ids and loc.mapping_status in ("unmapped", "suggested"):
                loc.mapping_status = "archived"

        await session.flush()

        await self._audit(
            session,
            event="gbp.discovery.locations_discovered",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary="GBP location discovery completed.",
            metadata={
                "accounts_scanned": len(accounts),
                "locations_found": total_raw,
                "new": len(seen_ext_ids - set(existing_by_ext)),
            },
        )

        return list(
            await session.scalars(
                select(GBPLocation)
                .where(GBPLocation.organization_id == organization_id)
                .order_by(GBPLocation.last_discovered_at.desc())
            )
        )

    # -- sync profile -------------------------------------------------------

    async def sync_profile(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        gbp_location_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPProfileSnapshot:
        """Fetch the current GBP profile for a location and store a snapshot.

        Returns the stored snapshot.  Idempotent: if the profile hash matches
        the most recent snapshot, no new row is created.
        """
        token = await self._fresh_token(session, settings, organization_id)
        gbp_location = await session.scalar(
            select(GBPLocation).where(
                GBPLocation.organization_id == organization_id,
                GBPLocation.id == gbp_location_id,
            )
        )
        if not gbp_location:
            raise LookupError("GBP location not found")

        # Business Information v1 ``locations.get`` uses the canonical
        # ``locations/{locationId}`` resource name — NOT the account-qualified
        # ``accounts/{accountId}/locations/{locationId}`` form.  Using the
        # account-qualified form here was the root cause of the production 404
        # during initial profile sync.
        location_name = v1_location_name(gbp_location.external_location_id)

        try:
            raw = await self.adapter.get_location(token, location_name)
        except Exception as exc:
            await self._audit(
                session,
                event="gbp.sync.profile_failed",
                organization_id=organization_id,
                actor_id=actor_id,
                resource_type="gbp_location",
                resource_id=gbp_location.id,
                correlation_id=correlation_id,
                summary="GBP profile sync failed.",
                metadata={"error": str(exc)[:200]},
                result=AuditResult.FAILED,
            )
            raise

        snapshot = await self.gbp_service.store_snapshot(session, gbp_location, raw, partial=False)

        # Record a capability snapshot derived from the fields the provider
        # actually returned so the operations surface (completeness, change
        # sets, posts) does not 404 immediately after a successful sync.  A
        # field present in the response is readable; writability follows the
        # adapter's declared write field set.  This uses the existing
        # ``GBPOperationsService.record_capability_snapshot`` path.
        await self._record_sync_capability_snapshot(
            session, organization_id, gbp_location_id, raw, correlation_id
        )

        await self._audit(
            session,
            event="gbp.sync.profile_synced",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="gbp_location",
            resource_id=gbp_location.id,
            correlation_id=correlation_id,
            summary="GBP profile synced.",
            metadata={"snapshot_id": str(snapshot.id), "content_hash": snapshot.content_hash},
        )

        return snapshot

    async def _record_sync_capability_snapshot(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        raw_profile: dict[str, Any],
        correlation_id: str,
    ) -> None:
        """Derive a provider capability snapshot from a fetched profile.

        Every top-level field the provider returned for this location is
        readable; writability is gated by the adapter's declared write field
        set.  Delegates to ``GBPOperationsService.record_capability_snapshot``,
        which is idempotent on the capability document hash.
        """
        from apps.api.app.products.gbp.adapter import SUPPORTED_WRITE_FIELDS
        from apps.api.app.products.gbp.operations_service import GBPOperationsService

        # Map the normalized profile field keys to the capability keys used by
        # the operations surface.  ``profile.description`` is the writable
        # leaf; the read capability is tracked on the top-level ``profile``.
        write_keys = {key.split(".", 1)[0] for key in SUPPORTED_WRITE_FIELDS}
        capabilities: dict[str, object] = {}
        for field_key in raw_profile:
            if field_key == "name":
                continue
            capabilities[field_key] = {
                "readable": True,
                "writable": field_key in write_keys,
                "reason": None,
            }
        operations = GBPOperationsService()
        await operations.record_capability_snapshot(
            session,
            organization_id,
            gbp_location_id,
            capabilities,
            datetime.now(UTC),
            actor_id=None,
            correlation_id=correlation_id,
        )

    # -- combined discover + sync -------------------------------------------

    async def discover_and_sync(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Full discovery pass: accounts, locations, then initial profile sync
        for every newly-discovered location.

        Returns a summary dict suitable for an API response.
        """
        accounts = await self.discover_accounts(
            session,
            settings,
            organization_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        locations = await self.discover_locations(
            session,
            settings,
            organization_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

        synced = 0
        for loc in locations:
            if loc.last_synced_at is None:
                try:
                    await self.sync_profile(
                        session,
                        settings,
                        organization_id,
                        loc.id,
                        actor_id=actor_id,
                        correlation_id=correlation_id,
                    )
                    synced += 1
                except Exception:
                    # Individual profile sync failures don't block discovery
                    pass

        return {
            "accounts_discovered": len(accounts),
            "locations_discovered": len(locations),
            "profiles_synced": synced,
        }
