"""Insight rules: thresholds, ordering, and silence when the data does not support a claim."""

from apps.api.app.products.seo.local_search_insights import (
    InsightCode,
    InsightLink,
    ProfileActions,
    build_insights,
)


def report(
    clicks: tuple[float, float] = (100, 100),
    impressions: tuple[float, float] = (1000, 1000),
    **extra: object,
) -> dict[str, object]:
    return {
        "connected": True,
        "metrics": {
            "clicks": {"current": clicks[0], "previous": clicks[1]},
            "impressions": {"current": impressions[0], "previous": impressions[1]},
        },
        "top_queries": [],
        "top_pages": [],
        **extra,
    }


def codes(data: dict[str, object], actions: ProfileActions | None = None) -> list[InsightCode]:
    return [item.code for item in build_insights(data, actions)]


def test_a_flat_period_says_nothing() -> None:
    assert codes(report()) == []


def test_clicks_up_and_down_need_ten_percent_and_a_real_base() -> None:
    assert codes(report(clicks=(130, 100))) == [InsightCode.SEARCH_CLICKS_UP]
    assert codes(report(clicks=(70, 100))) == [InsightCode.SEARCH_CLICKS_DOWN]
    assert codes(report(clicks=(105, 100))) == []
    assert codes(report(clicks=(9, 5))) == []  # +80% off five clicks is noise


def test_impressions_outrunning_clicks_is_a_click_through_finding() -> None:
    found = build_insights(report(clicks=(100, 100), impressions=(2000, 1000)), None)
    assert [item.code for item in found] == [InsightCode.IMPRESSIONS_OUTRUNNING_CLICKS]
    assert found[0].percent_change == 100


def test_profile_actions_are_reported_with_their_own_link() -> None:
    found = build_insights(report(), ProfileActions(current=150, previous=100))
    assert (found[0].code, found[0].link) == (
        InsightCode.PROFILE_ACTIONS_UP,
        InsightLink.GOOGLE_BUSINESS_PROFILE,
    )
    assert codes(report(), ProfileActions(current=None, previous=None)) == []
    assert codes(report(), ProfileActions(current=150, previous=None)) == []
    assert codes(report(), ProfileActions(current=3, previous=2)) == []


def test_profile_actions_stand_alone_when_search_console_is_not_connected() -> None:
    found = build_insights({"connected": False, "metrics": {}}, ProfileActions(60, 100))
    assert [item.code for item in found] == [InsightCode.PROFILE_ACTIONS_DOWN]


def test_movers_need_both_windows_and_a_meaningful_move() -> None:
    now = [{"query": "brunch", "clicks": 90}, {"query": "menu", "clicks": 40}]
    then = [{"query": "brunch", "clicks": 30}, {"query": "menu", "clicks": 38}]
    found = build_insights(report(top_queries=now, previous_top_queries=then), None)
    assert (found[0].code, found[0].subject, found[0].link) == (
        InsightCode.QUERY_GAINING_CLICKS,
        "brunch",
        InsightLink.SEARCH_CONSOLE,
    )
    # No previous-window rows: no mover claim at all.
    assert codes(report(top_queries=now)) == []
    pages_now = [{"page": "https://x.test/menu/", "clicks": 10}]
    pages_then = [{"page": "https://x.test/menu/", "clicks": 40}]
    page = build_insights(report(top_pages=pages_now, previous_top_pages=pages_then), None)
    assert (page[0].code, page[0].link) == (InsightCode.PAGE_LOSING_CLICKS, InsightLink.PAGES)


def test_queries_near_page_one_count_and_name_the_biggest() -> None:
    queries = [
        {"query": "a", "impressions": 500, "position": 11.0},
        {"query": "b", "impressions": 900, "position": 14.2},
        {"query": "c", "impressions": 50, "position": 12.0},  # too few impressions
        {"query": "d", "impressions": 5000, "position": 3.0},  # already on page one
    ]
    (found,) = build_insights(report(top_queries=queries), None)
    assert (found.code, found.subject, found.count, found.current) == (
        InsightCode.QUERIES_NEAR_PAGE_ONE,
        "b",
        2,
        14.2,
    )


def test_at_most_three_most_specific_first() -> None:
    data = report(
        clicks=(150, 100),
        impressions=(3000, 1000),
        top_queries=[{"query": "brunch", "clicks": 90, "impressions": 900, "position": 9.0}],
        previous_top_queries=[{"query": "brunch", "clicks": 30}],
    )
    found = codes(data, ProfileActions(200, 100))
    assert len(found) == 3
    assert found[0] == InsightCode.QUERY_GAINING_CLICKS
