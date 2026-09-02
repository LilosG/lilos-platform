"""Durable, write-once publication of approved Google review replies."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.integrations.errors import (
    IntegrationNotFoundError,
    IntegrationReconnectRequiredError,
)
from apps.api.app.integrations.models import ProviderResourceMapping
from apps.api.app.integrations.secrets import SecretUnavailableError
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.provider_write_outcome import classify_provider_write_failure
from apps.api.app.products.gbp.resource_names import v4_review_name
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision
from apps.api.app.products.reviews.service import (
    PROVIDER_REPLY_STATE_UNSPECIFIED,
    ProviderReplyObservation,
    lilos_publication_confirmation_lifecycle,
)

logger = logging.getLogger(__name__)

# Every code in this set is emitted only after the durable dispatch boundary was
# crossed. Retrying these states must therefore be read-only: another updateReply
# could duplicate or overwrite a reply that Google already accepted.
VERIFY_ONLY_SAFE_ERRORS = frozenset(
    {
        "PROVIDER_WRITE_DISPATCHED",
        "PROVIDER_WRITE_AMBIGUOUS",
        "VERIFICATION_REREAD_FAILED",
        "VERIFICATION_CONTENT_PENDING",
        "VERIFICATION_CONTENT_MISMATCH",
        "GOOGLE_REVIEW_REPLY_PENDING_MODERATION",
        "GOOGLE_REVIEW_REPLY_STATE_UNRESOLVED",
    }
)
LEGACY_VERIFICATION_SAFE_ERRORS = frozenset(
    {"VERIFICATION_REREAD_FAILED", "VERIFICATION_CONTENT_MISMATCH"}
)


async def _response_for_update(
    session: AsyncSession,
    organization_id: UUID,
    response_id: UUID,
) -> ReviewResponseRevision | None:
    return cast(
        ReviewResponseRevision | None,
        await session.scalar(
            select(ReviewResponseRevision)
            .where(
                ReviewResponseRevision.organization_id == organization_id,
                ReviewResponseRevision.id == response_id,
            )
            .with_for_update()
        ),
    )


def _verification_only(response: ReviewResponseRevision) -> bool:
    return response.status == "reconciliation_required" and (
        response.safe_error_code in VERIFY_ONLY_SAFE_ERRORS
        or response.external_response_id is not None
    )


def _provider_observation(
    raw_review: dict[str, Any],
    *,
    review_name: str,
) -> ProviderReplyObservation | None:
    raw_reply = raw_review.get("reviewReply")
    if not isinstance(raw_reply, dict):
        return None
    raw_comment = raw_reply.get("comment")
    comment = raw_comment if isinstance(raw_comment, str) else ""
    raw_state = raw_reply.get("reviewReplyState")
    state = (
        raw_state.strip().upper()
        if isinstance(raw_state, str) and raw_state.strip()
        else PROVIDER_REPLY_STATE_UNSPECIFIED
    )
    raw_policy = raw_reply.get("policyViolation")
    policy_violation = (
        raw_policy.strip().upper() if isinstance(raw_policy, str) and raw_policy.strip() else None
    )
    if (
        not comment.strip()
        and state == PROVIDER_REPLY_STATE_UNSPECIFIED
        and policy_violation is None
    ):
        return None
    return ProviderReplyObservation(
        comment=comment,
        updated_at=None,
        state=state,
        policy_violation=policy_violation,
        external_response_id=review_name,
    )


async def handle_reviews_publish_response(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Publish once, then reconcile Google reply state with read-only retries."""
    del correlation_id, workflow_run_id

    # Keep the execution registry as the dependency boundary so the existing
    # test injection points and production connection lifecycle remain canonical.
    from apps.api.app.execution import handlers as execution_handlers

    response_id_raw = input_document.get("response_id")
    if not response_id_raw:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_RESPONSE_ID")
    try:
        response_id = UUID(str(response_id_raw))
    except (TypeError, ValueError):
        return JobOutcome(result="permanent_failure", safe_error="INVALID_RESPONSE_ID")

    response = await _response_for_update(session, organization_id, response_id)
    if response is None:
        return JobOutcome(result="permanent_failure", safe_error="RESPONSE_NOT_FOUND")
    if response.status == "published":
        return JobOutcome(result="succeeded", result_reference=f"response:{response.id}")

    initial_publish = response.status == "publishing"
    verify_only = _verification_only(response)
    if not initial_publish and not verify_only:
        return JobOutcome(result="permanent_failure", safe_error="RESPONSE_NOT_PUBLISHING")

    review = await session.scalar(
        select(Review).where(
            Review.organization_id == organization_id,
            Review.id == response.review_id,
        )
    )
    if review is None:
        response.status = "failed"
        response.safe_error_code = "REVIEW_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="REVIEW_NOT_FOUND")
    if location_id is not None and review.location_id != location_id:
        response.status = "failed"
        response.safe_error_code = "REVIEW_LOCATION_SCOPE_MISMATCH"
        return JobOutcome(result="permanent_failure", safe_error="REVIEW_LOCATION_SCOPE_MISMATCH")

    resource_mapping = await session.scalar(
        select(ProviderResourceMapping).where(
            ProviderResourceMapping.organization_id == organization_id,
            ProviderResourceMapping.id == review.integration_resource_id,
            ProviderResourceMapping.status == "active",
        )
    )
    if resource_mapping is None:
        response.status = "failed"
        response.safe_error_code = "PROVIDER_MAPPING_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_MAPPING_NOT_FOUND")

    gbp_location = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.integration_resource_id == resource_mapping.id,
        )
    )
    if gbp_location is None:
        response.status = "failed"
        response.safe_error_code = "GBP_LOCATION_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")

    gbp_account = await session.get(GBPAccount, gbp_location.account_id)
    if gbp_account is None:
        response.status = "failed"
        response.safe_error_code = "GBP_ACCOUNT_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="GBP_ACCOUNT_NOT_FOUND")

    if initial_publish and (
        not execution_handlers._provider_writes_enabled()
        or not gbp_location.write_enabled
        or gbp_location.mapping_status != "confirmed"
    ):
        response.status = "failed"
        response.safe_error_code = "WRITE_NOT_ENABLED"
        return JobOutcome(result="permanent_failure", safe_error="WRITE_NOT_ENABLED")

    review_name = v4_review_name(
        gbp_account.external_account_id,
        gbp_location.external_location_id,
        review.external_review_id,
    )
    approved_comment = response.response_text.strip()
    review_id = review.id

    # Legacy verification rows were produced only after updateReply had already
    # returned. Backfill their deterministic provider reference before OAuth so
    # even a token-refresh failure cannot erase the verify-only recovery phase.
    if (
        verify_only
        and response.external_response_id is None
        and response.safe_error_code in LEGACY_VERIFICATION_SAFE_ERRORS
    ):
        response.external_response_id = review_name

    # Release the response row lock before OAuth and provider I/O. Every later
    # state transition re-locks the response before writing durable state.
    await session.commit()

    try:
        token, _connection = await execution_handlers._token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        response = await _response_for_update(session, organization_id, response_id)
        if response is not None:
            response.status = "failed"
            response.safe_error_code = "NO_CONNECTED_INTEGRATION"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="NO_CONNECTED_INTEGRATION")
    except IntegrationReconnectRequiredError:
        response = await _response_for_update(session, organization_id, response_id)
        if response is not None:
            response.status = "reconciliation_required" if verify_only else "publishing"
            response.safe_error_code = "TOKEN_REFRESH_FAILED"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except SecretUnavailableError as exc:
        logger.warning(
            "Secret resolution failed in review reply workflow",
            extra={
                "event_name": "reviews.publish.secret_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        response = await _response_for_update(session, organization_id, response_id)
        if response is not None:
            response.status = "reconciliation_required" if verify_only else "failed"
            response.safe_error_code = "SECRET_RESOLUTION_FAILED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="SECRET_RESOLUTION_FAILED")
    except Exception as exc:
        logger.warning(
            "Token resolution failed in review reply workflow",
            extra={
                "event_name": "reviews.publish.token_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        response = await _response_for_update(session, organization_id, response_id)
        if response is not None:
            response.status = "reconciliation_required" if verify_only else "publishing"
            response.safe_error_code = "TOKEN_RESOLUTION_FAILED"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_RESOLUTION_FAILED")

    # Token refresh may have mutated connection state. Make that durable before
    # crossing the provider write boundary.
    await session.commit()
    adapter = execution_handlers._adapter_factory()

    if initial_publish:
        # Claim the provider-write boundary durably before the network request.
        # If the process dies after this commit, the next attempt can only read
        # Google state; it cannot issue a second updateReply on an unknown outcome.
        response = await _response_for_update(session, organization_id, response_id)
        if response is None:
            await session.rollback()
            return JobOutcome(result="ambiguous", safe_error="RESPONSE_LOST_BEFORE_DISPATCH")
        if response.status != "publishing":
            await session.rollback()
            return JobOutcome(result="ambiguous", safe_error="REVIEW_REPLY_DISPATCH_CONFLICT")
        response.external_response_id = review_name
        response.status = "reconciliation_required"
        response.safe_error_code = "PROVIDER_WRITE_DISPATCHED"
        await session.commit()

        try:
            await adapter.update_review_reply(token, review_name, approved_comment)
        except Exception as exc:
            outcome = classify_provider_write_failure(exc)
            response = await _response_for_update(session, organization_id, response_id)
            if response is not None:
                if outcome.requires_reconciliation:
                    response.status = "reconciliation_required"
                elif outcome.job_result == "retryable_failure":
                    # Google proved the write was not applied. Clear the dispatch
                    # marker and permit a later attempt to cross the write boundary.
                    response.status = "publishing"
                    response.external_response_id = None
                else:
                    response.status = "failed"
                    response.external_response_id = None
                response.safe_error_code = outcome.safe_error_code
            await session.commit()
            logger.warning(
                "Review reply publication failed",
                extra={
                    "event_name": "reviews.publish.failed",
                    "response_id": str(response_id),
                    "provider_write_applied": outcome.applied,
                    "safe_error_code": outcome.safe_error_code,
                    "error": str(exc)[:200],
                },
            )
            return JobOutcome(result=outcome.job_result, safe_error=outcome.safe_error_code)

        # updateReply returned successfully. Advance the durable dispatch marker
        # before the verification re-read; all later attempts remain read-only.
        response = await _response_for_update(session, organization_id, response_id)
        if response is None:
            await session.rollback()
            return JobOutcome(result="ambiguous", safe_error="RESPONSE_LOST_AFTER_DISPATCH")
        response.status = "reconciliation_required"
        response.safe_error_code = "VERIFICATION_CONTENT_PENDING"
        await session.commit()

    try:
        re_read = await adapter.get_review(token, review_name)
    except Exception as exc:
        response = await _response_for_update(session, organization_id, response_id)
        if response is not None:
            response.status = "reconciliation_required"
            response.safe_error_code = "VERIFICATION_REREAD_FAILED"
        await session.commit()
        logger.warning(
            "Review reply verification re-read failed",
            extra={
                "event_name": "reviews.publish.verification_failed",
                "response_id": str(response_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")

    observation = _provider_observation(re_read, review_name=review_name)
    if observation is None or not observation.comment.strip():
        response = await _response_for_update(session, organization_id, response_id)
        review = await session.get(Review, review_id)
        if response is not None:
            response.status = "reconciliation_required"
            response.safe_error_code = "VERIFICATION_CONTENT_PENDING"
        if review is not None:
            review.status = "publishing"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_CONTENT_PENDING")

    if observation.comment.strip() != approved_comment:
        response = await _response_for_update(session, organization_id, response_id)
        review = await session.get(Review, review_id)
        if response is not None:
            response.status = "reconciliation_required"
            response.safe_error_code = "VERIFICATION_CONTENT_MISMATCH"
        if review is not None:
            review.status = "publication_failed"
        await session.commit()
        logger.warning(
            "Review reply verification found different provider content",
            extra={
                "event_name": "reviews.publish.mismatch",
                "response_id": str(response_id),
            },
        )
        return JobOutcome(result="permanent_failure", safe_error="VERIFICATION_CONTENT_MISMATCH")

    response_status, review_status, safe_error = lilos_publication_confirmation_lifecycle(
        observation
    )
    response = await _response_for_update(session, organization_id, response_id)
    review = await session.get(Review, review_id)
    if response is None or review is None:
        await session.rollback()
        return JobOutcome(result="ambiguous", safe_error="REVIEW_STATE_LOST_AFTER_VERIFICATION")

    response.external_response_id = review_name
    response.status = response_status
    response.safe_error_code = safe_error
    review.status = review_status

    if response_status == "published":
        response.published_at = datetime.now(UTC)
        await session.commit()
        return JobOutcome(result="succeeded", result_reference=f"response:{response.id}")

    if response_status == "rejected":
        await session.commit()
        return JobOutcome(
            result="permanent_failure",
            safe_error=safe_error or "GOOGLE_REVIEW_REPLY_REJECTED",
        )

    retry_code = safe_error or "GOOGLE_REVIEW_REPLY_STATE_UNRESOLVED"
    await session.commit()
    return JobOutcome(result="retryable_failure", safe_error=retry_code)
