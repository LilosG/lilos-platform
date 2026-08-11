"""Reviews ingestion from a connected Google Business Profile location.

Resolves the GBP provider mapping for a platform location, pulls the current
review list via the legacy My Business v4 API, and ingests each review through
the existing ``ReviewService.ingest`` idempotent path.  This is the production
read-side counterpart to the response publication write path — it does NOT
publish any reply and preserves the approval workflow before publication.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.integrations.models import ProviderResourceMapping
from apps.api.app.products.gbp.adapter import GBPAdapter, GoogleBusinessProfileAdapter
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.resource_names import v4_location_parent
from apps.api.app.products.reviews.service import (
    PROVIDER_REPLY_STATE_UNSPECIFIED,
    ProviderReplyObservation,
    ReviewService,
)

_STAR_RATING = {
    "STAR_RATING_UNSPECIFIED": None,
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
}


def _parse_rating(raw: Any) -> float | None:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        mapped = _STAR_RATING.get(raw.upper())
        return float(mapped) if mapped is not None else None
    return None


def _parse_time(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=UTC) if raw.tzinfo is None else raw.astimezone(UTC)
    if isinstance(raw, str):
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return datetime.now(UTC)


def _provider_enum(raw: Any, *, default: str | None) -> str | None:
    if raw is None or raw == "":
        return default
    if not isinstance(raw, str):
        raise ValueError("invalid Google review reply enum")
    value = raw.strip().upper()
    if not value or len(value) > 96 or not value.replace("_", "").isalnum():
        raise ValueError("invalid Google review reply enum")
    return value


def _normalize_provider_reply(
    raw_review: dict[str, Any], *, external_response_id: str
) -> ProviderReplyObservation | None:
    raw_reply = raw_review.get("reviewReply")
    if raw_reply is None:
        return None
    if not isinstance(raw_reply, dict):
        raise ValueError("invalid Google review reply")

    raw_comment = raw_reply.get("comment")
    if raw_comment is not None and not isinstance(raw_comment, str):
        raise ValueError("invalid Google review reply comment")
    comment = raw_comment or ""
    state = _provider_enum(
        raw_reply.get("reviewReplyState"), default=PROVIDER_REPLY_STATE_UNSPECIFIED
    )
    assert state is not None
    policy_violation = _provider_enum(raw_reply.get("policyViolation"), default=None)
    updated_at_raw = raw_reply.get("updateTime")
    updated_at = _parse_time(updated_at_raw) if updated_at_raw else None

    # Treat a wholly empty compatibility object as absence. A moderation state,
    # timestamp, policy code, or comment is otherwise provider-owned evidence.
    if (
        not comment.strip()
        and state == PROVIDER_REPLY_STATE_UNSPECIFIED
        and updated_at is None
        and policy_violation is None
    ):
        return None
    return ProviderReplyObservation(
        comment=comment,
        updated_at=updated_at,
        state=state,
        policy_violation=policy_violation,
        external_response_id=external_response_id,
    )


@dataclass(slots=True)
class ReviewIngestionService:
    """Pull reviews from GBP and ingest them through the governed review path."""

    adapter: GBPAdapter = field(default_factory=GoogleBusinessProfileAdapter)
    connection: GBPConnectionService = field(default_factory=GBPConnectionService)
    reviews: ReviewService = field(default_factory=ReviewService)
    audit: AuditEventService = field(default_factory=AuditEventService)

    async def ingest_for_location(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        location_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> dict[str, object]:
        """Ingest reviews for the platform location's mapped GBP resource.

        Returns a summary dict: ``ingested``, ``updated``, ``total``.  No
        review response is published; the approval workflow is preserved.
        """
        # Resolve the active GBP location resource mapping for this location.
        mapping = await session.scalar(
            select(ProviderResourceMapping).where(
                ProviderResourceMapping.organization_id == organization_id,
                ProviderResourceMapping.platform_resource_id == location_id,
                ProviderResourceMapping.resource_type == "location",
                ProviderResourceMapping.status == "active",
            )
        )
        if mapping is None:
            raise LookupError("No active GBP location mapping for this location")

        gbp_location = await session.scalar(
            select(GBPLocation).where(
                GBPLocation.organization_id == organization_id,
                GBPLocation.integration_resource_id == mapping.id,
            )
        )
        if gbp_location is None:
            raise LookupError("GBP location not found for mapping")

        gbp_account = await session.get(GBPAccount, gbp_location.account_id)
        if gbp_account is None:
            raise LookupError("GBP account not found")

        token = await self.connection.ensure_fresh_token(
            session,
            settings,
            await self.connection.get_connection(session, organization_id),
        )

        # Legacy My Business v4 reviews require the account-qualified parent.
        location_name = v4_location_parent(
            gbp_account.external_account_id, gbp_location.external_location_id
        )
        raw_reviews = await self.adapter.list_reviews(token, location_name)

        ingested = 0
        updated = 0
        for raw in raw_reviews:
            external_review_id = str(raw.get("reviewId") or "")
            if not external_review_id:
                continue
            rating = _parse_rating(raw.get("starRating"))
            comment = raw.get("comment") or ""
            body = comment if isinstance(comment, str) else None
            created_at = _parse_time(raw.get("createTime"))
            updated_at_raw = raw.get("updateTime")
            updated_at = _parse_time(updated_at_raw) if updated_at_raw else None
            raw_name = raw.get("name")
            external_response_id = (
                raw_name.strip()
                if isinstance(raw_name, str) and raw_name.strip()
                else f"{location_name}/reviews/{external_review_id}"
            )
            provider_reply = _normalize_provider_reply(
                raw, external_response_id=external_response_id
            )
            _review, _revision, created = await self.reviews.ingest(
                session,
                organization_id=organization_id,
                location_id=location_id,
                integration_resource_id=mapping.id,
                external_review_id=external_review_id,
                provider="google_business_profile",
                rating=rating,
                title=None,
                body=body,
                created_at=created_at,
                updated_at=updated_at,
                correlation_id=correlation_id,
                provider_reply=provider_reply,
            )
            if created:
                ingested += 1
            else:
                updated += 1

        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="reviews.ingest.completed",
                action="reviews.ingest",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=location_id,
                product_key="reviews",
                resource_type="location",
                resource_id=location_id,
                correlation_id=correlation_id,
                summary="Review ingestion completed.",
                metadata=cast(
                    dict[str, JsonValue],
                    {
                        "total": len(raw_reviews),
                        "ingested": ingested,
                        "updated": updated,
                    },
                ),
            ),
        )
        return {"total": len(raw_reviews), "ingested": ingested, "updated": updated}
