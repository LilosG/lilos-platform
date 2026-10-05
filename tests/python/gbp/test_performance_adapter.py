"""Business Profile Performance API adapter, against recorded Google response shapes."""

from datetime import date
from typing import Any

import httpx
import pytest

from apps.api.app.products.gbp.adapter import (
    PERFORMANCE_BASE,
    GBPPerformanceProviderError,
    GoogleBusinessProfileAdapter,
)
from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceFailureCode,
    GBPPerformanceMetric,
)

# Recorded shape of locations/{id}:fetchMultiDailyMetricsTimeSeries. Google sends int64 as a
# string and omits a zero, so a listed day with no "value" is a real zero.
DAILY_RESPONSE: dict[str, Any] = {
    "multiDailyMetricTimeSeries": [
        {
            "dailyMetricTimeSeries": [
                {
                    "dailyMetric": "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
                    "timeSeries": {
                        "datedValues": [
                            {"date": {"year": 2026, "month": 9, "day": 1}, "value": "120"},
                            {"date": {"year": 2026, "month": 9, "day": 2}},
                            {"date": {"year": 2026, "month": 9, "day": 3}, "value": "7"},
                        ]
                    },
                },
                {
                    "dailyMetric": "CALL_CLICKS",
                    "timeSeries": {
                        "datedValues": [
                            {"date": {"year": 2026, "month": 9, "day": 1}, "value": "4"}
                        ]
                    },
                },
                {
                    # A metric Google added after the model was written is ignored, not fatal.
                    "dailyMetric": "SOMETHING_NEW",
                    "timeSeries": {
                        "datedValues": [
                            {"date": {"year": 2026, "month": 9, "day": 1}, "value": "9"}
                        ]
                    },
                },
                {"dailyMetric": "BUSINESS_BOOKINGS", "timeSeries": {}},
            ]
        }
    ]
}

# Recorded shape of locations/{id}/searchkeywords/impressions/monthly: an exact "value", or a
# "threshold" when Google withholds a small count ("fewer than 15").
KEYWORD_PAGE_1: dict[str, Any] = {
    "searchKeywordsCounts": [
        {"searchKeyword": "pizza near me", "insightsValue": {"value": "812"}},
        {"searchKeyword": "gluten free pizza", "insightsValue": {"threshold": "15"}},
    ],
    "nextPageToken": "page-2",
}
KEYWORD_PAGE_2: dict[str, Any] = {
    "searchKeywordsCounts": [
        {"searchKeyword": "best italian", "insightsValue": {"value": "40"}},
        {"searchKeyword": "unknown count", "insightsValue": {}},
    ]
}


class RecordingAdapter(GoogleBusinessProfileAdapter):
    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def _request(self, method: str, url: str, token: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"method": method, "url": url, "token": token, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", PERFORMANCE_BASE)
    return httpx.HTTPStatusError(
        "boom", request=request, response=httpx.Response(status, request=request)
    )


@pytest.mark.anyio
async def test_daily_metrics_request_asks_for_every_metric_and_the_inclusive_range() -> None:
    adapter = RecordingAdapter([DAILY_RESPONSE])

    await adapter.fetch_daily_metrics("token", "locations/55", date(2026, 3, 1), date(2026, 9, 3))

    call = adapter.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == f"{PERFORMANCE_BASE}/locations/55:fetchMultiDailyMetricsTimeSeries"
    params = call["params"]
    assert [v for k, v in params if k == "dailyMetrics"] == [m.value for m in GBPPerformanceMetric]
    assert len([v for k, v in params if k == "dailyMetrics"]) == 11
    assert dict(p for p in params if p[0] != "dailyMetrics") == {
        "dailyRange.startDate.year": "2026",
        "dailyRange.startDate.month": "3",
        "dailyRange.startDate.day": "1",
        "dailyRange.endDate.year": "2026",
        "dailyRange.endDate.month": "9",
        "dailyRange.endDate.day": "3",
    }


@pytest.mark.anyio
async def test_account_qualified_location_names_use_the_v1_resource_name() -> None:
    adapter = RecordingAdapter([{}])

    await adapter.fetch_daily_metrics(
        "token", "accounts/9/locations/55", date(2026, 9, 1), date(2026, 9, 2)
    )

    assert adapter.calls[0]["url"].startswith(f"{PERFORMANCE_BASE}/locations/55:")


@pytest.mark.anyio
async def test_daily_metrics_parse_strings_omitted_zeros_and_unknown_metrics() -> None:
    adapter = RecordingAdapter([DAILY_RESPONSE])

    points = await adapter.fetch_daily_metrics(
        "token", "locations/55", date(2026, 9, 1), date(2026, 9, 3)
    )

    assert {(p.metric, p.day, p.value) for p in points} == {
        (GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_SEARCH, date(2026, 9, 1), 120),
        (GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_SEARCH, date(2026, 9, 2), 0),
        (GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_SEARCH, date(2026, 9, 3), 7),
        (GBPPerformanceMetric.CALL_CLICKS, date(2026, 9, 1), 4),
    }


@pytest.mark.anyio
async def test_an_empty_response_is_no_points_not_an_error() -> None:
    adapter = RecordingAdapter([{}])

    assert (
        await adapter.fetch_daily_metrics("t", "locations/1", date(2026, 9, 1), date(2026, 9, 1))
        == []
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"multiDailyMetricTimeSeries": [{"dailyMetricTimeSeries": [
            {"dailyMetric": "CALL_CLICKS", "timeSeries": {"datedValues": [{"value": "1"}]}}
        ]}]},
        {"multiDailyMetricTimeSeries": [{"dailyMetricTimeSeries": [
            {"dailyMetric": "CALL_CLICKS", "timeSeries": {"datedValues": [
                {"date": {"year": 2026, "month": 9, "day": 1}, "value": "-3"}
            ]}}
        ]}]},
        {"multiDailyMetricTimeSeries": [{"dailyMetricTimeSeries": [
            {"dailyMetric": "CALL_CLICKS", "timeSeries": {"datedValues": [
                {"date": {"year": 2026, "month": 9, "day": 1}, "value": "lots"}
            ]}}
        ]}]},
    ],
)  # fmt: skip
async def test_malformed_daily_responses_fail_with_a_typed_code(payload: dict[str, Any]) -> None:
    adapter = RecordingAdapter([payload])

    with pytest.raises(GBPPerformanceProviderError) as raised:
        await adapter.fetch_daily_metrics("t", "locations/1", date(2026, 9, 1), date(2026, 9, 1))

    assert raised.value.code is GBPPerformanceFailureCode.PROVIDER_RESPONSE_INVALID


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (_status_error(401), GBPPerformanceFailureCode.PROVIDER_ACCESS_DENIED),
        (_status_error(403), GBPPerformanceFailureCode.PROVIDER_ACCESS_DENIED),
        (_status_error(429), GBPPerformanceFailureCode.PROVIDER_RATE_LIMITED),
        (_status_error(503), GBPPerformanceFailureCode.PROVIDER_UNAVAILABLE),
        (_status_error(400), GBPPerformanceFailureCode.PROVIDER_REJECTED_REQUEST),
        (_status_error(404), GBPPerformanceFailureCode.PROVIDER_REJECTED_REQUEST),
        (httpx.ConnectTimeout("slow"), GBPPerformanceFailureCode.PROVIDER_UNAVAILABLE),
    ],
)
async def test_http_failures_map_to_typed_codes_without_provider_text(
    error: Exception, code: GBPPerformanceFailureCode
) -> None:
    adapter = RecordingAdapter([error])

    with pytest.raises(GBPPerformanceProviderError) as raised:
        await adapter.fetch_daily_metrics("t", "locations/1", date(2026, 9, 1), date(2026, 9, 1))

    assert raised.value.code is code
    assert str(raised.value) == code.value


def test_only_transient_failure_codes_are_retryable() -> None:
    assert GBPPerformanceFailureCode.PROVIDER_RATE_LIMITED.retryable
    assert GBPPerformanceFailureCode.PROVIDER_UNAVAILABLE.retryable
    assert not GBPPerformanceFailureCode.RECONNECT_REQUIRED.retryable
    assert not GBPPerformanceFailureCode.PROVIDER_ACCESS_DENIED.retryable
    assert not GBPPerformanceFailureCode.LOCATION_NOT_FOUND.retryable


@pytest.mark.anyio
async def test_keywords_store_thresholds_as_thresholds_never_as_zero_and_follow_pages() -> None:
    adapter = RecordingAdapter([KEYWORD_PAGE_1, KEYWORD_PAGE_2])

    points = await adapter.list_search_keyword_impressions(
        "token", "locations/55", date(2026, 8, 1)
    )

    assert {(p.keyword, p.value, p.threshold) for p in points} == {
        ("pizza near me", 812, None),
        ("gluten free pizza", None, 15),
        ("best italian", 40, None),
    }  # "unknown count" had neither field: unknown is not stored as 0
    first, second = adapter.calls
    assert first["url"] == f"{PERFORMANCE_BASE}/locations/55/searchkeywords/impressions/monthly"
    assert dict(first["params"]) == {
        "monthlyRange.startMonth.year": "2026",
        "monthlyRange.startMonth.month": "8",
        "monthlyRange.endMonth.year": "2026",
        "monthlyRange.endMonth.month": "8",
        "pageSize": "100",
    }
    assert dict(second["params"])["pageToken"] == "page-2"


@pytest.mark.anyio
async def test_a_repeated_page_token_fails_closed() -> None:
    page = {"searchKeywordsCounts": [], "nextPageToken": "same"}
    adapter = RecordingAdapter([page, page, page])

    with pytest.raises(GBPPerformanceProviderError) as raised:
        await adapter.list_search_keyword_impressions("t", "locations/1", date(2026, 8, 1))

    assert raised.value.code is GBPPerformanceFailureCode.PROVIDER_RESPONSE_INVALID


@pytest.mark.anyio
async def test_a_zero_threshold_is_invalid() -> None:
    adapter = RecordingAdapter(
        [{"searchKeywordsCounts": [{"searchKeyword": "x", "insightsValue": {"threshold": "0"}}]}]
    )

    with pytest.raises(GBPPerformanceProviderError):
        await adapter.list_search_keyword_impressions("t", "locations/1", date(2026, 8, 1))
