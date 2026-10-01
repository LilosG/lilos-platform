"""Deterministic provider implementations using the canonical parsers and protocols.

No live HTTP: the transport refuses unrecognized routes, resources and all writes.
Fixture tokens are scenario references, never credentials or production fallbacks.
"""

import json
from enum import StrEnum
from typing import Any
from urllib.parse import unquote

import httpx

from apps.api.app.products.analytics.adapter import GoogleAnalyticsAdminAdapter
from apps.api.app.products.gbp.adapter import GoogleBusinessProfileAdapter
from apps.api.app.products.seo.search_console_adapter import GoogleSearchConsoleAdapter


class FixtureScenario(StrEnum):
    HEALTHY = "healthy"
    EXPIRED = "expired"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    PARTIAL = "partial"
    MISSING_MAPPING = "missing_mapping"


def fixture_token(reference: str) -> str:
    parts = reference.split(":")
    if len(parts) != 3 or parts[0] != "fixture" or not parts[2].replace("-", "").isalnum():
        raise ValueError("Invalid fixture reference")
    scenario = FixtureScenario(parts[1])
    if scenario is FixtureScenario.EXPIRED:
        from apps.api.app.integrations.errors import IntegrationReconnectRequiredError

        raise IntegrationReconnectRequiredError
    return reference


def fixture_response(request: httpx.Request) -> httpx.Response:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    parts = token.split(":")
    if len(parts) != 3 or parts[0] != "fixture":
        raise ValueError("Fixture transport refuses live credentials")
    _, raw_scenario, tenant = parts
    scenario = FixtureScenario(raw_scenario)
    path = unquote(request.url.path)
    if scenario is FixtureScenario.EXPIRED:
        return httpx.Response(401, json={"error": {"code": 401}})
    if scenario is FixtureScenario.TIMEOUT:
        raise httpx.ReadTimeout("Synthetic provider timeout", request=request)
    if scenario in {FixtureScenario.RATE_LIMITED, FixtureScenario.UNAVAILABLE}:
        status = 429 if scenario is FixtureScenario.RATE_LIMITED else 503
        return httpx.Response(
            status, json={"error": {"code": status}}, headers={"Retry-After": "60"}
        )
    missing = scenario is FixtureScenario.MISSING_MAPPING
    partial = scenario is FixtureScenario.PARTIAL
    body: dict[str, Any]
    if request.method == "GET" and path == "/webmasters/v3/sites":
        body = {
            "siteEntry": []
            if missing
            else [{"siteUrl": f"sc-domain:{tenant}.invalid", "permissionLevel": "siteOwner"}]
        }
    elif request.method == "POST" and path.endswith("/searchAnalytics/query"):
        if f"sc-domain:{tenant}.invalid" not in path or missing:
            return httpx.Response(404, json={"error": {"code": 404}})
        if partial:
            return httpx.Response(200, json={"rows": "incomplete"})
        document = json.loads(request.content)
        dimensions = document["dimensions"]
        keys = {
            "query": "synthetic search",
            "page": f"https://{tenant}.invalid/",
            "date": document["startDate"],
        }
        body = {
            "rows": [
                {
                    "keys": [keys[key] for key in dimensions],
                    "clicks": 8,
                    "impressions": 80,
                    "ctr": 0.1,
                    "position": 4.0,
                }
            ]
        }
        if document.get("startRow", 0):
            body = {"rows": []}
    elif request.method == "GET" and path == "/v1beta/accountSummaries":
        body = {
            "accountSummaries": []
            if missing
            else [
                {
                    "displayName": "Synthetic account",
                    "propertySummaries": [
                        {"property": "properties/1001", "displayName": "Synthetic analytics"}
                    ],
                }
            ]
        }
    elif request.method == "POST" and path.endswith(":checkCompatibility"):
        document = json.loads(request.content)
        body = {
            f"{kind}Compatibilities": [
                {f"{kind}Metadata": {"apiName": item["name"]}, "compatibility": "COMPATIBLE"}
                for item in document[f"{kind}s"]
            ]
            for kind in ("dimension", "metric")
        }
    elif request.method == "POST" and path == "/v1beta/properties/1001:runReport":
        if missing:
            return httpx.Response(404, json={"error": {"code": 404}})
        document = json.loads(request.content)
        metrics = [item["name"] for item in document["metrics"]]
        dimensions = [item["name"] for item in document.get("dimensions", [])]
        if partial:
            metrics = metrics[:-1]
        values = {
            "landingPagePlusQueryString": "/",
            "hostName": f"{tenant}.invalid",
            "sessionDefaultChannelGroup": "Organic Search",
            "date": document["dateRanges"][0]["startDate"].replace("-", ""),
        }
        body = {
            "metricHeaders": [{"name": name} for name in metrics],
            "dimensionHeaders": [{"name": name} for name in dimensions],
            "rows": [
                {
                    "metricValues": [{"value": "12"} for _ in metrics],
                    "dimensionValues": [{"value": values[name]} for name in dimensions],
                }
            ],
            "rowCount": 1,
        }
    elif request.method == "GET" and path == "/v1/accounts":
        body = {
            "accounts": []
            if missing
            else [{"name": "accounts/1001", "accountName": "Synthetic account"}]
        }
    elif request.method == "GET" and path == "/v1/accounts/1001/locations":
        body = {
            "locations": []
            if missing
            else [{"name": "locations/1001", "title": "Synthetic location"}]
        }
    elif request.method == "GET" and path == "/v1/locations/1001" and not missing:
        body = {"name": "locations/1001", "title": "Synthetic location"}
        if not partial:
            body["profile"] = {"description": "Synthetic staging profile"}
    elif request.method == "GET" and path.endswith("/reviews"):
        body = {"reviews": []}
    elif request.method == "GET" and path.endswith("/localPosts"):
        body = {"localPosts": []}
    else:
        raise ValueError("Fixture transport refuses unsupported provider operation")
    return httpx.Response(200, json=body)


def fixture_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(fixture_response), follow_redirects=False
    )


class FixtureSearchConsoleAdapter(GoogleSearchConsoleAdapter):
    def __init__(self) -> None:
        from apps.api.app.config import EnvironmentName, Settings

        if Settings().environment is EnvironmentName.PRODUCTION:
            raise ValueError("Production refuses fixture implementations")
        super().__init__(http_client_factory=fixture_client)


class FixtureAnalyticsAdapter(GoogleAnalyticsAdminAdapter):
    def __init__(self) -> None:
        from apps.api.app.config import EnvironmentName, Settings

        if Settings().environment is EnvironmentName.PRODUCTION:
            raise ValueError("Production refuses fixture implementations")
        super().__init__(http_client_factory=fixture_client)


class FixtureGBPAdapter(GoogleBusinessProfileAdapter):
    def __init__(self) -> None:
        from apps.api.app.config import EnvironmentName, Settings

        if Settings().environment is EnvironmentName.PRODUCTION:
            raise ValueError("Production refuses fixture implementations")
        super().__init__(http_client_factory=fixture_client)
