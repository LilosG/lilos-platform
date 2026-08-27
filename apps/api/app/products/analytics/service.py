"""GA4 Analytics discovery, property mapping, and metric sync.

The real operator workflow for the Insights product's GA4 integration, driven
by the shared Google ``IntegrationConnection``:

    authorize Analytics scope
      -> discover accessible GA4 accounts/properties (Admin accountSummaries)
      -> recommend/match a property where reasonable
      -> operator selects a property
      -> idempotent AnalyticsProperty mapping is persisted
      -> real GA4 metrics (sessions/users/pageviews/conversions) sync into
         MetricObservation through a versioned MetricDefinition catalog
      -> Insights consumes them; Insights stays usable when GA4 is disconnected

No fabricated metrics: only the real GA4 Data API metrics the Insights model
already defines are stored.
"""

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.insights.models import (
    InsightSource,
    MetricDefinition,
    MetricObservation,
)
from apps.api.app.integrations.connection_service import (
    ANALYTICS_SCOPE,
    GBPConnectionService,
    connection_has_scope,
)
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.analytics.adapter import (
    GA4_METRICS,
    AnalyticsReportRow,
    DiscoveredAnalyticsProperty,
    GoogleAnalyticsAdapter,
    GoogleAnalyticsAdminAdapter,
)
from apps.api.app.products.analytics.errors import (
    AnalyticsDiscoveryFailedError,
    AnalyticsNotConfiguredError,
    AnalyticsPropertyNotFoundError,
    AnalyticsScopeRequiredError,
)
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.models import SEOWebsite
from apps.api.app.reporting_periods import (
    GA4_SYNC_TAIL_EXCLUSION_DAYS,
    VALID_REPORTING_PERIODS,
    comparison_window,
    format_range_label,
    provider_end_date,
    provider_start_date,
    reporting_window,
)

ANALYTICS_PROVIDER_KEY = "google_analytics"
DEFAULT_SYNC_WINDOW_DAYS = 28
DEFAULT_FRESHNESS_STALE_SECONDS = 172_800  # 48 hours

# Versioned metric-definition catalog for the modeled GA4 metrics. These are
# global (not org-scoped) and upserted idempotently on first sync.
GA4_METRIC_DEFINITIONS: tuple[dict[str, object], ...] = (
    {
        "key": "ga4.sessions",
        "name": "GA4 Sessions",
        "description": "Total sessions from Google Analytics 4.",
        "unit": "count",
        "data_type": "integer",
    },
    {
        "key": "ga4.totalUsers",
        "name": "GA4 Users",
        "description": "Total users from Google Analytics 4.",
        "unit": "count",
        "data_type": "integer",
    },
    {
        "key": "ga4.screenPageViews",
        "name": "GA4 Pageviews",
        "description": "Total screen page views from Google Analytics 4.",
        "unit": "count",
        "data_type": "integer",
    },
    {
        "key": "ga4.conversions",
        "name": "GA4 Conversions",
        "description": "Total conversions from Google Analytics 4.",
        "unit": "count",
        "data_type": "integer",
    },
)
METRIC_DEFINITION_VERSION = 1


@dataclass(frozen=True, slots=True)
class AnalyticsRecommendation:
    properties: tuple[DiscoveredAnalyticsProperty, ...]
    recommended: DiscoveredAnalyticsProperty | None


def _canonical_host(origin: str | None) -> str:
    if not origin:
        return ""
    return (urlsplit(origin).hostname or "").lower().removeprefix("www.")


def _registrable_label(host: str) -> str:
    """Return the first DNS label of a host (e.g. 'wheylandelectric' from
    'wheylandelectric.com') for fuzzy display-name matching."""
    return host.split(".", 1)[0] if host else ""


def recommend_property(
    properties: Sequence[DiscoveredAnalyticsProperty], website: SEOWebsite | None
) -> DiscoveredAnalyticsProperty | None:
    """Recommend a GA4 property by matching the website's canonical domain.

    GA4 property display names are free-form, so matching is best-effort: a
    property whose display name (whitespace-collapsed) contains the website's
    registrable label (e.g. 'wheylandelectric') is recommended. Returns
    ``None`` when nothing matches, forcing explicit operator choice rather
    than a guess.
    """
    if website is None:
        return None
    label = _registrable_label(_canonical_host(website.canonical_origin))
    if not label:
        return None
    for prop in properties:
        compact = prop.display_name.lower().replace(" ", "").replace("-", "")
        if label in compact:
            return prop
    return None


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def normalize_observation_date(value: object) -> str:
    """Return a GA4 date dimension as ISO `YYYY-MM-DD`.

    The Analytics Data API returns its `date` dimension in basic format,
    `YYYYMMDD`. Python's date.fromisoformat accepts that, so ingestion never
    complained, and the raw value was stored and served straight through to the
    reporting series. `new Date("20260813T00:00:00Z")` is invalid in JavaScript, so
    every GA4 chart axis label rendered "Invalid Date" while Search Console -- which
    returns extended format -- rendered correctly.

    Anything already ISO, or unrecognised, is returned unchanged so a bad value
    surfaces as itself rather than as a wrong date.
    """
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _dimension_hash(dimensions: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(dimensions, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(slots=True)
class AnalyticsService:
    """Discover, map, and sync GA4 properties and metric observations."""

    adapter: GoogleAnalyticsAdapter = field(default_factory=GoogleAnalyticsAdminAdapter)
    connection: GBPConnectionService = field(default_factory=GBPConnectionService)
    audit: AuditEventService = field(default_factory=AuditEventService)
    http_client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient

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
                product_key="insights",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    async def _connection(
        self, session: AsyncSession, organization_id: UUID
    ) -> IntegrationConnection:
        connection = await self.connection.find_connection(session, organization_id)
        if connection is None or connection.status == "disconnected":
            raise AnalyticsNotConfiguredError
        return connection

    async def _fresh_token(
        self, session: AsyncSession, settings: Settings, organization_id: UUID
    ) -> tuple[str, IntegrationConnection]:
        connection = await self._connection(session, organization_id)
        if not connection_has_scope(connection, ANALYTICS_SCOPE):
            raise AnalyticsScopeRequiredError
        token = await self.connection.ensure_fresh_token(session, settings, connection)
        return token, connection

    # -- discovery -----------------------------------------------------------

    async def discover_properties(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        website_id: UUID | None,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> AnalyticsRecommendation:
        website = await self._optional_website(session, organization_id, website_id)
        token, connection = await self._fresh_token(session, settings, organization_id)
        try:
            properties = await self.adapter.list_account_summaries(token)
        except Exception as exc:
            await self._audit(
                session,
                event="insights.analytics.discovery_failed",
                organization_id=organization_id,
                actor_id=actor_id,
                resource_type="integration_connection",
                resource_id=connection.id,
                correlation_id=correlation_id,
                summary="GA4 property discovery failed.",
                metadata={"error": str(exc)[:200]},
                result=AuditResult.FAILED,
            )
            raise AnalyticsDiscoveryFailedError from exc
        recommended = recommend_property(properties, website)
        await self._audit(
            session,
            event="insights.analytics.discovered",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary=f"Discovered {len(properties)} GA4 properties.",
            metadata={"count": len(properties), "recommended": recommended is not None},
        )
        return AnalyticsRecommendation(properties=tuple(properties), recommended=recommended)

    # -- idempotent mapping --------------------------------------------------

    async def map_property(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        external_property_id: str,
        property_number: str,
        display_name: str,
        website_id: UUID | None,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> AnalyticsProperty:
        token, connection = await self._fresh_token(session, settings, organization_id)
        del token
        existing = await session.scalar(
            select(AnalyticsProperty).where(
                AnalyticsProperty.organization_id == organization_id,
                AnalyticsProperty.provider == ANALYTICS_PROVIDER_KEY,
                AnalyticsProperty.external_property_id == external_property_id,
            )
        )
        if existing is not None:
            existing.connection_id = connection.id
            existing.website_id = website_id
            existing.property_number = property_number
            existing.display_name = display_name
            existing.mapping_status = "mapped"
            await session.flush()
            item = existing
            event = "insights.analytics.remapped"
        else:
            item = AnalyticsProperty(
                organization_id=organization_id,
                connection_id=connection.id,
                website_id=website_id,
                provider=ANALYTICS_PROVIDER_KEY,
                external_property_id=external_property_id,
                property_number=property_number,
                display_name=display_name,
                mapping_status="mapped",
                freshness_status="never_synced",
            )
            session.add(item)
            await session.flush()
            event = "insights.analytics.mapped"
        await self._audit(
            session,
            event=event,
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="analytics_property",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary="GA4 property mapped.",
            metadata={"external_property_id": external_property_id, "display_name": display_name},
        )
        return item

    # -- sync ----------------------------------------------------------------

    async def _ensure_metric_definitions(
        self, session: AsyncSession
    ) -> dict[str, MetricDefinition]:
        """Idempotently upsert the GA4 metric definitions; return key->definition."""
        by_key: dict[str, MetricDefinition] = {}
        for definition in GA4_METRIC_DEFINITIONS:
            key = str(definition["key"])
            existing = await session.scalar(
                select(MetricDefinition).where(
                    MetricDefinition.key == key,
                    MetricDefinition.version == METRIC_DEFINITION_VERSION,
                )
            )
            if existing is not None:
                by_key[key] = existing
                continue
            row = MetricDefinition(
                key=key,
                version=METRIC_DEFINITION_VERSION,
                name=str(definition["name"]),
                description=str(definition["description"]),
                source_product="insights",
                unit=str(definition["unit"]),
                data_type=str(definition["data_type"]),
                aggregation_behavior="sum",
                supported_dimensions=[],
                required_filters=[],
                freshness_seconds=86_400,
                partial_period_behavior="mark_partial",
                missing_data_behavior="mark_missing",
                status="active",
            )
            session.add(row)
            await session.flush()
            by_key[key] = row
        return by_key

    async def _get_cached_definitions(self, session: AsyncSession) -> dict[str, MetricDefinition]:
        """Return existing metric definitions without provisioning writes."""
        by_key: dict[str, MetricDefinition] = {}
        for definition in GA4_METRIC_DEFINITIONS:
            key = str(definition["key"])
            existing = await session.scalar(
                select(MetricDefinition).where(
                    MetricDefinition.key == key,
                    MetricDefinition.version == METRIC_DEFINITION_VERSION,
                )
            )
            if existing is not None:
                by_key[key] = existing
        return by_key

    async def _insight_source(
        self, session: AsyncSession, organization_id: UUID, prop: AnalyticsProperty
    ) -> InsightSource:
        source = await session.scalar(
            select(InsightSource).where(
                InsightSource.organization_id == organization_id,
                InsightSource.key == prop.external_property_id,
            )
        )
        if source is not None:
            return source
        source = InsightSource(
            organization_id=organization_id,
            key=prop.external_property_id,
            source_type="analytics_property",
            product_key="insights",
            provider=ANALYTICS_PROVIDER_KEY,
            status="active",
            authority_scope="organization",
        )
        session.add(source)
        await session.flush()
        return source

    async def sync_metrics(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        analytics_property_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        days: int = DEFAULT_SYNC_WINDOW_DAYS,
    ) -> dict[str, object]:
        prop = await session.scalar(
            select(AnalyticsProperty).where(
                AnalyticsProperty.organization_id == organization_id,
                AnalyticsProperty.id == analytics_property_id,
            )
        )
        if prop is None:
            raise AnalyticsPropertyNotFoundError
        token, connection = await self._fresh_token(session, settings, organization_id)
        del connection
        now = datetime.now(UTC)
        definitions = await self._ensure_metric_definitions(session)
        source = await self._insight_source(session, organization_id, prop)
        upserted = 0
        failed = False
        failures: list[dict[str, object]] = []

        # Persist the 7/28/90 contract atomically: a partial attempt must never
        # publish a newer incomplete current window. On any required failure the
        # savepoint is rolled back and the previous successful dataset remains.
        nested = session.begin_nested()
        await nested.start()
        try:
            for period_days in VALID_REPORTING_PERIODS:
                start, end = reporting_window(now, period_days, GA4_SYNC_TAIL_EXCLUSION_DAYS)
                comp_start, comp_end = comparison_window(start, period_days)
                try:
                    aggregate_rows = await self.adapter.run_report(
                        token,
                        prop.property_number,
                        start_date=provider_start_date(start),
                        end_date=provider_end_date(end),
                        metrics=GA4_METRICS,
                    )
                    prior_aggregate_rows = await self.adapter.run_report(
                        token,
                        prop.property_number,
                        start_date=provider_start_date(comp_start),
                        end_date=provider_end_date(comp_end),
                        metrics=GA4_METRICS,
                    )
                    daily_rows = await self.adapter.run_report(
                        token,
                        prop.property_number,
                        start_date=provider_start_date(start),
                        end_date=provider_end_date(end),
                        metrics=GA4_METRICS,
                        dimensions=("date",),
                    )
                except Exception as exc:
                    failed = True
                    failures.append({"period_days": period_days, "error": str(exc)[:200]})
                    continue

                upserted += await self._sync_aggregate(
                    session,
                    organization_id,
                    source,
                    definitions,
                    prop,
                    aggregate_rows,
                    start,
                    end,
                    period_days,
                )
                upserted += await self._sync_aggregate(
                    session,
                    organization_id,
                    source,
                    definitions,
                    prop,
                    prior_aggregate_rows,
                    comp_start,
                    comp_end,
                    period_days,
                )

                from datetime import date as date_type

                for row in daily_rows:
                    observation_date = normalize_observation_date(
                        row.dimension_values.get("date", "")
                    )
                    if not observation_date:
                        continue
                    day_dims: dict[str, object] = {
                        "observation_type": "daily",
                        "date": observation_date,
                    }
                    day_dim_hash = _dimension_hash(day_dims)
                    day_dt = date_type.fromisoformat(observation_date)
                    day_start = datetime(day_dt.year, day_dt.month, day_dt.day, tzinfo=UTC)
                    day_end = day_start + timedelta(days=1)
                    for key in GA4_METRICS:
                        definition = definitions[f"ga4.{key}"]
                        value = row.metric_values.get(key, 0)
                        existing = await session.scalar(
                            select(MetricObservation).where(
                                MetricObservation.organization_id == organization_id,
                                MetricObservation.source_id == source.id,
                                MetricObservation.metric_definition_id == definition.id,
                                MetricObservation.period_start == day_start,
                                MetricObservation.period_end == day_end,
                                MetricObservation.dimension_hash == day_dim_hash,
                            )
                        )
                        if existing is not None:
                            existing.value = Decimal(value)
                            existing.quality_state = "valid" if value else "zero"
                            existing.provenance = {
                                "provider": ANALYTICS_PROVIDER_KEY,
                                "property": prop.external_property_id,
                                "window_days": period_days,
                                "observation_type": "daily",
                                "observation_date": observation_date,
                            }
                        else:
                            session.add(
                                MetricObservation(
                                    organization_id=organization_id,
                                    location_id=None,
                                    source_id=source.id,
                                    metric_definition_id=definition.id,
                                    period_start=day_start,
                                    period_end=day_end,
                                    dimensions=day_dims,
                                    dimension_hash=day_dim_hash,
                                    value=Decimal(value),
                                    quality_state="valid" if value else "zero",
                                    completeness=Decimal("1.0"),
                                    provenance={
                                        "provider": ANALYTICS_PROVIDER_KEY,
                                        "property": prop.external_property_id,
                                        "window_days": period_days,
                                        "observation_type": "daily",
                                        "observation_date": observation_date,
                                    },
                                )
                            )
                        upserted += 1
                await session.flush()
        except BaseException:
            await nested.rollback()
            raise

        if failed:
            await nested.rollback()
            if prop.last_synced_at is None:
                prop.freshness_status = "never_synced"
            else:
                prop.freshness_status = "stale"
            await session.flush()
            await self._audit(
                session,
                event="insights.analytics.sync_incomplete",
                organization_id=organization_id,
                actor_id=actor_id,
                resource_type="analytics_property",
                resource_id=prop.id,
                correlation_id=correlation_id,
                summary="GA4 sync incomplete: one or more required periods failed; "
                "previous successful dataset preserved.",
                metadata={"failures": failures},
                result=AuditResult.FAILED,
            )
            return {
                "analytics_property_id": str(prop.id),
                "metrics_synced": 0,
                "window_days": days,
                "periods_synced": [],
                "freshness_status": prop.freshness_status,
            }

        await nested.commit()
        prop.last_synced_at = now
        prop.freshness_status = "fresh"
        source.last_synced_at = prop.last_synced_at
        await session.flush()
        await self._audit(
            session,
            event="insights.analytics.synced",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="analytics_property",
            resource_id=prop.id,
            correlation_id=correlation_id,
            summary=f"Synced {upserted} GA4 metric observations across "
            f"{len(VALID_REPORTING_PERIODS)} periods.",
            metadata={
                "observations": upserted,
                "periods_synced": list(VALID_REPORTING_PERIODS),
            },
        )
        return {
            "analytics_property_id": str(prop.id),
            "metrics_synced": upserted,
            "window_days": days,
            "periods_synced": list(VALID_REPORTING_PERIODS),
            "freshness_status": prop.freshness_status,
        }

    async def _sync_aggregate(
        self,
        session: AsyncSession,
        organization_id: UUID,
        source: InsightSource,
        definitions: dict[str, MetricDefinition],
        prop: AnalyticsProperty,
        aggregate_rows: list[AnalyticsReportRow],
        start: datetime,
        end: datetime,
        period_days: int,
    ) -> int:
        """Upsert authoritative aggregate observations for one exact window.

        ``totalUsers`` and every other metric come from aggregate provider rows
        (dimensionless), never summed from daily rows. Returns rows upserted.
        """
        agg_dims: dict[str, object] = {"observation_type": "aggregate"}
        agg_dim_hash = _dimension_hash(agg_dims)
        metric_totals: dict[str, int] = {key: 0 for key in GA4_METRICS}
        for row in aggregate_rows:
            for key in GA4_METRICS:
                metric_totals[key] += row.metric_values.get(key, 0)

        upserted = 0
        for key in GA4_METRICS:
            definition = definitions[f"ga4.{key}"]
            value = metric_totals.get(key, 0)
            existing = await session.scalar(
                select(MetricObservation).where(
                    MetricObservation.organization_id == organization_id,
                    MetricObservation.source_id == source.id,
                    MetricObservation.metric_definition_id == definition.id,
                    MetricObservation.period_start == start,
                    MetricObservation.period_end == end,
                    MetricObservation.dimension_hash == agg_dim_hash,
                )
            )
            if existing is not None:
                existing.value = Decimal(value)
                existing.quality_state = "valid" if value else "zero"
                existing.provenance = {
                    "provider": ANALYTICS_PROVIDER_KEY,
                    "property": prop.external_property_id,
                    "window_days": period_days,
                    "observation_type": "aggregate",
                }
            else:
                session.add(
                    MetricObservation(
                        organization_id=organization_id,
                        location_id=None,
                        source_id=source.id,
                        metric_definition_id=definition.id,
                        period_start=start,
                        period_end=end,
                        dimensions=agg_dims,
                        dimension_hash=agg_dim_hash,
                        value=Decimal(value),
                        quality_state="valid" if value else "zero",
                        completeness=Decimal("1.0"),
                        provenance={
                            "provider": ANALYTICS_PROVIDER_KEY,
                            "property": prop.external_property_id,
                            "window_days": period_days,
                            "observation_type": "aggregate",
                        },
                    )
                )
            upserted += 1
        return upserted

    # -- read helpers --------------------------------------------------------

    async def _optional_website(
        self, session: AsyncSession, organization_id: UUID, website_id: UUID | None
    ) -> SEOWebsite | None:
        if website_id is None:
            return None
        website = await session.scalar(
            select(SEOWebsite).where(
                SEOWebsite.organization_id == organization_id, SEOWebsite.id == website_id
            )
        )
        return website

    async def performance_report(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        days: int = DEFAULT_SYNC_WINDOW_DAYS,
        location_id: UUID | None = None,
    ) -> dict[str, object]:
        """Return a reporting-safe GA4 performance contract.

        Uses the canonical reporting-window math (exact day counts, no overlap)
        and queries cached metric definitions (no write side effects).
        Freshness uses a fixed SLA threshold independent of report range.
        """
        statement = select(AnalyticsProperty).where(
            AnalyticsProperty.organization_id == organization_id,
            AnalyticsProperty.provider == ANALYTICS_PROVIDER_KEY,
            AnalyticsProperty.mapping_status == "mapped",
        )
        if location_id is not None:
            statement = statement.join(
                SEOWebsite,
                (SEOWebsite.organization_id == AnalyticsProperty.organization_id)
                & (SEOWebsite.id == AnalyticsProperty.website_id),
            ).where(or_(SEOWebsite.location_id == location_id, SEOWebsite.location_id.is_(None)))
        properties = list(await session.scalars(statement))
        if not properties:
            return {
                "connected": False,
                "properties": [],
                "range": None,
                "comparison_range": None,
                "freshness": {"last_synced_at": None, "status": "never_synced"},
                "metrics": {},
                "series": [],
            }

        if days not in VALID_REPORTING_PERIODS:
            days = DEFAULT_SYNC_WINDOW_DAYS

        now = datetime.now(UTC)
        last_synced = max(
            (p.last_synced_at for p in properties if p.last_synced_at is not None),
            default=None,
        )
        stale_threshold = now - timedelta(seconds=DEFAULT_FRESHNESS_STALE_SECONDS)
        freshness_status = "fresh"
        if last_synced is None:
            freshness_status = "never_synced"
        elif (
            any(p.freshness_status == "stale" for p in properties) or last_synced < stale_threshold
        ):
            freshness_status = "stale"

        metric_keys = [f"ga4.{m}" for m in GA4_METRICS]
        metric_labels: dict[str, str] = {
            "ga4.sessions": "sessions",
            "ga4.totalUsers": "users",
            "ga4.screenPageViews": "page_views",
            "ga4.conversions": "conversions",
        }

        definitions = await self._get_cached_definitions(session)
        metrics: dict[str, dict[str, object]] = {}

        prop_data = [
            {
                "id": str(p.id),
                "display_name": p.display_name,
                "external_property_id": p.external_property_id,
                "freshness_status": p.freshness_status,
                "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
            }
            for p in properties
        ]

        # Anchor the report to the latest successfully persisted current window,
        # not wall-clock "now", so a calendar rollover before the next sync does
        # not shift the exact-match boundaries away from stored observations.
        window = await self._latest_aggregate_current_window(
            session, organization_id, properties, days
        )

        if window is None:
            for key in metric_keys:
                if key in definitions:
                    metrics[key] = {
                        "label": metric_labels.get(key, key),
                        "current": None,
                        "previous": None,
                        "delta": None,
                        "percent_delta": None,
                        "quality": "missing",
                    }
            return {
                "connected": True,
                "properties": prop_data,
                "range": None,
                "comparison_range": None,
                "freshness": {
                    "last_synced_at": last_synced.isoformat() if last_synced else None,
                    "status": freshness_status,
                },
                "metrics": metrics,
                "series": [],
            }

        current_start, current_end = window
        comp_start, comp_end = comparison_window(current_start, days)

        for key in metric_keys:
            definition = definitions.get(key)
            if definition is None:
                continue
            current_value = await self._sum_observations(
                session,
                organization_id,
                definition.id,
                properties,
                current_start,
                current_end,
            )
            prior_value = await self._sum_observations(
                session,
                organization_id,
                definition.id,
                properties,
                comp_start,
                comp_end,
            )
            absolute_delta: int | None = None
            if current_value is not None and prior_value is not None:
                absolute_delta = int(Decimal(current_value) - Decimal(prior_value))
            percent_delta: float | None = None
            if current_value is not None and prior_value is not None and prior_value != 0:
                delta_pct = (
                    (Decimal(current_value) - Decimal(prior_value))
                    / abs(Decimal(prior_value))
                    * 100
                )
                percent_delta = float(delta_pct)
            quality = "valid"
            if current_value is None:
                quality = "missing"
            elif prior_value is None:
                quality = "partial"

            metrics[key] = {
                "label": metric_labels.get(key, key),
                "current": int(current_value) if current_value is not None else None,
                "previous": int(prior_value) if prior_value is not None else None,
                "delta": absolute_delta,
                "percent_delta": percent_delta,
                "quality": quality,
            }

        daily_labels: set[str] = set()
        daily_rows: dict[str, dict[str, int]] = {}
        for key in metric_keys:
            definition = definitions.get(key)
            if definition is None:
                continue
            daily_obs = await self._daily_observations(
                session,
                organization_id,
                definition.id,
                properties,
                current_start,
                current_end,
            )
            for date_str, value in daily_obs:
                daily_labels.add(date_str)
                if date_str not in daily_rows:
                    daily_rows[date_str] = {}
                daily_rows[date_str][metric_labels.get(key, key)] = value

        sorted_dates = sorted(daily_labels)
        series = [{"date": d, "metrics": daily_rows.get(d, {})} for d in sorted_dates]

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
        }

    async def _latest_aggregate_current_window(
        self,
        session: AsyncSession,
        organization_id: UUID,
        properties: list[AnalyticsProperty],
        days: int,
    ) -> tuple[datetime, datetime] | None:
        """Return the latest authoritative aggregate current window for `days`.

        Selects the newest exact-duration aggregate observation (not its prior
        comparison, which has the same duration but an earlier ``period_end``).
        """
        latest: MetricObservation | None = None
        for prop in properties:
            source = await session.scalar(
                select(InsightSource).where(
                    InsightSource.organization_id == organization_id,
                    InsightSource.key == prop.external_property_id,
                )
            )
            if source is None:
                continue
            obs = await session.scalar(
                select(MetricObservation)
                .where(
                    MetricObservation.organization_id == organization_id,
                    MetricObservation.source_id == source.id,
                    MetricObservation.dimensions["observation_type"].astext == "aggregate",
                    MetricObservation.quality_state.in_(["valid", "zero"]),
                    func.extract(
                        "epoch", MetricObservation.period_end - MetricObservation.period_start
                    )
                    == days * 86_400,
                )
                .order_by(MetricObservation.period_end.desc())
            )
            if obs is not None and (latest is None or obs.period_end > latest.period_end):
                latest = obs
        if latest is None:
            return None
        return latest.period_start, latest.period_end

    async def _sum_observations(
        self,
        session: AsyncSession,
        organization_id: UUID,
        metric_definition_id: UUID,
        properties: list[AnalyticsProperty],
        period_start: datetime,
        period_end: datetime,
    ) -> Decimal | None:
        """Sum the aggregate (not daily-typed) observations for a period across properties."""
        total: Decimal | None = None
        for prop in properties:
            source = await session.scalar(
                select(InsightSource).where(
                    InsightSource.organization_id == organization_id,
                    InsightSource.key == prop.external_property_id,
                )
            )
            if source is None:
                continue
            obs = await session.scalar(
                select(MetricObservation)
                .where(
                    MetricObservation.organization_id == organization_id,
                    MetricObservation.source_id == source.id,
                    MetricObservation.metric_definition_id == metric_definition_id,
                    MetricObservation.period_start == period_start,
                    MetricObservation.period_end == period_end,
                    MetricObservation.dimensions["observation_type"].astext == "aggregate",
                    MetricObservation.quality_state.in_(["valid", "zero"]),
                )
                .order_by(MetricObservation.period_end.desc())
            )
            if obs is not None and obs.value is not None:
                if total is None:
                    total = Decimal(0)
                total += obs.value
        return total

    async def _daily_observations(
        self,
        session: AsyncSession,
        organization_id: UUID,
        metric_definition_id: UUID,
        properties: list[AnalyticsProperty],
        period_start: datetime,
        period_end: datetime,
    ) -> list[tuple[str, int]]:
        """Return (date_string, value) pairs for daily observations in the period."""
        results: list[tuple[str, int]] = []
        for prop in properties:
            source = await session.scalar(
                select(InsightSource).where(
                    InsightSource.organization_id == organization_id,
                    InsightSource.key == prop.external_property_id,
                )
            )
            if source is None:
                continue
            rows = list(
                await session.scalars(
                    select(MetricObservation)
                    .where(
                        MetricObservation.organization_id == organization_id,
                        MetricObservation.source_id == source.id,
                        MetricObservation.metric_definition_id == metric_definition_id,
                        MetricObservation.period_start >= period_start,
                        MetricObservation.period_end <= period_end,
                        MetricObservation.dimensions["observation_type"].astext == "daily",
                        MetricObservation.quality_state.in_(["valid", "zero"]),
                    )
                    .order_by(MetricObservation.period_start.asc())
                )
            )
            for obs in rows:
                if obs.value is not None:
                    date_label = str(
                        obs.dimensions.get(
                            "date",
                            obs.period_start.strftime("%Y-%m-%d"),
                        )
                    )
                    results.append((normalize_observation_date(date_label), int(obs.value)))
        # Aggregate across properties by date
        by_date: dict[str, int] = {}
        for date_label, value in results:
            by_date[date_label] = by_date.get(date_label, 0) + value
        return sorted(by_date.items())

    async def summary(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        location_id: UUID | None = None,
    ) -> dict[str, object]:
        """Aggregate synced GA4 metrics for the Insights summary.

        Returns a truthful disconnected state (empty metrics) when no GA4
        property is mapped, so Insights stays usable without GA4 and never
        fabricates values.
        """
        statement = select(AnalyticsProperty).where(
            AnalyticsProperty.organization_id == organization_id,
            AnalyticsProperty.provider == ANALYTICS_PROVIDER_KEY,
            AnalyticsProperty.mapping_status == "mapped",
        )
        if location_id is not None:
            statement = statement.join(
                SEOWebsite,
                (SEOWebsite.organization_id == AnalyticsProperty.organization_id)
                & (SEOWebsite.id == AnalyticsProperty.website_id),
            ).where(or_(SEOWebsite.location_id == location_id, SEOWebsite.location_id.is_(None)))
        properties = list(await session.scalars(statement))
        if not properties:
            return {"connected": False, "properties": [], "metrics": {}}
        metric_keys = [f"ga4.{m}" for m in GA4_METRICS]
        metrics: dict[str, int] = {key: 0 for key in metric_keys}
        for prop in properties:
            source = await session.scalar(
                select(InsightSource).where(
                    InsightSource.organization_id == organization_id,
                    InsightSource.key == prop.external_property_id,
                )
            )
            if source is None:
                continue
            for key in metric_keys:
                definition = await session.scalar(
                    select(MetricDefinition).where(
                        MetricDefinition.key == key,
                        MetricDefinition.version == METRIC_DEFINITION_VERSION,
                    )
                )
                if definition is None:
                    continue
                observation = await session.scalar(
                    select(MetricObservation)
                    .where(
                        MetricObservation.organization_id == organization_id,
                        MetricObservation.source_id == source.id,
                        MetricObservation.metric_definition_id == definition.id,
                        MetricObservation.dimensions["observation_type"].astext == "aggregate",
                    )
                    .order_by(MetricObservation.period_end.desc())
                )
                if observation is not None and observation.value is not None:
                    metrics[key] += int(observation.value)
        return {
            "connected": True,
            "properties": [
                {
                    "id": str(p.id),
                    "display_name": p.display_name,
                    "external_property_id": p.external_property_id,
                    "freshness_status": p.freshness_status,
                    "last_synced_at": p.last_synced_at,
                }
                for p in properties
            ],
            "metrics": metrics,
        }
