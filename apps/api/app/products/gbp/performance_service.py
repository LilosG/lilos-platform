"""Deterministic Business Profile performance sync: Google's daily metrics and search keywords.

No model is involved. A run reads everything from Google first, with no database transaction
open across a provider call, then writes in one short transaction; a failed read leaves the
previously stored values untouched. Every write is an upsert on the natural key, so a re-run, a
retry and the daily 10-day re-sync (Google revises recent days) are all idempotent.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.database.scope import TransactionScope
from apps.api.app.integrations.adapter_factory import gbp_performance_adapter
from apps.api.app.integrations.connection_service import (
    GBPConnectionService,
    TokenRefreshPlan,
    connection_has_scope,
)
from apps.api.app.integrations.errors import (
    IntegrationNotFoundError,
    IntegrationReconnectRequiredError,
    IntegrationTokenRejectedError,
)
from apps.api.app.integrations.models import IntegrationConnection, ProviderResourceMapping
from apps.api.app.products.gbp.adapter import (
    BUSINESS_MANAGE_SCOPE,
    DailyMetricPoint,
    GBPPerformanceAdapter,
    GBPPerformanceProviderError,
    KeywordImpressionPoint,
)
from apps.api.app.products.gbp.models import GBPLocation
from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceFailureCode,
    GBPPerformanceSyncMode,
    GBPPerformanceSyncStatus,
)
from apps.api.app.products.gbp.performance_models import (
    GBPPerformanceDailyMetric,
    GBPPerformanceKeywordImpression,
    GBPPerformanceSyncRun,
)

BACKFILL_MONTHS = 18
RESYNC_DAYS = 10
# Google serves daily metrics some days late and revises them; a run asks up to yesterday.
LAST_DAY_OFFSET = 1
UPSERT_BATCH = 1_000


class GBPPerformanceSyncError(Exception):
    """A sync could not finish; ``code`` is the typed reason and nothing was half-written."""

    def __init__(self, code: GBPPerformanceFailureCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class SyncWindow:
    mode: GBPPerformanceSyncMode
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class SyncResult:
    run_id: UUID
    status: GBPPerformanceSyncStatus
    window: SyncWindow
    metric_rows: int
    keyword_rows: int
    failure_code: GBPPerformanceFailureCode | None = None


@dataclass(slots=True)
class _Fetched:
    metrics: list[DailyMetricPoint] = field(default_factory=list)
    keywords: dict[date, list[KeywordImpressionPoint]] = field(default_factory=dict)
    keyword_failure: GBPPerformanceFailureCode | None = None


def months_before(day: date, months: int) -> date:
    """The same day-of-month ``months`` earlier, clamped to the shorter month's last day."""
    index = day.year * 12 + (day.month - 1) - months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def plan_window(today: date, *, backfilled: bool) -> SyncWindow:
    """First run: 18 months back. Afterwards: the last 10 days, which Google keeps revising."""
    end = today - timedelta(days=LAST_DAY_OFFSET)
    if not backfilled:
        return SyncWindow(
            GBPPerformanceSyncMode.BACKFILL, months_before(today, BACKFILL_MONTHS), end
        )
    return SyncWindow(GBPPerformanceSyncMode.RESYNC, today - timedelta(days=RESYNC_DAYS), end)


def keyword_months(window: SyncWindow, today: date) -> list[date]:
    """Completed months to read search keywords for, oldest first.

    Google publishes a month's terms after it ends, and revises the last one for a while, so a
    re-sync always re-reads the two most recent completed months.
    """
    last_complete = months_before(first_of_month(today), 1)
    if window.mode is GBPPerformanceSyncMode.BACKFILL:
        first = first_of_month(window.start)
    else:
        first = months_before(last_complete, 1)
    months: list[date] = []
    month = first
    while month <= last_complete:
        months.append(month)
        month = months_before(month, -1)
    return months


def day_chunks(start: date, end: date, span_days: int = 186) -> list[tuple[date, date]]:
    """Split an inclusive range so one Google request never covers more than ``span_days``."""
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=span_days - 1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _mapped_location_conditions() -> tuple[ColumnElement[bool], ...]:
    """What makes a GBP location "mapped"; shared by the per-client and the set-based reads."""
    return (
        GBPLocation.mapping_status == "confirmed",
        GBPLocation.location_id.is_not(None),
        ProviderResourceMapping.status == "active",
        ProviderResourceMapping.resource_type == "location",
        ProviderResourceMapping.platform_resource_id == GBPLocation.location_id,
    )


async def mapped_gbp_locations(session: AsyncSession, organization_id: UUID) -> list[GBPLocation]:
    """GBP locations that are confirmed and have an active resource mapping to a platform location.

    This is the one definition of "a mapped GBP location": the schedules and the sync agree on it.
    """
    rows = await session.scalars(
        select(GBPLocation)
        .join(
            ProviderResourceMapping,
            ProviderResourceMapping.id == GBPLocation.integration_resource_id,
        )
        .where(GBPLocation.organization_id == organization_id, *_mapped_location_conditions())
        .order_by(GBPLocation.created_at, GBPLocation.id)
    )
    return list(rows)


async def mapped_gbp_location_counts(
    session: AsyncSession, organization_ids: Sequence[UUID]
) -> dict[UUID, int]:
    """How many mapped GBP locations each organization has, in one query for all of them."""
    rows = await session.execute(
        select(GBPLocation.organization_id, func.count(GBPLocation.id))
        .join(
            ProviderResourceMapping,
            ProviderResourceMapping.id == GBPLocation.integration_resource_id,
        )
        .where(GBPLocation.organization_id.in_(organization_ids), *_mapped_location_conditions())
        .group_by(GBPLocation.organization_id)
    )
    return {organization_id: int(count) for organization_id, count in rows}


async def resolve_gbp_location(
    session: AsyncSession,
    organization_id: UUID,
    *,
    gbp_location_id: UUID | None,
    platform_location_id: UUID | None,
) -> GBPLocation:
    """The one mapped GBP location a run is for, by GBP id (manual) or platform id (schedule)."""
    if gbp_location_id is None and platform_location_id is None:
        raise GBPPerformanceSyncError(GBPPerformanceFailureCode.LOCATION_ID_MISSING)
    mapped = await mapped_gbp_locations(session, organization_id)
    if gbp_location_id is not None:
        found = [row for row in mapped if row.id == gbp_location_id]
    else:
        found = [row for row in mapped if row.location_id == platform_location_id]
    if not found:
        raise GBPPerformanceSyncError(GBPPerformanceFailureCode.LOCATION_NOT_FOUND)
    if len(found) > 1:
        raise GBPPerformanceSyncError(GBPPerformanceFailureCode.LOCATION_AMBIGUOUS)
    return found[0]


@dataclass(slots=True)
class GBPPerformanceService:
    adapter: GBPPerformanceAdapter = field(default_factory=gbp_performance_adapter)
    connection: GBPConnectionService = field(default_factory=GBPConnectionService)
    audit: AuditEventService = field(default_factory=AuditEventService)

    async def sync_location(
        self,
        scope: TransactionScope,
        settings: Settings,
        organization_id: UUID,
        gbp_location_id: UUID,
        *,
        correlation_id: str,
        workflow_run_id: UUID | None = None,
        now: datetime | None = None,
    ) -> SyncResult:
        today = (now or datetime.now(UTC)).astimezone(UTC).date()

        # -- phase 1: read, and record that the run started ----------------------------
        async with scope.begin() as session:
            gbp_location = await session.scalar(
                select(GBPLocation).where(
                    GBPLocation.organization_id == organization_id,
                    GBPLocation.id == gbp_location_id,
                )
            )
            if gbp_location is None:
                raise GBPPerformanceSyncError(GBPPerformanceFailureCode.LOCATION_NOT_FOUND)
            try:
                connection = await self.connection.get_connection(session, organization_id)
            except IntegrationNotFoundError:
                raise GBPPerformanceSyncError(
                    GBPPerformanceFailureCode.INTEGRATION_NOT_FOUND
                ) from None
            if not connection_has_scope(connection, BUSINESS_MANAGE_SCOPE):
                raise GBPPerformanceSyncError(GBPPerformanceFailureCode.SCOPE_REQUIRED)
            try:
                plan = await self.connection.begin_token_refresh(session, settings, connection)
            except IntegrationReconnectRequiredError:
                raise GBPPerformanceSyncError(
                    GBPPerformanceFailureCode.RECONNECT_REQUIRED
                ) from None
            connection_id = connection.id
            external_location_id = gbp_location.external_location_id
            platform_location_id = gbp_location.location_id
            backfilled = (
                await session.scalar(
                    select(func.count())
                    .select_from(GBPPerformanceSyncRun)
                    .where(
                        GBPPerformanceSyncRun.organization_id == organization_id,
                        GBPPerformanceSyncRun.gbp_location_id == gbp_location_id,
                        GBPPerformanceSyncRun.mode == GBPPerformanceSyncMode.BACKFILL.value,
                        GBPPerformanceSyncRun.status == GBPPerformanceSyncStatus.SUCCEEDED.value,
                    )
                )
                or 0
            ) > 0
            window = plan_window(today, backfilled=backfilled)
            run = GBPPerformanceSyncRun(
                organization_id=organization_id,
                gbp_location_id=gbp_location_id,
                workflow_run_id=workflow_run_id,
                mode=window.mode.value,
                status=GBPPerformanceSyncStatus.RUNNING.value,
                window_start=window.start,
                window_end=window.end,
            )
            session.add(run)
            await session.flush()
            run_id = run.id

        # -- phase 2: Google, with nothing open ------------------------------------------
        try:
            token = await self._access_token(scope, settings, connection_id, plan)
            fetched = await self._fetch(token, external_location_id, window, today)
        except (GBPPerformanceProviderError, GBPPerformanceSyncError) as exc:
            await self._fail(
                scope, organization_id, gbp_location_id, platform_location_id, run_id, exc.code,
                correlation_id,
            )  # fmt: skip
            raise GBPPerformanceSyncError(exc.code) from None
        except Exception:
            await self._fail(
                scope, organization_id, gbp_location_id, platform_location_id, run_id,
                GBPPerformanceFailureCode.SYNC_FAILED, correlation_id,
            )  # fmt: skip
            raise

        # -- phase 3: persist ------------------------------------------------------------
        status = (
            GBPPerformanceSyncStatus.PARTIAL
            if fetched.keyword_failure is not None
            else GBPPerformanceSyncStatus.SUCCEEDED
        )
        async with scope.begin() as session:
            metric_rows = await self._upsert_metrics(
                session, organization_id, gbp_location_id, run_id, fetched.metrics
            )
            keyword_rows = await self._upsert_keywords(
                session, organization_id, gbp_location_id, run_id, fetched.keywords
            )
            finished = await session.get(GBPPerformanceSyncRun, run_id)
            assert finished is not None
            finished.status = status.value
            finished.metric_rows_written = metric_rows
            finished.keyword_rows_written = keyword_rows
            finished.failure_code = (
                fetched.keyword_failure.value if fetched.keyword_failure else None
            )
            finished.completed_at = datetime.now(UTC)
            await self._audit(
                session,
                organization_id=organization_id,
                gbp_location_id=gbp_location_id,
                platform_location_id=platform_location_id,
                run_id=run_id,
                correlation_id=correlation_id,
                result=AuditResult.SUCCEEDED
                if status is GBPPerformanceSyncStatus.SUCCEEDED
                else AuditResult.PARTIALLY_SUCCEEDED,
                code=fetched.keyword_failure,
                window=window,
                metric_rows=metric_rows,
                keyword_rows=keyword_rows,
            )
        return SyncResult(
            run_id, status, window, metric_rows, keyword_rows, fetched.keyword_failure
        )

    async def _access_token(
        self,
        scope: TransactionScope,
        settings: Settings,
        connection_id: UUID,
        refresh: TokenRefreshPlan,
    ) -> str:
        if refresh.access_token is not None:
            return refresh.access_token
        assert refresh.refresh_token is not None
        try:
            payload = await self.connection.refresh_token_pair(settings, refresh.refresh_token)
        except IntegrationTokenRejectedError:
            async with scope.begin() as session:
                stale = await session.get(IntegrationConnection, connection_id)
                if stale is not None:
                    await self.connection.fail_token_refresh(session, stale)
            raise GBPPerformanceSyncError(GBPPerformanceFailureCode.RECONNECT_REQUIRED) from None
        except Exception:
            raise GBPPerformanceSyncError(
                GBPPerformanceFailureCode.TOKEN_RESOLUTION_FAILED
            ) from None
        async with scope.begin() as session:
            refreshed = await session.get(IntegrationConnection, connection_id)
            if refreshed is None:
                raise GBPPerformanceSyncError(GBPPerformanceFailureCode.INTEGRATION_NOT_FOUND)
            return await self.connection.complete_token_refresh(
                session, settings, refreshed, refresh, payload
            )

    async def _fetch(
        self, token: str, external_location_id: str, window: SyncWindow, today: date
    ) -> _Fetched:
        fetched = _Fetched()
        # Daily metrics are required: any failure fails the run before anything is written.
        for start, end in day_chunks(window.start, window.end):
            fetched.metrics += await self.adapter.fetch_daily_metrics(
                token, external_location_id, start, end
            )
        # Search terms are best-effort per month: what was read is kept, the failure is recorded.
        for month in keyword_months(window, today):
            try:
                fetched.keywords[month] = await self.adapter.list_search_keyword_impressions(
                    token, external_location_id, month
                )
            except GBPPerformanceProviderError as exc:
                fetched.keyword_failure = fetched.keyword_failure or exc.code
        return fetched

    async def _upsert_metrics(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        run_id: UUID,
        points: Sequence[DailyMetricPoint],
    ) -> int:
        rows = [
            {
                "id": uuid4(),
                "organization_id": organization_id,
                "gbp_location_id": gbp_location_id,
                "metric": point.metric.value,
                "metric_date": point.day,
                "value": point.value,
                "sync_run_id": run_id,
            }
            for point in points
        ]
        for start in range(0, len(rows), UPSERT_BATCH):
            statement = pg_insert(GBPPerformanceDailyMetric).values(
                rows[start : start + UPSERT_BATCH]
            )
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_gbp_performance_daily_metric",
                    set_={
                        "value": statement.excluded.value,
                        "sync_run_id": statement.excluded.sync_run_id,
                        "updated_at": func.now(),
                    },
                )
            )
        return len(rows)

    async def _upsert_keywords(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        run_id: UUID,
        by_month: dict[date, list[KeywordImpressionPoint]],
    ) -> int:
        rows = [
            {
                "id": uuid4(),
                "organization_id": organization_id,
                "gbp_location_id": gbp_location_id,
                "month": month,
                "keyword": point.keyword,
                "value": point.value,
                "threshold": point.threshold,
                "sync_run_id": run_id,
            }
            for month, points in by_month.items()
            for point in points
        ]
        for start in range(0, len(rows), UPSERT_BATCH):
            statement = pg_insert(GBPPerformanceKeywordImpression).values(
                rows[start : start + UPSERT_BATCH]
            )
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_gbp_performance_keyword_impression",
                    set_={
                        "value": statement.excluded.value,
                        "threshold": statement.excluded.threshold,
                        "sync_run_id": statement.excluded.sync_run_id,
                        "updated_at": func.now(),
                    },
                )
            )
        return len(rows)

    async def _fail(
        self,
        scope: TransactionScope,
        organization_id: UUID,
        gbp_location_id: UUID,
        platform_location_id: UUID | None,
        run_id: UUID,
        code: GBPPerformanceFailureCode,
        correlation_id: str,
    ) -> None:
        async with scope.begin() as session:
            run = await session.get(GBPPerformanceSyncRun, run_id)
            if run is None:
                return
            run.status = GBPPerformanceSyncStatus.FAILED.value
            run.failure_code = code.value
            run.completed_at = datetime.now(UTC)
            await self._audit(
                session,
                organization_id=organization_id,
                gbp_location_id=gbp_location_id,
                platform_location_id=platform_location_id,
                run_id=run_id,
                correlation_id=correlation_id,
                result=AuditResult.FAILED,
                code=code,
                window=SyncWindow(
                    GBPPerformanceSyncMode(run.mode), run.window_start, run.window_end
                ),
                metric_rows=0,
                keyword_rows=0,
            )

    async def _audit(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        gbp_location_id: UUID,
        platform_location_id: UUID | None,
        run_id: UUID,
        correlation_id: str,
        result: AuditResult,
        code: GBPPerformanceFailureCode | None,
        window: SyncWindow,
        metric_rows: int,
        keyword_rows: int,
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="gbp.performance.synced",
                action="gbp.performance.sync",
                result=result,
                actor_type=AuditActorType.SYSTEM,
                organization_id=organization_id,
                location_id=platform_location_id,
                product_key="gbp",
                resource_type="gbp_location",
                resource_id=gbp_location_id,
                correlation_id=correlation_id[:64],
                summary="Business Profile performance sync finished.",
                error_code=code.value if code else None,
                metadata=cast(
                    dict[str, JsonValue],
                    {
                        "sync_run_id": str(run_id),
                        "mode": window.mode.value,
                        "window_start": window.start.isoformat(),
                        "window_end": window.end.isoformat(),
                        "metric_rows": metric_rows,
                        "keyword_rows": keyword_rows,
                    },
                ),
            ),
        )
