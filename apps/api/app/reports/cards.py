"""Result cards: the figures a card may be about, and the checks a drafted card must pass.

Hermes picks which figures to show and writes a title and a sentence. Everything numeric is code:
the figures are looked up here from the stored report, and every number in the words must be one of
those figures. A card whose words state another number, claim a cause, or call a result good or
bad when the figure did not move that way is dropped. Nothing here invents a win.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

from apps.api.app.products.gbp.performance_enums import GBPPerformanceMetric
from apps.api.app.reports.contracts import (
    Availability,
    CardTone,
    ComparedAs,
    FigureKey,
    FigureUnit,
    NarrativeFailureCode,
    ReportCountComparison,
    ReportFigureValue,
    ReportRateComparison,
    ReportSearchResults,
    ReportSnapshot,
    ResultCard,
    ResultCardUpdate,
)
from apps.api.app.reports.errors import ReportCardFigureUnavailableError
from apps.api.app.reports.verify import (
    claims_cause,
    decimal_of,
    mentions_authorship,
    numbers_in,
    variants,
)

MAX_CARDS = 4
_ACTION_METRIC: dict[FigureKey, GBPPerformanceMetric] = {
    FigureKey.CALLS: GBPPerformanceMetric.CALL_CLICKS,
    FigureKey.WEBSITE_CLICKS: GBPPerformanceMetric.WEBSITE_CLICKS,
    FigureKey.DIRECTION_REQUESTS: GBPPerformanceMetric.BUSINESS_DIRECTION_REQUESTS,
}


def _count(key: FigureKey, comparison: ReportCountComparison) -> ReportFigureValue | None:
    """A count set against its comparison, only when both sides are settled."""
    if (
        comparison.current.availability is not Availability.AVAILABLE
        or comparison.compared.availability is not Availability.AVAILABLE
        or comparison.change is None
        or comparison.current.value is None
        or comparison.compared.value is None
    ):
        return None
    averaged = comparison.compared_as is ComparedAs.MONTHLY_AVERAGE
    current = comparison.current_monthly_average if averaged else comparison.current.value
    if current is None:
        return None
    return ReportFigureValue(
        key=key,
        unit=FigureUnit.COUNT,
        current=float(current),
        monthly_average=averaged,
        compared=float(comparison.compared.value),
        change=float(comparison.change),
        change_percent=comparison.change_percent,
    )


def _rating(key: FigureKey, comparison: ReportRateComparison) -> ReportFigureValue | None:
    if (
        comparison.current.availability is not Availability.AVAILABLE
        or comparison.compared.availability is not Availability.AVAILABLE
        or comparison.change is None
        or comparison.current.value is None
        or comparison.compared.value is None
    ):
        return None
    return ReportFigureValue(
        key=key,
        unit=FigureUnit.STARS,
        current=comparison.current.value,
        compared=comparison.compared.value,
        change=comparison.change,
    )


def figure_table(
    snapshot: ReportSnapshot, results: ReportSearchResults | None
) -> dict[FigureKey, ReportFigureValue]:
    """Every figure a card may be about: the ones the stored report can actually state."""
    found: list[ReportFigureValue | None] = [
        _count(FigureKey.PROFILE_VIEWS, snapshot.gbp.profile_views.total),
        _count(FigureKey.PROFILE_ACTIONS, snapshot.gbp.actions.total),
        *[
            _count(key, row.comparison)
            for key, metric in _ACTION_METRIC.items()
            for row in snapshot.gbp.actions.actions
            if row.metric is metric and row.reported
        ],
        _count(FigureKey.SEARCH_CLICKS, snapshot.search_console.clicks),
        _count(FigureKey.SEARCH_IMPRESSIONS, snapshot.search_console.impressions),
        _count(FigureKey.ORGANIC_SESSIONS, snapshot.analytics.organic_sessions),
        _count(FigureKey.NEW_REVIEWS, snapshot.reviews.new_reviews),
        _rating(FigureKey.AVERAGE_RATING, snapshot.reviews.average_rating_overall),
    ]
    table = {item.key: item for item in found if item is not None}
    if results is not None and results.comparable and results.top_ten_before is not None:
        before = float(results.top_ten_before)
        change = float(results.top_ten_after) - before
        table[FigureKey.SEARCHES_IN_TOP_TEN] = ReportFigureValue(
            key=FigureKey.SEARCHES_IN_TOP_TEN,
            unit=FigureUnit.COUNT,
            current=float(results.top_ten_after),
            compared=before,
            change=change,
            change_percent=round(change / before * 100, 1) if before else None,
        )
        if results.new_to_page_one is not None:
            table[FigureKey.NEW_TO_PAGE_ONE] = ReportFigureValue(
                key=FigureKey.NEW_TO_PAGE_ONE,
                unit=FigureUnit.COUNT,
                current=float(results.new_to_page_one),
            )
    return table


def evidence_figures(table: Mapping[FigureKey, ReportFigureValue]) -> dict[str, Any]:
    """The figures as the model sees them, keyed by the key it must answer with."""
    return {
        key.value: {
            "this_period": figure.current,
            "this_period_is_monthly_average": figure.monthly_average,
            "compared_period": figure.compared,
            "change": figure.change,
            "change_percent": figure.change_percent,
            "unit": figure.unit.value,
        }
        for key, figure in table.items()
    }


def figure_numbers(figures: Iterable[ReportFigureValue]) -> set[Decimal]:
    """The numbers a sentence about these figures may state."""
    allowed: set[Decimal] = set()
    for figure in figures:
        for value in (figure.current, figure.compared, figure.change, figure.change_percent):
            number = decimal_of(value) if value is not None else None
            if number is not None:
                allowed.update(variants(number))
    return allowed


def _direction(figures: list[ReportFigureValue]) -> float:
    return figures[0].change or 0.0


def card_failure(
    card: ResultCard, snapshot: ReportSnapshot, table: Mapping[FigureKey, ReportFigureValue]
) -> NarrativeFailureCode | None:
    """Why this card may not be used, or None when every check passes."""
    text = f"{card.title}\n{card.text}"
    if not card.title.strip() or not card.text.strip():
        return NarrativeFailureCode.DRAFT_EMPTY
    if mentions_authorship(text):
        return NarrativeFailureCode.AUTHORSHIP_MENTIONED
    if claims_cause(text):
        return NarrativeFailureCode.CAUSAL_CLAIM
    allowed = figure_numbers(card.figures)
    allowed.update(
        Decimal(month.year) for month in (snapshot.period.start_month, snapshot.period.end_month)
    )
    if any(number not in allowed for number in numbers_in(text)):
        return NarrativeFailureCode.NUMBER_NOT_IN_DATA
    moved = _direction(card.figures)
    if (card.tone is CardTone.GOOD and moved <= 0) or (card.tone is CardTone.BAD and moved >= 0):
        return NarrativeFailureCode.TONE_NOT_SUPPORTED
    return None


def resolve_card(
    raw: ResultCardUpdate, table: Mapping[FigureKey, ReportFigureValue]
) -> ResultCard | None:
    """A card with its figures looked up; None when one of its figures cannot be stated."""
    figures = [table[key] for key in raw.figure_keys if key in table]
    if len(figures) != len(raw.figure_keys):
        return None
    return ResultCard(
        figure_keys=raw.figure_keys,
        figures=figures,
        tone=raw.tone,
        headline=raw.headline,
        title=raw.title.strip(),
        text=raw.text.strip(),
    )


def edited_cards(
    updates: list[ResultCardUpdate], table: Mapping[FigureKey, ReportFigureValue]
) -> list[ResultCard]:
    """The cards a person saved. A card about a figure the report cannot state is refused."""
    cards: list[ResultCard] = []
    for update in updates[:MAX_CARDS]:
        card = resolve_card(update, table)
        if card is None:
            raise ReportCardFigureUnavailableError
        cards.append(card)
    return one_headline(cards)


def one_headline(cards: list[ResultCard]) -> list[ResultCard]:
    """At most one card is the headline: the first one marked."""
    seen = False
    out: list[ResultCard] = []
    for card in cards:
        flag = card.headline and not seen
        seen = seen or flag
        out.append(card.model_copy(update={"headline": flag}))
    return out


def parse_cards(raw: object) -> tuple[list[ResultCardUpdate], int]:
    """The cards of a gateway output shaped as asked, and how many were not."""
    if not isinstance(raw, list):
        return [], 0
    parsed: list[ResultCardUpdate] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            parsed.append(
                ResultCardUpdate.model_validate(
                    {
                        key: item.get(key)
                        for key in ("figure_keys", "tone", "headline", "title", "text")
                        if key in item
                    }
                )
            )
        except ValueError:
            continue
    return parsed, len(raw) - len(parsed)
