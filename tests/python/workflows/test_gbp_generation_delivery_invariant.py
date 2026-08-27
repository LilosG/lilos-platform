"""Regression tests for automated GBP post delivery readiness."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.app.execution.operational_extensions import _handle_gbp_generate_post
from apps.api.app.products.gbp.post_generation import GBPPostGenerationService
from apps.api.app.products.gbp.proposal_enrichment import GBPProposalEnrichmentError


@pytest.mark.anyio
async def test_gbp_generate_post_rejects_invalid_review_source() -> None:
    session = AsyncMock()

    outcome = await _handle_gbp_generate_post(
        session,
        organization_id=uuid4(),
        location_id=uuid4(),
        input_document={"review_id": "not-a-uuid"},
        correlation_id="invalid-review",
        workflow_run_id=uuid4(),
    )

    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == "GBP_REVIEW_SOURCE_INVALID"
    session.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_gbp_generate_post_passes_explicit_review_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    revision_id = uuid4()
    review_id = uuid4()
    captured: dict[str, object] = {}

    async def successful_generation(
        *args: object, **kwargs: object
    ) -> tuple[object, object, object]:
        captured.update(kwargs)
        return (
            SimpleNamespace(id=revision_id),
            SimpleNamespace(id=uuid4()),
            SimpleNamespace(id=uuid4()),
        )

    monkeypatch.setattr(GBPPostGenerationService, "generate", successful_generation)
    outcome = await _handle_gbp_generate_post(
        session,
        organization_id=uuid4(),
        location_id=uuid4(),
        input_document={"review_id": str(review_id)},
        correlation_id="explicit-review",
        workflow_run_id=uuid4(),
    )

    assert outcome.result == "succeeded"
    assert captured["source_review_id"] == review_id


@pytest.mark.anyio
async def test_gbp_generate_post_never_succeeds_without_required_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()

    async def fail_generation(*args: object, **kwargs: object) -> object:
        raise GBPProposalEnrichmentError(
            "GBP_DRIVE_NO_ELIGIBLE_IMAGE",
            "No eligible client image is available.",
        )

    monkeypatch.setattr(GBPPostGenerationService, "generate", fail_generation)
    outcome = await _handle_gbp_generate_post(
        session,
        organization_id=uuid4(),
        location_id=uuid4(),
        input_document={},
        correlation_id="missing-image",
        workflow_run_id=uuid4(),
    )

    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == "GBP_DRIVE_NO_ELIGIBLE_IMAGE"
    assert outcome.result_reference is None
    session.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_gbp_generate_post_retries_transient_drive_enrichment_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()

    async def fail_generation(*args: object, **kwargs: object) -> object:
        raise GBPProposalEnrichmentError(
            "GBP_DRIVE_MEDIA_UNAVAILABLE",
            "Drive media discovery is temporarily unavailable.",
        )

    monkeypatch.setattr(GBPPostGenerationService, "generate", fail_generation)
    outcome = await _handle_gbp_generate_post(
        session,
        organization_id=uuid4(),
        location_id=uuid4(),
        input_document={},
        correlation_id="drive-unavailable",
        workflow_run_id=uuid4(),
    )

    assert outcome.result == "retryable_failure"
    assert outcome.safe_error == "GBP_DRIVE_MEDIA_UNAVAILABLE"
    assert outcome.result_reference is None
    session.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_gbp_generate_post_success_is_always_image_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    revision_id = uuid4()

    async def successful_generation(
        *args: object, **kwargs: object
    ) -> tuple[object, object, object]:
        return (
            SimpleNamespace(id=revision_id),
            SimpleNamespace(id=uuid4()),
            SimpleNamespace(id=uuid4()),
        )

    monkeypatch.setattr(GBPPostGenerationService, "generate", successful_generation)
    outcome = await _handle_gbp_generate_post(
        session,
        organization_id=uuid4(),
        location_id=uuid4(),
        input_document={},
        correlation_id="image-bound",
        workflow_run_id=uuid4(),
    )

    assert outcome.result == "succeeded"
    assert outcome.safe_error is None
    assert outcome.result_reference == f"gbp-post-revision:{revision_id}:image"
    assert ":text" not in outcome.result_reference
    session.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_gbp_generate_post_defensively_rejects_null_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()

    async def invalid_generation(*args: object, **kwargs: object) -> tuple[object, object, None]:
        return SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4()), None

    monkeypatch.setattr(GBPPostGenerationService, "generate", invalid_generation)
    outcome = await _handle_gbp_generate_post(
        session,
        organization_id=uuid4(),
        location_id=uuid4(),
        input_document={},
        correlation_id="null-asset",
        workflow_run_id=uuid4(),
    )

    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == "GBP_POST_DELIVERY_BINDING_MISSING"
    assert outcome.result_reference is None
    session.rollback.assert_awaited_once()
