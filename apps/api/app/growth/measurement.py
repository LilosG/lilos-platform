"""Measurement and outcome persistence for Growth actions.

Automatic measurement reads only persisted provider observations already owned by
LILOs. It never calls providers, never invents a causal claim, and never treats a
successful execution as proof that the expected business outcome occurred.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.growth.contracts import GrowthActionOutcomeRecord
from apps.api.app.growth.models import GrowthAction, GrowthInitiative, GrowthOutcome
from apps.api.app.growth.service import GrowthStateError
from apps.api.app.insights.models import InsightSource, MetricDefinition, MetricObservation
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.models import (
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.reporting_periods import (
    GA4_SYNC_TAIL_EXCLUSION_DAYS,
    GSC_SYNC_TAIL_EXCLUSION_DAYS,
)

SUPPORTED_WINDOWS = frozenset({7, 28, 90})
MEASUREMENT_DATA_GRACE_DAYS = 7

MetricFamily = Literal["gsc", "ga4"]
Direction = Literal["increase", "decrease"]


@dataclass(frozen=True, slots=True)
class MetricSpec:
    family: MetricFamily
    source_key: str
    direction: Direction


METRIC_SPECS: dict[str, MetricSpec] = {
    "gsc_clicks": MetricSpec("gsc", "clicks", "increase"),
    "gsc_impressions": MetricSpec("gsc", "impressions", "increase"),
    "gsc_ctr": MetricSpec("gsc", "ctr", "increase"),
    "gsc_position": MetricSpec("gsc", "position", "decrease"),
    "ga4_sessions": MetricSpec("ga4", "ga4.sessions", "increase"),
    "ga4_users": MetricSpec("ga4", "ga4.totalUsers", "increase"),
    "ga4_pageviews": MetricSpec("ga4", "ga4.screenPageViews", "increase"),
    "ga4_conversions": MetricSpec("ga4", "ga4.conversions", "increase"),
}

METRIC_ALIASES = {
    "gsc.clicks": "gsc_clicks",
    "gsc.impressions": "gsc_impressions",
    "gsc.ctr": "gsc_ctr",
    "gsc.position": "gsc_position",
    "ga4.sessions": "ga4_sessions",
    "ga4.totalusers": "ga4_users",
    "ga4.users": "ga4_users",
    "ga4.screenpageviews": "ga4_pageviews",
    "ga4.pageviews": "ga4_pageviews",
    "ga4.conversions": "ga4_conversions",
}


@dataclass(frozen=True, slots=True)
class VerificationPlan:
    metric: str
    window_days: int
    direction: Direction
    minimum_change_percent: Decimal


@dataclass(frozen=True, slots=True)
class MetricWindow:
    value: Decimal | None
    period_start: datetime
    period_end: datetime
    coverage: Decimal
    observed_rows: int
    expected_rows: int
    source_count: int
    provider: str

    @property
    def complete(self) -> bool:
        return (
            self.value is not None and self.expected_rows > 0 and self.coverage >= Decimal("0.95")
        )


@dataclass(frozen=True, slots=True)
class GrowthMeasurementSweepResult:
    scanned: int = 0
    measured: int = 0
    pending: int = 0
    manual: int = 0
    inconclusive: int = 0


def normalize_metric(value: object) -> str:
    raw = str(value or "").strip().lower()
    return METRIC_ALIASES.get(raw, raw)


def parse_verification_plan(raw: dict[str, object]) -> VerificationPlan | None:
    metric = normalize_metric(raw.get("metric"))
    spec = METRIC_SPECS.get(metric)
    if spec is None:
        return None
    try:
        window_days = int(raw.get("window_days", 28))
    except (TypeError, ValueError):
        return None
    if window_days not in SUPPORTED_WINDOWS:
        return None
    requested_direction = str(raw.get("direction") or spec.direction).strip().lower()
    if requested_direction not in {"increase", "decrease"}:
        return None
    try:
        threshold = Decimal(str(raw.get("minimum_change_percent", 0)))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if threshold < 0 or threshold > 1000:
        return None
    return VerificationPlan(
        metric=metric,
        window_days=window_days,
        direction=requested_direction,  # type: ignore[arg-type]
        minimum_change_percent=threshold,
    )


def classify_change(
    baseline: Decimal,
    measurement: Decimal,
    *,
    direction: Direction,
    minimum_change_percent: Decimal,
) -> tuple[str, Decimal | None]:
    """Classify direction and materiality without making a causal claim."""
    if baseline == measurement:
        return "unchanged", Decimal("0")
    if baseline == 0:
        if measurement == 0:
            return "unchanged", Decimal("0")
        favorable = measurement > 0 if direction == "increase" else measurement < 0
        return ("improved" if favorable else "regressed"), None

    change_percent = ((measurement - baseline) / abs(baseline)) * Decimal("100")
    if abs(change_percent) < minimum_change_percent:
        return "unchanged", change_percent
    favorable = change_percent > 0 if direction == "increase" else change_percent < 0
    return ("improved" if favorable else "regressed"), change_percent


def utc_day_after(value: datetime) -> datetime:
    value = value.astimezone(UTC)
    day = value.replace(hour=0, minute=0, second=0, microsecond=0)
    return day + timedelta(days=1)


class GrowthMeasurementService:
    """Persist human-entered and scheduler-measured Growth outcomes."""

    def __init__(self) -> None:
        self.audit = AuditEventService()

    async def record(
        self,
        session: AsyncSession,
        organization_id: UUID,
        action_id: UUID,
        command: GrowthActionOutcomeRecord,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> GrowthOutcome:
        action = await session.scalar(
            select(GrowthAction).where(
                GrowthAction.organization_id == organization_id,
                GrowthAction.id == action_id,
            )
        )
        if action is None:
            raise GrowthStateError("growth action not found")
        if action.status != "completed":
            raise GrowthStateError("only completed growth actions may be measured")
        return await self._persist(
            session,
            action,
            classification=command.classification,
            baseline=command.baseline,
            measurement=command.measurement,
            limitations=list(command.limitations),
            actor_id=actor_id,
            correlation_id=correlation_id,
            automated=False,
        )

    async def measure_ready_batch(
        self,
        session: AsyncSession,
        *,
        limit: int = 100,
        now: datetime | None = None,
    ) -> GrowthMeasurementSweepResult:
        """Measure completed actions whose declared provider-evidence window matured.

        Unsupported or non-quantitative verification plans remain available for
        explicit human measurement instead of being converted into fabricated data.
        """
        bounded_limit = min(max(limit, 1), 500)
        observed_now = (now or datetime.now(UTC)).astimezone(UTC)
        candidate_ids = list(
            await session.scalars(
                select(GrowthAction.id)
                .where(
                    GrowthAction.status == "completed",
                    GrowthAction.completed_at.is_not(None),
                )
                .order_by(GrowthAction.completed_at, GrowthAction.id)
                .limit(bounded_limit)
            )
        )

        measured = 0
        pending = 0
        manual = 0
        inconclusive = 0
        for action_id in candidate_ids:
            action = await session.scalar(
                select(GrowthAction).where(GrowthAction.id == action_id).with_for_update()
            )
            if action is None or action.completed_at is None:
                continue
            existing = await session.scalar(
                select(GrowthOutcome.id)
                .where(
                    GrowthOutcome.organization_id == action.organization_id,
                    GrowthOutcome.action_id == action.id,
                )
                .limit(1)
            )
            if existing is not None:
                continue

            plan = parse_verification_plan(dict(action.verification_plan or {}))
            if plan is None:
                manual += 1
                continue
            initiative = await session.scalar(
                select(GrowthInitiative).where(
                    GrowthInitiative.organization_id == action.organization_id,
                    GrowthInitiative.id == action.initiative_id,
                )
            )
            if initiative is None:
                manual += 1
                continue

            measurement_start = utc_day_after(action.completed_at)
            measurement_end = measurement_start + timedelta(days=plan.window_days)
            tail_days = (
                GSC_SYNC_TAIL_EXCLUSION_DAYS
                if METRIC_SPECS[plan.metric].family == "gsc"
                else GA4_SYNC_TAIL_EXCLUSION_DAYS
            )
            ready_at = measurement_end + timedelta(days=tail_days)
            if observed_now < ready_at:
                pending += 1
                continue

            baseline_start = measurement_start - timedelta(days=plan.window_days)
            baseline = await self._metric_window(
                session,
                action.organization_id,
                initiative.location_id,
                plan.metric,
                baseline_start,
                measurement_start,
            )
            measurement = await self._metric_window(
                session,
                action.organization_id,
                initiative.location_id,
                plan.metric,
                measurement_start,
                measurement_end,
            )

            limitations = [
                "Observed association; external factors may contribute to the measured change.",
                "Uses persisted provider observations; missing provider data is never inferred.",
            ]
            if plan.minimum_change_percent == 0:
                limitations.append(
                    "No materiality threshold was declared; any directional change may classify."
                )
            if baseline.source_count > 1 or measurement.source_count > 1:
                limitations.append(
                    "Multiple properties were aggregated; audiences are not deduplicated."
                )
            if action.target_reference:
                limitations.append(
                    "The provider metric may not isolate the action target by itself."
                )

            if not baseline.complete or not measurement.complete:
                grace_deadline = ready_at + timedelta(days=MEASUREMENT_DATA_GRACE_DAYS)
                if observed_now < grace_deadline:
                    pending += 1
                    continue
                limitations.append(
                    "Provider observations remained incomplete after the measurement grace period."
                )
                await self._persist(
                    session,
                    action,
                    classification="inconclusive",
                    baseline=self._window_payload(plan, baseline),
                    measurement=self._window_payload(plan, measurement),
                    limitations=limitations,
                    actor_id=None,
                    correlation_id=f"growth-measurement-{action.id}"[:64],
                    automated=True,
                )
                measured += 1
                inconclusive += 1
                continue

            assert baseline.value is not None
            assert measurement.value is not None
            classification, change_percent = classify_change(
                baseline.value,
                measurement.value,
                direction=plan.direction,
                minimum_change_percent=plan.minimum_change_percent,
            )
            measurement_payload = self._window_payload(plan, measurement)
            measurement_payload.update(
                {
                    "change": str(measurement.value - baseline.value),
                    "change_percent": str(change_percent) if change_percent is not None else None,
                    "direction": plan.direction,
                    "minimum_change_percent": str(plan.minimum_change_percent),
                }
            )
            await self._persist(
                session,
                action,
                classification=classification,
                baseline=self._window_payload(plan, baseline),
                measurement=measurement_payload,
                limitations=limitations,
                actor_id=None,
                correlation_id=f"growth-measurement-{action.id}"[:64],
                automated=True,
            )
            measured += 1

        return GrowthMeasurementSweepResult(
            scanned=len(candidate_ids),
            measured=measured,
            pending=pending,
            manual=manual,
            inconclusive=inconclusive,
        )

    async def _metric_window(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID | None,
        metric: str,
        start: datetime,
        end: datetime,
    ) -> MetricWindow:
        spec = METRIC_SPECS[metric]
        if spec.family == "gsc":
            return await self._gsc_window(
                session, organization_id, location_id, spec.source_key, start, end
            )
        return await self._ga4_window(
            session, organization_id, location_id, spec.source_key, start, end
        )

    async def _gsc_window(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID | None,
        field: str,
        start: datetime,
        end: datetime,
    ) -> MetricWindow:
        statement = (
            select(SEOSearchProperty.id)
            .join(
                SEOWebsite,
                (SEOWebsite.organization_id == SEOSearchProperty.organization_id)
                & (SEOWebsite.id == SEOSearchProperty.website_id),
            )
            .where(
                SEOSearchProperty.organization_id == organization_id,
                SEOSearchProperty.mapping_status == "mapped",
            )
        )
        if location_id is not None:
            statement = statement.where(
                or_(SEOWebsite.location_id == location_id, SEOWebsite.location_id.is_(None))
            )
        property_ids = list(await session.scalars(statement))
        expected_rows = len(property_ids) * (end - start).days
        if not property_ids:
            return MetricWindow(None, start, end, Decimal("0"), 0, 0, 0, "google_search_console")

        observations = list(
            await session.scalars(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.organization_id == organization_id,
                    SEOSearchObservation.search_property_id.in_(property_ids),
                    SEOSearchObservation.date_start >= start,
                    SEOSearchObservation.date_start < end,
                    SEOSearchObservation.partial.is_(False),
                    SEOSearchObservation.quality_status == "valid",
                    SEOSearchObservation.dimensions.op("->>")("observation_type") == "daily",
                )
            )
        )
        observed_keys = {(item.search_property_id, item.date_start.date()) for item in observations}
        coverage = (
            Decimal(len(observed_keys)) / Decimal(expected_rows) if expected_rows else Decimal("0")
        )
        value: Decimal | None
        if field == "clicks":
            value = sum((Decimal(item.clicks or 0) for item in observations), Decimal("0"))
        elif field == "impressions":
            value = sum((Decimal(item.impressions or 0) for item in observations), Decimal("0"))
        elif field == "ctr":
            clicks = sum((Decimal(item.clicks or 0) for item in observations), Decimal("0"))
            impressions = sum(
                (Decimal(item.impressions or 0) for item in observations), Decimal("0")
            )
            value = clicks / impressions if impressions else None
        else:
            weighted = Decimal("0")
            impressions = Decimal("0")
            for item in observations:
                weight = Decimal(item.impressions or 0)
                if item.position is not None and weight:
                    weighted += Decimal(str(item.position)) * weight
                    impressions += weight
            value = weighted / impressions if impressions else None
        return MetricWindow(
            value,
            start,
            end,
            coverage,
            len(observations),
            expected_rows,
            len(property_ids),
            "google_search_console",
        )

    async def _ga4_window(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID | None,
        metric_key: str,
        start: datetime,
        end: datetime,
    ) -> MetricWindow:
        statement = select(AnalyticsProperty).where(
            AnalyticsProperty.organization_id == organization_id,
            AnalyticsProperty.provider == "google_analytics",
            AnalyticsProperty.mapping_status == "mapped",
        )
        if location_id is not None:
            statement = statement.join(
                SEOWebsite,
                (SEOWebsite.organization_id == AnalyticsProperty.organization_id)
                & (SEOWebsite.id == AnalyticsProperty.website_id),
            ).where(or_(SEOWebsite.location_id == location_id, SEOWebsite.location_id.is_(None)))
        properties = list(await session.scalars(statement))
        expected_rows = len(properties) * (end - start).days
        if not properties:
            return MetricWindow(None, start, end, Decimal("0"), 0, 0, 0, "google_analytics")

        definition = await session.scalar(
            select(MetricDefinition)
            .where(MetricDefinition.key == metric_key, MetricDefinition.status == "active")
            .order_by(MetricDefinition.version.desc())
            .limit(1)
        )
        if definition is None:
            return MetricWindow(
                None,
                start,
                end,
                Decimal("0"),
                0,
                expected_rows,
                len(properties),
                "google_analytics",
            )

        external_ids = [item.external_property_id for item in properties]
        sources = list(
            await session.scalars(
                select(InsightSource).where(
                    InsightSource.organization_id == organization_id,
                    InsightSource.source_type == "analytics_property",
                    InsightSource.key.in_(external_ids),
                    InsightSource.status == "active",
                )
            )
        )
        source_ids = [item.id for item in sources]
        if not source_ids:
            return MetricWindow(
                None,
                start,
                end,
                Decimal("0"),
                0,
                expected_rows,
                len(properties),
                "google_analytics",
            )

        observations = list(
            await session.scalars(
                select(MetricObservation).where(
                    MetricObservation.organization_id == organization_id,
                    MetricObservation.source_id.in_(source_ids),
                    MetricObservation.metric_definition_id == definition.id,
                    MetricObservation.period_start >= start,
                    MetricObservation.period_start < end,
                    MetricObservation.quality_state.in_(("valid", "zero")),
                    MetricObservation.dimensions.op("->>")("observation_type") == "daily",
                )
            )
        )
        observed_keys = {(item.source_id, item.period_start.date()) for item in observations}
        coverage = (
            Decimal(len(observed_keys)) / Decimal(expected_rows) if expected_rows else Decimal("0")
        )
        value = sum((Decimal(item.value or 0) for item in observations), Decimal("0"))
        return MetricWindow(
            value,
            start,
            end,
            coverage,
            len(observations),
            expected_rows,
            len(properties),
            "google_analytics",
        )

    @staticmethod
    def _window_payload(plan: VerificationPlan, window: MetricWindow) -> dict[str, object]:
        return {
            "metric": plan.metric,
            "value": str(window.value) if window.value is not None else None,
            "period_start": window.period_start.isoformat(),
            "period_end": window.period_end.isoformat(),
            "coverage": str(window.coverage),
            "observed_rows": window.observed_rows,
            "expected_rows": window.expected_rows,
            "source_count": window.source_count,
            "provider": window.provider,
            "window_days": plan.window_days,
        }

    async def _persist(
        self,
        session: AsyncSession,
        action: GrowthAction,
        *,
        classification: str,
        baseline: dict[str, object],
        measurement: dict[str, object],
        limitations: list[str],
        actor_id: UUID | None,
        correlation_id: str,
        automated: bool,
    ) -> GrowthOutcome:
        outcome = GrowthOutcome(
            organization_id=action.organization_id,
            action_id=action.id,
            classification=classification,
            baseline=baseline,
            measurement=measurement,
            limitations=limitations,
        )
        session.add(outcome)
        await session.flush()
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="growth.outcome.measured" if automated else "growth.outcome.recorded",
                action="growth.outcome.measure" if automated else "growth.outcome.record",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM if automated else AuditActorType.USER,
                actor_id=actor_id,
                actor_display_reference="growth-measurement" if automated else None,
                organization_id=action.organization_id,
                product_key="growth",
                resource_type="growth_outcome",
                resource_id=outcome.id,
                correlation_id=correlation_id,
                summary=(
                    "Measured Growth action outcome from persisted provider evidence."
                    if automated
                    else "Measured outcome recorded for a Growth action."
                ),
                metadata={
                    "action_id": str(action.id),
                    "classification": classification,
                    "automated": automated,
                },
            ),
        )
        return outcome

    async def list_for_initiative(
        self,
        session: AsyncSession,
        organization_id: UUID,
        initiative_id: UUID,
    ) -> list[GrowthOutcome]:
        return list(
            await session.scalars(
                select(GrowthOutcome)
                .join(
                    GrowthAction,
                    (GrowthAction.organization_id == GrowthOutcome.organization_id)
                    & (GrowthAction.id == GrowthOutcome.action_id),
                )
                .where(
                    GrowthOutcome.organization_id == organization_id,
                    GrowthAction.initiative_id == initiative_id,
                )
                .order_by(GrowthOutcome.observed_at.desc())
            )
        )
