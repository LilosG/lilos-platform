"""Deterministic "what is driving search performance" insights for the Local Search Overview.

Pure functions over data already stored: Search Console's current and previous period (site
totals always; per-query and per-page rows only when the previous window was synced as a
window of its own) and the Business Profile's calls, website clicks and directions. No model
call and no provider call. An insight is a typed code with numbers; the console turns the
code into a sentence. With too little data there are simply no insights, never an invented one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# A percentage change off a tiny base is noise: the previous period needs this many clicks.
MIN_BASE_CLICKS = 20
MIN_CHANGE_PERCENT = 10.0
# A query or page moves the story only when it gained or lost at least this many clicks.
MIN_MOVER_CLICKS = 10
MIN_NEAR_PAGE_ONE_IMPRESSIONS = 100
NEAR_PAGE_ONE_FROM = 8.0
NEAR_PAGE_ONE_TO = 20.0
MAX_INSIGHTS = 3


class InsightCode(StrEnum):
    QUERY_GAINING_CLICKS = "QUERY_GAINING_CLICKS"
    QUERY_LOSING_CLICKS = "QUERY_LOSING_CLICKS"
    PAGE_GAINING_CLICKS = "PAGE_GAINING_CLICKS"
    PAGE_LOSING_CLICKS = "PAGE_LOSING_CLICKS"
    SEARCH_CLICKS_UP = "SEARCH_CLICKS_UP"
    SEARCH_CLICKS_DOWN = "SEARCH_CLICKS_DOWN"
    IMPRESSIONS_OUTRUNNING_CLICKS = "IMPRESSIONS_OUTRUNNING_CLICKS"
    PROFILE_ACTIONS_UP = "PROFILE_ACTIONS_UP"
    PROFILE_ACTIONS_DOWN = "PROFILE_ACTIONS_DOWN"
    QUERIES_NEAR_PAGE_ONE = "QUERIES_NEAR_PAGE_ONE"


class InsightLink(StrEnum):
    """The console screen that shows the evidence for an insight."""

    SEARCH_CONSOLE = "search_console"
    PAGES = "pages"
    GOOGLE_BUSINESS_PROFILE = "google_business_profile"


@dataclass(frozen=True, slots=True)
class Insight:
    """One finding. ``current`` and ``previous`` are the two periods' values; for
    QUERIES_NEAR_PAGE_ONE ``count`` is how many queries qualify, ``subject`` the one with the most
    impressions and ``current`` its average position. ``percent_change`` is null with no base."""

    code: InsightCode
    link: InsightLink
    subject: str | None = None
    current: float | None = None
    previous: float | None = None
    percent_change: float | None = None
    count: int | None = None


@dataclass(frozen=True, slots=True)
class ProfileActions:
    current: int | None
    previous: int | None


def _percent(current: float, previous: float) -> float | None:
    return None if previous == 0 else (current - previous) / abs(previous) * 100


def _metric(metrics: Mapping[str, Any], key: str) -> tuple[float, float] | None:
    metric = metrics.get(key) or {}
    current, previous = metric.get("current"), metric.get("previous")
    if current is None or previous is None:
        return None
    return float(current), float(previous)


def _site_insights(metrics: Mapping[str, Any]) -> list[Insight]:
    found: list[Insight] = []
    clicks = _metric(metrics, "clicks")
    impressions = _metric(metrics, "impressions")
    clicks_change = _percent(*clicks) if clicks and clicks[1] >= MIN_BASE_CLICKS else None
    if clicks and clicks_change is not None and abs(clicks_change) >= MIN_CHANGE_PERCENT:
        found.append(
            Insight(
                code=InsightCode.SEARCH_CLICKS_UP
                if clicks_change > 0
                else InsightCode.SEARCH_CLICKS_DOWN,
                link=InsightLink.SEARCH_CONSOLE,
                current=clicks[0],
                previous=clicks[1],
                percent_change=clicks_change,
            )
        )
    impressions_change = _percent(*impressions) if impressions and impressions[1] > 0 else None
    if (
        impressions
        and clicks
        and clicks_change is not None
        and impressions_change is not None
        and impressions_change >= MIN_CHANGE_PERCENT
        and clicks_change <= impressions_change - MIN_CHANGE_PERCENT
    ):
        # More people saw the results but proportionally fewer clicked: a click-through problem.
        found.append(
            Insight(
                code=InsightCode.IMPRESSIONS_OUTRUNNING_CLICKS,
                link=InsightLink.SEARCH_CONSOLE,
                current=impressions[0],
                previous=impressions[1],
                percent_change=impressions_change,
            )
        )
    return found


def _profile_insight(actions: ProfileActions | None) -> list[Insight]:
    if actions is None or actions.current is None or actions.previous is None:
        return []
    change = _percent(actions.current, actions.previous)
    if actions.previous < MIN_BASE_CLICKS or change is None or abs(change) < MIN_CHANGE_PERCENT:
        return []
    return [
        Insight(
            code=InsightCode.PROFILE_ACTIONS_UP if change > 0 else InsightCode.PROFILE_ACTIONS_DOWN,
            link=InsightLink.GOOGLE_BUSINESS_PROFILE,
            current=float(actions.current),
            previous=float(actions.previous),
            percent_change=change,
        )
    ]


def _mover(
    current_rows: Sequence[Mapping[str, Any]],
    previous_rows: Sequence[Mapping[str, Any]],
    key: str,
    *,
    gaining: InsightCode,
    losing: InsightCode,
    link: InsightLink,
) -> list[Insight]:
    """The query or page whose clicks moved most between two synced windows, if it moved enough."""
    if not current_rows or not previous_rows:
        return []
    before = {str(row[key]): float(row.get("clicks") or 0) for row in previous_rows}
    best: tuple[float, str, float, float] | None = None
    for row in current_rows:
        name = str(row[key])
        if name not in before:
            continue
        now = float(row.get("clicks") or 0)
        delta = now - before[name]
        if abs(delta) >= MIN_MOVER_CLICKS and (best is None or abs(delta) > abs(best[0])):
            best = (delta, name, now, before[name])
    if best is None:
        return []
    delta, name, now, then = best
    return [
        Insight(
            code=gaining if delta > 0 else losing,
            link=link,
            subject=name,
            current=now,
            previous=then,
            percent_change=_percent(now, then),
        )
    ]


def _near_page_one(queries: Sequence[Mapping[str, Any]]) -> list[Insight]:
    near = [
        row
        for row in queries
        if row.get("position") is not None
        and NEAR_PAGE_ONE_FROM <= float(row["position"]) <= NEAR_PAGE_ONE_TO
        and float(row.get("impressions") or 0) >= MIN_NEAR_PAGE_ONE_IMPRESSIONS
    ]
    if not near:
        return []
    top = max(near, key=lambda row: float(row.get("impressions") or 0))
    return [
        Insight(
            code=InsightCode.QUERIES_NEAR_PAGE_ONE,
            link=InsightLink.SEARCH_CONSOLE,
            subject=str(top["query"]),
            current=float(top["position"]),
            count=len(near),
        )
    ]


def build_insights(
    report: Mapping[str, Any], profile_actions: ProfileActions | None
) -> list[Insight]:
    """At most three insights, the most specific first. Empty when the data does not support one."""
    if not report.get("connected") or not report.get("metrics"):
        return _profile_insight(profile_actions)[:MAX_INSIGHTS]
    ordered = [
        *_mover(
            report.get("top_queries", []),
            report.get("previous_top_queries", []),
            "query",
            gaining=InsightCode.QUERY_GAINING_CLICKS,
            losing=InsightCode.QUERY_LOSING_CLICKS,
            link=InsightLink.SEARCH_CONSOLE,
        ),
        *_mover(
            report.get("top_pages", []),
            report.get("previous_top_pages", []),
            "page",
            gaining=InsightCode.PAGE_GAINING_CLICKS,
            losing=InsightCode.PAGE_LOSING_CLICKS,
            link=InsightLink.PAGES,
        ),
        *_site_insights(report["metrics"]),
        *_profile_insight(profile_actions),
        *_near_page_one(report.get("top_queries", [])),
    ]
    return ordered[:MAX_INSIGHTS]
