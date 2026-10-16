"""Non-branded search results from the stored movement and the topics: pure code, no model.

Everything here is added up from the highest-ranking searches Google reports each month, so a
search missing from a window is unknown there, never zero. Nothing is stated between two windows
unless the snapshot says they are comparable.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from apps.api.app.reports.contracts import (
    ReportGain,
    ReportGainGroup,
    ReportMovementQuery,
    ReportSearchResults,
    ReportSnapshot,
    ReportTopic,
    ReportTopicResult,
    ReportTopics,
)
from apps.api.app.reports.snapshot_search import MOVEMENT_MIN_IMPRESSIONS

PAGE_ONE = 10.0
GAIN_PLACES = 1.0
GAINS_PER_GROUP = 6
EXAMPLES = 3
OTHER_KEY = "other"
MIN_TOPICS = 2
MAX_TOPICS = 8
LABEL_LENGTH = 40
_NOT_KEY = re.compile(r"[^a-z0-9]+")


def topic_key(label: str) -> str:
    return _NOT_KEY.sub("-", label.lower()).strip("-")[:40] or "topic"


def _top_ten(position: float | None, impressions: int | None) -> bool:
    return (
        position is not None
        and position <= PAGE_ONE
        and (impressions or 0) >= MOVEMENT_MIN_IMPRESSIONS
    )


def _weighted(rows: Sequence[ReportMovementQuery], *, before: bool) -> float | None:
    total = weighted = 0.0
    for row in rows:
        position = row.before_position if before else row.after_position
        impressions = (row.before_impressions if before else row.after_impressions) or 0
        if position is None or not impressions:
            continue
        total += impressions
        weighted += position * impressions
    return round(weighted / total, 1) if total else None


def clean_topics(
    raw: object, known: set[str], *, label_limit: int = LABEL_LENGTH
) -> ReportTopics | None:
    """Hermes's grouping, made safe: known searches only, each in one topic, 2 to 8 topics.

    Returns None when too little survives for the grouping to be worth showing.
    """
    if not isinstance(raw, dict):
        return None
    taken: set[str] = set()
    variants: list[str] = []
    for item in raw.get("brand_variants") or []:
        if isinstance(item, str) and item in known and item not in taken:
            variants.append(item)
            taken.add(item)
    topics: list[ReportTopic] = []
    keys: set[str] = set()
    for item in raw.get("topics") or []:
        if not isinstance(item, dict) or not isinstance(item.get("label"), str):
            continue
        label = " ".join(item["label"].split())[:label_limit]
        queries: list[str] = []
        for query in item.get("queries") or []:
            if isinstance(query, str) and query in known and query not in taken:
                queries.append(query)
                taken.add(query)
        key = topic_key(label)
        if not label or not queries or key in keys or key == OTHER_KEY:
            continue
        keys.add(key)
        topics.append(ReportTopic(key=key, label=label, queries=queries))
    if len(topics) < MIN_TOPICS:
        return None
    return ReportTopics(topics=topics[:MAX_TOPICS], brand_variants=variants)


def search_results(
    snapshot: ReportSnapshot, topics: ReportTopics | None
) -> ReportSearchResults | None:
    movement = snapshot.search_movement
    if movement is None:
        return None
    variants = set(topics.brand_variants) if topics else set()
    rows = [row for row in movement.queries if row.query not in variants]
    if not rows:
        return None
    comparable = movement.comparable

    def counts(selected: Sequence[ReportMovementQuery]) -> tuple[int | None, int]:
        before = sum(_top_ten(row.before_position, row.before_impressions) for row in selected)
        after = sum(_top_ten(row.after_position, row.after_impressions) for row in selected)
        return (before if comparable else None), after

    def sums(selected: Sequence[ReportMovementQuery]) -> tuple[int | None, int, int | None, int]:
        return (
            sum(row.before_clicks or 0 for row in selected) if comparable else None,
            sum(row.after_clicks for row in selected),
            sum(row.before_impressions or 0 for row in selected) if comparable else None,
            sum(row.after_impressions for row in selected),
        )

    top_before, top_after = counts(rows)
    new = (
        sum(
            _top_ten(row.after_position, row.after_impressions)
            and not _top_ten(row.before_position, row.before_impressions)
            for row in rows
        )
        if comparable
        else None
    )
    clicks_before, clicks_after, impressions_before, impressions_after = sums(rows)

    by_query = {row.query: row for row in rows}
    results: list[ReportTopicResult] = []
    groups: list[tuple[str, str, list[ReportMovementQuery]]] = []
    placed: set[str] = set()
    for topic in topics.topics if topics else []:
        members = [by_query[query] for query in topic.queries if query in by_query]
        placed.update(row.query for row in members)
        if not members:
            continue
        before, after = counts(members)
        c_before, c_after, _, _ = sums(members)
        results.append(
            ReportTopicResult(
                key=topic.key,
                label=topic.label,
                examples=[
                    row.query
                    for row in sorted(members, key=lambda item: -item.after_impressions)[:EXAMPLES]
                ],
                top_ten_before=before,
                top_ten_after=after,
                position_before=_weighted(members, before=True) if comparable else None,
                position_after=_weighted(members, before=False),
                clicks_before=c_before,
                clicks_after=c_after,
            )
        )
        groups.append((topic.key, topic.label, members))
    rest = [row for row in rows if row.query not in placed]
    if topics and rest:
        groups.append((OTHER_KEY, "Other searches", rest))
    if not topics:
        groups.append((OTHER_KEY, "Searches", rows))

    gain_groups: list[ReportGainGroup] = []
    if comparable:
        for key, label, members in groups:
            gained = [row for row in members if _gained(row)]
            gained.sort(key=lambda row: (-row.after_clicks, -row.after_impressions, row.query))
            if gained:
                gain_groups.append(
                    ReportGainGroup(
                        key=key,
                        label=label,
                        rows=[
                            ReportGain(
                                query=row.query,
                                position_before=row.before_position,
                                position_after=row.after_position or 0.0,
                                impressions_before=row.before_impressions,
                                impressions_after=row.after_impressions,
                                clicks_before=row.before_clicks,
                                clicks_after=row.after_clicks,
                            )
                            for row in gained[:GAINS_PER_GROUP]
                        ],
                    )
                )
    return ReportSearchResults(
        comparable=comparable,
        months_covered=movement.months_covered,
        months_expected=movement.months_expected,
        top_ten_before=top_before,
        top_ten_after=top_after,
        new_to_page_one=new,
        clicks_before=clicks_before,
        clicks_after=clicks_after,
        impressions_before=impressions_before,
        impressions_after=impressions_after,
        position_before=_weighted(rows, before=True) if comparable else None,
        position_after=_weighted(rows, before=False),
        topics=results,
        gains=gain_groups,
    )


def _gained(row: ReportMovementQuery) -> bool:
    """A search that ranks now with enough impressions and ranks better than it did, or is new."""
    if row.after_position is None or row.after_impressions < MOVEMENT_MIN_IMPRESSIONS:
        return False
    return row.before_position is None or row.before_position - row.after_position >= GAIN_PLACES
