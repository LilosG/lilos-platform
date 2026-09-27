"""SEO-linked Growth actions require verified product truth."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from apps.api.app.growth.artifacts import GrowthArtifactLifecycleService, GrowthArtifactState
from apps.api.app.growth.contracts import GrowthActionOutcomeRecord
from apps.api.app.growth.measurement import GrowthMeasurementService, seo_page_periods
from apps.api.app.growth.service import GrowthService, GrowthStateError


@pytest.mark.anyio
async def test_agent_completion_keeps_seo_growth_action_waiting() -> None:
    org, initiative_id, revision_id, workflow_id = (uuid4() for _ in range(4))
    initiative = SimpleNamespace(id=initiative_id, status="executing", completed_at=None)
    action = SimpleNamespace(
        workflow_run_id=workflow_id,
        status="running",
        evidence_references=[f"seo-recommendation:{revision_id}"],
        result_reference=None,
        completed_at=None,
    )
    workflow = SimpleNamespace(
        id=workflow_id,
        status="completed",
        output_reference=None,
        completed_at=datetime.now(UTC),
    )

    class Session:
        scalar = AsyncMock(side_effect=[workflow, None])
        flush = AsyncMock()

    service = GrowthService()
    service.get = AsyncMock(return_value=initiative)  # type: ignore[method-assign]
    service.actions = AsyncMock(return_value=[action])  # type: ignore[method-assign]
    await service.reconcile(cast(Any, Session()), org, initiative_id)
    assert action.status == "waiting_approval"
    assert action.result_reference == f"seo-recommendation:{revision_id}"
    assert action.completed_at is None


@pytest.mark.anyio
async def test_verified_status_requires_verified_at_and_exact_scope() -> None:
    org, revision_id, opportunity_id, website_id, location_id, page_id = (uuid4() for _ in range(6))
    context = {
        "organization_id": str(org),
        "website_id": str(website_id),
        "location_id": str(location_id),
        "page_id": str(page_id),
    }
    revision = SimpleNamespace(
        id=revision_id,
        status="approved",
        opportunity_id=opportunity_id,
        evidence_references=[{"decision_context": context}],
    )
    task = SimpleNamespace(
        status="verified",
        verified_at=None,
        target_reference=f"seo-page:{page_id}",
        verification_evidence=None,
    )
    opportunity = SimpleNamespace(
        id=opportunity_id, website_id=website_id, location_id=location_id, page_id=page_id
    )

    class Session:
        scalar = AsyncMock(side_effect=[revision, task, opportunity])

    state = await GrowthArtifactLifecycleService()._seo_recommendation(
        cast(Any, Session()), org, revision_id
    )
    assert state == GrowthArtifactState("pending", "verified")


@pytest.mark.anyio
async def test_later_contradiction_stops_growth_from_claiming_current_implementation() -> None:
    org, revision_id, opportunity_id, website_id, location_id, page_id = (uuid4() for _ in range(6))
    revision = SimpleNamespace(
        id=revision_id,
        status="approved",
        opportunity_id=opportunity_id,
        evidence_references=[
            {
                "decision_context": {
                    "organization_id": str(org),
                    "website_id": str(website_id),
                    "location_id": str(location_id),
                    "page_id": str(page_id),
                }
            }
        ],
    )
    task = SimpleNamespace(
        status="verified",
        verified_at=datetime.now(UTC),
        target_reference=f"seo-page:{page_id}",
        verification_evidence={"result": "verified", "current_recheck": {"result": "failed"}},
    )
    opportunity = SimpleNamespace(
        id=opportunity_id, website_id=website_id, location_id=location_id, page_id=page_id
    )

    class Session:
        scalar = AsyncMock(side_effect=[revision, task, opportunity])

    state = await GrowthArtifactLifecycleService()._seo_recommendation(
        cast(Any, Session()), org, revision_id
    )
    assert state == GrowthArtifactState(
        "pending", "verification_contested", "DOWNSTREAM_VERIFICATION_CONTRADICTED"
    )


@pytest.mark.anyio
async def test_manual_seo_outcome_assertion_is_rejected() -> None:
    org, action_id = uuid4(), uuid4()
    action = SimpleNamespace(
        status="completed", evidence_references=[f"seo-recommendation:{uuid4()}"]
    )

    class Session:
        scalar = AsyncMock(return_value=action)

    with pytest.raises(GrowthStateError, match="deterministic page measurement"):
        await GrowthMeasurementService().record(
            cast(Any, Session()),
            org,
            action_id,
            GrowthActionOutcomeRecord(classification="improved"),
            actor_id=uuid4(),
            correlation_id="packet-5",
        )


def test_baseline_end_precedes_post_verification_measurement_start() -> None:
    verified_at = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)
    baseline_start, baseline_end, measurement_start, measurement_end = seo_page_periods(
        verified_at, 28
    )
    assert baseline_start < baseline_end <= verified_at < measurement_start
    assert (
        baseline_end - baseline_start == measurement_end - measurement_start == timedelta(days=28)
    )


@pytest.mark.anyio
async def test_repeated_outcome_persistence_reuses_existing_growth_result() -> None:
    existing = SimpleNamespace(id=uuid4())
    action = SimpleNamespace(organization_id=uuid4(), id=uuid4())
    session = MagicMock()
    session.scalar = AsyncMock(return_value=existing)
    service = GrowthMeasurementService()
    result = await service._persist(
        cast(Any, session),
        cast(Any, action),
        classification="inconclusive",
        baseline={},
        measurement={},
        limitations=["missing evidence"],
        actor_id=None,
        correlation_id="packet-5",
        automated=True,
    )
    assert result.id == existing.id
    session.add.assert_not_called()
