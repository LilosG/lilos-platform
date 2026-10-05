"""Performance sync and read: backfill, 10-day re-sync, idempotent upsert, failures, isolation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import Settings
from apps.api.app.execution.provider_sync_handlers import handle_gbp_performance_sync
from apps.api.app.integrations.connection_service import (
    GBP_PROVIDER_KEY,
    GBPConnectionService,
    TokenRefreshPlan,
)
from apps.api.app.integrations.errors import (
    IntegrationReconnectRequiredError,
    IntegrationTokenRejectedError,
)
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.adapter import (
    BUSINESS_MANAGE_SCOPE,
    DailyMetricPoint,
    GBPPerformanceProviderError,
    GoogleBusinessProfileAdapter,
    KeywordImpressionPoint,
)
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceAvailability,
    GBPPerformanceFailureCode,
    GBPPerformanceMetric,
    GBPPerformanceSyncMode,
    GBPPerformanceSyncStatus,
)
from apps.api.app.products.gbp.performance_models import (
    GBPPerformanceDailyMetric,
    GBPPerformanceKeywordImpression,
    GBPPerformanceSyncRun,
)
from apps.api.app.products.gbp.performance_read import PerformancePeriod, read_performance
from apps.api.app.products.gbp.performance_service import (
    GBPPerformanceService,
    GBPPerformanceSyncError,
    resolve_gbp_location,
)

NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
TODAY = NOW.date()
YESTERDAY = TODAY - timedelta(days=1)
IMPRESSION = GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_SEARCH
CALLS = GBPPerformanceMetric.CALL_CLICKS


class FakeConnection(GBPConnectionService):
    """A connection whose token is already fresh, or whose refresh behaves as scripted."""

    def __init__(self, *, plan: TokenRefreshPlan | Exception | None = None) -> None:
        super().__init__()
        self.plan = plan or TokenRefreshPlan(access_token="token", refresh_token=None)
        self.refresh_error: Exception | None = None

    async def begin_token_refresh(self, session: Any, settings: Any, connection: Any) -> Any:
        if isinstance(self.plan, Exception):
            raise self.plan
        return self.plan

    async def refresh_token_pair(self, settings: Any, refresh_token: str) -> dict[str, object]:
        assert self.refresh_error is not None
        raise self.refresh_error


class FakeGoogle(GoogleBusinessProfileAdapter):
    """Serves one value per metric-day from a callable, and records every request."""

    def __init__(self) -> None:
        super().__init__()
        self.daily_calls: list[tuple[str, date, date]] = []
        self.keyword_calls: list[tuple[str, date]] = []
        self.value_for: Callable[[GBPPerformanceMetric, date], int] = lambda metric, day: 1
        self.keywords: dict[date, list[KeywordImpressionPoint]] = {}
        self.daily_error: Exception | None = None
        self.keyword_error: Exception | None = None

    async def fetch_daily_metrics(
        self, access_token: str, location_name: str, start: date, end: date
    ) -> list[DailyMetricPoint]:
        self.daily_calls.append((location_name, start, end))
        if self.daily_error is not None:
            raise self.daily_error
        points = []
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            points += [
                DailyMetricPoint(IMPRESSION, day, self.value_for(IMPRESSION, day)),
                DailyMetricPoint(CALLS, day, self.value_for(CALLS, day)),
            ]
        return points

    async def list_search_keyword_impressions(
        self, access_token: str, location_name: str, month: date
    ) -> list[KeywordImpressionPoint]:
        self.keyword_calls.append((location_name, month))
        if self.keyword_error is not None:
            raise self.keyword_error
        return self.keywords.get(month, [])


def service(google: FakeGoogle, connection: FakeConnection | None = None) -> GBPPerformanceService:
    return GBPPerformanceService(adapter=google, connection=connection or FakeConnection())


async def seed_client(
    factory: async_sessionmaker[AsyncSession], name: str = "Client"
) -> tuple[UUID, UUID, UUID]:
    """An organization with a connected Google connection and one mapped GBP location.

    Returns (organization id, GBP location id, platform location id).
    """
    async with factory.begin() as session:
        organization = Organization(
            name=name,
            slug=f"{name.lower()}-{uuid4().hex[:6]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        provider = await session.scalar(select(Provider).where(Provider.key == GBP_PROVIDER_KEY))
        if provider is None:
            provider = Provider(
                key=GBP_PROVIDER_KEY,
                name="Google Business Profile",
                status="active",
                capabilities=[],
                manifest_version=1,
            )
            session.add(provider)
        session.add(organization)
        await session.flush()
        connection = IntegrationConnection(
            organization_id=organization.id,
            provider_id=provider.id,
            external_account_reference="google",
            status="connected",
            granted_capabilities=[BUSINESS_MANAGE_SCOPE],
            version=1,
        )
        session.add(connection)
        await session.flush()
        account = GBPAccount(
            organization_id=organization.id,
            connection_id=connection.id,
            external_account_id="accounts/1",
            display_name="Account",
            status="selected",
        )
        location = Location(
            organization_id=organization.id,
            name="Main",
            slug="main",
            location_type=LocationType.VIRTUAL,
            status=LocationStatus.ACTIVE,
            timezone="UTC",
            country_code="US",
            website_url="https://example.invalid",
            is_primary=True,
            version=1,
        )
        session.add_all([account, location])
        await session.flush()
        mapping = ProviderResourceMapping(
            organization_id=organization.id,
            connection_id=connection.id,
            resource_type="location",
            external_resource_id="locations/555",
            platform_resource_id=location.id,
            status="active",
        )
        session.add(mapping)
        await session.flush()
        gbp_location = GBPLocation(
            organization_id=organization.id,
            location_id=location.id,
            connection_id=connection.id,
            account_id=account.id,
            integration_resource_id=mapping.id,
            external_location_id="locations/555",
            business_name="Main",
            mapping_status="confirmed",
            write_enabled=False,
        )
        session.add(gbp_location)
        await session.flush()
        return organization.id, gbp_location.id, location.id


async def metric_rows(
    factory: async_sessionmaker[AsyncSession], organization_id: UUID, metric: GBPPerformanceMetric
) -> dict[date, int]:
    async with factory() as session:
        rows = await session.execute(
            select(GBPPerformanceDailyMetric.metric_date, GBPPerformanceDailyMetric.value).where(
                GBPPerformanceDailyMetric.organization_id == organization_id,
                GBPPerformanceDailyMetric.metric == metric.value,
            )
        )
        return {day: value for day, value in rows}


async def run_sync(
    factory: async_sessionmaker[AsyncSession],
    svc: GBPPerformanceService,
    organization_id: UUID,
    gbp_location_id: UUID,
    now: datetime = NOW,
) -> Any:
    return await svc.sync_location(
        factory,
        Settings(),
        organization_id,
        gbp_location_id,
        correlation_id="test",
        now=now,
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_first_run_backfills_eighteen_months_then_resyncs_ten_days(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()

    first = await run_sync(gbp_session_factory, service(google), organization_id, gbp_id)

    assert first.window.mode is GBPPerformanceSyncMode.BACKFILL
    assert first.status is GBPPerformanceSyncStatus.SUCCEEDED
    assert (first.window.start, first.window.end) == (date(2025, 4, 5), YESTERDAY)
    # Google is never asked for more than half a year at once, and the chunks tile the window.
    ranges = [(start, end) for _, start, end in google.daily_calls]
    assert ranges[0][0] == first.window.start and ranges[-1][1] == first.window.end
    assert all((end - start).days < 186 for start, end in ranges)
    assert all(b[0] == a[1] + timedelta(days=1) for a, b in zip(ranges, ranges[1:], strict=False))
    assert {name for name, _, _ in google.daily_calls} == {"locations/555"}
    # Search terms: every completed month in the window, never the month still running.
    months = [month for _, month in google.keyword_calls]
    assert months[0] == date(2025, 4, 1) and months[-1] == date(2026, 9, 1)
    assert len(months) == 18
    days = (first.window.end - first.window.start).days + 1
    assert len(await metric_rows(gbp_session_factory, organization_id, IMPRESSION)) == days

    google.daily_calls.clear()
    google.keyword_calls.clear()
    second = await run_sync(
        gbp_session_factory, service(google), organization_id, gbp_id, now=NOW + timedelta(days=1)
    )

    assert second.window.mode is GBPPerformanceSyncMode.RESYNC
    assert (second.window.start, second.window.end) == (TODAY - timedelta(days=9), TODAY)
    assert [(s, e) for _, s, e in google.daily_calls] == [(second.window.start, second.window.end)]
    assert [m for _, m in google.keyword_calls] == [date(2026, 8, 1), date(2026, 9, 1)]


@pytest.mark.integration
@pytest.mark.anyio
async def test_resync_revises_recent_days_in_place_and_a_repeat_is_idempotent(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()
    await run_sync(gbp_session_factory, service(google), organization_id, gbp_id)
    before = await metric_rows(gbp_session_factory, organization_id, IMPRESSION)
    old_day = date(2026, 9, 1)

    # Google revises the last days upward on the next day's pass.
    google.value_for = lambda metric, day: 50 if day >= TODAY - timedelta(days=3) else 1
    now = NOW + timedelta(days=1)
    await run_sync(gbp_session_factory, service(google), organization_id, gbp_id, now=now)
    after = await metric_rows(gbp_session_factory, organization_id, IMPRESSION)

    revised = {day for day, value in after.items() if value == 50}
    assert revised == {TODAY - timedelta(days=3) + timedelta(days=i) for i in range(4)}
    assert after[old_day] == before[old_day] == 1
    assert len(after) == len(before) + 1  # one new day (today), no duplicates

    snapshot = dict(after)
    await run_sync(gbp_session_factory, service(google), organization_id, gbp_id, now=now)
    assert await metric_rows(gbp_session_factory, organization_id, IMPRESSION) == snapshot
    async with gbp_session_factory() as session:
        duplicates = await session.scalar(
            text(
                "SELECT count(*) FROM (SELECT 1 FROM gbp_performance_daily_metrics "
                "GROUP BY organization_id, gbp_location_id, metric, metric_date "
                "HAVING count(*) > 1) d"
            )
        )
    assert duplicates == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_threshold_keywords_are_stored_as_thresholds_and_revised_to_values(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()
    august = date(2026, 8, 1)
    google.keywords = {
        august: [
            KeywordImpressionPoint("pizza near me", 812, None),
            KeywordImpressionPoint("gluten free pizza", None, 15),
        ]
    }
    await run_sync(gbp_session_factory, service(google), organization_id, gbp_id)

    async def stored() -> dict[str, tuple[int | None, int | None]]:
        async with gbp_session_factory() as session:
            rows = await session.execute(
                select(
                    GBPPerformanceKeywordImpression.keyword,
                    GBPPerformanceKeywordImpression.value,
                    GBPPerformanceKeywordImpression.threshold,
                ).where(GBPPerformanceKeywordImpression.month == august)
            )
            return {keyword: (value, threshold) for keyword, value, threshold in rows}

    assert await stored() == {"pizza near me": (812, None), "gluten free pizza": (None, 15)}

    # Next month's pass learns the real number: the threshold gives way to a value.
    google.keywords = {august: [KeywordImpressionPoint("gluten free pizza", 22, None)]}
    await run_sync(
        gbp_session_factory, service(google), organization_id, gbp_id, now=NOW + timedelta(days=1)
    )
    assert (await stored())["gluten free pizza"] == (22, None)

    # A row is a value or a threshold, never both and never neither.
    async with gbp_session_factory() as session:
        session.add(
            GBPPerformanceKeywordImpression(
                organization_id=organization_id,
                gbp_location_id=gbp_id,
                month=date(2026, 7, 1),
                keyword="both set",
                value=1,
                threshold=15,
                sync_run_id=await session.scalar(select(GBPPerformanceSyncRun.id).limit(1)),
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_provider_failure_writes_nothing_and_keeps_the_previous_data(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()
    await run_sync(gbp_session_factory, service(google), organization_id, gbp_id)
    before = await metric_rows(gbp_session_factory, organization_id, IMPRESSION)

    google.value_for = lambda metric, day: 999
    google.daily_error = GBPPerformanceProviderError(
        GBPPerformanceFailureCode.PROVIDER_RATE_LIMITED
    )
    with pytest.raises(GBPPerformanceSyncError) as raised:
        await run_sync(
            gbp_session_factory,
            service(google),
            organization_id,
            gbp_id,
            now=NOW + timedelta(days=1),
        )

    assert raised.value.code is GBPPerformanceFailureCode.PROVIDER_RATE_LIMITED
    assert await metric_rows(gbp_session_factory, organization_id, IMPRESSION) == before
    async with gbp_session_factory() as session:
        failed = await session.scalar(
            select(GBPPerformanceSyncRun).where(
                GBPPerformanceSyncRun.status == GBPPerformanceSyncStatus.FAILED.value
            )
        )
        audited = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.event_type == "gbp.performance.synced",
                AuditEvent.error_code == "GBP_PERFORMANCE_RATE_LIMITED",
            )
        )
    assert failed is not None and failed.failure_code == "GBP_PERFORMANCE_RATE_LIMITED"
    assert audited == 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_failed_first_run_is_retried_as_a_backfill(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()
    google.daily_error = GBPPerformanceProviderError(GBPPerformanceFailureCode.PROVIDER_UNAVAILABLE)
    with pytest.raises(GBPPerformanceSyncError):
        await run_sync(gbp_session_factory, service(google), organization_id, gbp_id)

    google.daily_error = None
    retry = await run_sync(
        gbp_session_factory, service(google), organization_id, gbp_id, now=NOW + timedelta(days=1)
    )

    assert retry.window.mode is GBPPerformanceSyncMode.BACKFILL


@pytest.mark.integration
@pytest.mark.anyio
async def test_keywords_unavailable_keeps_the_daily_metrics_and_marks_the_run_partial(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()
    google.keyword_error = GBPPerformanceProviderError(
        GBPPerformanceFailureCode.PROVIDER_UNAVAILABLE
    )

    result = await run_sync(gbp_session_factory, service(google), organization_id, gbp_id)

    assert result.status is GBPPerformanceSyncStatus.PARTIAL
    assert result.failure_code is GBPPerformanceFailureCode.PROVIDER_UNAVAILABLE
    assert len(await metric_rows(gbp_session_factory, organization_id, IMPRESSION)) > 0
    # A partial backfill is not a finished backfill: the next run goes back again.
    again = await run_sync(
        gbp_session_factory, service(google), organization_id, gbp_id, now=NOW + timedelta(days=1)
    )
    assert again.window.mode is GBPPerformanceSyncMode.BACKFILL


@pytest.mark.integration
@pytest.mark.anyio
async def test_reconnect_required_is_typed_and_recorded_through_the_connection_service(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()

    # The stored credential is already known to be dead.
    with pytest.raises(GBPPerformanceSyncError) as dead:
        await run_sync(
            gbp_session_factory,
            service(google, FakeConnection(plan=IntegrationReconnectRequiredError())),
            organization_id,
            gbp_id,
        )
    assert dead.value.code is GBPPerformanceFailureCode.RECONNECT_REQUIRED

    # Google rejects the refresh token: the connection is flagged for reconnect.
    rejecting = FakeConnection(plan=TokenRefreshPlan(access_token=None, refresh_token="r"))
    rejecting.refresh_error = IntegrationTokenRejectedError()
    with pytest.raises(GBPPerformanceSyncError) as rejected:
        await run_sync(gbp_session_factory, service(google, rejecting), organization_id, gbp_id)

    assert rejected.value.code is GBPPerformanceFailureCode.RECONNECT_REQUIRED
    assert not GBPPerformanceFailureCode.RECONNECT_REQUIRED.retryable
    assert google.daily_calls == []
    async with gbp_session_factory() as session:
        status = await session.scalar(
            select(IntegrationConnection.status).where(
                IntegrationConnection.organization_id == organization_id
            )
        )
        run = await session.scalar(select(GBPPerformanceSyncRun))
    assert status == "reconnect_required"
    assert run is not None and run.failure_code == "INTEGRATION_RECONNECT_REQUIRED"


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_connection_without_the_business_scope_fails_with_scope_required(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    async with gbp_session_factory.begin() as session:
        connection = await session.scalar(select(IntegrationConnection))
        assert connection is not None
        connection.granted_capabilities = ["https://www.googleapis.com/auth/webmasters.readonly"]

    with pytest.raises(GBPPerformanceSyncError) as raised:
        await run_sync(gbp_session_factory, service(FakeGoogle()), organization_id, gbp_id)

    assert raised.value.code is GBPPerformanceFailureCode.SCOPE_REQUIRED


@pytest.mark.integration
@pytest.mark.anyio
async def test_tenant_isolation_in_sync_resolution_and_reads(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_a, gbp_a, platform_a = await seed_client(gbp_session_factory, "Alpha")
    org_b, gbp_b, platform_b = await seed_client(gbp_session_factory, "Bravo")
    google = FakeGoogle()
    google.value_for = lambda metric, day: 7
    await run_sync(gbp_session_factory, service(google), org_a, gbp_a)

    # B cannot sync, resolve or read A's location by naming A's ids.
    with pytest.raises(GBPPerformanceSyncError) as sync:
        await run_sync(gbp_session_factory, service(google), org_b, gbp_a)
    assert sync.value.code is GBPPerformanceFailureCode.LOCATION_NOT_FOUND
    async with gbp_session_factory() as session:
        for gbp_arg, platform_arg in ((gbp_a, None), (None, platform_a)):
            with pytest.raises(GBPPerformanceSyncError) as resolve:
                await resolve_gbp_location(
                    session, org_b, gbp_location_id=gbp_arg, platform_location_id=platform_arg
                )
            assert resolve.value.code is GBPPerformanceFailureCode.LOCATION_NOT_FOUND
        leaked = await read_performance(
            session, org_b, [gbp_a], PerformancePeriod.LAST_28_DAYS, now=NOW
        )
        own = await read_performance(
            session, org_a, [gbp_a], PerformancePeriod.LAST_28_DAYS, now=NOW
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(GBPPerformanceDailyMetric)
                .where(GBPPerformanceDailyMetric.organization_id == org_b)
            )
        ) == 0
    assert leaked.profile_views.current.value is None
    assert leaked.profile_views.current.availability is GBPPerformanceAvailability.NOT_SYNCED
    assert own.profile_views.current.value == 28 * 7
    del platform_b, gbp_b

    # The composite foreign key refuses a row that names A's location under B's organization.
    async with gbp_session_factory() as session:
        run_id = await session.scalar(select(GBPPerformanceSyncRun.id))
        session.add(
            GBPPerformanceDailyMetric(
                organization_id=org_b,
                gbp_location_id=gbp_a,
                metric=IMPRESSION.value,
                metric_date=YESTERDAY,
                value=1,
                sync_run_id=run_id,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.integration
@pytest.mark.anyio
async def test_read_totals_comparison_profile_views_and_top_terms(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    google = FakeGoogle()
    last_28 = TODAY - timedelta(days=28)
    google.value_for = lambda metric, day: (
        (10 if day >= last_28 else 5) if metric is IMPRESSION else 2
    )
    september = date(2026, 9, 1)
    google.keywords = {
        september: [
            KeywordImpressionPoint("small", 3, None),
            KeywordImpressionPoint("big", 900, None),
            KeywordImpressionPoint("withheld", None, 15),
        ]
    }
    await run_sync(gbp_session_factory, service(google), organization_id, gbp_id)

    async with gbp_session_factory() as session:
        read = await read_performance(
            session, organization_id, [gbp_id], PerformancePeriod.LAST_28_DAYS, now=NOW
        )
        month = await read_performance(
            session, organization_id, [gbp_id], PerformancePeriod.MONTH, month=september, now=NOW
        )

    assert (read.windows.current.start, read.windows.current.end) == (
        YESTERDAY - timedelta(days=27),
        YESTERDAY,
    )
    assert read.windows.previous.end == read.windows.current.start - timedelta(days=1)
    assert read.windows.previous.days == 28
    impressions = read.metrics[IMPRESSION]
    assert impressions.current.value == 28 * 10
    assert (impressions.previous.value, impressions.change) == (28 * 5, 28 * 5)
    assert impressions.current.availability is GBPPerformanceAvailability.AVAILABLE
    # Profile views are the four impression metrics; only one is modelled by the fake, so the
    # other three are missing, which makes the total partial rather than a confident number.
    assert read.profile_views.current.availability is GBPPerformanceAvailability.PARTIAL
    assert read.profile_views.current.value == 28 * 10
    assert read.profile_views.change is None
    # A metric Google never returned is "no data", never 0.
    assert read.metrics[GBPPerformanceMetric.BUSINESS_BOOKINGS].current.value is None
    assert (
        read.metrics[GBPPerformanceMetric.BUSINESS_BOOKINGS].current.availability
        is GBPPerformanceAvailability.NO_DATA
    )
    # Search terms: exact counts first, bounded ones after, with the bound kept.
    assert [
        (t.keyword, t.value, t.below_threshold, t.is_exact) for t in month.search_terms.terms
    ] == [
        ("big", 900, None, True),
        ("small", 3, None, True),
        ("withheld", None, 15, False),
    ]
    assert month.search_terms.month == september
    assert month.windows.current.start == september and month.windows.current.end == date(
        2026, 9, 30
    )
    assert month.windows.previous.start == date(2026, 8, 1) and month.windows.previous.days == 30
    assert read.source.last_status is GBPPerformanceSyncStatus.SUCCEEDED
    assert read.source.last_synced_at is not None


@pytest.mark.integration
@pytest.mark.anyio
async def test_unsynced_and_unmapped_locations_never_read_as_zero(
    gbp_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    organization_id, gbp_id, _ = await seed_client(gbp_session_factory)
    async with gbp_session_factory() as session:
        unsynced = await read_performance(
            session, organization_id, [gbp_id], PerformancePeriod.LAST_7_DAYS, now=NOW
        )
        unmapped = await read_performance(
            session, organization_id, [], PerformancePeriod.LAST_7_DAYS, now=NOW
        )

    assert unsynced.availability is GBPPerformanceAvailability.NOT_SYNCED
    assert unsynced.profile_views.current.value is None
    assert all(m.current.value is None for m in unsynced.metrics.values())
    assert unsynced.search_terms.availability is GBPPerformanceAvailability.NOT_SYNCED
    assert unmapped.availability is GBPPerformanceAvailability.NOT_CONNECTED
    assert unmapped.profile_views.current.value is None
    assert unmapped.search_terms.terms == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_the_workflow_handler_maps_failures_to_typed_outcomes(
    gbp_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.api.app.execution import provider_sync_handlers

    organization_id, _, platform_id = await seed_client(gbp_session_factory)
    outcomes: dict[str, Any] = {}

    def fake_service(error: Exception | None, status: GBPPerformanceSyncStatus) -> type:
        class Fake:
            async def sync_location(self, *args: Any, **kwargs: Any) -> Any:
                if error is not None:
                    raise error
                from apps.api.app.products.gbp.performance_service import SyncResult, SyncWindow

                return SyncResult(
                    uuid4(),
                    status,
                    SyncWindow(GBPPerformanceSyncMode.RESYNC, TODAY, TODAY),
                    0,
                    0,
                    GBPPerformanceFailureCode.PROVIDER_UNAVAILABLE
                    if status is GBPPerformanceSyncStatus.PARTIAL
                    else None,
                )

        return Fake

    async def call(location_id: UUID | None, input_document: dict[str, Any] | None = None) -> Any:
        async with gbp_session_factory() as session:
            return await handle_gbp_performance_sync(
                session,
                organization_id=organization_id,
                location_id=location_id,
                input_document=input_document or {},
                correlation_id="test",
                workflow_run_id=uuid4(),
            )

    scripted = [
        ("ok", None, GBPPerformanceSyncStatus.SUCCEEDED),
        ("partial", None, GBPPerformanceSyncStatus.PARTIAL),
        (
            "reconnect",
            GBPPerformanceSyncError(GBPPerformanceFailureCode.RECONNECT_REQUIRED),
            GBPPerformanceSyncStatus.FAILED,
        ),
        (
            "rate",
            GBPPerformanceSyncError(GBPPerformanceFailureCode.PROVIDER_RATE_LIMITED),
            GBPPerformanceSyncStatus.FAILED,
        ),
        ("crash", RuntimeError("boom"), GBPPerformanceSyncStatus.FAILED),
    ]
    for label, error, status in scripted:
        monkeypatch.setattr(
            provider_sync_handlers, "GBPPerformanceService", fake_service(error, status)
        )
        outcomes[label] = await call(platform_id)

    assert outcomes["ok"].result == "succeeded"
    assert (outcomes["partial"].result, outcomes["partial"].safe_error) == (
        "retryable_failure",
        "GBP_PERFORMANCE_PROVIDER_UNAVAILABLE",
    )
    assert (outcomes["reconnect"].result, outcomes["reconnect"].safe_error) == (
        "permanent_failure",
        "INTEGRATION_RECONNECT_REQUIRED",
    )
    assert outcomes["rate"].result == "retryable_failure"
    assert (outcomes["crash"].result, outcomes["crash"].safe_error) == (
        "retryable_failure",
        "GBP_PERFORMANCE_SYNC_FAILED",
    )
    unmapped = await call(uuid4())
    assert (unmapped.result, unmapped.safe_error) == ("permanent_failure", "GBP_LOCATION_NOT_FOUND")
    missing = await call(None)
    assert (missing.result, missing.safe_error) == ("permanent_failure", "LOCATION_ID_MISSING")
    invalid = await call(None, {"gbp_location_id": "not-a-uuid"})
    assert (invalid.result, invalid.safe_error) == ("permanent_failure", "LOCATION_ID_INVALID")
