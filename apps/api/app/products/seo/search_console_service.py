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
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.database.scope import TransactionScope
from apps.api.app.integrations.adapter_factory import search_console_adapter
from apps.api.app.integrations.connection_service import (
    SEARCH_CONSOLE_SCOPE,
    GBPConnectionService,
    connection_has_scope,
)
from apps.api.app.integrations.errors import (
    IntegrationNotFoundError,
    IntegrationReconnectRequiredError,
    IntegrationTokenExchangeFailedError,
)
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.seo.errors import (
    SEOSearchConsoleDiscoveryFailedError,
    SEOSearchConsoleScopeRequiredError,
    SEOSearchPropertyNotConfiguredError,
    SEOSearchPropertyNotFoundError,
)
from apps.api.app.products.seo.models import SEOSearchObservation, SEOSearchProperty, SEOWebsite
from apps.api.app.products.seo.page_identity import RESOLVER_VERSION, PageResolver
from apps.api.app.products.seo.search_console_adapter import (
    DiscoveredSearchProperty,
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


@dataclass(slots=True)
class PeriodFetch:
    """One reporting period's provider responses, fetched before anything is written.

    Each field is the rows, or the exception the request raised (so a failed
    request is recorded and audited exactly as it was when fetch and write were
    interleaved).
    """

    site_summary: "list[SearchAnalyticsRow] | Exception"
    prior_summary: "list[SearchAnalyticsRow] | Exception"
    daily: "list[SearchAnalyticsRow] | Exception"
    top_queries: "list[SearchAnalyticsRow] | Exception"
    top_pages: "list[SearchAnalyticsRow] | Exception"
    page_query: "list[SearchAnalyticsRow] | Exception"


DEFAULT_SYNC_WINDOW_DAYS = 28
DEFAULT_FRESHNESS_STALE_SECONDS = 172_800  # 48 hours
PAGE_OBSERVATION_CHUNK_SIZE = 200


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

    adapter: SearchConsoleAdapter = field(default_factory=search_console_adapter)
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

        # Verify the operator-selected property against Google's accessible
        # Search Console properties before treating the website as verified.
        # A matching string supplied by the client is not sufficient evidence.
        try:
            accessible_properties = await self.adapter.list_sites(token)
        except Exception as exc:
            raise SEOSearchConsoleDiscoveryFailedError from exc

        selected_property = next(
            (
                item
                for item in accessible_properties
                if item.external_property_id == external_property_id
                and item.property_type == property_type
            ),
            None,
        )
        if selected_property is None:
            raise SEOSearchPropertyNotFoundError

        if _property_host(selected_property.external_property_id) != _canonical_host(
            website.canonical_origin
        ):
            raise SEOSearchPropertyNotFoundError

        # Search Console has now supplied provider evidence that this Google
        # account can access the canonical website property.
        if website.status == "pending_verification":
            website.status = "active"
            website.ownership_status = "verified"
            website.verified_at = website.verified_at or datetime.now(UTC)

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
        scope: TransactionScope,
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
        pulls these observation types:

        - site_summary: no dimensions (authoritative site-level totals)
        - daily: date dimension (for trend series)
        - top_queries: query dimension (top search queries)
        - top_pages: page dimension (top landing pages)
        - page_query: page and query dimensions

        Rows are upserted idempotently on the
        (search_property, date_start, date_end, dimension_hash) uniqueness key.

        Three phases, so no database transaction is ever open while Google is
        being called: (1) a short read transaction, (2) every provider request --
        token refresh included -- with no transaction open, fetched into memory,
        (3) one short transaction that persists everything. Because nothing is
        written until every request has returned, a failed request leaves the
        previous successful dataset untouched, which is what the old per-request
        savepoint guaranteed.
        """
        # -- phase 1: read -------------------------------------------------------
        async with scope.begin() as session:
            property_row = await self.load_property(session, organization_id, search_property_id)
            website = await self._get_website(session, organization_id, property_row.website_id)
            resolver = await PageResolver.load(session, organization_id, website.id)
            connection = await self._connection(session, organization_id)
            if not connection_has_scope(connection, SEARCH_CONSOLE_SCOPE):
                raise SEOSearchConsoleScopeRequiredError
            plan = await self.connection.begin_token_refresh(session, settings, connection)
            external_id = property_row.external_property_id
            connection_id = connection.id

        # -- phase 2: provider HTTP, nothing open --------------------------------
        if plan.access_token is not None:
            token = plan.access_token
        else:
            assert plan.refresh_token is not None
            try:
                payload = await self.connection.refresh_token_pair(settings, plan.refresh_token)
            except IntegrationTokenExchangeFailedError:
                # Committed on its own so the status survives the error unwinding us.
                async with scope.begin() as session:
                    stale = await session.get(IntegrationConnection, connection_id)
                    if stale is not None:
                        await self.connection.fail_token_refresh(session, stale)
                raise IntegrationReconnectRequiredError from None
            async with scope.begin() as session:
                refreshed = await session.get(IntegrationConnection, connection_id)
                if refreshed is None:
                    raise SEOSearchPropertyNotConfiguredError
                token = await self.connection.complete_token_refresh(
                    session, settings, refreshed, plan, payload
                )

        now = datetime.now(UTC)
        windows = {
            period_days: reporting_window(now, period_days, GSC_SYNC_TAIL_EXCLUSION_DAYS)
            for period_days in VALID_REPORTING_PERIODS
        }
        fetched = {
            period_days: await self._fetch_period(token, external_id, start, end, period_days)
            for period_days, (start, end) in windows.items()
        }

        # -- phase 3: persist ----------------------------------------------------
        upserted = 0
        failed = False
        failures: list[dict[str, object]] = []
        async with scope.begin() as session:
            property_row = await self.load_property(session, organization_id, search_property_id)
            for period_days in VALID_REPORTING_PERIODS:
                start, window_end = windows[period_days]
                if await self._period_failed(fetched[period_days], period_days, failures):
                    failed = True
            if failed:
                # Nothing was written: the previous successful dataset is preserved.
                property_row.freshness_status = (
                    "never_synced" if property_row.last_synced_at is None else "stale"
                )
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
                return {
                    "search_property_id": str(property_row.id),
                    "rows_synced": 0,
                    "window_days": days,
                    "periods_synced": [],
                    "freshness_status": property_row.freshness_status,
                }

            for period_days in VALID_REPORTING_PERIODS:
                start, window_end = windows[period_days]
                upserted += await self._sync_period(
                    session,
                    organization_id,
                    property_row,
                    resolver,
                    start,
                    window_end,
                    period_days,
                    fetched[period_days],
                )
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
            return {
                "search_property_id": str(property_row.id),
                "rows_synced": upserted,
                "window_days": days,
                "periods_synced": list(VALID_REPORTING_PERIODS),
                "freshness_status": property_row.freshness_status,
            }

    async def load_property(
        self, session: AsyncSession, organization_id: UUID, search_property_id: UUID
    ) -> SEOSearchProperty:
        property_row = await session.scalar(
            select(SEOSearchProperty).where(
                SEOSearchProperty.organization_id == organization_id,
                SEOSearchProperty.id == search_property_id,
            )
        )
        if property_row is None or property_row.provider != "google_search_console":
            raise SEOSearchPropertyNotFoundError
        return property_row

    async def _query(
        self,
        token: str,
        external_id: str,
        *,
        start: datetime,
        end: datetime,
        dimensions: tuple[str, ...],
        row_limit: int,
    ) -> list[SearchAnalyticsRow] | Exception:
        try:
            return await self.adapter.query_search_analytics(
                token,
                external_id,
                start_date=provider_start_date(start),
                end_date=provider_end_date(end),
                dimensions=dimensions,
                row_limit=row_limit,
            )
        except Exception as exc:
            return exc

    async def _fetch_period(
        self,
        token: str,
        external_id: str,
        start: datetime,
        window_end: datetime,
        period_days: int,
    ) -> PeriodFetch:
        """Fetch one period's responses into memory. Touches no database."""
        comp_start, comp_end = comparison_window(start, period_days)
        summary = await self._query(
            token, external_id, start=start, end=window_end, dimensions=(), row_limit=1000
        )
        if isinstance(summary, Exception):
            # The period cannot be used without its site summary; skip its other
            # requests exactly as the interleaved version did.
            return PeriodFetch(summary, [], [], [], [], [])
        return PeriodFetch(
            site_summary=summary,
            prior_summary=await self._query(
                token, external_id, start=comp_start, end=comp_end, dimensions=(), row_limit=1000
            ),
            daily=await self._query(
                token,
                external_id,
                start=start,
                end=window_end,
                dimensions=("date",),
                row_limit=25000,
            ),
            top_queries=await self._query(
                token,
                external_id,
                start=start,
                end=window_end,
                dimensions=("query",),
                row_limit=1000,
            ),
            top_pages=await self._query(
                token,
                external_id,
                start=start,
                end=window_end,
                dimensions=("page",),
                row_limit=1000,
            ),
            page_query=await self._query(
                token,
                external_id,
                start=start,
                end=window_end,
                dimensions=("page", "query"),
                row_limit=25000,
            ),
        )

    @staticmethod
    async def _period_failed(
        fetched: PeriodFetch, period_days: int, failures: list[dict[str, object]]
    ) -> bool:
        """Record every failed request for the audit row; True if any required one failed."""
        failed = False
        for request, result in (
            ("site_summary", fetched.site_summary),
            ("prior_site_summary", fetched.prior_summary),
            ("daily", fetched.daily),
            ("top_queries", fetched.top_queries),
            ("top_pages", fetched.top_pages),
            ("page_query", fetched.page_query),
        ):
            if isinstance(result, Exception):
                failed = True
                failures.append(
                    {"request": request, "period_days": period_days, "error": str(result)[:200]}
                )
        return failed

    async def _sync_period(
        self,
        session: AsyncSession,
        organization_id: UUID,
        property_row: SEOSearchProperty,
        resolver: PageResolver,
        start: datetime,
        window_end: datetime,
        period_days: int,
        fetched: PeriodFetch,
    ) -> int:
        """Persist one period's already-fetched aggregates and dimensions.

        Only called when every required request succeeded (see
        ``_period_failed``), and it makes no provider request of its own.
        """
        upserted = 0
        comp_start, comp_end = comparison_window(start, period_days)
        assert not isinstance(fetched.site_summary, Exception)
        assert not isinstance(fetched.prior_summary, Exception)
        assert not isinstance(fetched.daily, Exception)
        assert not isinstance(fetched.top_queries, Exception)
        assert not isinstance(fetched.top_pages, Exception)
        assert not isinstance(fetched.page_query, Exception)
        summary_rows = fetched.site_summary
        prior_summary_rows = fetched.prior_summary
        daily_rows = fetched.daily
        query_rows = fetched.top_queries
        page_rows = fetched.top_pages
        page_query_rows = fetched.page_query

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

        if not summary_rows:
            await self._store_site_summary(
                session,
                property_row,
                organization_id,
                date_start=start,
                date_end=window_end,
                row=None,
            )
            upserted += 1

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

        if not prior_summary_rows:
            await self._store_site_summary(
                session,
                property_row,
                organization_id,
                date_start=comp_start,
                date_end=comp_end,
                row=None,
            )
            upserted += 1

        from datetime import date as date_type

        for row in daily_rows:
            date_val = row.keys[0] if row.keys else ""
            if not date_val:
                continue
            day_dims: dict[str, object] = {
                "observation_type": "daily",
                "date": date_val,
                "website_id": str(property_row.website_id),
            }
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
                existing.website_id = property_row.website_id
                existing.mapping_state = None
                existing.mapping_basis = None
                existing.mapping_limitation = None
                existing.resolver_version = None
            else:
                session.add(
                    SEOSearchObservation(
                        organization_id=organization_id,
                        search_property_id=property_row.id,
                        website_id=property_row.website_id,
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

        for row in query_rows:
            q = row.keys[0] if row.keys else ""
            query_dims: dict[str, object] = {
                "observation_type": "top_query",
                "query": q,
                "website_id": str(property_row.website_id),
            }
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
                existing.website_id = property_row.website_id
                existing.mapping_state = "unknown"
                existing.mapping_limitation = (
                    "Query-only evidence does not identify a landing page."
                )
                existing.resolver_version = RESOLVER_VERSION
            else:
                session.add(
                    SEOSearchObservation(
                        organization_id=organization_id,
                        search_property_id=property_row.id,
                        website_id=property_row.website_id,
                        mapping_state="unknown",
                        mapping_limitation="Query-only evidence does not identify a landing page.",
                        resolver_version=RESOLVER_VERSION,
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

        upserted += await self._store_page_rows(
            session,
            organization_id,
            property_row,
            resolver,
            start,
            window_end,
            page_rows,
            "top_page",
        )

        upserted += await self._store_page_rows(
            session,
            organization_id,
            property_row,
            resolver,
            start,
            window_end,
            page_query_rows,
            "page_query",
        )

        await session.flush()
        return upserted

    async def _store_page_rows(
        self,
        session: AsyncSession,
        organization_id: UUID,
        property_row: SEOSearchProperty,
        resolver: PageResolver,
        start: datetime,
        end: datetime,
        rows: list[SearchAnalyticsRow],
        observation_type: str,
    ) -> int:
        values_by_hash: dict[str, dict[str, object]] = {}
        for row in rows:
            raw_page = row.keys[0] if row.keys else ""
            query = row.keys[1] if observation_type == "page_query" and len(row.keys) > 1 else None
            dimensions: dict[str, object] = {
                "observation_type": observation_type,
                "page": raw_page,
                "website_id": str(property_row.website_id),
            }
            if query is not None:
                dimensions["query"] = query
            resolution = resolver.resolve(raw_page)
            dimension_hash = _dimension_hash(dimensions)
            values_by_hash[dimension_hash] = {
                "organization_id": organization_id,
                "search_property_id": property_row.id,
                "website_id": property_row.website_id,
                "page_id": resolution.page_id,
                "query": query,
                "date_start": start,
                "date_end": end,
                "dimensions": dimensions,
                "dimension_hash": dimension_hash,
                "mapping_state": resolution.state,
                "mapping_basis": resolution.basis,
                "mapping_limitation": resolution.limitation,
                "resolver_version": resolution.resolver_version,
                "clicks": row.clicks,
                "impressions": row.impressions,
                "ctr": row.ctr,
                "position": row.position,
                "quality_status": "valid",
                "partial": False,
            }
        values = list(values_by_hash.values())
        for offset in range(0, len(values), PAGE_OBSERVATION_CHUNK_SIZE):
            statement = pg_insert(SEOSearchObservation).values(
                values[offset : offset + PAGE_OBSERVATION_CHUNK_SIZE]
            )
            statement = statement.on_conflict_do_update(
                constraint="uq_seo_search_observation",
                set_={
                    key: getattr(statement.excluded, key)
                    for key in (
                        "website_id",
                        "page_id",
                        "query",
                        "dimensions",
                        "mapping_state",
                        "mapping_basis",
                        "mapping_limitation",
                        "resolver_version",
                        "clicks",
                        "impressions",
                        "ctr",
                        "position",
                        "quality_status",
                        "partial",
                    )
                },
            )
            await session.execute(statement)
        return len(rows)

    async def _store_site_summary(
        self,
        session: AsyncSession,
        property_row: SEOSearchProperty,
        organization_id: UUID,
        *,
        date_start: datetime,
        date_end: datetime,
        row: SearchAnalyticsRow | None = None,
    ) -> None:
        """Upsert one authoritative site_summary observation for the window.

        When *row* is None the caller is establishing an authoritative
        zero-data observation (provider call succeeded but returned no rows).
        """
        dims: dict[str, object] = {
            "observation_type": "site_summary",
            "website_id": str(property_row.website_id),
        }
        dim_hash = _dimension_hash(dims)
        existing = await session.scalar(
            select(SEOSearchObservation).where(
                SEOSearchObservation.search_property_id == property_row.id,
                SEOSearchObservation.date_start == date_start,
                SEOSearchObservation.date_end == date_end,
                SEOSearchObservation.dimension_hash == dim_hash,
            )
        )
        if row is None:
            quality = "zero"
            clicks: int = 0
            impressions: int = 0
            ctr = None
            position = None
        else:
            quality = "valid"
            clicks = row.clicks
            impressions = row.impressions
            ctr = row.ctr
            position = row.position
        if existing is not None:
            existing.clicks = clicks
            existing.impressions = impressions
            existing.ctr = ctr
            existing.position = position
            existing.query = None
            existing.dimensions = dims
            existing.quality_status = quality
            existing.partial = False
            existing.website_id = property_row.website_id
            existing.mapping_state = None
            existing.mapping_basis = None
            existing.mapping_limitation = None
            existing.resolver_version = None
        else:
            session.add(
                SEOSearchObservation(
                    organization_id=organization_id,
                    search_property_id=property_row.id,
                    website_id=property_row.website_id,
                    page_id=None,
                    query=None,
                    date_start=date_start,
                    date_end=date_end,
                    dimensions=dims,
                    dimension_hash=dim_hash,
                    clicks=clicks,
                    impressions=impressions,
                    ctr=ctr,
                    position=position,
                    quality_status=quality,
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
        self, session: AsyncSession, prop_ids: list[UUID], days: int, website_id: UUID
    ) -> tuple[datetime, datetime] | None:
        """Return the latest authoritative current site_summary window for `days`.

        The newest exact-duration site_summary is the current report window;
        its prior comparison has the same duration but an earlier ``date_end``.
        """
        current = await session.scalar(
            select(SEOSearchObservation)
            .where(
                SEOSearchObservation.search_property_id.in_(prop_ids),
                or_(
                    SEOSearchObservation.website_id == website_id,
                    SEOSearchObservation.website_id.is_(None),
                ),
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
        window = await self._latest_site_summary_current_window(session, prop_ids, days, website_id)

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
            session, prop_ids, current_start, current_end, "site_summary", website_id
        )
        comp_summary = await self._get_observation_by_type(
            session, prop_ids, comp_start, comp_end, "site_summary", website_id
        )

        metrics = {}
        for metric_key in ("clicks", "impressions", "ctr", "position"):
            curr_val = getattr(current_summary, metric_key, None) if current_summary else None
            prev_val = getattr(comp_summary, metric_key, None) if comp_summary else None
            absolute_delta = None
            percent_delta = None
            if curr_val is not None and prev_val is not None:
                curr_number = float(curr_val)
                prev_number = float(prev_val)
                absolute_delta = curr_number - prev_number
                if prev_number != 0:
                    percent_delta = absolute_delta / abs(prev_number) * 100

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
            session, prop_ids, current_start, current_end, "daily", website_id
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
            session,
            prop_ids,
            current_start,
            current_end,
            "top_query",
            website_id,
            exact_window=True,
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
            session, prop_ids, current_start, current_end, "top_page", website_id, exact_window=True
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
                if o.website_id in (None, website_id)
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
        website_id: UUID,
    ) -> SEOSearchObservation | None:
        """Get the authoritative observation of a given type for the exact period.

        Resolves against the single authoritative property (``prop_ids`` always
        contains exactly one id), so summary/daily/query/page reads share one
        source and never mix properties. CTR/position are never aggregated.
        """
        rows = list(
            await session.scalars(
                select(SEOSearchObservation)
                .where(
                    SEOSearchObservation.search_property_id.in_(prop_ids),
                    or_(
                        SEOSearchObservation.website_id == website_id,
                        SEOSearchObservation.website_id.is_(None),
                    ),
                    SEOSearchObservation.date_start == period_start,
                    SEOSearchObservation.date_end == period_end,
                    SEOSearchObservation.dimensions["observation_type"].astext == observation_type,
                    SEOSearchObservation.quality_status.in_(["valid", "zero"]),
                )
                .order_by(SEOSearchObservation.date_end.desc())
            )
        )
        return next((row for row in rows if row.website_id == website_id), None) or (
            rows[0] if rows else None
        )

    async def _get_typed_observations(
        self,
        session: AsyncSession,
        prop_ids: list[UUID],
        period_start: datetime,
        period_end: datetime,
        observation_type: str,
        website_id: UUID,
        *,
        exact_window: bool = False,
    ) -> list[SEOSearchObservation]:
        """Get all observations of a given type for the period.

        Containment mode (``exact_window=False``, the default) returns rows
        whose boundaries fall inside the period — correct for daily rows whose
        individual date_start/date_end are single days.

        Exact-window mode (``exact_window=True``) requires date_start and
        date_end to equal the requested period boundaries — correct for
        full-window dimensional observations (top_query, top_page) whose
        boundaries describe the entire reporting window and must not leak
        from shorter nested windows.
        """
        where_clauses = [
            SEOSearchObservation.search_property_id.in_(prop_ids),
            or_(
                SEOSearchObservation.website_id == website_id,
                SEOSearchObservation.website_id.is_(None),
            ),
            SEOSearchObservation.dimensions["observation_type"].astext == observation_type,
            SEOSearchObservation.quality_status.in_(["valid", "zero"]),
        ]
        if exact_window:
            where_clauses.append(SEOSearchObservation.date_start == period_start)
            where_clauses.append(SEOSearchObservation.date_end == period_end)
        else:
            where_clauses.append(SEOSearchObservation.date_start >= period_start)
            where_clauses.append(SEOSearchObservation.date_end <= period_end)
        rows = list(
            await session.scalars(
                select(SEOSearchObservation)
                .where(*where_clauses)
                .order_by(SEOSearchObservation.date_start.asc())
            )
        )
        pinned = [row for row in rows if row.website_id == website_id]
        return pinned if pinned else rows

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
