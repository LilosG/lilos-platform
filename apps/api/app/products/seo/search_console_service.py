"""Search Console discovery, property mapping, and search-observation sync.

This is the real operator workflow for the SEO product's Search Console
integration, driven by the shared Google ``IntegrationConnection``:

    discover accessible Search Console properties
      -> recommend/match a property using the client website's canonical domain
      -> operator confirms/selects a property
      -> idempotent ``SEOSearchProperty`` mapping is persisted
      -> search analytics (clicks/impressions/ctr/position) syncs into
         ``SEOSearchObservation``
      -> the SEO page consumes the mapped property + observations directly

It never asks the operator to type a property ID, never duplicates a mapping,
records freshness/last-sync state, and surfaces truthful zero-property and
reconnect states. Only the metrics the SEO model already defines are
synchronized -- nothing is fabricated.
"""

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.integrations.connection_service import (
    SEARCH_CONSOLE_SCOPE,
    GBPConnectionService,
    connection_has_scope,
)
from apps.api.app.integrations.errors import IntegrationNotFoundError
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.seo.errors import (
    SEOSearchConsoleDiscoveryFailedError,
    SEOSearchConsoleScopeRequiredError,
    SEOSearchPropertyNotConfiguredError,
    SEOSearchPropertyNotFoundError,
)
from apps.api.app.products.seo.models import SEOSearchObservation, SEOSearchProperty, SEOWebsite
from apps.api.app.products.seo.search_console_adapter import (
    DiscoveredSearchProperty,
    GoogleSearchConsoleAdapter,
    SearchConsoleAdapter,
)

DEFAULT_SYNC_WINDOW_DAYS = 28
# Search Console finalized data lags ~2 days; never request the most recent
# couple of days as though they were final.
SYNC_TAIL_EXCLUSION_DAYS = 2


@dataclass(frozen=True, slots=True)
class PropertyRecommendation:
    """Discovery result plus an optional canonical-domain recommendation."""

    properties: tuple[DiscoveredSearchProperty, ...]
    recommended: DiscoveredSearchProperty | None


def _canonical_host(canonical_origin: str) -> str:
    host = urlsplit(canonical_origin).hostname or ""
    return host.lower().removeprefix("www.")


def _property_host(site_url: str) -> str:
    """Extract the bare registrable host from a Search Console property id."""
    if site_url.startswith("sc-domain:"):
        return site_url.removeprefix("sc-domain:").lower().removeprefix("www.")
    return (urlsplit(site_url).hostname or "").lower().removeprefix("www.")


def recommend_property(
    properties: Sequence[DiscoveredSearchProperty], canonical_origin: str
) -> DiscoveredSearchProperty | None:
    """Recommend the Search Console property that matches the website domain.

    Prefers a domain property (``sc-domain:``) over a URL-prefix property when
    both cover the same host, since domain properties aggregate across schemes
    and subdomains. Returns ``None`` when no property covers the canonical host
    so the operator must select explicitly -- never silently guessing.
    """
    target = _canonical_host(canonical_origin)
    if not target:
        return None
    matches = [p for p in properties if _property_host(p.external_property_id) == target]
    if not matches:
        return None
    domain_matches = [p for p in matches if p.property_type == "domain"]
    return domain_matches[0] if domain_matches else matches[0]


def _dimension_hash(dimensions: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(dimensions, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _sync_window(now: datetime, days: int) -> tuple[datetime, datetime]:
    """Return the (start, end) sync window as day-aligned UTC datetimes.

    Day alignment is essential for idempotency: the ``SEOSearchObservation``
    uniqueness key includes ``date_start``/``date_end``, so a repeat sync on
    the same calendar day must produce the *same* range (not one shifted by
    microseconds). The most recent ~2 days are excluded because Search Console
    finalized data lags.
    """
    window_end_date = (now - timedelta(days=SYNC_TAIL_EXCLUSION_DAYS)).date()
    start_date = window_end_date - timedelta(days=days)
    start = datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)
    window_end = datetime(
        window_end_date.year, window_end_date.month, window_end_date.day, tzinfo=UTC
    )
    return start, window_end


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


@dataclass(slots=True)
class SearchConsoleService:
    """Discover, map, and sync Search Console properties and observations."""

    adapter: SearchConsoleAdapter = field(default_factory=GoogleSearchConsoleAdapter)
    connection: GBPConnectionService = field(default_factory=GBPConnectionService)
    audit: AuditEventService = field(default_factory=AuditEventService)
    http_client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient

    # -- audit ---------------------------------------------------------------

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
                product_key="seo",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    # -- token + scope gating ------------------------------------------------

    async def _connection(
        self, session: AsyncSession, organization_id: UUID
    ) -> IntegrationConnection:
        connection = await self.connection.find_connection(session, organization_id)
        if connection is None or connection.status == "disconnected":
            raise SEOSearchPropertyNotConfiguredError
        return connection

    async def _fresh_token(
        self, session: AsyncSession, settings: Settings, organization_id: UUID
    ) -> tuple[str, IntegrationConnection]:
        connection = await self._connection(session, organization_id)
        if not connection_has_scope(connection, SEARCH_CONSOLE_SCOPE):
            raise SEOSearchConsoleScopeRequiredError
        token = await self.connection.ensure_fresh_token(session, settings, connection)
        return token, connection

    # -- discovery -----------------------------------------------------------

    async def discover_properties(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        website_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> PropertyRecommendation:
        """Discover the operator's accessible Search Console properties.

        Recommends the property matching the website's canonical domain when
        one is present; otherwise returns all accessible properties for the
        operator to choose from. Does not persist anything.
        """
        website = await self._get_website(session, organization_id, website_id)
        token, connection = await self._fresh_token(session, settings, organization_id)
        try:
            properties = await self.adapter.list_sites(token)
        except Exception as exc:
            await self._audit(
                session,
                event="seo.search_console.discovery_failed",
                organization_id=organization_id,
                actor_id=actor_id,
                resource_type="integration_connection",
                resource_id=connection.id,
                correlation_id=correlation_id,
                summary="Search Console property discovery failed.",
                metadata={"error": str(exc)[:200]},
                result=AuditResult.FAILED,
            )
            raise SEOSearchConsoleDiscoveryFailedError from exc
        recommended = recommend_property(properties, website.canonical_origin)
        await self._audit(
            session,
            event="seo.search_console.discovered",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="seo_website",
            resource_id=website.id,
            correlation_id=correlation_id,
            summary=f"Discovered {len(properties)} Search Console properties.",
            metadata={
                "count": len(properties),
                "recommended": recommended.external_property_id if recommended else None,
            },
        )
        return PropertyRecommendation(properties=tuple(properties), recommended=recommended)

    # -- idempotent mapping --------------------------------------------------

    async def map_property(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        website_id: UUID,
        *,
        external_property_id: str,
        property_type: str,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> SEOSearchProperty:
        """Persist (idempotently) the operator's selected Search Console property.

        No duplicate mapping is ever created: a mapping for the same
        (organization, provider, external property) is updated in place.
        """
        website = await self._get_website(session, organization_id, website_id)
        token, connection = await self._fresh_token(session, settings, organization_id)
        del token  # mapping itself needs no provider call; scope already gated
        existing = await session.scalar(
            select(SEOSearchProperty).where(
                SEOSearchProperty.organization_id == organization_id,
                SEOSearchProperty.provider == "google_search_console",
                SEOSearchProperty.external_property_id == external_property_id,
            )
        )
        if existing is not None:
            existing.connection_id = connection.id
            existing.website_id = website.id
            existing.property_type = property_type
            existing.mapping_status = "mapped"
            await session.flush()
            item = existing
            event = "seo.search_property.remapped"
        else:
            item = SEOSearchProperty(
                organization_id=organization_id,
                website_id=website.id,
                connection_id=connection.id,
                provider="google_search_console",
                external_property_id=external_property_id,
                property_type=property_type,
                mapping_status="mapped",
                freshness_status="never_synced",
            )
            session.add(item)
            await session.flush()
            event = "seo.search_property.mapped"
        await self._audit(
            session,
            event=event,
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="seo_search_property",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary="Search Console property mapped.",
            metadata={
                "external_property_id": external_property_id,
                "property_type": property_type,
            },
        )
        return item

    # -- sync ----------------------------------------------------------------

    async def sync_observations(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        search_property_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        days: int = DEFAULT_SYNC_WINDOW_DAYS,
    ) -> dict[str, object]:
        """Pull real Search Console metrics into ``SEOSearchObservation``.

        Only the metrics the SEO model already defines are stored (clicks,
        impressions, ctr, position). Rows are upserted idempotently on the
        (search_property, date_start, date_end, dimension_hash) uniqueness key.
        """
        property_row = await session.scalar(
            select(SEOSearchProperty).where(
                SEOSearchProperty.organization_id == organization_id,
                SEOSearchProperty.id == search_property_id,
            )
        )
        if property_row is None:
            raise SEOSearchPropertyNotFoundError
        if property_row.provider != "google_search_console":
            raise SEOSearchPropertyNotFoundError
        website = await self._get_website(session, organization_id, property_row.website_id)
        token, connection = await self._fresh_token(session, settings, organization_id)
        del connection
        now = datetime.now(UTC)
        start, window_end = _sync_window(now, days)
        try:
            rows = await self.adapter.query_search_analytics(
                token,
                property_row.external_property_id,
                start_date=_date_str(start),
                end_date=_date_str(window_end),
                dimensions=("query",),
                row_limit=1000,
            )
        except Exception as exc:
            await self._audit(
                session,
                event="seo.search_console.sync_failed",
                organization_id=organization_id,
                actor_id=actor_id,
                resource_type="seo_search_property",
                resource_id=property_row.id,
                correlation_id=correlation_id,
                summary="Search Console sync failed.",
                metadata={"error": str(exc)[:200]},
                result=AuditResult.FAILED,
            )
            raise SEOSearchConsoleDiscoveryFailedError from exc

        upserted = 0
        for row in rows:
            query = row.keys[0] if row.keys else ""
            dimensions: dict[str, object] = {"query": query}
            dim_hash = _dimension_hash(dimensions)
            existing = await session.scalar(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.search_property_id == property_row.id,
                    SEOSearchObservation.date_start == start,
                    SEOSearchObservation.date_end == window_end,
                    SEOSearchObservation.dimension_hash == dim_hash,
                )
            )
            if existing is not None:
                existing.clicks = row.clicks
                existing.impressions = row.impressions
                existing.ctr = row.ctr
                existing.position = row.position
                existing.query = query or None
                existing.dimensions = dimensions
                existing.quality_status = "valid"
                existing.partial = False
            else:
                session.add(
                    SEOSearchObservation(
                        organization_id=organization_id,
                        search_property_id=property_row.id,
                        page_id=None,
                        query=query or None,
                        date_start=start,
                        date_end=window_end,
                        dimensions=dimensions,
                        dimension_hash=dim_hash,
                        clicks=row.clicks,
                        impressions=row.impressions,
                        ctr=row.ctr,
                        position=row.position,
                        quality_status="valid",
                        partial=False,
                    )
                )
            upserted += 1
        await session.flush()
        property_row.last_synced_at = datetime.now(UTC)
        property_row.freshness_status = "fresh"
        await session.flush()
        await self._audit(
            session,
            event="seo.search_console.synced",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="seo_search_property",
            resource_id=property_row.id,
            correlation_id=correlation_id,
            summary=f"Synced {upserted} Search Console observations.",
            metadata={"rows": upserted, "window_days": days},
        )
        del website
        return {
            "search_property_id": str(property_row.id),
            "rows_synced": upserted,
            "window_days": days,
            "freshness_status": property_row.freshness_status,
        }

    # -- read helpers --------------------------------------------------------

    async def _get_website(
        self, session: AsyncSession, organization_id: UUID, website_id: UUID
    ) -> SEOWebsite:
        website = await session.scalar(
            select(SEOWebsite).where(
                SEOWebsite.organization_id == organization_id, SEOWebsite.id == website_id
            )
        )
        if website is None:
            raise IntegrationNotFoundError
        return website

    async def search_performance_summary(
        self, session: AsyncSession, organization_id: UUID, website_id: UUID
    ) -> dict[str, object]:
        """Aggregate the synced observations for the SEO page.

        Returns zeros (not fabricated metrics) when nothing is synced yet, so
        the SEO page shows a truthful 'not synced' state rather than dummy data.
        """
        await self._get_website(session, organization_id, website_id)
        properties = list(
            await session.scalars(
                select(SEOSearchProperty).where(
                    SEOSearchProperty.organization_id == organization_id,
                    SEOSearchProperty.website_id == website_id,
                    SEOSearchProperty.provider == "google_search_console",
                    SEOSearchProperty.mapping_status == "mapped",
                )
            )
        )
        if not properties:
            return {"connected": False, "total_clicks": 0, "total_impressions": 0, "properties": []}
        prop_ids = [p.id for p in properties]
        rows = list(
            await session.scalars(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.organization_id == organization_id,
                    SEOSearchObservation.search_property_id.in_(prop_ids),
                )
            )
        )
        return {
            "connected": True,
            "total_clicks": sum(r.clicks or 0 for r in rows),
            "total_impressions": sum(r.impressions or 0 for r in rows),
            "properties": [
                {
                    "id": str(p.id),
                    "external_property_id": p.external_property_id,
                    "property_type": p.property_type,
                    "freshness_status": p.freshness_status,
                    "last_synced_at": p.last_synced_at,
                }
                for p in properties
            ],
        }
