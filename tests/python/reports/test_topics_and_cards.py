"""Search movement, topics and result cards: deterministic gains, grounded and verified cards."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from apps.api.app.reports.cards import card_failure, edited_cards, figure_numbers
from apps.api.app.reports.contracts import (
    CardTone,
    FigureKey,
    FigureUnit,
    NarrativeFailureCode,
    ReportFigureValue,
    ReportMovementQuery,
    ReportSearchMovement,
    ReportSnapshot,
    ReportTopic,
    ReportTopics,
    ResultCard,
    ResultCardUpdate,
)
from apps.api.app.reports.errors import ReportCardFigureUnavailableError
from apps.api.app.reports.search_results import clean_topics, search_results
from reports.routes_support import call
from reports.support import AUGUST, SEPTEMBER, Factory, store_search_queries
from reports.test_narrative import GOOD, SEPT, draft, generate, url, use

pytestmark = pytest.mark.integration


def row(
    query: str,
    before: tuple[float, int, int] | None,
    after: tuple[float, int, int] | None,
) -> ReportMovementQuery:
    """(position, impressions, clicks) before and after; None is "no stored row"."""
    return ReportMovementQuery(
        query=query,
        before_position=before[0] if before else None,
        before_impressions=before[1] if before else None,
        before_clicks=before[2] if before else None,
        after_position=after[0] if after else None,
        after_impressions=after[1] if after else 0,
        after_clicks=after[2] if after else 0,
    )


ROWS = [
    row("rooftop venues", (7.5, 100, 1), (3.2, 180, 4)),
    row("rooftop party", None, (4.4, 130, 0)),
    row("happy hour little italy", (10.7, 82, 3), (8.5, 392, 14)),
    row("brunch san diego", (30.6, 565, 7), (22.9, 898, 5)),
    row("little italy bars", (10.1, 224, 0), (8.8, 429, 1)),
    row("stays put", (5.0, 60, 2), (5.0, 60, 2)),
    row("too small", (9.0, 5, 0), (3.0, 10, 0)),
    row("coco maia", (2.0, 300, 20), (1.8, 320, 25)),
]


def snapshot_with(
    base: dict[str, Any], rows: list[ReportMovementQuery], *, comparable: bool = True
):
    snapshot = ReportSnapshot.model_validate(base)
    movement = ReportSearchMovement(
        comparable=comparable,
        months_covered=1,
        months_expected=1,
        compared_months_covered=1 if comparable else 0,
        compared_months_expected=1,
        queries=rows,
    )
    return snapshot.model_copy(update={"search_movement": movement})


TOPICS = ReportTopics(
    topics=[
        ReportTopic(
            key="private-events",
            label="Private events",
            queries=["rooftop venues", "rooftop party"],
        ),
        ReportTopic(key="happy-hour", label="Happy hour", queries=["happy hour little italy"]),
        ReportTopic(key="brunch", label="Brunch", queries=["brunch san diego"]),
    ],
    brand_variants=["coco maia"],
)


def test_gains_and_topic_figures_are_counted_by_code(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    base = generate(client, ids["org"])["snapshot"]

    results = search_results(snapshot_with(base, ROWS), TOPICS)

    assert results is not None and results.comparable
    # In the top 10 with 20+ impressions: before, rooftop venues and "stays put"; after, five.
    assert (results.top_ten_before, results.top_ten_after) == (2, 5)
    assert results.new_to_page_one == 3
    # A misspelling of the business name is not a non-branded search.
    assert all(g.query != "coco maia" for group in results.gains for g in group.rows)
    private = next(item for item in results.topics if item.key == "private-events")
    assert (private.top_ten_before, private.top_ten_after) == (1, 2)
    assert private.position_before == 7.5 and private.position_after == 3.7
    assert (private.clicks_before, private.clicks_after) == (1, 4)
    # Gains: better by a place or new; a search with too few impressions is left out.
    names = {g.query: g for group in results.gains for g in group.rows}
    assert "rooftop party" in names and names["rooftop party"].position_before is None
    assert "stays put" not in names and "too small" not in names
    assert {group.key for group in results.gains} >= {"private-events", "happy-hour", "brunch"}


def test_without_a_comparison_nothing_is_set_against_a_missing_window(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    base = generate(client, ids["org"])["snapshot"]
    # Miss B's: search data starts in May, so there is nothing before to compare with.
    alone = [
        row(r.query, None, (r.after_position, r.after_impressions, r.after_clicks))
        for r in ROWS
        if r.after_position
    ]

    results = search_results(snapshot_with(base, alone, comparable=False), TOPICS)

    assert results is not None and not results.comparable
    assert results.top_ten_before is None and results.new_to_page_one is None
    assert results.clicks_before is None and results.position_before is None
    assert results.gains == []
    assert all(
        item.top_ten_before is None and item.clicks_before is None for item in results.topics
    )
    assert results.top_ten_after > 0


def test_topics_are_made_safe_before_they_are_kept() -> None:
    known = {"a", "b", "c", "d", "e"}
    raw = {
        "topics": [
            {"label": "First", "queries": ["a", "b", "not a search"]},
            {"label": "Second", "queries": ["b", "c"]},
            {"label": "Empty", "queries": ["zzz"]},
            {"label": "Third", "queries": ["d"]},
        ],
        "brand_variants": ["e", "a"],
    }

    topics = clean_topics(raw, known)

    assert topics is not None
    # "a" is a brand variant, so it is in no topic; "b" is placed once.
    assert topics.brand_variants == ["e", "a"]
    placed = [query for topic in topics.topics for query in topic.queries]
    assert placed == ["b", "c", "d"] and len(placed) == len(set(placed))
    assert [topic.key for topic in topics.topics] == ["first", "second", "third"]
    assert clean_topics({"topics": [{"label": "One", "queries": ["a"]}]}, known) is None
    assert clean_topics("nonsense", known) is None


def card(
    keys: list[str], tone: str, title: str, text: str, headline: bool = False
) -> dict[str, Any]:
    return {"figure_keys": keys, "tone": tone, "headline": headline, "title": title, "text": text}


def test_cards_are_verified_one_by_one_and_stored_with_their_figures(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, factory = reports_app
    org = ids["org"]
    generate(client, org)
    views = call(client, "get", url(org, f"/{SEPT}/1"), "manager").json()["snapshot"]["gbp"][
        "profile_views"
    ]["total"]
    current, compared = views["current"]["value"], views["compared"]["value"]
    cards = [
        card(
            ["profile_views"],
            "good",
            "More profile views",
            f"Views reached {current}, up from {compared}.",
            True,
        ),
        card(["profile_views"], "good", "Invented", "Views reached 987,654."),
        card(["profile_views"], "good", "Caused", f"Views rose to {current} because of our posts."),
        card(["profile_views"], "bad", "Wrong tone", f"Views reached {current}."),
        card(["search_clicks"], "neutral", "Search clicks", "Search clicks moved.", True),
        card(["searches_in_top_ten", "bogus"], "good", "Bad key", "Nothing."),
    ]
    use(client, {**GOOD, "result_cards": cards})

    result = draft(client, org).json()

    stored = result["report"]["narrative"]["result_cards"]
    assert [item["title"] for item in stored] == ["More profile views", "Search clicks"]
    assert result["cards_dropped"] == 4
    first = stored[0]
    assert first["headline"] is True and stored[1]["headline"] is False
    assert (
        first["figures"][0]["key"] == "profile_views" and first["figures"][0]["current"] == current
    )
    assert first["figures"][0]["compared"] == compared and first["tone"] == CardTone.GOOD.value


def test_a_card_cannot_call_a_result_good_or_bad_when_the_figure_did_not_move_that_way(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    org = ids["org"]
    snapshot = ReportSnapshot.model_validate(generate(client, org)["snapshot"])
    fell = ReportFigureValue(
        key=FigureKey.PROFILE_VIEWS,
        unit=FigureUnit.COUNT,
        current=80.0,
        compared=100.0,
        change=-20.0,
        change_percent=-20.0,
    )

    def make(tone: CardTone, text: str) -> ResultCard:
        return ResultCard(
            figure_keys=[FigureKey.PROFILE_VIEWS],
            figures=[fell],
            tone=tone,
            title="Profile views",
            text=text,
        )

    table = {FigureKey.PROFILE_VIEWS: fell}
    assert card_failure(make(CardTone.GOOD, "Views were 80."), snapshot, table) is (
        NarrativeFailureCode.TONE_NOT_SUPPORTED
    )
    # The honest card says so with the numbers of its own figure and nothing else.
    assert (
        card_failure(make(CardTone.BAD, "Views fell to 80 from 100, down 20%."), snapshot, table)
        is None
    )
    assert card_failure(make(CardTone.BAD, "Views fell to 79."), snapshot, table) is (
        NarrativeFailureCode.NUMBER_NOT_IN_DATA
    )
    # Nothing improved and no card can be written: the list is simply empty, never a made-up win.
    assert figure_numbers([]) == set()
    with pytest.raises(ReportCardFigureUnavailableError):
        edited_cards(
            [
                ResultCardUpdate(
                    figure_keys=[FigureKey.NEW_TO_PAGE_ONE],
                    tone=CardTone.NEUTRAL,
                    title="x",
                    text="y",
                )
            ],
            {},
        )


def test_topics_are_stored_on_the_revision_and_change_only_when_regenerated(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    import asyncio

    client, ids, factory = reports_app
    org = ids["org"]
    asyncio.run(
        store_search_queries(
            factory,
            org,
            SEPTEMBER,
            {
                "rooftop venues": (9, 400, 3.2),
                "happy hour": (4, 300, 8.5),
                "brunch": (3, 200, 12.0),
            },
        )
    )
    asyncio.run(
        store_search_queries(
            factory, org, AUGUST, {"rooftop venues": (2, 350, 7.5), "happy hour": (1, 250, 10.7)}
        )
    )
    generate(client, org)
    gateway = use(
        client,
        GOOD,
        {
            "topics": [
                {"label": "Private events", "queries": ["rooftop venues", "invented"]},
                {"label": "Happy hour", "queries": ["happy hour"]},
                {"label": "Brunch", "queries": ["brunch", "rooftop venues"]},
            ],
            "brand_variants": [],
        },
    )

    body = draft(client, org).json()["report"]

    topics = body["topics"]["topics"]
    assert [item["key"] for item in topics] == ["private-events", "happy-hour", "brunch"]
    assert topics[0]["queries"] == ["rooftop venues"] and topics[2]["queries"] == ["brunch"]
    # Reads never call Hermes and always return the same grouping.
    requests = len(gateway.requests)
    first = call(client, "get", url(org, f"/{SEPT}/1"), "manager").json()
    second = call(client, "get", url(org, f"/{SEPT}/1"), "manager").json()
    assert first["topics"] == second["topics"] == body["topics"]
    assert len(gateway.requests) == requests
    results = first["search_results"]
    assert results["comparable"] and results["top_ten_before"] is not None
    assert [item["label"] for item in results["topics"]] == [
        "Private events",
        "Happy hour",
        "Brunch",
    ]
    # Regenerating asks again and replaces the grouping.
    use(
        client,
        GOOD,
        {
            "topics": [
                {"label": "Bars", "queries": ["happy hour"]},
                {"label": "Food", "queries": ["brunch"]},
            ]
        },
    )
    again = draft(client, org).json()["report"]["topics"]["topics"]
    assert [item["label"] for item in again] == ["Bars", "Food"]


def test_a_person_can_edit_cards_but_not_their_figures(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    org = ids["org"]
    generate(client, org)
    mine = {"what_changed": "Mine.", "next_work": "Plan."}
    edit = {
        **mine,
        "result_cards": [card(["profile_views"], "good", "Edited title", "Edited sentence.", True)],
    }

    saved = call(client, "put", url(org, f"/{SEPT}/1/narrative"), "manager", edit).json()

    kept = saved["narrative"]["result_cards"]
    assert kept[0]["title"] == "Edited title" and kept[0]["figures"][0]["key"] == "profile_views"
    # Saving only the words keeps the cards.
    again = call(client, "put", url(org, f"/{SEPT}/1/narrative"), "manager", mine).json()
    assert again["narrative"]["result_cards"] == kept
