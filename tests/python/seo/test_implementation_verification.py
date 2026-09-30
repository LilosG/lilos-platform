"""Packet 5 implementation truth and page measurement boundaries."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from apps.api.app.growth.measurement import GrowthMeasurementService, utc_day_after
from apps.api.app.products.seo.contracts import ImplementationTaskVerify
from apps.api.app.products.seo.service import SEOService
from apps.api.app.products.seo.verification import read_implementation_truth


class ScalarSession:
    def __init__(self, *values: object) -> None:
        self.values = iter(values)
        self.queries: list[str] = []

    async def scalar(self, query: Any) -> Any:
        self.queries.append(str(query.compile(compile_kwargs={"literal_binds": True})))
        return next(self.values)


def decision_fixture() -> tuple[Any, Any, Any]:
    now = datetime.now(UTC)
    org, site, location, page, opportunity_id, revision_id, task_id, workflow_id = (
        uuid4() for _ in range(8)
    )
    opportunity = SimpleNamespace(
        id=opportunity_id,
        organization_id=org,
        website_id=site,
        location_id=location,
        page_id=page,
        opportunity_type="missing_title",
    )
    task = SimpleNamespace(
        id=task_id,
        organization_id=org,
        recommendation_revision_id=revision_id,
        workflow_run_id=workflow_id,
        target_reference=f"seo-page:{page}",
        created_at=now - timedelta(days=2),
    )
    revision = SimpleNamespace(
        id=revision_id,
        organization_id=org,
        opportunity_id=opportunity_id,
        status="approved",
        change_set=None,  # an ordinary recommendation: no governed site change attached
        change_set_fingerprint=None,
        evidence_references=[
            {
                "decision_context": {
                    "organization_id": str(org),
                    "website_id": str(site),
                    "location_id": str(location),
                    "page_id": str(page),
                    "recommendation_class": "technical_regression",
                    "evidence_references": [f"seo-crawl-observation:{uuid4()}"],
                }
            }
        ],
    )
    return task, revision, opportunity


@pytest.mark.anyio
async def test_completed_workflow_without_new_evidence_is_not_verified() -> None:
    task, revision, opportunity = decision_fixture()
    workflow = SimpleNamespace(
        id=task.workflow_run_id, status="completed", completed_at=datetime.now(UTC)
    )
    session = ScalarSession(workflow, None)
    proof = await read_implementation_truth(cast(Any, session), task, revision, opportunity)
    assert proof["result"] == "unavailable"
    assert proof["implementation_task_id"] == str(task.id)
    assert proof["recommendation_revision_id"] == str(revision.id)
    assert task.organization_id.hex in session.queries[0]
    assert opportunity.location_id.hex in session.queries[0]
    assert opportunity.website_id.hex in session.queries[1]
    assert opportunity.page_id.hex in session.queries[1]


@pytest.mark.anyio
async def test_technical_verification_compares_exact_approved_baseline_and_new_page() -> None:
    task, revision, opportunity = decision_fixture()
    baseline_id = uuid4()
    revision.evidence_references[-1]["decision_context"]["evidence_references"] = [
        f"seo-crawl-observation:{baseline_id}"
    ]
    workflow = SimpleNamespace(
        id=task.workflow_run_id, status="completed", completed_at=datetime.now(UTC)
    )
    baseline = SimpleNamespace(
        id=baseline_id,
        technical_issues=["missing_title"],
        observed_at=task.created_at - timedelta(days=1),
    )
    current = SimpleNamespace(
        id=uuid4(),
        technical_issues=[],
        observed_at=datetime.now(UTC),
        quality_status="clean",
        http_status=200,
        title="Service page",
        meta_description="Description",
        h1="Service page",
    )
    session = ScalarSession(workflow, baseline, current)
    proof = await read_implementation_truth(cast(Any, session), task, revision, opportunity)
    assert proof["result"] == "verified"
    assert proof["observed_at"] == current.observed_at.isoformat()
    assert proof["evidence_references"] == [
        f"seo-crawl-observation:{baseline.id}",
        f"seo-crawl-observation:{current.id}",
    ]
    assert opportunity.website_id.hex in session.queries[2]
    assert opportunity.page_id.hex in session.queries[2]


@pytest.mark.anyio
async def test_scope_mismatch_fails_before_evidence_read() -> None:
    task, revision, opportunity = decision_fixture()
    opportunity.page_id = uuid4()
    session = ScalarSession()
    proof = await read_implementation_truth(cast(Any, session), task, revision, opportunity)
    assert proof["result"] == "unavailable"
    assert session.queries == []


@pytest.mark.anyio
async def test_content_approval_without_publication_cannot_verify_page() -> None:
    task, revision, opportunity = decision_fixture()
    revision.evidence_references[-1]["decision_context"]["recommendation_class"] = "growth_change"
    workflow = SimpleNamespace(
        id=task.workflow_run_id, status="completed", completed_at=datetime.now(UTC)
    )
    proof = await read_implementation_truth(
        cast(Any, ScalarSession(workflow, None)), task, revision, opportunity
    )
    assert proof["result"] == "unavailable"
    assert proof["verification_method"] == "content_publication_and_page"
    assert proof["evidence_references"] == []


@pytest.mark.anyio
async def test_content_deployment_identity_does_not_assert_exact_page_parity() -> None:
    task, revision, opportunity = decision_fixture()
    revision.evidence_references[-1]["decision_context"]["recommendation_class"] = "growth_change"
    now = datetime.now(UTC)
    publication = SimpleNamespace(
        id=uuid4(),
        verified_at=now,
        status="verified",
        content_revision_id=uuid4(),
        external_revision_id="a" * 40,
        published_url="https://deployment.example.test",
    )
    workflow = SimpleNamespace(id=task.workflow_run_id, status="completed", completed_at=now)
    session = ScalarSession(workflow, publication)
    proof = await read_implementation_truth(cast(Any, session), task, revision, opportunity)
    assert proof["result"] == "unavailable"
    actual = proof["actual"]
    assert isinstance(actual, dict)
    assert actual["merged_commit_sha"] == publication.external_revision_id
    assert proof["evidence_references"] == [f"content-publication:{publication.id}"]
    assert f"seo-opportunity:{opportunity.id}" in session.queries[1]


@pytest.mark.anyio
async def test_page_measurement_never_reads_query_only_or_site_daily_rows() -> None:
    task, _, opportunity = decision_fixture()
    del task
    property_id = uuid4()

    class PageSession:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def scalars(self, query: Any) -> list[Any]:
            self.queries.append(str(query.compile(compile_kwargs={"literal_binds": True})))
            return (
                [
                    SimpleNamespace(
                        id=property_id,
                        freshness_status="fresh",
                        last_synced_at=start + timedelta(days=8),
                    )
                ]
                if len(self.queries) == 1
                else []
            )

    session = PageSession()
    start = utc_day_after(datetime.now(UTC) - timedelta(days=28))
    window = await GrowthMeasurementService()._gsc_page_window(
        cast(Any, session),
        opportunity.organization_id,
        opportunity.location_id,
        opportunity,
        "clicks",
        start,
        start + timedelta(days=7),
    )
    assert window.complete is False
    assert window.value is None
    assert "seo_search_observations.page_id =" in session.queries[1]
    assert "seo_search_observations.query IS NULL" in session.queries[1]
    assert "observation_type" in session.queries[1]


@pytest.mark.anyio
async def test_exact_fresh_page_period_can_supply_a_growth_metric() -> None:
    _, _, opportunity = decision_fixture()
    property_id = uuid4()
    start = utc_day_after(datetime.now(UTC) - timedelta(days=28))
    end = start + timedelta(days=7)
    row = SimpleNamespace(
        id=uuid4(),
        search_property_id=property_id,
        clicks=12,
        impressions=100,
        position=4,
    )

    class PageSession:
        def __init__(self) -> None:
            self.calls = 0

        async def scalars(self, _query: Any) -> list[Any]:
            self.calls += 1
            if self.calls == 1:
                return [
                    SimpleNamespace(
                        id=property_id,
                        freshness_status="fresh",
                        last_synced_at=end + timedelta(days=1),
                    )
                ]
            return [row]

    window = await GrowthMeasurementService()._gsc_page_window(
        cast(Any, PageSession()),
        opportunity.organization_id,
        opportunity.location_id,
        opportunity,
        "ctr",
        start,
        end,
    )
    assert window.complete is True
    assert str(window.value) == "0.12"
    assert window.evidence_references == (f"seo-search-observation:{row.id}",)


@pytest.mark.anyio
async def test_later_contradiction_preserves_original_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task, revision, opportunity = decision_fixture()
    verified_at = datetime.now(UTC) - timedelta(days=1)
    task.status = "verified"
    task.verified_at = verified_at
    task.verification_evidence = {"result": "verified", "observed_at": verified_at.isoformat()}
    contradictory = {
        "result": "failed",
        "observed_at": datetime.now(UTC).isoformat(),
        "evidence_references": [f"seo-crawl-observation:{uuid4()}"],
    }
    monkeypatch.setattr(
        "apps.api.app.products.seo.service.read_implementation_truth",
        AsyncMock(return_value=contradictory),
    )
    service = SEOService()
    service.get_opportunity = AsyncMock(return_value=opportunity)  # type: ignore[method-assign]
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[task, revision])
    session.flush = AsyncMock()
    result = await service.verify_implementation_task(
        cast(Any, session),
        task.organization_id,
        task.id,
        ImplementationTaskVerify(),
        actor_id=None,
        correlation_id="packet-5",
    )
    assert result.status == "verified"
    assert result.verified_at == verified_at
    assert result.verification_evidence is not None
    assert result.verification_evidence["observed_at"] == verified_at.isoformat()
    assert result.verification_evidence["current_recheck"] == contradictory
    session.flush.assert_awaited_once()
