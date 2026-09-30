"""Syncs must never hold a database transaction open while Google is being called.

The probe runs inside every provider call (report requests and the token refresh)
and asks PostgreSQL itself, over a separate connection, whether any session is
sitting `idle in transaction`. That is the real failure mode -- a pinned connection
and its locks for as long as Google takes to answer -- not a proxy for it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.execution import provider_sync_handlers
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.errors import IntegrationReconnectRequiredError
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.seo.models import SEOSearchObservation
from apps.api.app.products.seo.search_console_adapter import (
    DiscoveredSearchProperty,
    SearchAnalyticsRow,
)
from apps.api.app.products.seo.search_console_service import SearchConsoleService

from .scope import ProbedConnectionService, TransactionProbe
from .test_search_console import (
    FakeSearchConsoleAdapter,
    make_connected_google_connection,
    make_organization,
    make_page,
    make_settings,
    make_website,
    token_handler,
)

GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


class ProbedSearchConsoleAdapter(FakeSearchConsoleAdapter):
    def __init__(self, probe: TransactionProbe, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.probe = probe

    async def query_search_analytics(
        self,
        access_token: str,
        site_url: str,
        *,
        start_date: str,
        end_date: str,
        dimensions: Sequence[str] = ("query",),
        row_limit: int = 1000,
    ) -> list[SearchAnalyticsRow]:
        await self.probe.record()
        return await super().query_search_analytics(
            access_token,
            site_url,
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensions,
            row_limit=row_limit,
        )


async def seed_property(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, *, expired_token: bool
) -> tuple[UUID, UUID, UUID]:
    """A mapped property on a connected Google connection, committed."""
    async with session_factory.begin() as session:
        org = await make_organization(session)
        connection = await make_connected_google_connection(
            session, settings, org.id, http_handler=token_handler(GSC_SCOPE)
        )
        website = await make_website(session, org.id, "https://example.com/")
        page = await make_page(session, org.id, website.id, "https://example.com/service")
        service = SearchConsoleService(
            adapter=FakeSearchConsoleAdapter(
                properties=[
                    DiscoveredSearchProperty("sc-domain:example.com", "domain", "siteOwner")
                ]
            )
        )
        prop = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id="sc-domain:example.com",
            property_type="domain",
            actor_id=None,
            correlation_id="map",
        )
        assert page.id
        if expired_token:
            # After mapping (which itself needs a fresh token): the sync must refresh.
            connection.token_expires_at = datetime.now(UTC) - timedelta(hours=1)
        return org.id, prop.id, connection.id


def fake_rows(probe: TransactionProbe, **extra: Any) -> ProbedSearchConsoleAdapter:
    return ProbedSearchConsoleAdapter(
        probe,
        properties=[DiscoveredSearchProperty("sc-domain:example.com", "domain", "siteOwner")],
        summary_rows=[SearchAnalyticsRow((), 3, 40, 0.07, 6.0)],
        query_rows=[SearchAnalyticsRow(("brunch",), 1, 30, 0.03, 8.0)],
        **extra,
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_sync_holds_no_transaction_during_provider_http(
    seo_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
) -> None:
    settings = make_settings()
    org_id, property_id, _ = await seed_property(seo_session_factory, settings, expired_token=True)
    probe = TransactionProbe(postgresql_test_url)
    try:
        service = SearchConsoleService(
            adapter=fake_rows(probe), connection=ProbedConnectionService(probe)
        )
        result = await service.sync_observations(
            seo_session_factory,
            settings,
            org_id,
            property_id,
            actor_id=None,
            correlation_id="no-open-transaction",
        )
    finally:
        await probe.close()

    assert result["periods_synced"] == [7, 28, 90]
    # One token refresh plus every report request, across three periods.
    assert len(probe.open_during_provider_calls) > 10
    assert probe.open_during_provider_calls == [0] * len(probe.open_during_provider_calls)
    async with seo_session_factory() as session:
        rows = list(
            await session.scalars(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.search_property_id == property_id
                )
            )
        )
    assert rows  # and the data really was persisted afterwards


@pytest.mark.integration
@pytest.mark.anyio
async def test_failed_provider_request_leaves_previous_data_and_holds_nothing(
    seo_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
) -> None:
    settings = make_settings()
    org_id, property_id, _ = await seed_property(seo_session_factory, settings, expired_token=False)
    probe = TransactionProbe(postgresql_test_url)
    service_ok = SearchConsoleService(adapter=fake_rows(probe))
    await service_ok.sync_observations(
        seo_session_factory, settings, org_id, property_id, actor_id=None, correlation_id="good"
    )
    async with seo_session_factory() as session:
        before = len(
            list(
                await session.scalars(
                    select(SEOSearchObservation.id).where(
                        SEOSearchObservation.search_property_id == property_id
                    )
                )
            )
        )
    probe.open_during_provider_calls.clear()
    try:
        failing = fake_rows(probe, fail_on_start=set(_window_starts(datetime.now(UTC))))
        result = await SearchConsoleService(adapter=failing).sync_observations(
            seo_session_factory, settings, org_id, property_id, actor_id=None, correlation_id="bad"
        )
    finally:
        await probe.close()

    assert result["periods_synced"] == []
    assert probe.open_during_provider_calls and set(probe.open_during_provider_calls) == {0}
    async with seo_session_factory() as session:
        after = len(
            list(
                await session.scalars(
                    select(SEOSearchObservation.id).where(
                        SEOSearchObservation.search_property_id == property_id
                    )
                )
            )
        )
    assert after == before  # the previous successful dataset is untouched


def _window_starts(now: datetime) -> list[str]:
    from apps.api.app.reporting_periods import (
        GSC_SYNC_TAIL_EXCLUSION_DAYS,
        VALID_REPORTING_PERIODS,
        provider_start_date,
        reporting_window,
    )

    return [
        provider_start_date(reporting_window(now, days, GSC_SYNC_TAIL_EXCLUSION_DAYS)[0])
        for days in VALID_REPORTING_PERIODS
    ]


@pytest.mark.integration
@pytest.mark.anyio
async def test_rejected_refresh_persists_reconnect_required_and_raises(
    seo_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
) -> None:
    settings = make_settings()
    org_id, property_id, connection_id = await seed_property(
        seo_session_factory, settings, expired_token=True
    )
    probe = TransactionProbe(postgresql_test_url)
    try:
        service = SearchConsoleService(
            adapter=fake_rows(probe), connection=ProbedConnectionService(probe, reject=True)
        )
        with pytest.raises(IntegrationReconnectRequiredError):
            await service.sync_observations(
                seo_session_factory,
                settings,
                org_id,
                property_id,
                actor_id=None,
                correlation_id="reject",
            )
    finally:
        await probe.close()

    assert probe.open_during_provider_calls == [0]
    # The status survived the error unwinding the sync (it is not rolled back with it).
    async with seo_session_factory() as session:
        connection = await session.get(IntegrationConnection, connection_id)
        assert connection is not None and connection.status == "reconnect_required"


@pytest.mark.integration
@pytest.mark.anyio
async def test_worker_handler_runs_the_sync_off_the_request_path(
    seo_session_factory: async_sessionmaker[AsyncSession],
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    org_id, property_id, _ = await seed_property(seo_session_factory, settings, expired_token=False)
    probe = TransactionProbe(postgresql_test_url)
    monkeypatch.setattr(provider_sync_handlers, "Settings", lambda: settings)
    probed = fake_rows(probe)
    monkeypatch.setattr(
        provider_sync_handlers,
        "SearchConsoleService",
        lambda: SearchConsoleService(adapter=probed),
    )
    try:
        async with seo_session_factory() as session:
            outcome = await provider_sync_handlers.handle_search_console_sync(
                session,
                organization_id=org_id,
                location_id=None,
                input_document={"search_property_id": str(property_id), "days": 28},
                correlation_id="handler",
                workflow_run_id=uuid4(),
            )
            # The handler's own session is idle too: it never pinned a transaction.
            assert not session.in_transaction()
    finally:
        await probe.close()

    assert outcome.result == "succeeded"
    assert outcome.result_reference == f"seo-search-property:{property_id}"
    assert set(probe.open_during_provider_calls) == {0}


@pytest.mark.integration
@pytest.mark.anyio
async def test_worker_handler_maps_failures_to_typed_codes(
    seo_session_factory: async_sessionmaker[AsyncSession],
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    org_id, property_id, _ = await seed_property(seo_session_factory, settings, expired_token=True)
    probe = TransactionProbe(postgresql_test_url)
    monkeypatch.setattr(provider_sync_handlers, "Settings", lambda: settings)
    monkeypatch.setattr(
        provider_sync_handlers,
        "SearchConsoleService",
        lambda: SearchConsoleService(
            adapter=fake_rows(probe), connection=ProbedConnectionService(probe, reject=True)
        ),
    )

    async def run(document: dict[str, object]) -> Any:
        async with seo_session_factory() as session:
            return await provider_sync_handlers.handle_search_console_sync(
                session,
                organization_id=org_id,
                location_id=None,
                input_document=document,
                correlation_id="handler",
                workflow_run_id=uuid4(),
            )

    try:
        reconnect = await run({"search_property_id": str(property_id)})
        assert (reconnect.result, reconnect.safe_error) == (
            "permanent_failure",
            "INTEGRATION_RECONNECT_REQUIRED",
        )
        assert (await run({"search_property_id": "not-a-uuid"})).safe_error == (
            "SEARCH_PROPERTY_ID_INVALID"
        )
        assert (await run({"search_property_id": str(uuid4())})).safe_error == (
            "SEARCH_PROPERTY_NOT_FOUND"
        )
    finally:
        await probe.close()


@pytest.mark.integration
@pytest.mark.anyio
async def test_sync_route_enqueues_and_returns_without_calling_google(
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The request only queues `seo.sync_search_console`; it makes no provider call."""
    from types import SimpleNamespace
    from typing import cast

    from starlette.requests import Request

    from apps.api.app.routes import seo as seo_routes

    settings = make_settings()
    org_id, property_id, _ = await seed_property(seo_session_factory, settings, expired_token=False)
    async with seo_session_factory() as session:
        prop = await seo_routes.search_console.load_property(session, org_id, property_id)
        website_id = prop.website_id

    class NoGoogle(FakeSearchConsoleAdapter):
        async def query_search_analytics(
            self, *args: Any, **kwargs: Any
        ) -> list[SearchAnalyticsRow]:
            raise AssertionError("the request path must not call Google")

    monkeypatch.setattr(seo_routes.search_console, "adapter", NoGoogle(properties=[]))
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
    async with seo_session_factory.begin() as session:
        response = await seo_routes.sync_search_console(
            request,
            org_id,
            website_id,
            property_id,
            session,
            principal,
            cast(Any, None),
            None,
        )
    data = cast(dict[str, Any], response["data"])
    assert data["workflow_key"] == "seo.sync_search_console"
    assert data["status"] in {"queued", "pending"}

    async with seo_session_factory() as session:
        run = await session.get(WorkflowRun, UUID(data["workflow_run_id"]))
        assert run is not None
        assert run.input_document["search_property_id"] == str(property_id)
        assert run.status in {"queued", "pending"}
        _ = ExecutionService  # the run was created through the governed service


@pytest.mark.integration
@pytest.mark.anyio
async def test_probe_control_sees_a_transaction_that_is_held_open(
    seo_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
) -> None:
    """The regression tests above are only meaningful if the probe can see a leak."""
    probe = TransactionProbe(postgresql_test_url)
    try:
        async with seo_session_factory() as session:
            await session.execute(text("SELECT 1"))  # autobegin: now idle in transaction
            await probe.record()
        await probe.record()  # closed again
    finally:
        await probe.close()

    assert probe.open_during_provider_calls == [1, 0]
