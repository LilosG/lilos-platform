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
from apps.api.app.products.seo.errors import (
    SEOSearchConsoleScopeRequiredError,
    SEOSearchPropertyNotConfiguredError,
    SEOSearchPropertyNotFoundError,
)
from apps.api.app.products.seo.search_console_service import SearchConsoleService

logger = logging.getLogger(__name__)

DEFAULT_DAYS = 28


async def scheduled_property_id(
    session: AsyncSession, organization_id: UUID, input_document: dict[str, Any], *, analytics: bool
) -> UUID | None:
    """Schedules have no arbitrary input: resolve exactly one confirmed mapping in scope."""
    if not input_document.get("schedule_id"):
        return None
    from apps.api.app.execution.models import Schedule
    from apps.api.app.products.analytics.models import AnalyticsProperty
    from apps.api.app.products.seo.models import SEOSearchProperty

    schedule = await session.scalar(
        select(Schedule).where(
            Schedule.id == _uuid(input_document["schedule_id"]),
            Schedule.organization_id == organization_id,
            Schedule.status == "active",
        )
    )
    if schedule is None:
        return None
    if analytics:
        ids = list(
            await session.scalars(
                select(AnalyticsProperty.id).where(
                    AnalyticsProperty.organization_id == organization_id,
                    AnalyticsProperty.mapping_status == "mapped",
                )
            )
        )
    else:
        ids = list(
            await session.scalars(
                select(SEOSearchProperty.id).where(
                    SEOSearchProperty.organization_id == organization_id,
                    SEOSearchProperty.mapping_status == "mapped",
                )
            )
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
    """`seo.sync_search_console`: sync one mapped Search Console property."""
    del location_id, workflow_run_id
    property_id = _uuid(input_document.get("search_property_id"))
    if property_id is None:
        property_id = await scheduled_property_id(
            session, organization_id, input_document, analytics=False
        )
    if property_id is None:
        return JobOutcome(result="permanent_failure", safe_error="SEARCH_PROPERTY_ID_INVALID")
    days = input_document.get("days")
    # Release anything this session auto-began: nothing may be open during Google calls.
    await session.rollback()
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
            actor_id=_uuid(input_document.get("actor_id")),
            correlation_id=correlation_id,
            days=days if isinstance(days, int) else DEFAULT_DAYS,
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
    """`insights.sync_analytics`: sync one mapped GA4 property."""
    del location_id, workflow_run_id
    property_id = _uuid(input_document.get("analytics_property_id"))
    if property_id is None:
        property_id = await scheduled_property_id(
            session, organization_id, input_document, analytics=True
        )
    if property_id is None:
        return JobOutcome(result="permanent_failure", safe_error="ANALYTICS_PROPERTY_ID_INVALID")
    days = input_document.get("days")
    await session.rollback()
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
            actor_id=_uuid(input_document.get("actor_id")),
            correlation_id=correlation_id,
            days=days if isinstance(days, int) else DEFAULT_DAYS,
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
