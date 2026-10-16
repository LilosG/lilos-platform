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
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.ai.factory import build_ai_gateway
from apps.api.app.ai.gateway import AIGateway, AIGatewayRequest
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.reports.cards import (
    card_failure,
    evidence_figures,
    figure_numbers,
    figure_table,
    one_headline,
    parse_cards,
    resolve_card,
)
from apps.api.app.reports.contracts import (
    FigureKey,
    NarrativeFailureCode,
    NarrativeOrigin,
    ReportCountComparison,
    ReportFigureValue,
    ReportNarrative,
    ReportPeriod,
    ReportRateComparison,
    ReportSearchResults,
    ReportSnapshot,
    ReportTopics,
    ResultCard,
)
from apps.api.app.reports.search_results import clean_topics
from apps.api.app.reports.verify import (
    ISO_DATE,
    MONTHS,
    claims_cause,
    decimal_of,
    leaves,
    mentions_authorship,
    numbers_in,
    variants,
)

AI_TASK_KEY = "reports.narrative_draft"
TOPICS_TASK_KEY = "reports.topic_grouping"
RETENTION_POLICY_KEY = "reports.ai_draft.default"
TOPIC_QUERIES = 150
MAXIMUM_LATENCY_MS = 60_000
SECTION_LIMIT = 4_000


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
    for leaf in leaves(snapshot.model_dump(mode="json")):
        if isinstance(leaf, bool) or leaf is None:
            continue
        if isinstance(leaf, (int, float)):
            number = decimal_of(leaf)
            if number is not None:
                allowed.update(variants(number))
        elif isinstance(leaf, str) and not ISO_DATE.match(leaf):
            # Titles, queries and search terms may carry digits a sentence can quote.
            allowed.update(numbers_in(leaf))
    return allowed


def failure_of(
    narrative: ReportNarrative,
    snapshot: ReportSnapshot,
    table: Mapping[FigureKey, ReportFigureValue] | None = None,
) -> NarrativeFailureCode | None:
    """Why this draft may not be used, or None when every check passes."""
    if narrative.is_empty:
        return NarrativeFailureCode.DRAFT_EMPTY
    text = f"{narrative.what_changed}\n{narrative.next_work}"
    if mentions_authorship(text):
        return NarrativeFailureCode.AUTHORSHIP_MENTIONED
    if claims_cause(text):
        return NarrativeFailureCode.CAUSAL_CLAIM
    allowed = allowed_numbers(snapshot) | figure_numbers((table or {}).values())
    if any(number not in allowed for number in numbers_in(text)):
        return NarrativeFailureCode.NUMBER_NOT_IN_DATA
    return None


def label_of(period: ReportPeriod) -> str:
    """ "September 2026", or "May to September 2026" (with both years when they differ)."""
    first, last = period.start_month, period.end_month
    if first == last:
        return f"{MONTHS[first.month - 1]} {first.year}"
    start = MONTHS[first.month - 1] + ("" if first.year == last.year else f" {first.year}")
    return f"{start} to {MONTHS[last.month - 1]} {last.year}"


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


def evidence_of(
    snapshot: ReportSnapshot, table: Mapping[FigureKey, ReportFigureValue] | None = None
) -> dict[str, Any]:
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
        # The only figures a result card may be about, keyed by the key a card answers with.
        "result_figures": evidence_figures(table or {}),
        "data_gaps": sorted({note.code.value for note in snapshot.notes}),
        "local_rank_tracking": "not tracked yet",
    }


def parse_draft(output: dict[str, Any]) -> tuple[ReportNarrative, list[Any], int] | None:
    """The sections and the raw cards from a gateway output; None when it is not shaped as asked."""
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
    narrative = ReportNarrative(
        what_changed=what.strip()[:SECTION_LIMIT],
        next_work=nxt.strip()[:SECTION_LIMIT],
        origin=NarrativeOrigin.HERMES,
    )
    cards, skipped = parse_cards(document.get("result_cards"))
    return narrative, cards, skipped


def checked_cards(
    raw: list[Any], snapshot: ReportSnapshot, table: Mapping[FigureKey, ReportFigureValue]
) -> tuple[list[ResultCard], int]:
    """The cards that pass every check, in order (at most four), and how many were dropped."""
    kept: list[ResultCard] = []
    for item in raw:
        card = resolve_card(item, table)
        if card is not None and card_failure(card, snapshot, table) is None:
            kept.append(card)
    kept = kept[:4]
    return one_headline(kept), len(raw) - len(kept)


@dataclass(frozen=True, slots=True)
class DraftResult:
    narrative: ReportNarrative | None
    failure: NarrativeFailureCode | None
    cards_dropped: int = 0


class NarrativeDrafter:
    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> AIGateway:
        if self._gateway is None:
            self._gateway = build_ai_gateway()
        return self._gateway

    async def _task(
        self, session: AsyncSession, key: str, purpose: str, output_schema: dict[str, Any]
    ) -> AITaskDefinition:
        task = await session.scalar(
            select(AITaskDefinition).where(
                AITaskDefinition.key == key, AITaskDefinition.status == "active"
            )
        )
        if task is None:
            task = AITaskDefinition(
                key=key,
                version=1,
                owning_product="insights",
                purpose=purpose,
                input_schema={"evidence": "object"},
                output_schema=output_schema,
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

    async def _execute(
        self,
        session: AsyncSession,
        task: AITaskDefinition,
        *,
        organization_id: UUID,
        revision_id: UUID,
        input_document: dict[str, Any],
    ) -> tuple[dict[str, Any], bool, str]:
        """Run one gateway task. Returns the output, whether the provider failed, and the key."""
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
            task_key=task.key,
            input_document=input_document,
            input_references=(revision_id,),
            # The stored, immutable snapshot is what the draft is grounded in.
            approved_fact_revision_ids=(revision_id,),
            maximum_cost_microunits=task.maximum_cost_microunits,
            maximum_latency_ms=task.maximum_latency_ms,
        )
        key = hashlib.sha256(f"{task.key}:{revision_id}:{attempt + 1}".encode()).hexdigest()
        try:
            return await self.gateway.execute(request), False, key
        except Exception:
            # Whatever the provider did, the report is unaffected and a person can write it.
            return {}, True, key

    @staticmethod
    def _record(
        session: AsyncSession,
        task: AITaskDefinition,
        *,
        organization_id: UUID,
        revision_id: UUID,
        key: str,
        output: dict[str, Any],
        failure: NarrativeFailureCode | None,
    ) -> None:
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

    async def draft(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        revision_id: UUID,
        snapshot: ReportSnapshot,
        results: ReportSearchResults | None = None,
    ) -> DraftResult:
        """Ask for a draft (summary, next steps and result cards) and judge it.

        The execution is recorded whatever the outcome. A summary that fails a check is not used;
        a card that fails one is dropped alone.
        """
        task = await self._task(
            session,
            AI_TASK_KEY,
            "Draft the narrative sections of a monthly client report for human review.",
            {"what_changed": "string", "next_work": "string", "result_cards": "array"},
        )
        table = figure_table(snapshot, results)
        output, provider_failed, key = await self._execute(
            session,
            task,
            organization_id=organization_id,
            revision_id=revision_id,
            input_document={"evidence": evidence_of(snapshot, table)},
        )
        failure: NarrativeFailureCode | None = None
        narrative: ReportNarrative | None = None
        dropped = 0
        if provider_failed:
            failure = NarrativeFailureCode.DRAFT_FAILED
        else:
            parsed = parse_draft(output)
            if parsed is None:
                failure = NarrativeFailureCode.DRAFT_MALFORMED
            else:
                narrative, raw_cards, dropped = parsed
                failure = failure_of(narrative, snapshot, table)
                if failure is None:
                    cards, refused = checked_cards(raw_cards, snapshot, table)
                    dropped += refused
                    narrative = narrative.model_copy(update={"result_cards": cards})
        self._record(
            session,
            task,
            organization_id=organization_id,
            revision_id=revision_id,
            key=key,
            output=output,
            failure=failure,
        )
        await session.flush()
        return DraftResult(None if failure else narrative, failure, dropped)

    async def group_topics(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        revision_id: UUID,
        snapshot: ReportSnapshot,
    ) -> ReportTopics | None:
        """Ask Hermes to group the period's non-branded searches into topics.

        Only searches the report holds can be placed, each in one topic. None when there is nothing
        to group, the provider failed, or too little of the answer was usable.
        """
        movement = snapshot.search_movement
        if movement is None or not movement.queries:
            return None
        queries: list[dict[str, Any]] = [
            {
                "query": row.query,
                "impressions": row.after_impressions,
                "clicks": row.after_clicks,
            }
            for row in movement.queries[:TOPIC_QUERIES]
        ]
        task = await self._task(
            session,
            TOPICS_TASK_KEY,
            "Group a client's non-branded searches into topics for the report.",
            {"topics": "array", "brand_variants": "array"},
        )
        output, provider_failed, key = await self._execute(
            session,
            task,
            organization_id=organization_id,
            revision_id=revision_id,
            input_document={"evidence": {"searches": queries}},
        )
        topics: ReportTopics | None = None
        failure: NarrativeFailureCode | None = NarrativeFailureCode.DRAFT_FAILED
        if not provider_failed:
            document = output.get("topics_document")
            topics = clean_topics(document, {str(item["query"]) for item in queries})
            failure = None if topics else NarrativeFailureCode.DRAFT_MALFORMED
        self._record(
            session,
            task,
            organization_id=organization_id,
            revision_id=revision_id,
            key=key,
            output=output,
            failure=failure,
        )
        await session.flush()
        return topics
