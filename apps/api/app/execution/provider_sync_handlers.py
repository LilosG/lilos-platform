"""Worker handlers for the long provider syncs: Search Console and GA4.

These used to run inside an API request, holding a database transaction open across
every Google call. They now run here, in the worker, and the routes only enqueue.
The services open their own short transactions (read, then persist) and call Google
between them with nothing open, so the handler hands them a scope derived from the
session's engine rather than using the session itself for the provider work.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.integrations.errors import IntegrationReconnectRequiredError
from apps.api.app.products.analytics.errors import (
    AnalyticsNotConfiguredError,
    AnalyticsPropertyNotFoundError,
    AnalyticsScopeRequiredError,
)
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceFailureCode,
    GBPPerformanceSyncStatus,
)
from apps.api.app.products.gbp.performance_service import (
    GBPPerformanceService,
    GBPPerformanceSyncError,
    resolve_gbp_location,
)
from apps.api.app.products.seo.errors import (
    SEOSearchConsoleScopeRequiredError,
    SEOSearchPropertyNotConfiguredError,
    SEOSearchPropertyNotFoundError,
)
from apps.api.app.products.seo.search_console_service import SearchConsoleService

logger = logging.getLogger(__name__)

DEFAULT_DAYS = 28


async def scheduled_property_ids(
    session: AsyncSession, organization_id: UUID, input_document: dict[str, Any], *, analytics: bool
) -> list[UUID]:
    """Schedules have no arbitrary input: resolve every mapped property in the schedule's scope.

    A location-scoped schedule covers the properties of that location's websites and of
    organization-wide websites; an organization-wide schedule covers every mapped property.
    """
    if not input_document.get("schedule_id"):
        return []
    from apps.api.app.execution.models import Schedule
    from apps.api.app.products.analytics.models import AnalyticsProperty
    from apps.api.app.products.seo.models import SEOSearchProperty, SEOWebsite

    schedule = await session.scalar(
        select(Schedule).where(
            Schedule.id == _uuid(input_document["schedule_id"]),
            Schedule.organization_id == organization_id,
            Schedule.status == "active",
        )
    )
    if schedule is None:
        return []
    if analytics:
        query = select(AnalyticsProperty.id).where(
            AnalyticsProperty.organization_id == organization_id,
            AnalyticsProperty.mapping_status == "mapped",
        )
        website_column = AnalyticsProperty.website_id
        order = AnalyticsProperty.created_at
    else:
        query = select(SEOSearchProperty.id).where(
            SEOSearchProperty.organization_id == organization_id,
            SEOSearchProperty.mapping_status == "mapped",
        )
        website_column = SEOSearchProperty.website_id
        order = SEOSearchProperty.created_at
    if schedule.location_id is not None:
        # An analytics property may have no website link; it is organization-wide then.
        in_scope = select(SEOWebsite.id).where(
            SEOWebsite.organization_id == organization_id,
            (SEOWebsite.location_id == schedule.location_id) | SEOWebsite.location_id.is_(None),
        )
        query = query.where(website_column.is_(None) | website_column.in_(in_scope))
    return list(await session.scalars(query.order_by(order)))


async def scheduled_property_id(
    session: AsyncSession, organization_id: UUID, input_document: dict[str, Any], *, analytics: bool
) -> UUID | None:
    """The one mapped property of a schedule, or None when there are none or several."""
    ids = await scheduled_property_ids(
        session, organization_id, input_document, analytics=analytics
    )
    return ids[0] if len(ids) == 1 else None


def live_smoke_authorized(settings: Settings, organization_id: UUID) -> bool:
    return settings.environment.value == "staging" and str(
        organization_id
    ) in settings.staging_live_google_organization_ids.split(",")


def transaction_scope(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """A factory of short transactions on the same database as ``session``."""
    bind = session.bind
    if bind is None:
        raise RuntimeError("the worker session is not bound to an engine")
    return async_sessionmaker(bind=bind, expire_on_commit=False)


def _uuid(raw: object) -> UUID | None:
    try:
        return UUID(str(raw)) if raw else None
    except (TypeError, ValueError):
        return None


async def handle_search_console_sync(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """`seo.sync_search_console`: sync one mapped property, or every one on a schedule."""
    del location_id, workflow_run_id
    property_id = _uuid(input_document.get("search_property_id"))
    if property_id is not None:
        property_ids = [property_id]
    else:
        property_ids = await scheduled_property_ids(
            session, organization_id, input_document, analytics=False
        )
        if not property_ids:
            code = (
                "SEARCH_PROPERTY_NOT_FOUND"
                if input_document.get("schedule_id")
                else "SEARCH_PROPERTY_ID_INVALID"
            )
            return JobOutcome(result="permanent_failure", safe_error=code)
    days = input_document.get("days")
    # Release anything this session auto-began: nothing may be open during Google calls.
    await session.rollback()
    failure: JobOutcome | None = None
    for property_id in property_ids:
        outcome = await _sync_search_property(
            session,
            organization_id,
            property_id,
            actor_id=_uuid(input_document.get("actor_id")),
            correlation_id=correlation_id,
            days=days if isinstance(days, int) else DEFAULT_DAYS,
        )
        # Every property is attempted: one client's broken mapping must not starve the rest.
        if outcome.result != "succeeded" and failure is None:
            failure = outcome
    if failure is not None:
        return failure
    if len(property_ids) == 1:
        return JobOutcome(result="succeeded", result_reference=f"seo-search-property:{property_id}")
    return JobOutcome(
        result="succeeded", result_reference=f"seo-search-properties:{len(property_ids)}"
    )


async def _sync_search_property(
    session: AsyncSession,
    organization_id: UUID,
    property_id: UUID,
    *,
    actor_id: UUID | None,
    correlation_id: str,
    days: int,
) -> JobOutcome:
    try:
        service = SearchConsoleService()
        if live_smoke_authorized(Settings(), organization_id):
            from apps.api.app.products.seo.search_console_adapter import GoogleSearchConsoleAdapter

            service.adapter = GoogleSearchConsoleAdapter()
        result = await service.sync_observations(
            transaction_scope(session),
            Settings(),
            organization_id,
            property_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            days=days,
        )
    except IntegrationReconnectRequiredError:
        return JobOutcome(result="permanent_failure", safe_error="INTEGRATION_RECONNECT_REQUIRED")
    except SEOSearchPropertyNotFoundError:
        return JobOutcome(result="permanent_failure", safe_error="SEARCH_PROPERTY_NOT_FOUND")
    except SEOSearchPropertyNotConfiguredError:
        return JobOutcome(result="permanent_failure", safe_error="SEARCH_PROPERTY_NOT_CONFIGURED")
    except SEOSearchConsoleScopeRequiredError:
        return JobOutcome(result="permanent_failure", safe_error="SEARCH_CONSOLE_SCOPE_REQUIRED")
    except Exception:
        logger.exception(
            "Search Console sync failed", extra={"search_property_id": str(property_id)}
        )
        return JobOutcome(result="retryable_failure", safe_error="SEARCH_CONSOLE_SYNC_FAILED")
    if not result.get("periods_synced"):
        # A required request failed; the previous dataset is preserved and audited.
        return JobOutcome(result="retryable_failure", safe_error="SEARCH_CONSOLE_SYNC_INCOMPLETE")
    return JobOutcome(result="succeeded", result_reference=f"seo-search-property:{property_id}")


async def handle_analytics_sync(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """`insights.sync_analytics`: sync one mapped GA4 property, or every one on a schedule."""
    del location_id, workflow_run_id
    property_id = _uuid(input_document.get("analytics_property_id"))
    if property_id is not None:
        property_ids = [property_id]
    else:
        property_ids = await scheduled_property_ids(
            session, organization_id, input_document, analytics=True
        )
        if not property_ids:
            code = (
                "ANALYTICS_PROPERTY_NOT_FOUND"
                if input_document.get("schedule_id")
                else "ANALYTICS_PROPERTY_ID_INVALID"
            )
            return JobOutcome(result="permanent_failure", safe_error=code)
    days = input_document.get("days")
    await session.rollback()
    failure: JobOutcome | None = None
    for property_id in property_ids:
        outcome = await _sync_analytics_property(
            session,
            organization_id,
            property_id,
            actor_id=_uuid(input_document.get("actor_id")),
            correlation_id=correlation_id,
            days=days if isinstance(days, int) else DEFAULT_DAYS,
        )
        if outcome.result != "succeeded" and failure is None:
            failure = outcome
    if failure is not None:
        return failure
    if len(property_ids) == 1:
        return JobOutcome(result="succeeded", result_reference=f"analytics-property:{property_id}")
    return JobOutcome(
        result="succeeded", result_reference=f"analytics-properties:{len(property_ids)}"
    )


async def _sync_analytics_property(
    session: AsyncSession,
    organization_id: UUID,
    property_id: UUID,
    *,
    actor_id: UUID | None,
    correlation_id: str,
    days: int,
) -> JobOutcome:
    try:
        service = AnalyticsService()
        if live_smoke_authorized(Settings(), organization_id):
            from apps.api.app.products.analytics.adapter import GoogleAnalyticsAdminAdapter

            service.adapter = GoogleAnalyticsAdminAdapter()
        result = await service.sync_metrics(
            transaction_scope(session),
            Settings(),
            organization_id,
            property_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            days=days,
        )
    except IntegrationReconnectRequiredError:
        return JobOutcome(result="permanent_failure", safe_error="INTEGRATION_RECONNECT_REQUIRED")
    except AnalyticsPropertyNotFoundError:
        return JobOutcome(result="permanent_failure", safe_error="ANALYTICS_PROPERTY_NOT_FOUND")
    except AnalyticsNotConfiguredError:
        return JobOutcome(result="permanent_failure", safe_error="ANALYTICS_NOT_CONFIGURED")
    except AnalyticsScopeRequiredError:
        return JobOutcome(result="permanent_failure", safe_error="ANALYTICS_SCOPE_REQUIRED")
    except Exception:
        logger.exception("GA4 sync failed", extra={"analytics_property_id": str(property_id)})
        return JobOutcome(result="retryable_failure", safe_error="ANALYTICS_SYNC_FAILED")
    if not result.get("periods_synced"):
        return JobOutcome(result="retryable_failure", safe_error="ANALYTICS_SYNC_INCOMPLETE")
    return JobOutcome(result="succeeded", result_reference=f"analytics-property:{property_id}")


async def handle_gbp_performance_sync(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """`gbp.sync_performance`: Google's daily metrics and search keywords for one GBP location.

    Deterministic: no model. The location is the schedule's platform location, or
    ``gbp_location_id`` on a manual run.
    """
    raw_gbp_location_id = input_document.get("gbp_location_id")
    gbp_location_id = _uuid(raw_gbp_location_id)
    if raw_gbp_location_id and gbp_location_id is None:
        return _performance_failure(GBPPerformanceFailureCode.LOCATION_ID_INVALID)
    try:
        gbp_location = await resolve_gbp_location(
            session,
            organization_id,
            gbp_location_id=gbp_location_id,
            platform_location_id=location_id,
        )
    except GBPPerformanceSyncError as exc:
        return _performance_failure(exc.code)
    pk = gbp_location.id
    # Release anything this session auto-began: nothing may be open during Google calls.
    await session.rollback()
    try:
        service = GBPPerformanceService()
        if live_smoke_authorized(Settings(), organization_id):
            from apps.api.app.products.gbp.adapter import GoogleBusinessProfileAdapter

            service.adapter = GoogleBusinessProfileAdapter()
        result = await service.sync_location(
            transaction_scope(session),
            Settings(),
            organization_id,
            pk,
            correlation_id=correlation_id,
            workflow_run_id=workflow_run_id,
        )
    except GBPPerformanceSyncError as exc:
        return _performance_failure(exc.code)
    except Exception:
        logger.exception("GBP performance sync failed", extra={"gbp_location_id": str(pk)})
        return _performance_failure(GBPPerformanceFailureCode.SYNC_FAILED)
    if result.status is not GBPPerformanceSyncStatus.SUCCEEDED:
        # Daily metrics are stored; the search keywords were not all readable. Surface it.
        return _performance_failure(
            result.failure_code or GBPPerformanceFailureCode.KEYWORDS_UNAVAILABLE
        )
    return JobOutcome(result="succeeded", result_reference=f"gbp-performance:{pk}")


def _performance_failure(code: GBPPerformanceFailureCode) -> JobOutcome:
    return JobOutcome(
        result="retryable_failure" if code.retryable else "permanent_failure",
        safe_error=code.value,
    )
