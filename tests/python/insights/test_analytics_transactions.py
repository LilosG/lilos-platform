"""GA4 sync must never hold a database transaction open while Google is being called.

Same probe as the Search Console suite: PostgreSQL is asked, over a separate
connection, for `idle in transaction` sessions at the moment of every provider call
-- the token refresh, each reporting period's reports, and the organic landing-page
reports that run as a second stage.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from seo.scope import ProbedConnectionService, TransactionProbe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from apps.api.app.config import Settings
from apps.api.app.execution import provider_sync_handlers
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.insights.models import MetricObservation
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.analytics.adapter import AnalyticsReportRow
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.routes import insights as insights_routes

from .test_analytics import (
    FakeAnalyticsAdapter,
    PageFakeAnalyticsAdapter,
    make_connected_connection,
    make_organization,
    make_seo_page,
    make_settings,
    make_website,
)

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


class ProbedAnalyticsAdapter(PageFakeAnalyticsAdapter):
    def __init__(self, probe: TransactionProbe, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.probe = probe

    async def run_report(
        self,
        access_token: str,
        property_number: str,
        *,
        start_date: str,
        end_date: str,
        metrics: Sequence[str] = ("sessions", "totalUsers", "screenPageViews", "conversions"),
        dimensions: Sequence[str] = (),
    ) -> list[AnalyticsReportRow]:
        await self.probe.record()
        return await super().run_report(
            access_token,
            property_number,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            dimensions=dimensions,
        )

    async def organic_page_report_compatible(
        self, access_token: str, property_number: str, *, hostname: str
    ) -> bool:
        await self.probe.record()
        return await super().organic_page_report_compatible(
            access_token, property_number, hostname=hostname
        )

    async def run_organic_page_report(
        self,
        access_token: str,
        property_number: str,
        *,
        start_date: str,
        end_date: str,
        hostname: str,
    ) -> list[AnalyticsReportRow]:
        await self.probe.record()
        return await super().run_organic_page_report(
            access_token,
            property_number,
            start_date=start_date,
            end_date=end_date,
            hostname=hostname,
        )


async def seed_property(
    factory: async_sessionmaker[AsyncSession], settings: Settings, *, expired_token: bool
) -> tuple[UUID, UUID, UUID]:
    """(organization_id, analytics_property_id, connection_id), committed."""
    async with factory.begin() as session:
        org = await make_organization(session)
        await make_connected_connection(session, settings, org.id, ANALYTICS_SCOPE)
        website = await make_website(session, org.id, "https://example.com/")
        await make_seo_page(session, org.id, website.id)
        prop = await AnalyticsService(adapter=FakeAnalyticsAdapter(properties=[])).map_property(
            session,
            settings,
            org.id,
            external_property_id="properties/123",
            property_number="123",
            display_name="Example",
            website_id=website.id,
            actor_id=None,
            correlation_id="map",
        )
        connection = await session.scalar(
            select(IntegrationConnection).where(IntegrationConnection.organization_id == org.id)
        )
        assert connection is not None
        if expired_token:
            connection.token_expires_at = datetime.now(UTC) - timedelta(hours=1)
        return org.id, prop.id, connection.id


@pytest.mark.integration
@pytest.mark.anyio
async def test_analytics_sync_holds_no_transaction_during_provider_http(
    insights_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
) -> None:
    settings = make_settings()
    org_id, property_id, _ = await seed_property(
        insights_session_factory, settings, expired_token=True
    )
    probe = TransactionProbe(postgresql_test_url)
    try:
        service = AnalyticsService(
            adapter=ProbedAnalyticsAdapter(probe), connection=ProbedConnectionService(probe)
        )
        result = await service.sync_metrics(
            insights_session_factory,
            settings,
            org_id,
            property_id,
            actor_id=None,
            correlation_id="no-open-transaction",
        )
    finally:
        await probe.close()

    assert result["periods_synced"] == [7, 28, 90]
    # Token refresh + 3 reports x 3 periods + the compatibility check + 3 organic reports.
    assert len(probe.open_during_provider_calls) == 1 + 9 + 1 + 3
    assert set(probe.open_during_provider_calls) == {0}
    async with insights_session_factory() as session:
        observations = list(await session.scalars(select(MetricObservation.id)))
        prop = await session.get(AnalyticsProperty, property_id)
    assert observations
    assert prop is not None and prop.page_evidence_status == "observed"


@pytest.mark.integration
@pytest.mark.anyio
async def test_analytics_failed_period_holds_nothing_and_preserves_data(
    insights_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
) -> None:
    from apps.api.app.reporting_periods import (
        GA4_SYNC_TAIL_EXCLUSION_DAYS,
        VALID_REPORTING_PERIODS,
        provider_start_date,
        reporting_window,
    )

    settings = make_settings()
    org_id, property_id, _ = await seed_property(
        insights_session_factory, settings, expired_token=False
    )
    probe = TransactionProbe(postgresql_test_url)

    async def observation_count() -> int:
        async with insights_session_factory() as session:
            return len(list(await session.scalars(select(MetricObservation.id))))

    try:
        await AnalyticsService(adapter=ProbedAnalyticsAdapter(probe)).sync_metrics(
            insights_session_factory,
            settings,
            org_id,
            property_id,
            actor_id=None,
            correlation_id="a",
        )
        before = await observation_count()
        probe.open_during_provider_calls.clear()
        now = datetime.now(UTC)
        failing = ProbedAnalyticsAdapter(probe)
        failing._fail_on_start = {
            provider_start_date(reporting_window(now, days, GA4_SYNC_TAIL_EXCLUSION_DAYS)[0])
            for days in VALID_REPORTING_PERIODS
        }
        result = await AnalyticsService(adapter=failing).sync_metrics(
            insights_session_factory,
            settings,
            org_id,
            property_id,
            actor_id=None,
            correlation_id="b",
        )
    finally:
        await probe.close()

    assert result["periods_synced"] == []
    assert probe.open_during_provider_calls and set(probe.open_during_provider_calls) == {0}
    assert await observation_count() == before  # the previous successful dataset is untouched


@pytest.mark.integration
@pytest.mark.anyio
async def test_analytics_handler_runs_the_sync_off_the_request_path(
    insights_session_factory: async_sessionmaker[AsyncSession],
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    org_id, property_id, _ = await seed_property(
        insights_session_factory, settings, expired_token=False
    )
    probe = TransactionProbe(postgresql_test_url)
    monkeypatch.setattr(provider_sync_handlers, "Settings", lambda: settings)
    adapter = ProbedAnalyticsAdapter(probe)
    monkeypatch.setattr(
        provider_sync_handlers, "AnalyticsService", lambda: AnalyticsService(adapter=adapter)
    )
    try:
        async with insights_session_factory() as session:
            outcome = await provider_sync_handlers.handle_analytics_sync(
                session,
                organization_id=org_id,
                location_id=None,
                input_document={"analytics_property_id": str(property_id), "days": 28},
                correlation_id="handler",
                workflow_run_id=uuid4(),
            )
            assert not session.in_transaction()
    finally:
        await probe.close()

    assert outcome.result == "succeeded"
    assert outcome.result_reference == f"analytics-property:{property_id}"
    assert set(probe.open_during_provider_calls) == {0}


@pytest.mark.integration
@pytest.mark.anyio
async def test_analytics_handler_maps_failures_to_typed_codes(
    insights_session_factory: async_sessionmaker[AsyncSession],
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    org_id, property_id, _ = await seed_property(
        insights_session_factory, settings, expired_token=True
    )
    probe = TransactionProbe(postgresql_test_url)
    monkeypatch.setattr(provider_sync_handlers, "Settings", lambda: settings)
    monkeypatch.setattr(
        provider_sync_handlers,
        "AnalyticsService",
        lambda: AnalyticsService(
            adapter=ProbedAnalyticsAdapter(probe),
            connection=ProbedConnectionService(probe, reject=True),
        ),
    )

    async def run(document: dict[str, object]) -> Any:
        async with insights_session_factory() as session:
            return await provider_sync_handlers.handle_analytics_sync(
                session,
                organization_id=org_id,
                location_id=None,
                input_document=document,
                correlation_id="handler",
                workflow_run_id=uuid4(),
            )

    try:
        reconnect = await run({"analytics_property_id": str(property_id)})
        assert (reconnect.result, reconnect.safe_error) == (
            "permanent_failure",
            "INTEGRATION_RECONNECT_REQUIRED",
        )
        assert (await run({"analytics_property_id": "nope"})).safe_error == (
            "ANALYTICS_PROPERTY_ID_INVALID"
        )
        assert (await run({"analytics_property_id": str(uuid4())})).safe_error == (
            "ANALYTICS_PROPERTY_NOT_FOUND"
        )
    finally:
        await probe.close()


@pytest.mark.integration
@pytest.mark.anyio
async def test_sync_route_enqueues_and_returns_without_calling_google(
    insights_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    settings = make_settings()
    org_id, property_id, _ = await seed_property(
        insights_session_factory, settings, expired_token=False
    )

    class NoGoogle(FakeAnalyticsAdapter):
        async def run_report(self, *args: Any, **kwargs: Any) -> list[AnalyticsReportRow]:
            raise AssertionError("the request path must not call Google")

    monkeypatch.setattr(insights_routes.analytics, "adapter", NoGoogle(properties=[]))
    request = cast(
        Request,
        SimpleNamespace(
            state=SimpleNamespace(correlation_id="route"),
            headers={},
            app=SimpleNamespace(state=SimpleNamespace()),
            url=SimpleNamespace(path="/"),
        ),
    )
    principal = cast(Any, SimpleNamespace(platform_user_id=None))
    async with insights_session_factory.begin() as session:
        response = await insights_routes.sync_analytics(
            request, org_id, property_id, session, principal, cast(Any, None), None
        )
    data = cast(dict[str, Any], response["data"])
    assert data["workflow_key"] == "insights.sync_analytics"

    async with insights_session_factory() as session:
        run = await session.get(WorkflowRun, UUID(data["workflow_run_id"]))
        assert run is not None
        assert run.input_document["analytics_property_id"] == str(property_id)
