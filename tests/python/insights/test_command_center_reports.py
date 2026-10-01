"""Phase 7 report readiness and delivery semantics from canonical rows."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from workflows.test_automation_product import p5_client  # noqa: F401

from apps.api.app.routes.command_center_reports import (
    delivery_state,
    generation_state,
    reports_workspace,
)


def row(**values: object) -> SimpleNamespace:
    return SimpleNamespace(**values)


def test_report_projection_preserves_data_quality_and_delivery_evidence() -> None:
    now = datetime.now(UTC)
    org, source_id = uuid4(), uuid4()
    metric_ids = [uuid4() for _ in range(5)]
    definitions = [
        row(id=uuid4(), organization_id=org, name=name, status="active",
            requested_scope={"organization_id": str(org)},
            metric_references=[{"metric_definition_id": str(metric_id)}])
        for name, metric_id in zip(
            ["Ready", "Missing", "Stale", "Partial", "Unavailable"],
            metric_ids,
            strict=True,
        )
    ]
    sources = [row(id=source_id, key="persisted-source", status="active", last_synced_at=now)]
    metrics = [row(id=key, name=f"Metric {index}", freshness_seconds=86400)
               for index, key in enumerate(metric_ids)]
    observations = [
        row(id=uuid4(), metric_definition_id=metric_ids[index], source_id=source_id,
            quality_state=state, period_start=now-timedelta(hours=2),
            period_end=now-timedelta(hours=1))
        for index, state in [(0, "valid"), (2, "stale"), (3, "partial"), (4, "unavailable")]
    ]
    revision = row(id=uuid4(), report_definition_id=definitions[0].id,
                   status="approved", created_at=now, organization_id=org)
    delivery = row(id=uuid4(), report_revision_id=revision.id,
                   notification_delivery_id=uuid4(), status="delivered",
                   artifact_reference="canonical-artifact", created_at=now)
    notification = row(id=delivery.notification_delivery_id, status="delivered")
    session = MagicMock()
    session.scalars = AsyncMock(side_effect=[
        definitions, [revision], [delivery], observations, sources, metrics, [notification]
    ])
    with patch(
        "apps.api.app.routes.command_center_reports.allowed", new=AsyncMock(return_value=True)
    ):
        result = asyncio.run(reports_workspace(MagicMock(), org, session, MagicMock()))
    reports = {report.name: report for report in result.data.reports}
    assert reports["Ready"].readiness == "ready"
    assert reports["Ready"].generation == "sent"
    assert reports["Ready"].deliveries[0].status == "sent"
    assert reports["Ready"].artifact_reference == "canonical-artifact"
    for name, expected in [
        ("Missing", "DATA_MISSING"), ("Stale", "DATA_STALE"),
        ("Partial", "DATA_PARTIAL"), ("Unavailable", "SOURCE_UNAVAILABLE"),
    ]:
        assert reports[name].readiness == "not_ready"
        assert [blocker.code for blocker in reports[name].blockers] == [expected]
    assert result.data.schedule_state == "unavailable_no_canonical_report_schedule"
    assert result.data.generation_state == "unavailable_no_canonical_report_workflow"


def test_generation_and_delivery_never_infer_success() -> None:
    now = datetime.now(UTC)
    report = row(id=uuid4(), status="delivered", created_at=now, artifact_reference="artifact")
    assert delivery_state(report, None).status == "unavailable"
    assert delivery_state(report, row(status="queued")).status == "unavailable"
    assert delivery_state(report, row(status="failed")).status == "failed"
    assert generation_state(None, []) == "unavailable"
    assert generation_state(row(status="queued"), []) == "queued"
    assert generation_state(row(status="generating"), []) == "generating"
    assert generation_state(row(status="failed"), []) == "failed"
    assert generation_state(row(status="approved"), []) == "ready"


def test_report_api_tenant_permission_and_persisted_readiness(
    p5_client, postgresql_test_url: str
) -> None:
    from functools import partial

    from apps.api.app.insights.models import (
        InsightSource, MetricDefinition, MetricObservation, ReportDefinition,
    )
    from workflows import test_automation_product as canonical

    client, ids = p5_client.client, p5_client.ids
    org = ids["organization"]
    url = f"/api/v1/organizations/{org}/command-center/reports/"
    assert client.get(url).status_code == 401
    assert client.get(
        f"/api/v1/organizations/{ids['other_org']}/command-center/reports/",
        headers=canonical.HEADERS,
    ).status_code == 403
    assert client.get(url, headers=canonical.HEADERS).json()["data"]["reports"] == []

    async def seed(session):
        now = datetime.now(UTC)
        source = InsightSource(
            organization_id=org, key="phase7-source", source_type="canonical",
            product_key="insights", status="active", authority_scope="organization",
            last_synced_at=now,
        )
        metric = MetricDefinition(
            key="phase7.metric", version=1, name="Observed metric",
            description="Persisted evidence", source_product="insights", unit="count",
            data_type="decimal", aggregation_behavior="sum", supported_dimensions=[],
            required_filters=[], freshness_seconds=86400,
            partial_period_behavior="partial", missing_data_behavior="missing",
            status="active",
        )
        session.add_all([source, metric])
        await session.flush()
        definition = ReportDefinition(
            organization_id=org, key="phase7-report", name="Persisted report",
            requested_scope={"organization_id": str(org)},
            metric_references=[{"metric_definition_id": str(metric.id)}],
            status="active", version=1,
        )
        observation = MetricObservation(
            organization_id=org, source_id=source.id, metric_definition_id=metric.id,
            period_start=now-timedelta(hours=2), period_end=now-timedelta(hours=1),
            dimensions={}, dimension_hash="phase7", value=1, quality_state="valid",
            completeness=1, provenance={},
        )
        session.add_all([definition, observation])
        await session.commit()
        return observation.id

    observation_id = canonical.run_db(postgresql_test_url, seed)
    response = client.get(url, headers=canonical.HEADERS)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    report = response.json()["data"]["reports"][0]
    assert report["name"] == "Persisted report"
    assert report["readiness"] == "ready"
    assert report["generation"] == "unavailable"
    assert report["metrics"][0]["state"] == "valid"

    async def degrade(session, status):
        observation = await session.get(MetricObservation, observation_id)
        observation.quality_state = status
        await session.commit()

    for state, expected in [("partial", "DATA_PARTIAL"), ("stale", "DATA_STALE"),
                            ("missing", "DATA_MISSING"), ("unavailable", "SOURCE_UNAVAILABLE")]:
        canonical.run_db(postgresql_test_url, partial(degrade, status=state))
        report = client.get(url, headers=canonical.HEADERS).json()["data"]["reports"][0]
        assert report["readiness"] == "not_ready"
        assert report["blockers"][0]["code"] == expected
    p5_client.verifier.result = p5_client.no_permission_claims
    assert client.get(url, headers=canonical.HEADERS).status_code == 403
