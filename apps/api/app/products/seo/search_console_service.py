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
from sqlalchemy import func, select
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
    SearchAnalyticsRow,
    SearchConsoleAdapter,
)
from apps.api.app.reporting_periods import (
    GSC_SYNC_TAIL_EXCLUSION_DAYS,
    VALID_REPORTING_PERIODS,
    comparison_window,
    format_range_label,
    provider_end_date,
    provider_start_date,
    reporting_window,
)

DEFAULT_SYNC_WINDOW_DAYS = 28
DEFAULT_FRESHNESS_STALE_SECONDS = 172_800  # 48 hours


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

        A website has exactly one authoritative mapped property. Selecting a
        new property replaces any prior authoritative mapping for the same
        website (transitioned to ``replaced``), so reporting resolves a single
        deterministic source without ambiguity.
        """
        website = await self._get_website(session, organization_id, website_id)
        token, connection = await self._fresh_token(session, settings, organization_id)
        del token  # mapping itself needs no provider call; scope already gated
        # Replace any other authoritative mapping for this website.
        prior_authoritative = list(
            await session.scalars(
                select(SEOSearchProperty).where(
                    SEOSearchProperty.organization_id == organization_id,
                    SEOSearchProperty.website_id == website.id,
                    SEOSearchProperty.provider == "google_search_console",
                    SEOSearchProperty.mapping_status == "mapped",
                    SEOSearchProperty.external_property_id != external_property_id,
                )
            )
        )
        for prior in prior_authoritative:
            prior.mapping_status = "replaced"
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

        Syncs all supported reporting periods (7/28/90 days) so the reporting
        selector is populated by a single governed sync. For each period it
        pulls four observation types:

        - site_summary: no dimensions (authoritative site-level totals)
        - daily: date dimension (for trend series)
        - top_queries: query dimension (top search queries)
        - top_pages: page dimension (top landing pages)

        Rows are upserted idempotently on the
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
        upserted = 0
        failed = False
        failures: list[dict[str, object]] = []

        # Persist the 7/28/90 contract atomically so a partial attempt never
        # publishes a newer incomplete current window. On any required failure
        # the savepoint is rolled back and the previous successful dataset stays.
        nested = session.begin_nested()
        await nested.start()
        try:
            for period_days in VALID_REPORTING_PERIODS:
                start, window_end = reporting_window(now, period_days, GSC_SYNC_TAIL_EXCLUSION_DAYS)
                period_upserted, period_failed = await self._sync_period(
                    session,
                    token,
                    organization_id,
                    property_row,
                    start,
                    window_end,
                    period_days,
                    actor_id,
                    correlation_id,
                    failures,
                )
                upserted += period_upserted
                if period_failed:
                    failed = True
        except BaseException:
            await nested.rollback()
            raise

        if failed:
            await nested.rollback()
            if property_row.last_synced_at is None:
                property_row.freshness_status = "never_synced"
            else:
                property_row.freshness_status = "stale"
            await session.flush()
            await self._audit(
                session,
                event="seo.search_console.sync_incomplete",
                organization_id=organization_id,
                actor_id=actor_id,
                resource_type="seo_search_property",
                resource_id=property_row.id,
                correlation_id=correlation_id,
                summary="Search Console sync incomplete: one or more required requests "
                "failed; previous successful dataset preserved.",
                metadata={"failures": failures},
                result=AuditResult.FAILED,
            )
            del website
            return {
                "search_property_id": str(property_row.id),
                "rows_synced": 0,
                "window_days": days,
                "periods_synced": [],
                "freshness_status": property_row.freshness_status,
            }

        await nested.commit()
        property_row.last_synced_at = now
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
            summary=f"Synced {upserted} Search Console observations across "
            f"{len(VALID_REPORTING_PERIODS)} periods.",
            metadata={
                "rows": upserted,
                "periods_synced": list(VALID_REPORTING_PERIODS),
            },
        )
        del website
        return {
            "search_property_id": str(property_row.id),
            "rows_synced": upserted,
            "window_days": days,
            "periods_synced": list(VALID_REPORTING_PERIODS),
            "freshness_status": property_row.freshness_status,
        }

    async def _sync_period(
        self,
        session: AsyncSession,
        token: str,
        organization_id: UUID,
        property_row: SEOSearchProperty,
        start: datetime,
        window_end: datetime,
        period_days: int,
        actor_id: UUID | None,
        correlation_id: str,
        failures: list[dict[str, object]],
    ) -> tuple[int, bool]:
        """Sync one period's current + prior aggregates and current dimensions.

        Returns ``(rows_upserted, failed)``; ``failed`` is True when any
        required provider request for the reporting contract did not succeed.
        Provider failures are appended to ``failures`` for auditing after the
        atomic savepoint decision.
        """
        upserted = 0
        failed = False
        external_id = property_row.external_property_id
        comp_start, comp_end = comparison_window(start, period_days)

        # A. Current site summary — no dimensions, authoritative site-level totals
        try:
            summary_rows = await self.adapter.query_search_analytics(
                token,
                external_id,
                start_date=provider_start_date(start),
                end_date=provider_end_date(window_end),
                dimensions=(),
                row_limit=1000,
            )
        except Exception as exc:
            failures.append(
                {
                    "request": "site_summary",
                    "period_days": period_days,
                    "error": str(exc)[:200],
                }
            )
            return 0, True

        for row in summary_rows:
            await self._store_site_summary(
                session,
                property_row,
                organization_id,
                date_start=start,
                date_end=window_end,
                row=row,
            )
            upserted += 1

        # B. Prior site summary — exact comparison window for delta/percent
        try:
            prior_summary_rows = await self.adapter.query_search_analytics(
                token,
                external_id,
                start_date=provider_start_date(comp_start),
                end_date=provider_end_date(comp_end),
                dimensions=(),
                row_limit=1000,
            )
        except Exception as exc:
            prior_summary_rows = []
            failed = True
            failures.append(
                {
                    "request": "prior_site_summary",
                    "period_days": period_days,
                    "error": str(exc)[:200],
                }
            )

        for row in prior_summary_rows:
            await self._store_site_summary(
                session,
                property_row,
                organization_id,
                date_start=comp_start,
                date_end=comp_end,
                row=row,
            )
            upserted += 1

        # B. Daily series — date dimension for trend charts
        try:
            daily_rows = await self.adapter.query_search_analytics(
                token,
                external_id,
                start_date=provider_start_date(start),
                end_date=provider_end_date(window_end),
                dimensions=("date",),
                row_limit=25000,
            )
        except Exception as exc:
            daily_rows = []
            failed = True
            failures.append(
                {
                    "request": "daily",
                    "period_days": period_days,
                    "error": str(exc)[:200],
                }
            )

        from datetime import date as date_type

        for row in daily_rows:
            date_val = row.keys[0] if row.keys else ""
            if not date_val:
                continue
            day_dims: dict[str, object] = {"observation_type": "daily", "date": date_val}
            day_dim_hash = _dimension_hash(day_dims)
            day_dt = date_type.fromisoformat(date_val)
            day_start = datetime(day_dt.year, day_dt.month, day_dt.day, tzinfo=UTC)
            day_end = day_start + timedelta(days=1)
            existing = await session.scalar(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.search_property_id == property_row.id,
                    SEOSearchObservation.date_start == day_start,
                    SEOSearchObservation.date_end == day_end,
                    SEOSearchObservation.dimension_hash == day_dim_hash,
                )
            )
            if existing is not None:
                existing.clicks = row.clicks
                existing.impressions = row.impressions
                existing.ctr = row.ctr
                existing.position = row.position
                existing.query = None
                existing.dimensions = day_dims
                existing.quality_status = "valid"
                existing.partial = False
            else:
                session.add(
                    SEOSearchObservation(
                        organization_id=organization_id,
                        search_property_id=property_row.id,
                        page_id=None,
                        query=None,
                        date_start=day_start,
                        date_end=day_end,
                        dimensions=day_dims,
                        dimension_hash=day_dim_hash,
                        clicks=row.clicks,
                        impressions=row.impressions,
                        ctr=row.ctr,
                        position=row.position,
                        quality_status="valid",
                        partial=False,
                    )
                )
            upserted += 1

        # C. Top queries — query dimension
        try:
            query_rows = await self.adapter.query_search_analytics(
                token,
                external_id,
                start_date=provider_start_date(start),
                end_date=provider_end_date(window_end),
                dimensions=("query",),
                row_limit=1000,
            )
        except Exception as exc:
            query_rows = []
            failed = True
            failures.append(
                {
                    "request": "top_queries",
                    "period_days": period_days,
                    "error": str(exc)[:200],
                }
            )

        for row in query_rows:
            q = row.keys[0] if row.keys else ""
            query_dims: dict[str, object] = {"observation_type": "top_query", "query": q}
            query_dim_hash = _dimension_hash(query_dims)
            existing = await session.scalar(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.search_property_id == property_row.id,
                    SEOSearchObservation.date_start == start,
                    SEOSearchObservation.date_end == window_end,
                    SEOSearchObservation.dimension_hash == query_dim_hash,
                )
            )
            if existing is not None:
                existing.clicks = row.clicks
                existing.impressions = row.impressions
                existing.ctr = row.ctr
                existing.position = row.position
                existing.query = q or None
                existing.dimensions = query_dims
                existing.quality_status = "valid"
                existing.partial = False
            else:
                session.add(
                    SEOSearchObservation(
                        organization_id=organization_id,
                        search_property_id=property_row.id,
                        page_id=None,
                        query=q or None,
                        date_start=start,
                        date_end=window_end,
                        dimensions=query_dims,
                        dimension_hash=query_dim_hash,
                        clicks=row.clicks,
                        impressions=row.impressions,
                        ctr=row.ctr,
                        position=row.position,
                        quality_status="valid",
                        partial=False,
                    )
                )
            upserted += 1

        # D. Top pages — page dimension
        try:
            page_rows = await self.adapter.query_search_analytics(
                token,
                external_id,
                start_date=provider_start_date(start),
                end_date=provider_end_date(window_end),
                dimensions=("page",),
                row_limit=1000,
            )
        except Exception as exc:
            page_rows = []
            failed = True
            failures.append(
                {
                    "request": "top_pages",
                    "period_days": period_days,
                    "error": str(exc)[:200],
                }
            )

        for row in page_rows:
            p = row.keys[0] if row.keys else ""
            page_dims: dict[str, object] = {"observation_type": "top_page", "page": p}
            page_dim_hash = _dimension_hash(page_dims)
            existing = await session.scalar(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.search_property_id == property_row.id,
                    SEOSearchObservation.date_start == start,
                    SEOSearchObservation.date_end == window_end,
                    SEOSearchObservation.dimension_hash == page_dim_hash,
                )
            )
            if existing is not None:
                existing.clicks = row.clicks
                existing.impressions = row.impressions
                existing.ctr = row.ctr
                existing.position = row.position
                existing.query = None
                existing.dimensions = page_dims
                existing.quality_status = "valid"
                existing.partial = False
            else:
                session.add(
                    SEOSearchObservation(
                        organization_id=organization_id,
                        search_property_id=property_row.id,
                        page_id=None,
                        query=None,
                        date_start=start,
                        date_end=window_end,
                        dimensions=page_dims,
                        dimension_hash=page_dim_hash,
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
        return upserted, failed

    async def _store_site_summary(
        self,
        session: AsyncSession,
        property_row: SEOSearchProperty,
        organization_id: UUID,
        *,
        date_start: datetime,
        date_end: datetime,
        row: SearchAnalyticsRow,
    ) -> None:
        """Upsert one authoritative site_summary observation for the window."""
        dims: dict[str, object] = {"observation_type": "site_summary"}
        dim_hash = _dimension_hash(dims)
        existing = await session.scalar(
            select(SEOSearchObservation).where(
                SEOSearchObservation.search_property_id == property_row.id,
                SEOSearchObservation.date_start == date_start,
                SEOSearchObservation.date_end == date_end,
                SEOSearchObservation.dimension_hash == dim_hash,
            )
        )
        if existing is not None:
            existing.clicks = row.clicks
            existing.impressions = row.impressions
            existing.ctr = row.ctr
            existing.position = row.position
            existing.query = None
            existing.dimensions = dims
            existing.quality_status = "valid"
            existing.partial = False
        else:
            session.add(
                SEOSearchObservation(
                    organization_id=organization_id,
                    search_property_id=property_row.id,
                    page_id=None,
                    query=None,
                    date_start=date_start,
                    date_end=date_end,
                    dimensions=dims,
                    dimension_hash=dim_hash,
                    clicks=row.clicks,
                    impressions=row.impressions,
                    ctr=row.ctr,
                    position=row.position,
                    quality_status="valid",
                    partial=False,
                )
            )

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

    async def _authoritative_property(
        self, session: AsyncSession, organization_id: UUID, website_id: UUID
    ) -> SEOSearchProperty | None:
        """Return the single authoritative mapped Search Console property.

        Deterministic when more than one ``mapped`` row exists (legacy data):
        the earliest-created mapped property wins. New mappings replace prior
        authoritative mappings, so in practice at most one ``mapped`` row
        exists per website.
        """
        prop = await session.scalar(
            select(SEOSearchProperty)
            .where(
                SEOSearchProperty.organization_id == organization_id,
                SEOSearchProperty.website_id == website_id,
                SEOSearchProperty.provider == "google_search_console",
                SEOSearchProperty.mapping_status == "mapped",
            )
            .order_by(SEOSearchProperty.created_at.asc(), SEOSearchProperty.id.asc())
        )
        return prop

    async def _latest_site_summary_current_window(
        self, session: AsyncSession, prop_ids: list[UUID], days: int
    ) -> tuple[datetime, datetime] | None:
        """Return the latest authoritative current site_summary window for `days`.

        The newest exact-duration site_summary is the current report window;
        its prior comparison has the same duration but an earlier ``date_end``.
        """
        current = await session.scalar(
            select(SEOSearchObservation)
            .where(
                SEOSearchObservation.search_property_id.in_(prop_ids),
                SEOSearchObservation.dimensions["observation_type"].astext == "site_summary",
                SEOSearchObservation.quality_status.in_(["valid", "zero"]),
                func.extract(
                    "epoch", SEOSearchObservation.date_end - SEOSearchObservation.date_start
                )
                == days * 86_400,
            )
            .order_by(SEOSearchObservation.date_end.desc())
        )
        if current is None:
            return None
        return current.date_start, current.date_end

    async def performance_report(
        self,
        session: AsyncSession,
        organization_id: UUID,
        website_id: UUID,
        *,
        days: int = DEFAULT_SYNC_WINDOW_DAYS,
    ) -> dict[str, object]:
        """Return a reporting-safe Search Console performance contract.

        Selects only the exact authoritative window's observations to prevent
        overlapping-window double counting. Returns site summary KPIs, daily
        trend series, top queries, and top pages with comparisons.
        """
        await self._get_website(session, organization_id, website_id)
        prop = await self._authoritative_property(session, organization_id, website_id)
        if prop is None:
            return {
                "connected": False,
                "properties": [],
                "range": None,
                "comparison_range": None,
                "freshness": {"last_synced_at": None, "status": "never_synced"},
                "metrics": {},
                "series": [],
                "top_queries": [],
                "top_pages": [],
            }

        if days not in VALID_REPORTING_PERIODS:
            days = DEFAULT_SYNC_WINDOW_DAYS

        now = datetime.now(UTC)
        last_synced = prop.last_synced_at
        stale_threshold = now - timedelta(seconds=DEFAULT_FRESHNESS_STALE_SECONDS)
        freshness_status = "fresh"
        if last_synced is None:
            freshness_status = "never_synced"
        elif prop.freshness_status == "stale" or last_synced < stale_threshold:
            freshness_status = "stale"

        prop_ids = [prop.id]
        window = await self._latest_site_summary_current_window(session, prop_ids, days)

        if window is None:
            return {
                "connected": True,
                "properties": [
                    {
                        "id": str(prop.id),
                        "external_property_id": prop.external_property_id,
                        "property_type": prop.property_type,
                        "freshness_status": prop.freshness_status,
                        "last_synced_at": prop.last_synced_at.isoformat()
                        if prop.last_synced_at
                        else None,
                    }
                ],
                "range": None,
                "comparison_range": None,
                "freshness": {
                    "last_synced_at": last_synced.isoformat() if last_synced else None,
                    "status": freshness_status,
                },
                "metrics": {},
                "series": [],
                "top_queries": [],
                "top_pages": [],
            }

        current_start, current_end = window
        comp_start, comp_end = comparison_window(current_start, days)

        # Get site summary observations for current and comparison periods
        current_summary = await self._get_observation_by_type(
            session, prop_ids, current_start, current_end, "site_summary"
        )
        comp_summary = await self._get_observation_by_type(
            session, prop_ids, comp_start, comp_end, "site_summary"
        )

        metrics = {}
        for metric_key in ("clicks", "impressions", "ctr", "position"):
            curr_val = getattr(current_summary, metric_key, None) if current_summary else None
            prev_val = getattr(comp_summary, metric_key, None) if comp_summary else None
            absolute_delta = None
            percent_delta = None
            if (
                curr_val is not None
                and prev_val is not None
                and isinstance(curr_val, (int, float))
                and isinstance(prev_val, (int, float))
            ):
                absolute_delta = float(curr_val) - float(prev_val)
                if prev_val != 0:
                    pct = (float(curr_val) - float(prev_val)) / abs(float(prev_val)) * 100
                    percent_delta = pct

            quality = "valid"
            if curr_val is None:
                quality = "missing"
            elif prev_val is None:
                quality = "partial"

            metrics[metric_key] = {
                "current": float(curr_val) if curr_val is not None else None,
                "previous": float(prev_val) if prev_val is not None else None,
                "delta": absolute_delta,
                "percent_delta": percent_delta,
                "quality": quality,
            }

        # Daily series
        daily_obs = await self._get_typed_observations(
            session, prop_ids, current_start, current_end, "daily"
        )
        series = []
        for obs in sorted(
            daily_obs,
            key=lambda o: o.date_start if o.date_start else datetime.min.replace(tzinfo=UTC),
        ):
            date_label = obs.dimensions.get(
                "date",
                obs.date_start.strftime("%Y-%m-%d") if obs.date_start else "",
            )
            series.append(
                {
                    "date": date_label,
                    "clicks": obs.clicks,
                    "impressions": obs.impressions,
                    "ctr": float(obs.ctr) if obs.ctr is not None else None,
                    "position": float(obs.position) if obs.position is not None else None,
                }
            )

        # Top queries
        top_query_obs = await self._get_typed_observations(
            session, prop_ids, current_start, current_end, "top_query"
        )
        top_queries = sorted(
            [
                {
                    "query": str(o.dimensions.get("query", "")),
                    "clicks": o.clicks,
                    "impressions": o.impressions,
                    "ctr": float(o.ctr) if o.ctr is not None else None,
                    "position": float(o.position) if o.position is not None else None,
                }
                for o in top_query_obs
            ],
            key=lambda x: cast(int, x["clicks"]) if x["clicks"] is not None else -1,
            reverse=True,
        )[:25]

        # Top pages
        top_page_obs = await self._get_typed_observations(
            session, prop_ids, current_start, current_end, "top_page"
        )
        top_pages = sorted(
            [
                {
                    "page": str(o.dimensions.get("page", "")),
                    "clicks": o.clicks,
                    "impressions": o.impressions,
                    "ctr": float(o.ctr) if o.ctr is not None else None,
                    "position": float(o.position) if o.position is not None else None,
                }
                for o in top_page_obs
            ],
            key=lambda x: cast(int, x["clicks"]) if x["clicks"] is not None else -1,
            reverse=True,
        )[:25]

        prop_data = [
            {
                "id": str(prop.id),
                "external_property_id": prop.external_property_id,
                "property_type": prop.property_type,
                "freshness_status": prop.freshness_status,
                "last_synced_at": prop.last_synced_at.isoformat() if prop.last_synced_at else None,
            }
        ]

        return {
            "connected": True,
            "properties": prop_data,
            "range": format_range_label(current_start, current_end, days),
            "comparison_range": format_range_label(comp_start, comp_end, days),
            "freshness": {
                "last_synced_at": last_synced.isoformat() if last_synced else None,
                "status": freshness_status,
            },
            "metrics": metrics,
            "series": series,
            "top_queries": top_queries,
            "top_pages": top_pages,
        }

    async def _get_observation_by_type(
        self,
        session: AsyncSession,
        prop_ids: list[UUID],
        period_start: datetime,
        period_end: datetime,
        observation_type: str,
    ) -> SEOSearchObservation | None:
        """Get the authoritative observation of a given type for the exact period.

        Resolves against the single authoritative property (``prop_ids`` always
        contains exactly one id), so summary/daily/query/page reads share one
        source and never mix properties. CTR/position are never aggregated.
        """
        result = await session.scalar(
            select(SEOSearchObservation)
            .where(
                SEOSearchObservation.search_property_id.in_(prop_ids),
                SEOSearchObservation.date_start == period_start,
                SEOSearchObservation.date_end == period_end,
                SEOSearchObservation.dimensions["observation_type"].astext == observation_type,
                SEOSearchObservation.quality_status.in_(["valid", "zero"]),
            )
            .order_by(SEOSearchObservation.date_end.desc())
        )
        return result

    async def _get_typed_observations(
        self,
        session: AsyncSession,
        prop_ids: list[UUID],
        period_start: datetime,
        period_end: datetime,
        observation_type: str,
    ) -> list[SEOSearchObservation]:
        """Get all observations of a given type for the exact period."""
        rows = list(
            await session.scalars(
                select(SEOSearchObservation)
                .where(
                    SEOSearchObservation.search_property_id.in_(prop_ids),
                    SEOSearchObservation.date_start >= period_start,
                    SEOSearchObservation.date_end <= period_end,
                    SEOSearchObservation.dimensions["observation_type"].astext == observation_type,
                    SEOSearchObservation.quality_status.in_(["valid", "zero"]),
                )
                .order_by(SEOSearchObservation.date_start.asc())
            )
        )
        return rows

    async def search_performance_summary(
        self, session: AsyncSession, organization_id: UUID, website_id: UUID
    ) -> dict[str, object]:
        """Aggregate the synced observations for the SEO page.

        Returns zeros (not fabricated metrics) when nothing is synced yet, so
        the SEO page shows a truthful 'not synced' state rather than dummy data.
        """
        await self._get_website(session, organization_id, website_id)
        prop = await self._authoritative_property(session, organization_id, website_id)
        if prop is None:
            return {"connected": False, "total_clicks": 0, "total_impressions": 0, "properties": []}
        # Select only the most recent site_summary to prevent overlapping-window
        # double counting. Multiple syncs produce multiple site_summary rows
        # (current + prior per period); only the latest current one is used.
        latest = await session.scalar(
            select(SEOSearchObservation)
            .where(
                SEOSearchObservation.organization_id == organization_id,
                SEOSearchObservation.search_property_id == prop.id,
                SEOSearchObservation.dimensions["observation_type"].astext == "site_summary",
            )
            .order_by(SEOSearchObservation.date_end.desc())
        )
        return {
            "connected": True,
            "total_clicks": latest.clicks if latest is not None else 0,
            "total_impressions": latest.impressions if latest is not None else 0,
            "properties": [
                {
                    "id": str(prop.id),
                    "external_property_id": prop.external_property_id,
                    "property_type": prop.property_type,
                    "freshness_status": prop.freshness_status,
                    "last_synced_at": prop.last_synced_at,
                }
            ],
        }
