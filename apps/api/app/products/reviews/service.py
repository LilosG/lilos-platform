"""Deterministic review ingestion, risk, drafting, approval, and publication intent."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypedDict, cast
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.ai.factory import build_ai_gateway
from apps.api.app.ai.gateway import AIGatewayRequest
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.models import AuditEvent
from apps.api.app.audit.repository import AuditEventRepository
from apps.api.app.audit.service import AuditEventService
from apps.api.app.execution.service import ExecutionService
from apps.api.app.notifications.models import NotificationTemplate
from apps.api.app.notifications.service import NotificationService
from apps.api.app.products.reviews.errors import (
    GroundingRequiredError,
    InvalidReviewQueryError,
    ResponseNotApprovalEligibleError,
    ResponseNotPublishEligibleError,
    RestrictedReviewCannotAutoPublishError,
    ReviewChangedAfterDraftError,
    ReviewNotFoundError,
    ReviewResponseNotFoundError,
    ReviewRevisionNotFoundError,
    UnsafeDraftError,
)
from apps.api.app.products.reviews.models import (
    Review,
    ReviewEscalation,
    ReviewResponseRevision,
    ReviewRevision,
)

RISK_TERMS = {
    "legal": ("lawyer", "lawsuit", "attorney"),
    "injury": ("injured", "hospital", "hurt"),
    "discrimination": ("discrimination", "racist"),
    "employee_misconduct": ("employee assaulted", "staff stole"),
    "refund": ("refund", "chargeback"),
    "privacy": ("private information", "phone number"),
}
PROHIBITED_DRAFT_TERMS = (
    "we admit liability",
    "we guarantee compensation",
    "the reviewer is lying",
)
AI_TASK_KEY = "reviews.response_draft"
NOTIFICATION_TEMPLATES = {
    "reviews.restricted_case_created": (
        "in_app",
        "A review requires human review before any response.",
    ),
    "reviews.response.publication_reserved": (
        "in_app",
        "A review response was reserved for publication.",
    ),
}
PROVIDER_OBSERVED_TYPE = "imported"
ACTIVE_LOCAL_RESPONSE_STATUSES = ("draft", "generated", "awaiting_approval", "approved")
PROVIDER_REPLY_STATE_UNSPECIFIED = "REVIEW_REPLY_STATE_UNSPECIFIED"


class ReviewClassification(TypedDict):
    risks: list[str]
    restricted: bool
    sentiment: str
    rating_band: str | None


@dataclass(frozen=True, slots=True)
class ProviderReplyObservation:
    """Normalized, read-only provider truth for an observed review reply."""

    comment: str
    updated_at: datetime | None
    state: str
    policy_violation: str | None
    external_response_id: str


def provider_reply_hash(reply: ProviderReplyObservation) -> str:
    """Fingerprint every provider-owned field that can change independently."""

    payload = {
        "comment": reply.comment,
        "external_response_id": reply.external_response_id,
        "policy_violation": reply.policy_violation,
        "state": reply.state,
        "updated_at": reply.updated_at.isoformat() if reply.updated_at else None,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def provider_reply_lifecycle(
    reply: ProviderReplyObservation,
) -> tuple[str, str, str | None, datetime | None]:
    """Map Google moderation truth to response and review lifecycle states."""

    state = reply.state
    if state == "APPROVED":
        return "published", "responded", None, reply.updated_at
    if state == "PENDING":
        return "publishing", "publishing", None, None
    if state == "REJECTED":
        return "rejected", "publication_failed", "GOOGLE_REVIEW_REPLY_REJECTED", None
    if state == PROVIDER_REPLY_STATE_UNSPECIFIED and reply.comment.strip():
        # Compatibility for legacy responses returned before moderation state
        # was available, and for accounts that omit the optional state.
        return "published", "responded", None, reply.updated_at
    return (
        "reconciliation_required",
        "publication_failed",
        "GOOGLE_REVIEW_REPLY_STATE_UNRESOLVED",
        None,
    )


def lilos_publication_confirmation_lifecycle(
    reply: ProviderReplyObservation,
) -> tuple[str, str, str | None]:
    """Map provider moderation without making a confirmed write retryable."""

    response_status, review_status, safe_error_code, _published_at = provider_reply_lifecycle(reply)
    if response_status == "publishing":
        return (
            "reconciliation_required",
            review_status,
            "GOOGLE_REVIEW_REPLY_PENDING_MODERATION",
        )
    return response_status, review_status, safe_error_code


def review_hash(rating: float | None, title: str | None, body: str | None) -> str:
    return hashlib.sha256(f"{rating}|{title or ''}|{body or ''}".encode()).hexdigest()


def classify(body: str | None, rating: float | None) -> ReviewClassification:
    text = (body or "").casefold()
    risks = sorted(key for key, terms in RISK_TERMS.items() if any(term in text for term in terms))
    sentiment = (
        "unknown"
        if not text
        else ("negative" if any(x in text for x in ("bad", "terrible", "awful")) else "unknown")
    )
    return {
        "risks": risks,
        "restricted": bool(risks),
        "sentiment": sentiment,
        "rating_band": None
        if rating is None
        else ("positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"),
    }


def validate_draft(text: str) -> None:
    normalized = text.casefold()
    if not text.strip() or any(term in normalized for term in PROHIBITED_DRAFT_TERMS):
        raise UnsafeDraftError


class ReviewService:
    def __init__(self) -> None:
        self.audit = AuditEventService()
        self.audit_repository = AuditEventRepository()
        self.notifications = NotificationService()
        self.ai_gateway = build_ai_gateway()
        self.execution = ExecutionService()

    async def _audit(
        self,
        session: AsyncSession,
        *,
        event: str,
        organization_id: UUID,
        location_id: UUID | None,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        correlation_id: str,
        summary: str,
        metadata: dict[str, object],
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=location_id,
                product_key="reviews",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    async def _notify(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        event_type: str,
        idempotency_key: str,
        context: dict[str, object],
        priority: str = "normal",
    ) -> None:
        channel, body = NOTIFICATION_TEMPLATES[event_type]
        template = await session.scalar(
            select(NotificationTemplate).where(
                NotificationTemplate.organization_id == organization_id,
                NotificationTemplate.key == event_type,
                NotificationTemplate.status == "active",
            )
        )
        if template is None:
            template = NotificationTemplate(
                organization_id=organization_id,
                key=event_type,
                version=1,
                channel=channel,
                body_template=body,
                status="active",
            )
            session.add(template)
            await session.flush()
        await self.notifications.create_event(
            session,
            organization_id=organization_id,
            template_id=template.id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            context=context,
            priority=priority,
            location_id=location_id,
        )

    @staticmethod
    def _restore_actionable_status(review: Review, revision: ReviewRevision) -> None:
        """Restore the review's content-derived state after a provider reply disappears."""

        result = classify(
            revision.body,
            float(revision.rating) if revision.rating is not None else None,
        )
        review.sentiment = str(result["sentiment"])
        review.status = "escalated" if result["restricted"] else "classified"
        review.risk_level = "high" if result["restricted"] else "low"

    @staticmethod
    def _is_lilos_publication(response: ReviewResponseRevision) -> bool:
        return (
            response.generated_by_type != PROVIDER_OBSERVED_TYPE
            and response.external_response_id is not None
            and response.published_at is not None
        )

    async def _audit_provider_confirmation_once(
        self,
        session: AsyncSession,
        *,
        response: ReviewResponseRevision,
        review: Review,
        provider_reply: ProviderReplyObservation,
        provider_observation_hash: str,
        correlation_id: str,
    ) -> None:
        existing = await session.scalar(
            select(AuditEvent.id)
            .where(
                AuditEvent.organization_id == review.organization_id,
                AuditEvent.resource_type == "review_response_revision",
                AuditEvent.resource_id == response.id,
                AuditEvent.event_type == "reviews.response.provider_confirmed",
                AuditEvent.event_metadata.contains(
                    {"provider_observation_hash": provider_observation_hash}
                ),
            )
            .limit(1)
        )
        if existing is not None:
            return
        await self._audit(
            session,
            event="reviews.response.provider_confirmed",
            organization_id=review.organization_id,
            location_id=review.location_id,
            actor_id=None,
            resource_type="review_response_revision",
            resource_id=response.id,
            correlation_id=correlation_id,
            summary="A response published through LILOs was confirmed by Google.",
            metadata={
                "external_response_id": provider_reply.external_response_id,
                "policy_violation": provider_reply.policy_violation,
                "provider_observation_hash": provider_observation_hash,
                "provider_reply_state": provider_reply.state,
                "provider_updated_at": provider_reply.updated_at.isoformat()
                if provider_reply.updated_at
                else None,
                "response_status": response.status,
                "review_status": review.status,
                "revision": response.revision_number,
            },
        )

    async def _reconcile_provider_reply(
        self,
        session: AsyncSession,
        *,
        review: Review,
        review_revision: ReviewRevision,
        provider_reply: ProviderReplyObservation | None,
        correlation_id: str,
    ) -> None:
        """Reconcile provider-owned reply truth independently from review content."""

        responses = list(
            await session.scalars(
                select(ReviewResponseRevision)
                .where(
                    ReviewResponseRevision.organization_id == review.organization_id,
                    ReviewResponseRevision.location_id == review.location_id,
                    ReviewResponseRevision.review_id == review.id,
                )
                .order_by(ReviewResponseRevision.revision_number)
                .with_for_update()
            )
        )
        active_provider = [
            response
            for response in responses
            if response.generated_by_type == PROVIDER_OBSERVED_TYPE
            and response.status != "superseded"
        ]
        lilos_publications = [
            response for response in responses if self._is_lilos_publication(response)
        ]
        active_lilos_publications = [
            response
            for response in lilos_publications
            if response.status != "superseded"
            and not (
                response.status == "reconciliation_required"
                and response.safe_error_code == "GOOGLE_REVIEW_REPLY_MISSING"
            )
        ]

        if provider_reply is None:
            if not active_provider and not active_lilos_publications:
                return
            for response in active_provider:
                response.status = "superseded"
                await self._audit(
                    session,
                    event="reviews.response.provider_removed",
                    organization_id=review.organization_id,
                    location_id=review.location_id,
                    actor_id=None,
                    resource_type="review_response_revision",
                    resource_id=response.id,
                    correlation_id=correlation_id,
                    summary="A previously observed Google response is no longer present.",
                    metadata={
                        "external_response_id": response.external_response_id,
                        "revision": response.revision_number,
                    },
                )
            for response in active_lilos_publications:
                response.status = "reconciliation_required"
                response.safe_error_code = "GOOGLE_REVIEW_REPLY_MISSING"
                await self._audit(
                    session,
                    event="reviews.response.provider_removed",
                    organization_id=review.organization_id,
                    location_id=review.location_id,
                    actor_id=None,
                    resource_type="review_response_revision",
                    resource_id=response.id,
                    correlation_id=correlation_id,
                    summary="A LILOs-published response is no longer present on Google.",
                    metadata={
                        "external_response_id": response.external_response_id,
                        "revision": response.revision_number,
                    },
                )
            self._restore_actionable_status(review, review_revision)
            return

        digest = provider_reply_hash(provider_reply)
        matching_lilos = next(
            (
                response
                for response in reversed(lilos_publications)
                if response.external_response_id == provider_reply.external_response_id
                and response.response_text.strip() == provider_reply.comment.strip()
            ),
            None,
        )
        provider_confirmation = matching_lilos is not None
        if matching_lilos is not None:
            response_status, review_status, safe_error_code = (
                lilos_publication_confirmation_lifecycle(provider_reply)
            )
            current = matching_lilos
            current.status = response_status
            current.safe_error_code = safe_error_code
            for response in active_provider:
                response.status = "superseded"
            created = False
        else:
            response_status, review_status, safe_error_code, published_at = (
                provider_reply_lifecycle(provider_reply)
            )
            imported_current = next(
                (
                    response
                    for response in reversed(active_provider)
                    if response.content_hash == digest
                    and response.external_response_id == provider_reply.external_response_id
                ),
                None,
            )
            created = imported_current is None
            if imported_current is None:
                for response in active_provider:
                    response.status = "superseded"
                current = ReviewResponseRevision(
                    organization_id=review.organization_id,
                    location_id=review.location_id,
                    review_id=review.id,
                    review_revision_id=review_revision.id,
                    revision_number=(responses[-1].revision_number if responses else 0) + 1,
                    response_text=provider_reply.comment,
                    content_hash=digest,
                    status=response_status,
                    generated_by_type=PROVIDER_OBSERVED_TYPE,
                    ai_execution_id=None,
                    approved_fact_revision_ids=[],
                    approval_reference_id=None,
                    approved_by_user_id=None,
                    approved_at=None,
                    external_response_id=provider_reply.external_response_id,
                    published_at=published_at,
                    idempotency_key=None,
                    safe_error_code=safe_error_code,
                )
                session.add(current)
                await session.flush()
            else:
                current = imported_current
                # Re-assert deterministic current truth if an earlier workflow state
                # transition touched the provider-observation row.
                current.status = response_status
                current.safe_error_code = safe_error_code
                current.published_at = published_at
                for response in active_provider:
                    if response.id != current.id:
                        response.status = "superseded"

        superseded_local = [
            response
            for response in responses
            if response.id != current.id
            and response.generated_by_type != PROVIDER_OBSERVED_TYPE
            and (
                response.status in ACTIVE_LOCAL_RESPONSE_STATUSES
                or (self._is_lilos_publication(response) and response.status != "superseded")
            )
        ]
        for response in superseded_local:
            was_published = self._is_lilos_publication(response)
            response.status = "superseded"
            await self._audit(
                session,
                event="reviews.response.superseded_by_provider",
                organization_id=review.organization_id,
                location_id=review.location_id,
                actor_id=None,
                resource_type="review_response_revision",
                resource_id=response.id,
                correlation_id=correlation_id,
                summary=(
                    "A LILOs-published response was superseded by current Google content."
                    if was_published
                    else "Local response work was superseded by an existing Google response."
                ),
                metadata={
                    "provider_response_revision_id": str(current.id),
                    "reason": "provider_content_changed"
                    if was_published
                    else "provider_reply_exists",
                    "revision": response.revision_number,
                },
            )

        review.status = review_status
        if provider_confirmation:
            await self._audit_provider_confirmation_once(
                session,
                response=current,
                review=review,
                provider_reply=provider_reply,
                provider_observation_hash=digest,
                correlation_id=correlation_id,
            )
            return
        if created:
            await self._audit(
                session,
                event="reviews.response.provider_observed",
                organization_id=review.organization_id,
                location_id=review.location_id,
                actor_id=None,
                resource_type="review_response_revision",
                resource_id=current.id,
                correlation_id=correlation_id,
                summary="Google review response state was observed and reconciled.",
                metadata={
                    "external_response_id": provider_reply.external_response_id,
                    "policy_violation": provider_reply.policy_violation,
                    "provider_reply_state": provider_reply.state,
                    "provider_updated_at": provider_reply.updated_at.isoformat()
                    if provider_reply.updated_at
                    else None,
                    "response_status": response_status,
                    "review_status": review_status,
                    "revision": current.revision_number,
                },
            )

    async def ingest(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID,
        integration_resource_id: UUID,
        external_review_id: str,
        provider: str,
        rating: float | None,
        title: str | None,
        body: str | None,
        created_at: datetime,
        updated_at: datetime | None,
        correlation_id: str,
        provider_reply: ProviderReplyObservation | None = None,
    ) -> tuple[Review, ReviewRevision, bool]:
        digest = review_hash(rating, title, body)
        observed_at = datetime.now(UTC)
        content_changed = False
        review = await session.scalar(
            select(Review)
            .where(
                Review.organization_id == organization_id,
                Review.integration_resource_id == integration_resource_id,
                Review.external_review_id == external_review_id,
            )
            .with_for_update()
        )
        if review:
            review.last_synced_at = observed_at
            current = await session.scalar(
                select(ReviewRevision).where(
                    ReviewRevision.review_id == review.id, ReviewRevision.content_hash == digest
                )
            )
            if current:
                revision = current
            else:
                number = review.current_revision_number + 1
                review.current_revision_number = number
                review.rating = rating
                review.status = "new"
                review.review_updated_at = updated_at
                for response in (
                    await session.scalars(
                        select(ReviewResponseRevision).where(
                            ReviewResponseRevision.review_id == review.id,
                            ReviewResponseRevision.status.in_(("approved", "awaiting_approval")),
                        )
                    )
                ).all():
                    response.status = "superseded"
                revision = ReviewRevision(
                    organization_id=organization_id,
                    review_id=review.id,
                    revision_number=number,
                    rating=rating,
                    title=title,
                    body=body,
                    content_hash=digest,
                    change_summary="provider content changed",
                )
                session.add(revision)
                content_changed = True
        else:
            number = 1
            review = Review(
                organization_id=organization_id,
                location_id=location_id,
                integration_resource_id=integration_resource_id,
                external_review_id=external_review_id,
                provider=provider,
                rating=rating,
                status="new",
                sentiment="unknown",
                topics=[],
                risk_level="unknown",
                current_revision_number=1,
                review_created_at=created_at,
                review_updated_at=updated_at,
                last_synced_at=observed_at,
            )
            session.add(review)
            await session.flush()
            revision = ReviewRevision(
                organization_id=organization_id,
                review_id=review.id,
                revision_number=number,
                rating=rating,
                title=title,
                body=body,
                content_hash=digest,
                change_summary="initial provider observation",
            )
            session.add(revision)
            content_changed = True

        if content_changed:
            await session.flush()
            result = classify(body, rating)
            review.sentiment = str(result["sentiment"])
            review.status = "escalated" if result["restricted"] else "classified"
            review.risk_level = "high" if result["restricted"] else "low"
            if result["restricted"]:
                session.add(
                    ReviewEscalation(
                        organization_id=organization_id,
                        review_id=review.id,
                        case_type=str(result["risks"][0]),
                        severity="high",
                        status="open",
                        restricted=True,
                        safe_reason="Deterministic restricted-risk candidate.",
                    )
                )
                await self._notify(
                    session,
                    organization_id=organization_id,
                    location_id=location_id,
                    event_type="reviews.restricted_case_created",
                    idempotency_key=f"reviews.restricted.{review.id}.{revision.revision_number}",
                    context={"review_id": str(review.id), "risk_types": result["risks"]},
                    priority="high",
                )
            await session.flush()
            await self._audit(
                session,
                event="reviews.review.ingested",
                organization_id=organization_id,
                location_id=location_id,
                actor_id=None,
                resource_type="review",
                resource_id=review.id,
                correlation_id=correlation_id,
                summary="Review ingested and classified.",
                metadata={
                    "status": review.status,
                    "risk_level": review.risk_level,
                    "revision_number": revision.revision_number,
                },
            )

        await self._reconcile_provider_reply(
            session,
            review=review,
            review_revision=revision,
            provider_reply=provider_reply,
            correlation_id=correlation_id,
        )
        await session.flush()
        return review, revision, content_changed

    async def draft(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID,
        review_id: UUID,
        review_revision_id: UUID,
        text: str,
        generated_by_type: str,
        fact_ids: list[UUID],
        actor_id: UUID | None,
        correlation_id: str,
        ai_execution_id: UUID | None = None,
    ) -> ReviewResponseRevision:
        validate_draft(text)
        if not fact_ids:
            raise GroundingRequiredError
        review = await session.scalar(
            select(Review).where(
                Review.organization_id == organization_id,
                Review.location_id == location_id,
                Review.id == review_id,
            )
        )
        if not review:
            raise ReviewNotFoundError
        review_revision = await session.scalar(
            select(ReviewRevision).where(
                ReviewRevision.organization_id == organization_id,
                ReviewRevision.review_id == review_id,
                ReviewRevision.id == review_revision_id,
            )
        )
        if not review_revision:
            raise ReviewRevisionNotFoundError
        status = "awaiting_approval"
        last = await session.scalar(
            select(ReviewResponseRevision.revision_number)
            .where(ReviewResponseRevision.review_id == review_id)
            .order_by(ReviewResponseRevision.revision_number.desc())
            .limit(1)
        )
        item = ReviewResponseRevision(
            organization_id=organization_id,
            location_id=location_id,
            review_id=review_id,
            review_revision_id=review_revision_id,
            revision_number=(last or 0) + 1,
            response_text=text,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            status=status,
            generated_by_type=generated_by_type,
            ai_execution_id=ai_execution_id,
            approved_fact_revision_ids=[str(x) for x in fact_ids],
        )
        session.add(item)
        await session.flush()
        await self._audit(
            session,
            event="reviews.response.drafted",
            organization_id=organization_id,
            location_id=location_id,
            actor_id=actor_id,
            resource_type="review_response_revision",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary=f"Review response drafted ({generated_by_type}).",
            metadata={"generated_by_type": generated_by_type, "revision": item.revision_number},
        )
        return item

    async def generate_ai_draft(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID,
        review_id: UUID,
        review_revision_id: UUID,
        fact_ids: list[UUID],
        idempotency_key: str,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> tuple[ReviewResponseRevision, AIExecution]:
        """Generate a response draft through the shared AI Gateway.

        Routes through the configured production provider (or deterministic
        fixture in local/test). Always requires human approval before
        publication.
        """
        if not fact_ids:
            raise GroundingRequiredError
        revision = await session.scalar(
            select(ReviewRevision)
            .join(Review, Review.id == ReviewRevision.review_id)
            .where(
                ReviewRevision.organization_id == organization_id,
                ReviewRevision.id == review_revision_id,
                ReviewRevision.review_id == review_id,
                Review.organization_id == organization_id,
                Review.location_id == location_id,
            )
        )
        if not revision:
            raise ReviewRevisionNotFoundError

        task = await session.scalar(
            select(AITaskDefinition).where(
                AITaskDefinition.key == AI_TASK_KEY, AITaskDefinition.status == "active"
            )
        )
        if task is None:
            task = AITaskDefinition(
                key=AI_TASK_KEY,
                version=1,
                owning_product="reviews",
                purpose="Draft a grounded, policy-compliant review response for human approval.",
                input_schema={"rating": "number", "body": "string"},
                output_schema={"draft": "string"},
                risk_level="medium",
                maximum_cost_microunits=0,
                maximum_latency_ms=5_000,
                requires_human_review=True,
                retention_policy_key="reviews.ai_draft.default",
                status="active",
            )
            session.add(task)
            await session.flush()

        existing_execution = await session.scalar(
            select(AIExecution).where(
                AIExecution.organization_id == organization_id,
                AIExecution.idempotency_key == idempotency_key,
            )
        )
        if existing_execution is None:
            fallback = (
                "Thank you for sharing your experience. We take all feedback seriously and "
                "would like to make this right."
            )
            request = AIGatewayRequest(
                organization_id=organization_id,
                location_id=location_id,
                task_key=AI_TASK_KEY,
                input_document={
                    "rating": float(revision.rating) if revision.rating is not None else None,
                    "manual_fallback": fallback,
                },
                input_references=(revision.id,),
                approved_fact_revision_ids=tuple(fact_ids),
                maximum_cost_microunits=task.maximum_cost_microunits,
                maximum_latency_ms=task.maximum_latency_ms,
            )
            output = await self.ai_gateway.execute(request)
            usage = output.get("usage", {}) or {}
            execution = AIExecution(
                organization_id=organization_id,
                location_id=location_id,
                task_definition_id=task.id,
                idempotency_key=idempotency_key,
                status="completed",
                provider_key=str(output.get("provider")),
                model_key=str(output.get("model")),
                input_references=[str(revision.id)],
                approved_fact_revision_ids=[str(x) for x in fact_ids],
                output_document=output,
                output_hash=hashlib.sha256(str(output.get("draft", "")).encode()).hexdigest(),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                estimated_cost_microunits=output.get("cost_microunits"),
                latency_ms=output.get("latency_ms"),
                requires_human_review=bool(output.get("requires_human_review", True)),
                completed_at=datetime.now(UTC),
            )
            session.add(execution)
            await session.flush()
            draft_text = str(output.get("draft", ""))
        else:
            execution = existing_execution
            draft_text = str((execution.output_document or {}).get("draft", ""))

        response = await self.draft(
            session,
            organization_id=organization_id,
            location_id=location_id,
            review_id=review_id,
            review_revision_id=review_revision_id,
            text=draft_text,
            generated_by_type="ai",
            fact_ids=fact_ids,
            actor_id=actor_id,
            correlation_id=correlation_id,
            ai_execution_id=execution.id,
        )
        return response, execution

    async def approve(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        review_id: UUID,
        response_id: UUID,
        user_id: UUID,
        *,
        correlation_id: str,
    ) -> ReviewResponseRevision:
        item = await session.scalar(
            select(ReviewResponseRevision)
            .where(
                ReviewResponseRevision.organization_id == organization_id,
                ReviewResponseRevision.location_id == location_id,
                ReviewResponseRevision.review_id == review_id,
                ReviewResponseRevision.id == response_id,
            )
            .with_for_update()
        )
        if not item:
            raise ReviewResponseNotFoundError
        if item.status != "awaiting_approval":
            raise ResponseNotApprovalEligibleError
        review = await session.scalar(
            select(Review).where(
                Review.organization_id == organization_id,
                Review.location_id == location_id,
                Review.id == review_id,
            )
        )
        if not review or review.current_revision_number != (
            await session.scalar(
                select(ReviewRevision.revision_number).where(
                    ReviewRevision.organization_id == organization_id,
                    ReviewRevision.review_id == review_id,
                    ReviewRevision.id == item.review_revision_id,
                )
            )
        ):
            raise ReviewChangedAfterDraftError
        item.status = "approved"
        item.approved_by_user_id = user_id
        item.approved_at = datetime.now(UTC)
        await session.flush()
        await self._audit(
            session,
            event="reviews.response.approved",
            organization_id=organization_id,
            location_id=item.location_id,
            actor_id=user_id,
            resource_type="review_response_revision",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary="Review response approved.",
            metadata={"revision": item.revision_number},
        )
        return item

    async def reserve_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        review_id: UUID,
        response_id: UUID,
        idempotency_key: str,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> ReviewResponseRevision:
        item = await session.scalar(
            select(ReviewResponseRevision)
            .where(
                ReviewResponseRevision.organization_id == organization_id,
                ReviewResponseRevision.location_id == location_id,
                ReviewResponseRevision.review_id == review_id,
                ReviewResponseRevision.id == response_id,
            )
            .with_for_update()
        )
        if not item:
            raise ReviewResponseNotFoundError
        if item.status != "approved":
            raise ResponseNotPublishEligibleError
        review = await session.scalar(
            select(Review).where(
                Review.organization_id == organization_id,
                Review.location_id == location_id,
                Review.id == review_id,
            )
        )
        if review and review.status == "escalated":
            raise RestrictedReviewCannotAutoPublishError
        item.status = "publishing"
        item.idempotency_key = idempotency_key
        await session.flush()
        await self.execution.start_named(
            session,
            organization_id,
            "reviews.publish_response",
            idempotency_key,
            location_id=item.location_id,
            input_document={"response_id": str(item.id)},
            correlation_id=correlation_id,
            actor_id=actor_id,
        )
        await self._audit(
            session,
            event="reviews.response.publication_reserved",
            organization_id=organization_id,
            location_id=item.location_id,
            actor_id=actor_id,
            resource_type="review_response_revision",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary="Review response publication reserved.",
            metadata={"revision": item.revision_number},
        )
        await self._notify(
            session,
            organization_id=organization_id,
            location_id=item.location_id,
            event_type="reviews.response.publication_reserved",
            idempotency_key=f"reviews.publication_reserved.{item.id}",
            context={"review_id": str(item.review_id), "response_id": str(item.id)},
        )
        return item

    async def get(
        self, session: AsyncSession, organization_id: UUID, review_id: UUID
    ) -> tuple[Review, list[ReviewRevision]]:
        review = await session.scalar(
            select(Review).where(Review.organization_id == organization_id, Review.id == review_id)
        )
        if not review:
            raise ReviewNotFoundError
        revisions = list(
            await session.scalars(
                select(ReviewRevision)
                .where(ReviewRevision.review_id == review_id)
                .order_by(ReviewRevision.revision_number.desc())
            )
        )
        return review, revisions

    async def list_reviews(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        *,
        status_filter: str | None = None,
        rating_min: float | None = None,
        rating_max: float | None = None,
        search: str | None = None,
        sort: str = "recent",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Review], bool]:
        if not 1 <= limit <= 100:
            raise InvalidReviewQueryError
        if offset < 0:
            raise InvalidReviewQueryError
        statement: Select[tuple[Review]] = select(Review).where(
            Review.organization_id == organization_id, Review.location_id == location_id
        )
        if status_filter is not None:
            statement = statement.where(Review.status == status_filter)
        if rating_min is not None:
            statement = statement.where(Review.rating >= rating_min)
        if rating_max is not None:
            statement = statement.where(Review.rating <= rating_max)
        if search:
            pattern = f"%{search.casefold()}%"
            statement = statement.where(
                Review.id.in_(
                    select(ReviewRevision.review_id).where(
                        ReviewRevision.review_id == Review.id,
                        or_(
                            func.lower(ReviewRevision.body).like(pattern),
                            func.lower(ReviewRevision.title).like(pattern),
                        ),
                    )
                )
            )
        statement = statement.order_by(
            Review.rating.asc()
            if sort == "rating_asc"
            else Review.rating.desc()
            if sort == "rating_desc"
            else Review.review_created_at.desc()
        )
        rows = list(await session.scalars(statement.limit(limit + 1).offset(offset)))
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def list_responses(
        self, session: AsyncSession, organization_id: UUID, review_id: UUID
    ) -> list[ReviewResponseRevision]:
        return list(
            await session.scalars(
                select(ReviewResponseRevision)
                .where(
                    ReviewResponseRevision.organization_id == organization_id,
                    ReviewResponseRevision.review_id == review_id,
                )
                .order_by(ReviewResponseRevision.revision_number.desc())
            )
        )

    async def summary(
        self, session: AsyncSession, organization_id: UUID, location_id: UUID
    ) -> dict[str, object]:
        rows = (
            await session.execute(
                select(Review.status, func.count())
                .where(Review.organization_id == organization_id, Review.location_id == location_id)
                .group_by(Review.status)
            )
        ).all()
        average_rating = await session.scalar(
            select(func.avg(Review.rating)).where(
                Review.organization_id == organization_id,
                Review.location_id == location_id,
                Review.rating.is_not(None),
            )
        )
        restricted = await session.scalar(
            select(func.count())
            .select_from(ReviewEscalation)
            .join(Review, Review.id == ReviewEscalation.review_id)
            .where(
                Review.organization_id == organization_id,
                Review.location_id == location_id,
                ReviewEscalation.status == "open",
            )
        )
        return {
            "by_status": {status: count for status, count in rows},
            "average_rating": float(average_rating) if average_rating is not None else None,
            "open_restricted_cases": int(restricted or 0),
        }

    async def resource_history(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        resource_type: str,
        resource_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        events = await self.audit_repository.list_for_resource(
            session,
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
        return [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "action": event.action,
                "result": event.result,
                "occurred_at": event.occurred_at,
                "summary": event.summary,
                "actor_type": event.actor_type,
            }
            for event in events
        ]
