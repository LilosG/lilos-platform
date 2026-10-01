"""Deterministic quality gate for a proposed page title or meta description.

Length and "differs from current" were the only checks, so a proposal could drop the
year and the neighbourhood a page ranks for, add a vague phrase and a brand to a
roundup title, and still pass. This gate refuses that, with a typed code and the
specific reason for every problem at once, so Hermes can correct all of them in the
same run. It uses only facts LILOs holds -- the target query, the page's own top
Search Console queries, the location profile and the current value -- never a model's
opinion, and it never invents a requirement the current value did not already satisfy.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from apps.api.app.products.seo.change_set import SiteChangeField

TITLE_MIN_LENGTH, TITLE_MAX_LENGTH = 30, 60
DESCRIPTION_MIN_LENGTH, DESCRIPTION_MAX_LENGTH = 120, 160
# The target query's core phrase must begin within this many content words of the title.
QUERY_FRONT_LOAD_WORDS = 4
TOP_QUERY_LIMIT = 5

_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "in",
        "on",
        "at",
        "of",
        "for",
        "to",
        "and",
        "or",
        "near",
        "me",
        "by",
        "with",
        "from",
        "is",
        "are",
    ]
)
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_ENTITY = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]{1,8}|#\d{2,6}|#[xX][0-9A-Fa-f]{2,6});")
_NON_WORD = re.compile(r"[^0-9a-z]+")


class QualityCode(StrEnum):
    TITLE_TOO_SHORT = "TITLE_TOO_SHORT"
    TITLE_TOO_LONG = "TITLE_TOO_LONG"
    DESCRIPTION_TOO_SHORT = "DESCRIPTION_TOO_SHORT"
    DESCRIPTION_TOO_LONG = "DESCRIPTION_TOO_LONG"
    HTML_ENTITY = "HTML_ENTITY"
    QUERY_MISSING = "QUERY_MISSING"
    QUERY_NOT_NEAR_START = "QUERY_NOT_NEAR_START"
    YEAR_REMOVED = "YEAR_REMOVED"
    LOCATION_REMOVED = "LOCATION_REMOVED"
    TOP_QUERY_TERM_REMOVED = "TOP_QUERY_TERM_REMOVED"


@dataclass(frozen=True, slots=True)
class QualityProblem:
    code: QualityCode
    reason: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.reason}"


@dataclass(frozen=True, slots=True)
class QualityContext:
    """The facts the gate checks a proposal against. Empty values skip only their own check."""

    target_query: str | None = None
    top_queries: tuple[str, ...] = ()
    location_terms: tuple[str, ...] = ()


def _tokens(value: str) -> list[str]:
    return [token for token in _NON_WORD.sub(" ", value.lower()).split() if token]


def _content(value: str) -> list[str]:
    return [token for token in _tokens(value) if token not in _STOPWORDS]


def _contains_phrase(haystack: Sequence[str], phrase: Sequence[str]) -> bool:
    return bool(phrase) and any(
        list(haystack[start : start + len(phrase)]) == list(phrase)
        for start in range(len(haystack) - len(phrase) + 1)
    )


def _phrase_start(haystack: Sequence[str], phrase: Sequence[str]) -> int | None:
    for start in range(len(haystack) - len(phrase) + 1):
        if list(haystack[start : start + len(phrase)]) == list(phrase):
            return start
    return None


def location_phrases(*raw_terms: str | None) -> tuple[str, ...]:
    """Split profile text such as "Little Italy, Downtown and East Village" into phrases."""
    phrases: list[str] = []
    for raw in raw_terms:
        if not raw:
            continue
        for part in re.split(r"[,;/\n]| and | & ", raw):
            cleaned = " ".join(part.split())
            if len(cleaned) >= 3 and cleaned.lower() not in {p.lower() for p in phrases}:
                phrases.append(cleaned)
    return tuple(phrases)


def quality_problems(
    field: SiteChangeField, current: str, proposed: str, context: QualityContext
) -> list[QualityProblem]:
    """Every way `proposed` is worse than it should be. Empty means it passes the gate.

    Only the SEO title and meta description are gated; other fields pass through.
    """
    if field not in (SiteChangeField.SEO_TITLE, SiteChangeField.META_DESCRIPTION):
        return []
    is_title = field is SiteChangeField.SEO_TITLE
    label = "title" if is_title else "meta description"
    problems: list[QualityProblem] = []

    low, high = (
        (TITLE_MIN_LENGTH, TITLE_MAX_LENGTH)
        if is_title
        else (DESCRIPTION_MIN_LENGTH, DESCRIPTION_MAX_LENGTH)
    )
    if len(proposed) < low:
        problems.append(
            QualityProblem(
                QualityCode.TITLE_TOO_SHORT if is_title else QualityCode.DESCRIPTION_TOO_SHORT,
                f"the {label} is {len(proposed)} characters; it must be at least {low}",
            )
        )
    if len(proposed) > high:
        problems.append(
            QualityProblem(
                QualityCode.TITLE_TOO_LONG if is_title else QualityCode.DESCRIPTION_TOO_LONG,
                f"the {label} is {len(proposed)} characters; it must be at most {high}",
            )
        )
    entity = _ENTITY.search(proposed)
    if entity:
        problems.append(
            QualityProblem(
                QualityCode.HTML_ENTITY,
                f"the {label} contains the unresolved HTML entity {entity.group(0)!r}; "
                "write the plain character instead",
            )
        )

    proposed_tokens = _tokens(proposed)
    current_tokens = _tokens(current)
    proposed_content = _content(proposed)
    current_content = _content(current)

    # A year the current value carries is part of what the page is known for.
    for year in sorted(set(_YEAR.findall(current)) - set(_YEAR.findall(proposed))):
        problems.append(
            QualityProblem(
                QualityCode.YEAR_REMOVED,
                f"the current {label} contains the year {year} and the proposal drops it; keep it",
            )
        )

    # So is a place it names: city, neighbourhood or service area from the location profile.
    for term in context.location_terms:
        phrase = _tokens(term)
        if _contains_phrase(current_tokens, phrase) and not _contains_phrase(
            proposed_tokens, phrase
        ):
            problems.append(
                QualityProblem(
                    QualityCode.LOCATION_REMOVED,
                    f"the current {label} names the location {term!r} and the proposal "
                    "drops it; keep it",
                )
            )

    if not is_title:
        return problems

    # The target query's core phrase must be in the title and front-loaded.
    core = _content(context.target_query or "")
    if core:
        start = _phrase_start(proposed_content, core)
        shown = " ".join(core)
        if start is None:
            problems.append(
                QualityProblem(
                    QualityCode.QUERY_MISSING,
                    f"the title must contain the target query's core phrase {shown!r}",
                )
            )
        elif start > QUERY_FRONT_LOAD_WORDS - 1:
            problems.append(
                QualityProblem(
                    QualityCode.QUERY_NOT_NEAR_START,
                    f"the target query's core phrase {shown!r} starts at word {start + 1}; "
                    f"front-load it within the first {QUERY_FRONT_LOAD_WORDS} words",
                )
            )

    # Terms the page already earns impressions for must not be edited out of its title.
    already_reported = {token for term in context.location_terms for token in _tokens(term)}
    dropped: list[str] = []
    for query in context.top_queries[:TOP_QUERY_LIMIT]:
        for token in _content(query):
            if (
                len(token) >= 3
                and token in current_content
                and token not in proposed_content
                and token not in dropped
                and token not in already_reported
                and not _YEAR.fullmatch(token)
            ):
                dropped.append(token)
    if dropped:
        problems.append(
            QualityProblem(
                QualityCode.TOP_QUERY_TERM_REMOVED,
                "the proposal drops "
                + ", ".join(repr(token) for token in dropped)
                + ", which appear in this page's own top Search Console queries and in the "
                "current title; keep them",
            )
        )
    return problems
