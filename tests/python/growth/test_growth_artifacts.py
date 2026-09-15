from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from apps.api.app.growth.artifacts import (
    GrowthArtifactLifecycleService,
    GrowthArtifactState,
)


def test_verified_gbp_post_is_terminal_success() -> None:
    organization_id = uuid4()
    revision_id = uuid4()
    revision = SimpleNamespace(id=revision_id, status="approved")
    publication = SimpleNamespace(status="verified", safe_error_code=None)
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[revision, publication])

    result = asyncio.run(
        GrowthArtifactLifecycleService().resolve(
            cast(Any, session),
            organization_id,
            f"gbp-post-revision:{revision_id}",
        )
    )

    assert result == GrowthArtifactState("succeeded", "verified")


def test_approved_seo_recommendation_waits_for_verified_implementation() -> None:
    organization_id = uuid4()
    revision_id = uuid4()
    revision = SimpleNamespace(id=revision_id, status="approved")
    implementation = SimpleNamespace(status="pending", verified_at=None)
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[revision, implementation])

    result = asyncio.run(
        GrowthArtifactLifecycleService().resolve(
            cast(Any, session),
            organization_id,
            f"seo-recommendation:{revision_id}",
        )
    )

    assert result == GrowthArtifactState("pending", "pending")


def test_published_review_response_is_terminal_success() -> None:
    organization_id = uuid4()
    revision_id = uuid4()
    revision = SimpleNamespace(status="published", safe_error_code=None)
    session = MagicMock()
    session.scalar = AsyncMock(return_value=revision)

    result = asyncio.run(
        GrowthArtifactLifecycleService().resolve(
            cast(Any, session),
            organization_id,
            f"review-response-revision:{revision_id}",
        )
    )

    assert result == GrowthArtifactState("succeeded", "published")


def test_reconcile_waiting_actions_projects_verified_product_truth() -> None:
    organization_id = uuid4()
    initiative_id = uuid4()
    action = SimpleNamespace(
        status="waiting_approval",
        result_reference=f"review-response-revision:{uuid4()}",
        safe_error_code="DOWNSTREAM_RECONCILIATION_REQUIRED",
        completed_at=None,
    )
    session = MagicMock()
    session.scalars = AsyncMock(return_value=[action])
    session.flush = AsyncMock()
    service = GrowthArtifactLifecycleService()
    service.resolve = AsyncMock(return_value=GrowthArtifactState("succeeded", "published"))  # type: ignore[method-assign]

    transitions = asyncio.run(
        service.reconcile_waiting_actions(
            cast(Any, session),
            organization_id,
            initiative_id,
        )
    )

    assert transitions == 1
    assert action.status == "completed"
    assert action.safe_error_code is None
    assert action.completed_at is not None
    session.flush.assert_awaited_once()


def test_reconcile_waiting_actions_does_not_claim_pending_execution() -> None:
    organization_id = uuid4()
    initiative_id = uuid4()
    action = SimpleNamespace(
        status="waiting_approval",
        result_reference=f"content-revision:{uuid4()}",
        safe_error_code=None,
        completed_at=None,
    )
    session = MagicMock()
    session.scalars = AsyncMock(return_value=[action])
    session.flush = AsyncMock()
    service = GrowthArtifactLifecycleService()
    service.resolve = AsyncMock(  # type: ignore[method-assign]
        return_value=GrowthArtifactState(
            "pending",
            "reconciliation_required",
            "DOWNSTREAM_RECONCILIATION_REQUIRED",
        )
    )

    transitions = asyncio.run(
        service.reconcile_waiting_actions(
            cast(Any, session),
            organization_id,
            initiative_id,
        )
    )

    assert transitions == 0
    assert action.status == "waiting_approval"
    assert action.safe_error_code == "DOWNSTREAM_RECONCILIATION_REQUIRED"
    assert action.completed_at is None
