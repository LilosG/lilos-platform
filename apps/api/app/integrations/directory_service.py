"""Provider directory aggregation and detail workspace queries.

Provides a read model over the provider catalog, connection state,
confirmed mappings, and sync freshness that powers the Integrations
control plane -- one call per provider workspace, never requiring the
caller to assemble partial provider detail from product routes.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.integrations.connection_service import (
    GBPConnectionService,
    granted_services,
)
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.products.gbp.freshness import profile_sync_is_stale
from apps.api.app.products.gbp.models import GBPLocation


@dataclass(frozen=True, slots=True)
class ProviderDirectoryEntry:
    """One card in the Integrations directory grid."""

    provider_key: str
    provider_name: str
    description: str
    status: str  # "connected" | "degraded" | "not_connected" | "not_configured"
    status_label: str
    requires_attention: bool


@dataclass(frozen=True, slots=True)
class CapabilityRow:
    key: str
    label: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class MappedResource:
    id: UUID
    external_resource_id: str
    platform_resource_id: UUID | None
    resource_type: str
    status: str
    display_name: str | None
    last_synced_at: str | None
    sync_freshness: str  # "fresh" | "stale" | "never"
    gbp_location_id: str | None
    mapping_status: str | None
    write_enabled: bool | None


@dataclass(frozen=True, slots=True)
class GoogleWorkspace:
    """Google provider detail workspace read model."""

    connection_status: str
    connection_id: str | None
    token_expires_at: str | None
    last_verified_at: str | None
    capabilities: list[dict[str, object]]
    mapped_resources: list[dict[str, object]]
    unmapped_count: int


@dataclass(frozen=True, slots=True)
class GitHubWorkspace:
    """GitHub provider detail workspace read model."""

    connection_status: str  # "active" | "disconnected" | "none"
    connection_id: str | None
    external_account_reference: str | None
    repositories: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class EmailProviderState:
    configured: bool
    provider_name: str
    description: str


@dataclass(frozen=True, slots=True)
class SmsProviderState:
    configured: bool
    provider_name: str
    description: str


@dataclass(slots=True)
class IntegrationDirectoryService:
    """Read models for the Integrations control plane provider directory and workspaces."""

    connection: GBPConnectionService = field(default_factory=GBPConnectionService)

    # -- provider directory ----------------------------------------------------

    async def directory(
        self, session: AsyncSession, organization_id: UUID
    ) -> list[ProviderDirectoryEntry]:
        entries: list[ProviderDirectoryEntry] = []

        google_state = await self._google_directory_state(session, organization_id)
        entries.append(google_state)

        github_state = await self._github_directory_state(session, organization_id)
        entries.append(github_state)

        entries.append(
            ProviderDirectoryEntry(
                provider_key="resend",
                provider_name="Email",
                description="Transactional email delivery via Resend",
                status="not_configured",
                status_label="Not configured",
                requires_attention=False,
            )
        )

        entries.append(
            ProviderDirectoryEntry(
                provider_key="sms",
                provider_name="SMS",
                description="SMS messaging via Twilio or equivalent provider",
                status="not_configured",
                status_label="Not configured",
                requires_attention=False,
            )
        )

        return entries

    async def _google_directory_state(
        self, session: AsyncSession, organization_id: UUID
    ) -> ProviderDirectoryEntry:
        try:
            await self.connection.get_provider(session)
        except Exception:
            return ProviderDirectoryEntry(
                provider_key="google_business_profile",
                provider_name="Google",
                description="Business Profile, Search Console, and Analytics",
                status="not_configured",
                status_label="Not configured",
                requires_attention=False,
            )
        connection = await self.connection.find_connection(session, organization_id)
        if connection is None:
            return ProviderDirectoryEntry(
                provider_key="google_business_profile",
                provider_name="Google",
                description="Business Profile, Search Console, and Analytics",
                status="not_connected",
                status_label="Not connected",
                requires_attention=False,
            )
        if connection.status == "connected":
            return ProviderDirectoryEntry(
                provider_key="google_business_profile",
                provider_name="Google",
                description="Business Profile, Search Console, and Analytics",
                status="connected",
                status_label="Connected",
                requires_attention=False,
            )
        if connection.status in ("reconnect_required", "degraded"):
            return ProviderDirectoryEntry(
                provider_key="google_business_profile",
                provider_name="Google",
                description="Business Profile, Search Console, and Analytics",
                status="degraded",
                status_label="Needs attention",
                requires_attention=True,
            )
        return ProviderDirectoryEntry(
            provider_key="google_business_profile",
            provider_name="Google",
            description="Business Profile, Search Console, and Analytics",
            status="not_connected",
            status_label="Setup in progress",
            requires_attention=False,
        )

    async def _github_directory_state(
        self, session: AsyncSession, organization_id: UUID
    ) -> ProviderDirectoryEntry:
        connection = await session.scalar(
            select(IntegrationConnection)
            .join(Provider, Provider.id == IntegrationConnection.provider_id)
            .where(
                IntegrationConnection.organization_id == organization_id,
                Provider.key == "github",
            )
            .order_by(IntegrationConnection.created_at.desc())
        )
        if connection is not None and connection.status in ("connected", "active"):
            return ProviderDirectoryEntry(
                provider_key="github",
                provider_name="GitHub",
                description="Content publishing via GitHub repositories",
                status="connected",
                status_label="Connected",
                requires_attention=False,
            )
        return ProviderDirectoryEntry(
            provider_key="github",
            provider_name="GitHub",
            description="Content publishing via GitHub repositories",
            status="not_connected",
            status_label="Not connected",
            requires_attention=False,
        )

    # -- Google workspace ------------------------------------------------------

    async def google_workspace(
        self, session: AsyncSession, organization_id: UUID
    ) -> GoogleWorkspace:
        connection = await self.connection.find_connection(session, organization_id)
        if connection is None:
            return GoogleWorkspace(
                connection_status="none",
                connection_id=None,
                token_expires_at=None,
                last_verified_at=None,
                capabilities=[
                    {"key": "gbp", "label": "Business Profile", "enabled": False},
                    {"key": "search_console", "label": "Search Console", "enabled": False},
                    {"key": "analytics", "label": "Analytics", "enabled": False},
                ],
                mapped_resources=[],
                unmapped_count=0,
            )

        services = granted_services(connection)
        capabilities = [
            {"key": "gbp", "label": "Business Profile", "enabled": services["gbp"]},
            {
                "key": "search_console",
                "label": "Search Console",
                "enabled": services["search_console"],
            },
            {"key": "analytics", "label": "Analytics", "enabled": services["analytics"]},
        ]

        mapped = await self._confirmed_mappings(session, organization_id, connection.id)
        unmapped_count = await self._unmapped_count(session, organization_id, connection.id)

        return GoogleWorkspace(
            connection_status=connection.status,
            connection_id=str(connection.id),
            token_expires_at=connection.token_expires_at.isoformat()
            if connection.token_expires_at
            else None,
            last_verified_at=connection.last_verified_at.isoformat()
            if connection.last_verified_at
            else None,
            capabilities=capabilities,
            mapped_resources=mapped,
            unmapped_count=unmapped_count,
        )

    async def _confirmed_mappings(
        self, session: AsyncSession, organization_id: UUID, connection_id: UUID
    ) -> list[dict[str, object]]:
        mappings = (
            (
                await session.execute(
                    select(ProviderResourceMapping).where(
                        ProviderResourceMapping.organization_id == organization_id,
                        ProviderResourceMapping.connection_id == connection_id,
                        ProviderResourceMapping.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )

        result: list[dict[str, object]] = []
        freshness_observed_at = datetime.now(UTC)

        for mapping in mappings:
            display_name = None
            last_synced_at: str | None = None
            sync_freshness = "never"
            gbp_location_id: str | None = None
            mapping_status: str | None = None
            write_enabled: bool | None = None

            if mapping.resource_type == "location":
                # ProviderResourceMapping.platform_resource_id is the platform
                # Location.id, not GBPLocation.id. Resolve the GBP row through
                # the canonical integration mapping (with location-id fallback
                # for older rows) and use its actual provider sync timestamp.
                identity_predicate = GBPLocation.integration_resource_id == mapping.id
                if mapping.platform_resource_id is not None:
                    identity_predicate = identity_predicate | (
                        (GBPLocation.integration_resource_id.is_(None))
                        & (GBPLocation.location_id == mapping.platform_resource_id)
                        & (GBPLocation.external_location_id == mapping.external_resource_id)
                    )
                gbp_loc = await session.scalar(
                    select(GBPLocation)
                    .where(
                        GBPLocation.organization_id == organization_id,
                        GBPLocation.connection_id == connection_id,
                        identity_predicate,
                    )
                    .order_by(GBPLocation.last_discovered_at.desc())
                    .limit(1)
                )
                if gbp_loc is not None:
                    display_name = gbp_loc.business_name
                    gbp_location_id = str(gbp_loc.id)
                    mapping_status = gbp_loc.mapping_status
                    write_enabled = gbp_loc.write_enabled
                    if gbp_loc.last_synced_at is not None:
                        last_synced_at = gbp_loc.last_synced_at.isoformat()
                        sync_freshness = (
                            "stale"
                            if profile_sync_is_stale(
                                gbp_loc.last_synced_at, now=freshness_observed_at
                            )
                            else "fresh"
                        )

            result.append(
                {
                    "id": str(mapping.id),
                    "external_resource_id": mapping.external_resource_id,
                    "platform_resource_id": (
                        str(mapping.platform_resource_id) if mapping.platform_resource_id else None
                    ),
                    "resource_type": mapping.resource_type,
                    "status": mapping.status,
                    "display_name": display_name,
                    "last_synced_at": last_synced_at,
                    "sync_freshness": sync_freshness,
                    "gbp_location_id": gbp_location_id,
                    "mapping_status": mapping_status,
                    "write_enabled": write_enabled,
                }
            )

        return result

    async def _unmapped_count(
        self, session: AsyncSession, organization_id: UUID, connection_id: UUID
    ) -> int:
        """Count GBP locations that exist without a confirmed active mapping."""
        mapping_ids, platform_location_ids = await self.active_location_mapping_identities(
            session, organization_id, connection_id
        )
        rows = (
            await session.execute(
                select(
                    GBPLocation.integration_resource_id,
                    GBPLocation.location_id,
                ).where(
                    GBPLocation.organization_id == organization_id,
                    GBPLocation.connection_id == connection_id,
                )
            )
        ).all()
        return sum(
            1
            for integration_resource_id, location_id in rows
            if integration_resource_id not in mapping_ids
            and location_id not in platform_location_ids
        )

    async def active_location_mapping_identities(
        self,
        session: AsyncSession,
        organization_id: UUID,
        connection_id: UUID,
    ) -> tuple[set[UUID], set[UUID]]:
        """Return canonical mapping-row and platform-location identities for one connection."""
        rows = (
            await session.execute(
                select(
                    ProviderResourceMapping.id,
                    ProviderResourceMapping.platform_resource_id,
                ).where(
                    ProviderResourceMapping.organization_id == organization_id,
                    ProviderResourceMapping.connection_id == connection_id,
                    ProviderResourceMapping.resource_type == "location",
                    ProviderResourceMapping.status == "active",
                )
            )
        ).all()
        mapping_ids = {mapping_id for mapping_id, _platform_location_id in rows}
        platform_location_ids = {
            platform_location_id
            for _mapping_id, platform_location_id in rows
            if platform_location_id is not None
        }
        return mapping_ids, platform_location_ids

    # -- GitHub workspace ------------------------------------------------------

    async def github_workspace(
        self, session: AsyncSession, organization_id: UUID
    ) -> GitHubWorkspace:
        connection = await session.scalar(
            select(IntegrationConnection)
            .join(Provider, Provider.id == IntegrationConnection.provider_id)
            .where(
                IntegrationConnection.organization_id == organization_id,
                Provider.key == "github",
            )
            .order_by(IntegrationConnection.created_at.desc())
        )
        if connection is None:
            return GitHubWorkspace(
                connection_status="none",
                connection_id=None,
                external_account_reference=None,
                repositories=[],
            )
        return GitHubWorkspace(
            connection_status=connection.status,
            connection_id=str(connection.id),
            external_account_reference=connection.external_account_reference,
            repositories=[],
        )
