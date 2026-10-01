"""Shared contracts: fixture implementations and real parsers with recorded HTTP."""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from apps.api.app.products.analytics.adapter import GoogleAnalyticsAdminAdapter
from apps.api.app.products.gbp.adapter import GoogleBusinessProfileAdapter
from apps.api.app.products.seo.search_console_adapter import GoogleSearchConsoleAdapter
from apps.api.app.staging.provider_fixtures import (
    FixtureAnalyticsAdapter,
    FixtureGBPAdapter,
    FixtureSearchConsoleAdapter,
)

RECORDS = json.loads(Path("tests/fixtures/providers/recorded_responses.json").read_text())


def recorded_client(scenario: str) -> httpx.AsyncClient:
    def respond(request: httpx.Request) -> httpx.Response:
        if scenario in {"expired", "rate_limited", "unavailable"}:
            status = {"expired": 401, "rate_limited": 429, "unavailable": 503}[scenario]
            return httpx.Response(
                status, json={"error": {"code": status}}, headers={"Retry-After": "60"}
            )
        if scenario == "timeout":
            raise httpx.ReadTimeout("Recorded timeout", request=request)
        path = request.url.path
        if path.endswith("/sites"):
            body = RECORDS["gsc_sites"] if scenario != "missing_mapping" else {"siteEntry": []}
        elif path.endswith("/searchAnalytics/query"):
            body = RECORDS["gsc_query"] if scenario != "partial" else {"rows": "incomplete"}
        elif path.endswith("/accountSummaries"):
            body = (
                RECORDS["ga4_accounts"]
                if scenario != "missing_mapping"
                else {"accountSummaries": []}
            )
        elif path.endswith(":runReport"):
            body = json.loads(json.dumps(RECORDS["ga4_report"]))
            if scenario == "partial":
                body["metricHeaders"].pop()
                body["rows"][0]["metricValues"].pop()
        elif path.endswith("/accounts"):
            body = RECORDS["gbp_accounts"] if scenario != "missing_mapping" else {"accounts": []}
        elif path.endswith("/locations"):
            body = RECORDS["gbp_locations"]
        else:
            body = dict(RECORDS["gbp_location"])
            if scenario == "partial":
                body.pop("profile")
        return httpx.Response(200, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(respond))


def adapters(implementation: str, scenario: str) -> tuple[Any, Any, Any]:
    if implementation == "fixture":
        return FixtureSearchConsoleAdapter(), FixtureAnalyticsAdapter(), FixtureGBPAdapter()

    def factory() -> httpx.AsyncClient:
        return recorded_client(scenario)

    return (
        GoogleSearchConsoleAdapter(http_client_factory=factory),
        GoogleAnalyticsAdminAdapter(http_client_factory=factory),
        GoogleBusinessProfileAdapter(http_client_factory=factory),
    )


@pytest.mark.parametrize("implementation", ["fixture", "recorded"])
@pytest.mark.parametrize(
    "scenario",
    ["healthy", "expired", "rate_limited", "unavailable", "timeout", "partial", "missing_mapping"],
)
def test_shared_contract(implementation: str, scenario: str) -> None:
    async def run() -> None:
        gsc, ga4, gbp = adapters(implementation, scenario)
        token = (
            f"fixture:{scenario}:synthetic" if implementation == "fixture" else "sanitized-token"
        )
        if scenario in {"expired", "rate_limited", "unavailable", "timeout"}:
            for call in (gsc.list_sites, ga4.list_account_summaries, gbp.list_accounts):
                with pytest.raises((RuntimeError, httpx.HTTPError)):
                    await call(token)
            return
        sites = await gsc.list_sites(token)
        properties = await ga4.list_account_summaries(token)
        accounts = await gbp.list_accounts(token)
        if scenario == "missing_mapping":
            assert sites == properties == accounts == []
            return
        assert sites[0].external_property_id == "sc-domain:synthetic.invalid"
        assert properties[0].property_number == "1001"
        assert accounts[0]["name"] == "accounts/1001"
        args = dict(start_date="2026-09-01", end_date="2026-09-28")
        if scenario == "partial":
            with pytest.raises(RuntimeError, match="invalid Search Console analytics page"):
                await gsc.query_search_analytics(token, sites[0].external_property_id, **args)
        else:
            rows = await gsc.query_search_analytics(token, sites[0].external_property_id, **args)
            assert rows[0].clicks == 8 and rows[0].impressions == 80
        if scenario == "partial":
            with pytest.raises(RuntimeError, match="incomplete Analytics report headers"):
                await ga4.run_report(token, "1001", **args)
        else:
            rows = await ga4.run_report(token, "1001", **args)
            assert rows[0].metric_values["sessions"] == 12
            assert "conversions" in rows[0].metric_values
        locations = await gbp.list_locations(token, "accounts/1001")
        profile = await gbp.get_location(token, locations[0]["name"])
        assert ("profile" in profile) == (scenario != "partial")

    asyncio.run(run())


def test_fixture_never_falls_back_to_live_http() -> None:
    async def run() -> None:
        adapter = FixtureSearchConsoleAdapter()
        with pytest.raises(ValueError, match="live credentials"):
            await adapter.list_sites("not-a-fixture")

    asyncio.run(run())
