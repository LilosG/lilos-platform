"""Hermes drafts the two prose sections of a report; code decides whether the draft is usable.

The draft goes through the AI gateway like a review reply: a registered task, an ``ai_executions``
record and a retention policy key. The stored snapshot is the only evidence. After the draft
returns, every number in the text is extracted by code and checked against the snapshot; a draft
that states a number the data does not contain, mentions its author, or claims a cause is not
used, and the previous narrative stays exactly as it was.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.ai.factory import build_ai_gateway
from apps.api.app.ai.gateway import AIGateway, AIGatewayRequest
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.reports.contracts import (
    NarrativeFailureCode,
    NarrativeOrigin,
    ReportCountComparison,
    ReportNarrative,
    ReportPeriod,
    ReportRateComparison,
    ReportSnapshot,
)

AI_TASK_KEY = "reports.narrative_draft"
RETENTION_POLICY_KEY = "reports.ai_draft.default"
MAXIMUM_LATENCY_MS = 60_000
SECTION_LIMIT = 4_000

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_DATE_MENTION = re.compile(
    rf"\b(?:{'|'.join(_MONTHS)}|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{{1,2}}"
    r"(?:st|nd|rd|th)?\b(?:,?\s+\d{4})?",
    re.IGNORECASE,
)
_ORDINAL = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# "one" is left out on purpose: it is a pronoun far more often than a figure.
_WORD_NUMBERS: dict[str, int] = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
    "million": 1_000_000,
}
_WORD_NUMBER = re.compile(rf"\b(?:{'|'.join(_WORD_NUMBERS)})\b", re.IGNORECASE)
_AUTHORSHIP = re.compile(
    r"\bAI\b|\b(?:Claude|LILOs|Hermes|Anthropic|OpenAI|ChatGPT|GPT|artificial intelligence|"
    r"language model|machine[- ]generated|auto-?generated|assistant)\b",
    re.IGNORECASE,
)
_CAUSAL = re.compile(
    r"\b(?:because of|as a result of|resulted in|results? from|caused|causing|thanks to|"
    r"led to|driven by|owing to|attributable to|due to)\b",
    re.IGNORECASE,
)


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _variants(value: Decimal) -> Iterator[Decimal]:
    """A stored figure, its magnitude and its roundings: how a sentence may quote it."""
    for candidate in (value, abs(value)):
        yield candidate
        yield candidate.quantize(Decimal("1"))
        yield candidate.quantize(Decimal("0.1"))
        yield candidate.quantize(Decimal("0.01"))


def _leaves(document: object) -> Iterator[object]:
    if isinstance(document, dict):
        for value in document.values():
            yield from _leaves(value)
    elif isinstance(document, list):
        for value in document:
            yield from _leaves(value)
    else:
        yield document


def numbers_in(text: str) -> list[Decimal]:
    """Every number a text states: digits (with commas and decimals) and spelled-out numbers."""
    cleaned = _DATE_MENTION.sub(" ", text)
    cleaned = _ORDINAL.sub(" ", cleaned)
    cleaned = _LIST_MARKER.sub("", cleaned)
    found: list[Decimal] = []
    for whole, fraction in _NUMBER.findall(cleaned):
        number = _decimal(whole.replace(",", "") + (f".{fraction}" if fraction else ""))
        if number is not None:
            found.append(number)
    found.extend(Decimal(_WORD_NUMBERS[word.lower()]) for word in _WORD_NUMBER.findall(cleaned))
    return found


def allowed_numbers(snapshot: ReportSnapshot) -> set[Decimal]:
    """Every number the snapshot contains, anywhere in it, in the forms a sentence may use."""
    comparison = snapshot.comparison
    periods = [
        snapshot.period,
        comparison.compared,
        *([comparison.year_ago] if comparison.year_ago else []),
    ]
    allowed: set[Decimal] = {
        Decimal(month.year)
        for period in periods
        for month in (period.start_month, period.end_month)
    }
    for leaf in _leaves(snapshot.model_dump(mode="json")):
        if isinstance(leaf, bool) or leaf is None:
            continue
        if isinstance(leaf, (int, float)):
            number = _decimal(leaf)
            if number is not None:
                allowed.update(_variants(number))
        elif isinstance(leaf, str) and not _ISO_DATE.match(leaf):
            # Titles, queries and search terms may carry digits a sentence can quote.
            allowed.update(numbers_in(leaf))
    return allowed


def failure_of(narrative: ReportNarrative, snapshot: ReportSnapshot) -> NarrativeFailureCode | None:
    """Why this draft may not be used, or None when every check passes."""
    if narrative.is_empty:
        return NarrativeFailureCode.DRAFT_EMPTY
    text = f"{narrative.what_changed}\n{narrative.next_work}"
    if _AUTHORSHIP.search(text):
        return NarrativeFailureCode.AUTHORSHIP_MENTIONED
    if _CAUSAL.search(text):
        return NarrativeFailureCode.CAUSAL_CLAIM
    allowed = allowed_numbers(snapshot)
    if any(number not in allowed for number in numbers_in(text)):
        return NarrativeFailureCode.NUMBER_NOT_IN_DATA
    return None


def label_of(period: ReportPeriod) -> str:
    """ "September 2026", or "May to September 2026" (with both years when they differ)."""
    first, last = period.start_month, period.end_month
    if first == last:
        return f"{_MONTHS[first.month - 1]} {first.year}"
    start = _MONTHS[first.month - 1] + ("" if first.year == last.year else f" {first.year}")
    return f"{start} to {_MONTHS[last.month - 1]} {last.year}"


def _figure(comparison: ReportCountComparison) -> dict[str, Any]:
    out: dict[str, Any] = {
        "this_period": comparison.current.value,
        "compared_period": comparison.compared.value,
        "change": comparison.change,
        "change_percent": comparison.change_percent,
    }
    if comparison.compared_as.value == "monthly_average":
        # The compared figure is a monthly average, set against this period's monthly average.
        out["compared_period_is"] = "monthly average"
        out["this_period_monthly_average"] = comparison.current_monthly_average
    if comparison.year_ago is not None:
        out["same_period_last_year"] = comparison.year_ago.value
        out["change_vs_last_year"] = comparison.year_change
        out["change_percent_vs_last_year"] = comparison.year_change_percent
    if comparison.current.availability.value == "partial":
        out["partial"] = True
    return out


def _rate(comparison: ReportRateComparison) -> dict[str, Any]:
    return {
        "this_period": comparison.current.value,
        "compared_period": comparison.compared.value,
        "change": comparison.change,
    }


def evidence_of(snapshot: ReportSnapshot) -> dict[str, Any]:
    """The compact facts the model may write from. Every number here is a snapshot value."""
    gbp = snapshot.gbp
    reviews = snapshot.reviews
    return {
        "period": label_of(snapshot.period),
        "compared_with": label_of(snapshot.comparison.compared),
        "profile_views": _figure(gbp.profile_views.total),
        "profile_view_sources": {
            row.metric.value: _figure(row.comparison) for row in gbp.profile_views.sources
        },
        "profile_actions": _figure(gbp.actions.total),
        "actions_by_kind": {
            row.metric.value: _figure(row.comparison) for row in gbp.actions.actions
        },
        "other_actions": {
            row.metric.value: _figure(row.comparison)
            for row in gbp.actions.optional
            if row.comparable
        },
        "action_rate_percent": _rate(gbp.actions.action_rate),
        "search_terms": [
            {"term": term.keyword, "count": term.value, "fewer_than": term.below_threshold}
            for term in gbp.search_terms.terms[:10]
        ],
        "reviews": {
            "new_reviews": _figure(reviews.new_reviews),
            "average_rating_in_period": _rate(reviews.average_rating_in_period),
            "average_rating_overall": _rate(reviews.average_rating_overall),
            "total_reviews": reviews.total_count.value,
            "responses_published": reviews.responses_published.value,
            "response_rate_percent": _rate(reviews.response_rate_percent),
        },
        "search_console": {
            "clicks": _figure(snapshot.search_console.clicks),
            "impressions": _figure(snapshot.search_console.impressions),
            "average_position": _rate(snapshot.search_console.average_position),
            "branded_share_of_top_search_clicks_percent": (
                snapshot.search_console.branded_share_percent
            ),
            "top_queries": [
                {"query": row.query, "clicks": row.clicks, "clicks_change": row.clicks_change}
                for row in snapshot.search_console.top_queries[:5]
            ],
        },
        "website_visits_from_search": _figure(snapshot.analytics.organic_sessions),
        "work_completed": {
            group.kind.value: {"count": group.count, "examples": group.titles}
            for group in snapshot.work.groups
        },
        "data_gaps": sorted({note.code.value for note in snapshot.notes}),
        "local_rank_tracking": "not tracked yet",
    }


def parse_draft(output: dict[str, Any]) -> ReportNarrative | None:
    """The two sections from a gateway output; None when it is not shaped as asked."""
    document = output.get("narrative")
    if not isinstance(document, dict):
        try:
            document = json.loads(str(output.get("draft", "")))
        except ValueError:
            return None
    if not isinstance(document, dict):
        return None
    what, nxt = document.get("what_changed"), document.get("next_work")
    if not isinstance(what, str) or not isinstance(nxt, str):
        return None
    return ReportNarrative(
        what_changed=what.strip()[:SECTION_LIMIT],
        next_work=nxt.strip()[:SECTION_LIMIT],
        origin=NarrativeOrigin.HERMES,
    )


@dataclass(frozen=True, slots=True)
class DraftResult:
    narrative: ReportNarrative | None
    failure: NarrativeFailureCode | None


class NarrativeDrafter:
    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> AIGateway:
        if self._gateway is None:
            self._gateway = build_ai_gateway()
        return self._gateway

    async def _task(self, session: AsyncSession) -> AITaskDefinition:
        task = await session.scalar(
            select(AITaskDefinition).where(
                AITaskDefinition.key == AI_TASK_KEY, AITaskDefinition.status == "active"
            )
        )
        if task is None:
            task = AITaskDefinition(
                key=AI_TASK_KEY,
                version=1,
                owning_product="insights",
                purpose="Draft the narrative sections of a monthly client report for human review.",
                input_schema={"evidence": "object"},
                output_schema={"what_changed": "string", "next_work": "string"},
                risk_level="medium",
                maximum_cost_microunits=0,
                maximum_latency_ms=MAXIMUM_LATENCY_MS,
                requires_human_review=True,
                retention_policy_key=RETENTION_POLICY_KEY,
                status="active",
            )
            session.add(task)
            await session.flush()
        return task

    async def draft(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        revision_id: UUID,
        snapshot: ReportSnapshot,
    ) -> DraftResult:
        """Ask for a draft and judge it. The execution is recorded whatever the outcome."""
        task = await self._task(session)
        attempt = int(
            await session.scalar(
                select(func.count(AIExecution.id)).where(
                    AIExecution.organization_id == organization_id,
                    AIExecution.task_definition_id == task.id,
                    AIExecution.input_references.contains([str(revision_id)]),
                )
            )
            or 0
        )
        request = AIGatewayRequest(
            organization_id=organization_id,
            location_id=None,
            task_key=AI_TASK_KEY,
            input_document={"evidence": evidence_of(snapshot)},
            input_references=(revision_id,),
            # The stored, immutable snapshot is what the draft is grounded in.
            approved_fact_revision_ids=(revision_id,),
            maximum_cost_microunits=task.maximum_cost_microunits,
            maximum_latency_ms=task.maximum_latency_ms,
        )
        key = hashlib.sha256(f"report-narrative:{revision_id}:{attempt + 1}".encode()).hexdigest()
        output: dict[str, Any] = {}
        failure: NarrativeFailureCode | None = None
        narrative: ReportNarrative | None = None
        try:
            output = await self.gateway.execute(request)
        except Exception:
            # Whatever the provider did, the report is unaffected and a person can write it.
            failure = NarrativeFailureCode.DRAFT_FAILED
        if failure is None:
            narrative = parse_draft(output)
            failure = (
                NarrativeFailureCode.DRAFT_MALFORMED
                if narrative is None
                else failure_of(narrative, snapshot)
            )
        usage = output.get("usage", {}) or {}
        session.add(
            AIExecution(
                organization_id=organization_id,
                location_id=None,
                task_definition_id=task.id,
                idempotency_key=key[:128],
                status=(
                    "completed"
                    if failure is None
                    else "provider_failed"
                    if failure is NarrativeFailureCode.DRAFT_FAILED
                    else "validation_failed"
                ),
                provider_key=str(output.get("provider")) if output else None,
                model_key=str(output.get("model")) if output else None,
                input_references=[str(revision_id)],
                approved_fact_revision_ids=[str(revision_id)],
                output_document=output or None,
                output_hash=(
                    hashlib.sha256(str(output.get("draft", "")).encode()).hexdigest()
                    if output
                    else None
                ),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                estimated_cost_microunits=output.get("cost_microunits"),
                latency_ms=output.get("latency_ms"),
                requires_human_review=True,
                safe_error_code=failure.value.upper() if failure else None,
                completed_at=datetime.now(UTC),
            )
        )
        await session.flush()
        return DraftResult(None if failure else narrative, failure)
