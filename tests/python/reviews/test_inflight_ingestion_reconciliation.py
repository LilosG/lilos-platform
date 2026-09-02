"""Regression coverage for ingestion racing review-reply verification."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.reviews.ingestion_service import IngestionReviewService
from apps.api.app.products.reviews.models import Review, ReviewRevision
from apps.api.app.products.reviews.service import ProviderReplyObservation


class FakeSession:
    def __init__(self, inflight: Any) -> None:
        self.inflight = inflight
        self.scalar_calls = 0
        self.scalars_calls = 0
        self.add_calls = 0

    async def scalar(self, _statement: object) -> Any:
        self.scalar_calls += 1
        return self.inflight

    async def scalars(self, _statement: object) -> list[Any]:
        self.scalars_calls += 1
        return []

    def add(self, _value: object) -> None:
        self.add_calls += 1


def test_ingestion_confirms_matching_inflight_lilos_reply_without_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_id = "accounts/123/locations/456/reviews/review-789"
    approved_at = datetime(2026, 9, 2, 22, 45, tzinfo=UTC)
    inflight = SimpleNamespace(
        id=SimpleNamespace(),
        response_text="Thank you for the thoughtful review.",
        status="reconciliation_required",
        safe_error_code="VERIFICATION_CONTENT_PENDING",
        external_response_id=provider_id,
        published_at=None,
        revision_number=2,
    )
    review = SimpleNamespace(
        id=SimpleNamespace(),
        organization_id=SimpleNamespace(),
        location_id=SimpleNamespace(),
        status="publishing",
    )
    review_revision = SimpleNamespace(id=SimpleNamespace())
    provider_reply = ProviderReplyObservation(
        comment=inflight.response_text,
        updated_at=approved_at,
        state="APPROVED",
        policy_violation=None,
        external_response_id=provider_id,
    )
    service = IngestionReviewService()
    audit_calls: list[dict[str, Any]] = []

    async def record_confirmation(
        _session: AsyncSession,
        **kwargs: Any,
    ) -> None:
        audit_calls.append(kwargs)

    monkeypatch.setattr(service, "_audit_provider_confirmation_once", record_confirmation)
    fake_session = FakeSession(inflight)

    asyncio.run(
        service._reconcile_provider_reply(
            cast(AsyncSession, fake_session),
            review=cast(Review, review),
            review_revision=cast(ReviewRevision, review_revision),
            provider_reply=provider_reply,
            correlation_id="test-inflight-ingestion",
        )
    )

    assert inflight.status == "published"
    assert inflight.safe_error_code is None
    assert inflight.published_at == approved_at
    assert review.status == "responded"
    assert fake_session.scalar_calls == 1
    assert fake_session.scalars_calls == 1
    assert fake_session.add_calls == 0
    assert len(audit_calls) == 1
    assert audit_calls[0]["response"] is inflight
