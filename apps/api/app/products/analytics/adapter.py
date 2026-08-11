"""Real Google Analytics (GA4) adapter for the Insights product.

Implements the ``GoogleAnalyticsAdapter`` protocol against the Analytics
Admin API (``analyticsadmin.googleapis.com/v1beta``) for property discovery and
the Analytics Data API (``analyticsdata.googleapis.com/v1beta``) for reporting.

Only read-only, least-privilege scopes are used (``analytics.readonly``). The
adapter reports only the real GA4 metrics the Insights product models
(sessions, totalUsers, screenPageViews, conversions) -- nothing is fabricated,
and raw provider identifiers/bearer tokens are never returned by callers.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

ANALYTICS_ADMIN_API = "https://analyticsadmin.googleapis.com/v1beta"
ANALYTICS_DATA_API = "https://analyticsdata.googleapis.com/v1beta"

# Real GA4 Data API metrics the Insights product models. These are standard
# GA4 metrics (not invented), limited to what §13.42 justifies: sessions,
# users, pageviews, and conversions.
GA4_METRICS: tuple[str, ...] = ("sessions", "totalUsers", "screenPageViews", "conversions")


@dataclass(frozen=True, slots=True)
class DiscoveredAnalyticsProperty:
    """A GA4 property the operator's Google account can access."""

    external_property_id: str  # "properties/123456"
    property_number: str  # "123456"
    display_name: str
    account_display_name: str


@dataclass(frozen=True, slots=True)
class AnalyticsReportRow:
    """One metric-total row from a GA4 Data API runReport response."""

    metric_values: dict[str, int]


class GoogleAnalyticsAdapter(Protocol):
    """Read-only GA4 operations used by the Insights product."""

    async def list_account_summaries(
        self, access_token: str
    ) -> list[DiscoveredAnalyticsProperty]: ...

    async def run_report(
        self,
        access_token: str,
        property_number: str,
        *,
        start_date: str,
        end_date: str,
        metrics: Sequence[str] = GA4_METRICS,
    ) -> list[AnalyticsReportRow]: ...


def _property_number(name: str) -> str:
    # Admin API returns property resource names as "properties/123456".
    return name.rsplit("/", 1)[-1] if "/" in name else name


@dataclass(slots=True)
class GoogleAnalyticsAdminAdapter:
    """Concrete ``GoogleAnalyticsAdapter`` backed by the GA4 REST APIs."""

    timeout_seconds: float = 20.0
    http_client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    async def _get(
        self, access_token: str, url: str, *, expected_status: int = 200
    ) -> dict[str, Any]:
        async with self.http_client_factory() as client:
            response = await client.get(
                url, headers=self._headers(access_token), timeout=self.timeout_seconds
            )
        if response.status_code != expected_status:
            raise RuntimeError(
                f"Analytics GET {url} returned {response.status_code}: {response.text[:200]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("invalid Analytics response")
        return payload

    async def _post(
        self,
        access_token: str,
        url: str,
        body: dict[str, Any],
        *,
        expected_status: int = 200,
    ) -> dict[str, Any]:
        async with self.http_client_factory() as client:
            response = await client.post(
                url,
                headers=self._headers(access_token),
                json=body,
                timeout=self.timeout_seconds,
            )
        if response.status_code != expected_status:
            raise RuntimeError(
                f"Analytics POST {url} returned {response.status_code}: {response.text[:200]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("invalid Analytics response")
        return payload

    async def list_account_summaries(self, access_token: str) -> list[DiscoveredAnalyticsProperty]:
        payload = await self._get(access_token, f"{ANALYTICS_ADMIN_API}/accountSummaries")
        summaries = payload.get("accountSummaries") or []
        properties: list[DiscoveredAnalyticsProperty] = []
        for summary in summaries:
            account_name = str(summary.get("displayName", ""))
            for prop_summary in summary.get("propertySummaries") or []:
                resource_name = str(prop_summary.get("property", ""))
                properties.append(
                    DiscoveredAnalyticsProperty(
                        external_property_id=resource_name,
                        property_number=_property_number(resource_name),
                        display_name=str(prop_summary.get("displayName", "")),
                        account_display_name=account_name,
                    )
                )
        return properties

    async def run_report(
        self,
        access_token: str,
        property_number: str,
        *,
        start_date: str,
        end_date: str,
        metrics: Sequence[str] = GA4_METRICS,
    ) -> list[AnalyticsReportRow]:
        body = {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "metrics": [{"name": name} for name in metrics],
        }
        payload = await self._post(
            access_token,
            f"{ANALYTICS_DATA_API}/properties/{property_number}:runReport",
            body,
            expected_status=200,
        )
        rows = payload.get("rows") or []
        metric_headers = [str(h.get("name", "")) for h in payload.get("metricHeaders") or []]
        results: list[AnalyticsReportRow] = []
        for row in rows:
            values = row.get("metricValues") or []
            metric_values: dict[str, int] = {}
            for header, value in zip(metric_headers, values, strict=False):
                raw = value.get("value", "0") if isinstance(value, dict) else "0"
                try:
                    metric_values[header] = int(raw)
                except (TypeError, ValueError):
                    metric_values[header] = 0
            results.append(AnalyticsReportRow(metric_values=metric_values))
        return results
