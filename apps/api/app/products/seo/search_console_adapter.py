"""Real Google Search Console adapter for the SEO product.

Implements the ``SearchConsoleAdapter`` protocol against the Search Console
REST API (``https://www.googleapis.com/webmasters/v3``). The adapter is
configured per-organization through the shared Google ``IntegrationConnection``
and the operator-selected ``SEOSearchProperty`` mapping -- no credentials or
property values are hard-coded here.

The adapter performs only read operations required by the SEO spec
(``SEOSearchObservation``: clicks, impressions, ctr, position): listing the
operator's accessible Search Console properties and querying search analytics
grouped by ``query``. It deliberately does not call write endpoints (sitemap
submission, site add/delete) and does not invent metrics beyond what the
Search Console searchAnalytics report returns.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast
from urllib.parse import quote

import httpx

SEARCH_CONSOLE_API = "https://www.googleapis.com/webmasters/v3"
SEARCH_ANALYTICS_MAX_ROW_LIMIT = 25_000
MAX_SEARCH_ANALYTICS_PAGES = 1_000


@dataclass(frozen=True, slots=True)
class DiscoveredSearchProperty:
    """A Search Console property the operator's Google account can access."""

    external_property_id: str
    property_type: str  # 'domain' (sc-domain:) or 'url_prefix'
    permission_level: str


@dataclass(frozen=True, slots=True)
class SearchAnalyticsRow:
    """One grouped row from the Search Console searchAnalytics report."""

    keys: tuple[str, ...]
    clicks: int
    impressions: int
    ctr: float
    position: float


class SearchConsoleAdapter(Protocol):
    """Read-only Search Console operations used by the SEO product."""

    async def list_sites(self, access_token: str) -> list[DiscoveredSearchProperty]: ...

    async def query_search_analytics(
        self,
        access_token: str,
        site_url: str,
        *,
        start_date: str,
        end_date: str,
        dimensions: Sequence[str] = ("query",),
        row_limit: int = 1000,
    ) -> list[SearchAnalyticsRow]: ...


def _site_url_to_property_type(site_url: str) -> str:
    # Domain properties are exposed as ``sc-domain:example.com``; URL-prefix
    # properties keep their full origin form (``https://example.com/``).
    return "domain" if site_url.startswith("sc-domain:") else "url_prefix"


@dataclass(slots=True)
class GoogleSearchConsoleAdapter:
    """Concrete ``SearchConsoleAdapter`` backed by the Search Console REST API."""

    timeout_seconds: float = 20.0
    http_client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    async def _get(
        self, access_token: str, path: str, *, expected_status: int = 200
    ) -> dict[str, Any]:
        async with self.http_client_factory() as client:
            response = await client.get(
                f"{SEARCH_CONSOLE_API}{path}",
                headers=self._headers(access_token),
                timeout=self.timeout_seconds,
            )
        if response.status_code != expected_status:
            raise RuntimeError(
                f"Search Console GET {path} returned {response.status_code}: {response.text[:200]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("invalid Search Console response")
        return payload

    async def _post(
        self,
        access_token: str,
        path: str,
        body: dict[str, Any],
        *,
        expected_status: int = 200,
    ) -> dict[str, Any]:
        async with self.http_client_factory() as client:
            response = await client.post(
                f"{SEARCH_CONSOLE_API}{path}",
                headers=self._headers(access_token),
                json=body,
                timeout=self.timeout_seconds,
            )
        if response.status_code != expected_status:
            raise RuntimeError(
                f"Search Console POST {path} returned {response.status_code}: {response.text[:200]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("invalid Search Console response")
        return payload

    async def list_sites(self, access_token: str) -> list[DiscoveredSearchProperty]:
        payload = await self._get(access_token, "/sites")
        entries = payload.get("siteEntry") or []
        properties: list[DiscoveredSearchProperty] = []
        for entry in entries:
            site_url = str(entry.get("siteUrl", ""))
            if not site_url:
                continue
            properties.append(
                DiscoveredSearchProperty(
                    external_property_id=site_url,
                    property_type=_site_url_to_property_type(site_url),
                    permission_level=str(entry.get("permissionLevel", "")),
                )
            )
        return properties

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
        if not 1 <= row_limit <= SEARCH_ANALYTICS_MAX_ROW_LIMIT:
            raise ValueError("Search Console row_limit must be between 1 and 25,000")
        # The ``siteUrl`` path parameter must be fully URL-encoded; URL-prefix
        # properties contain slashes and a scheme, and domain properties contain
        # a colon (``sc-domain:``).
        encoded_site = quote(site_url, safe="")
        results: list[SearchAnalyticsRow] = []
        start_row = 0
        for _page_number in range(MAX_SEARCH_ANALYTICS_PAGES):
            body = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": list(dimensions),
                "rowLimit": row_limit,
                "startRow": start_row,
            }
            payload = await self._post(
                access_token,
                f"/sites/{encoded_site}/searchAnalytics/query",
                body,
                expected_status=200,
            )
            raw_rows = payload.get("rows", [])
            if not isinstance(raw_rows, list) or not all(isinstance(row, dict) for row in raw_rows):
                raise RuntimeError("invalid Search Console analytics page")
            rows = cast(list[dict[str, Any]], raw_rows)
            for row in rows:
                keys = tuple(str(key) for key in (row.get("keys") or []))
                results.append(
                    SearchAnalyticsRow(
                        keys=keys,
                        clicks=int(row.get("clicks", 0)),
                        impressions=int(row.get("impressions", 0)),
                        ctr=float(row.get("ctr", 0.0)),
                        position=float(row.get("position", 0.0)),
                    )
                )
            if len(rows) < row_limit:
                return results
            start_row += len(rows)

        raise RuntimeError("Search Console analytics pagination exceeded safety limit")
