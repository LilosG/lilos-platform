"""Write-once Reviews publication and handler-routing regression tests."""

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution import handlers as execution_handlers
from apps.api.app.execution.handler_resolver import resolve_workflow_handler
from apps.api.app.products.gbp.models import GBPAccount
from apps.api.app.products.reviews.models import Review
from apps.api.app.products.reviews.publish_handler import handle_reviews_publish_response


class FakeSession:
    def __init__(
        self,
        scalar_values: list[Any],
        *,
        account: Any,
        review: Any,
    ) -> None:
        self.scalar_values = list(scalar_values)
        self.account = account
        self.review = review
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, _statement: object) -> Any:
        if not self.scalar_values:
            raise AssertionError("unexpected scalar query")
        return self.scalar_values.pop(0)

    async def get(self, model: type[Any], _object_id: object) -> Any:
        if model is GBPAccount:
            return self.account
        if model is Review:
            return self.review
        raise AssertionError(f"unexpected get for {model}")

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeAdapter:
    def __init__(self, review_payload: dict[str, Any]) -> None:
        self.review_payload = review_payload
        self.update_calls = 0
        self.get_calls = 0

    async def update_review_reply(
        self, _token: str, _review_name: str, _comment: str
    ) -> dict[str, Any]:
        self.update_calls += 1
        return {}

    async def get_review(self, _token: str, _review_name: str) -> dict[str, Any]:
        self.get_calls += 1
        return self.review_payload


def _objects(*, response_status: str, safe_error_code: str | None = None) -> tuple[Any, ...]:
    response = SimpleNamespace(
        id=uuid4(),
        review_id=uuid4(),
        response_text="Thank you for the thoughtful review.",
        status=response_status,
        safe_error_code=safe_error_code,
        external_response_id=None,
        published_at=None,
    )
    review = SimpleNamespace(
        id=response.review_id,
        location_id=uuid4(),
        integration_resource_id=uuid4(),
        external_review_id="review-123",
        status="approved",
    )
    mapping = SimpleNamespace(id=review.integration_resource_id)
    gbp_location = SimpleNamespace(
        account_id=uuid4(),
        write_enabled=True,
        mapping_status="confirmed",
        external_location_id="location-456",
    )
    account = SimpleNamespace(external_account_id="account-789")
    return response, review, mapping, gbp_location, account


def _install_provider(monkeypatch: pytest.MonkeyPatch, adapter: FakeAdapter) -> None:
    async def token_resolver(
        _session: AsyncSession, _organization_id: object
    ) -> tuple[str, object]:
        return "token", object()

    monkeypatch.setattr(execution_handlers, "_adapter_factory", lambda: adapter)
    monkeypatch.setattr(execution_handlers, "_token_resolver", token_resolver)
    monkeypatch.setattr(execution_handlers, "_provider_writes_enabled", lambda: True)


def test_reviews_publish_handler_is_resolved_through_product_boundary() -> None:
    assert resolve_workflow_handler("reviews.publish_response") is handle_reviews_publish_response


def test_successful_write_with_eventual_consistency_is_not_reposted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, review, mapping, location, account = _objects(response_status="publishing")
    adapter = FakeAdapter({"reviewReply": {}})
    _install_provider(monkeypatch, adapter)
    fake = FakeSession(
        [response, review, mapping, location, response, response],
        account=account,
        review=review,
    )

    outcome = asyncio.run(
        handle_reviews_publish_response(
            cast(AsyncSession, fake),
            organization_id=uuid4(),
            location_id=review.location_id,
            input_document={"response_id": str(response.id)},
            correlation_id="test-review-publish",
            workflow_run_id=uuid4(),
        )
    )

    assert outcome.result == "retryable_failure"
    assert outcome.safe_error == "VERIFICATION_CONTENT_PENDING"
    assert adapter.update_calls == 1
    assert adapter.get_calls == 1
    assert response.external_response_id is not None
    assert response.status == "reconciliation_required"


def test_historical_verification_mismatch_recovers_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, review, mapping, location, account = _objects(
        response_status="reconciliation_required",
        safe_error_code="VERIFICATION_CONTENT_MISMATCH",
    )
    adapter = FakeAdapter(
        {"reviewReply": {"comment": response.response_text, "reviewReplyState": "APPROVED"}}
    )
    _install_provider(monkeypatch, adapter)
    fake = FakeSession(
        [response, review, mapping, location, response, response],
        account=account,
        review=review,
    )

    outcome = asyncio.run(
        handle_reviews_publish_response(
            cast(AsyncSession, fake),
            organization_id=uuid4(),
            location_id=review.location_id,
            input_document={"response_id": str(response.id)},
            correlation_id="test-review-verify",
            workflow_run_id=uuid4(),
        )
    )

    assert outcome.result == "succeeded"
    assert adapter.update_calls == 0
    assert adapter.get_calls == 1
    assert response.status == "published"
    assert response.safe_error_code is None
    assert response.published_at is not None


def test_true_provider_content_mismatch_never_rewrites_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, review, mapping, location, account = _objects(
        response_status="reconciliation_required",
        safe_error_code="VERIFICATION_CONTENT_MISMATCH",
    )
    adapter = FakeAdapter({"reviewReply": {"comment": "A different provider reply."}})
    _install_provider(monkeypatch, adapter)
    fake = FakeSession(
        [response, review, mapping, location, response, response],
        account=account,
        review=review,
    )

    outcome = asyncio.run(
        handle_reviews_publish_response(
            cast(AsyncSession, fake),
            organization_id=uuid4(),
            location_id=review.location_id,
            input_document={"response_id": str(response.id)},
            correlation_id="test-review-mismatch",
            workflow_run_id=uuid4(),
        )
    )

    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == "VERIFICATION_CONTENT_MISMATCH"
    assert adapter.update_calls == 0
    assert adapter.get_calls == 1
    assert response.status == "reconciliation_required"
    assert review.status == "publication_failed"
