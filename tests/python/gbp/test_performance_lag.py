"""Days Google has not counted yet are reported as 0: they are not stored and not read as values."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceAvailability,
    GBPPerformanceSyncMode,
    GBPPerformanceSyncStatus,
)
from apps.api.app.products.gbp.performance_models import (
    GBPPerformanceDailyMetric,
    GBPPerformanceSyncRun,
)
from apps.api.app.products.gbp.performance_read import PerformancePeriod, read_performance
from apps.api.app.products.gbp.performance_service import settled_through
from gbp.test_performance_sync import (
    CALLS,
    IMPRESSION,
    FakeGoogle,
    metric_rows,
    run_sync,
    seed_client,
    service,
)

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
OCTOBER = date(2026, 10, 1)
# What the daily table held on 2026-10-15: real days to the 11th, then Google's placeholder zeros.
ZERO_TAIL = [date(2026, 10, day) for day in (12, 13, 14)]


def test_the_settled_day_is_three_days_behind_yesterday() -> None:
    assert settled_through(NOW.date()) == date(2026, 10, 11)


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_zero_tail_inside_the_lag_window_is_not_stored(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()
    google.value_for = lambda metric, day: 0 if day >= ZERO_TAIL[0] else 5

    await run_sync(gbp_session_factory, service(google), organization_id, gbp_id, now=NOW)

    stored = await metric_rows(gbp_session_factory, organization_id, IMPRESSION)
    assert max(stored) == date(2026, 10, 11)
    assert not set(ZERO_TAIL) & set(stored)


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_recent_day_with_a_real_count_is_stored_and_a_settled_zero_stays_zero(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()
    google.value_for = lambda metric, day: 7 if day == ZERO_TAIL[-1] else (0 if day.day == 3 else 5)

    await run_sync(gbp_session_factory, service(google), organization_id, gbp_id, now=NOW)

    stored = await metric_rows(gbp_session_factory, organization_id, CALLS)
    assert stored[ZERO_TAIL[-1]] == 7
    assert stored[date(2026, 10, 3)] == 0  # a measured zero long enough ago is real


@pytest.mark.integration
@pytest.mark.anyio
async def test_stored_zero_rows_inside_the_lag_window_are_not_counted_as_synced(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    async with gbp_session_factory.begin() as session:
        run = GBPPerformanceSyncRun(
            organization_id=organization_id,
            gbp_location_id=gbp_id,
            mode=GBPPerformanceSyncMode.RESYNC.value,
            status=GBPPerformanceSyncStatus.SUCCEEDED.value,
            window_start=OCTOBER,
            window_end=ZERO_TAIL[-1],
            started_at=NOW,
            completed_at=NOW,
        )
        session.add(run)
        await session.flush()
        for offset in range(14):
            day = OCTOBER + timedelta(days=offset)
            session.add(
                GBPPerformanceDailyMetric(
                    organization_id=organization_id,
                    gbp_location_id=gbp_id,
                    metric=IMPRESSION.value,
                    metric_date=day,
                    value=0 if day in ZERO_TAIL else 5,
                    sync_run_id=run.id,
                )
            )

    async with gbp_session_factory() as session:
        read = await read_performance(
            session, organization_id, [gbp_id], PerformancePeriod.MONTH, month=OCTOBER, now=NOW
        )

    impressions = read.metrics[IMPRESSION].current
    assert impressions.availability is GBPPerformanceAvailability.PARTIAL
    assert (impressions.days_covered, impressions.days_expected) == (11, 14)
    assert impressions.value == 11 * 5
    assert [point.day for point in read.series][-1] == date(2026, 10, 11)
