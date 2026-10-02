"""Phase 6 durable-state projection and canonical action acceptance."""

from datetime import UTC, datetime, timedelta
from functools import partial
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.models import Job, WorkflowDefinition, WorkflowRun
from workflows import test_automation_product as canonical

p5_client = canonical.p5_client
HEADERS = canonical.HEADERS


def test_workspace_schedule_state_and_history(
    p5_client: canonical.P5Context, postgresql_test_url: str
) -> None:
    client, ids = p5_client.client, p5_client.ids
    root = f"/api/v1/organizations/{ids['organization']}"
    workspace = root + "/command-center/automations"
    empty = client.get(workspace, headers=HEADERS)
    assert empty.status_code == 200, empty.text
    assert empty.headers["cache-control"] == "private, no-store"
    data = empty.json()
    assert data["total_runs"] == 0
    assert not data["schedules"] and not data["outcomes"]
    assert data["runtime_health"] == "unavailable_no_scoped_heartbeat"
    assert all(d["definition_status"] == "not_persisted" for d in data["definitions"])
    schedule = client.post(
        root + "/workflows/schedules",
        headers=HEADERS,
        json={
            "workflow_key": "gbp.sync",
            "key": "phase6-durable-sync",
            "cron_expression": "0 9 * * *",
            "timezone": "UTC",
            "next_run_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "location_id": str(ids["location"]),
        },
    )
    assert schedule.status_code == 201, schedule.text
    schedule_id = schedule.json()["data"]["id"]
    recorded = client.get(workspace, headers=HEADERS).json()
    assert recorded["schedules"][0]["overdue"] is True
    next_run = recorded["schedules"][0]["next_run_at"]
    assert recorded["schedules"][0]["can_manage"]
    paused = client.patch(
        root + f"/workflows/schedules/{schedule_id}", headers=HEADERS, json={"status": "paused"}
    )
    assert paused.status_code == 200, paused.text
    state = client.get(workspace, headers=HEADERS).json()["schedules"][0]
    assert state["status"] == "paused" and not state["overdue"]
    assert state["next_run_at"] == next_run
    command = {"idempotency_key": "phase6-read-test-run", "input_document": {}, "execute": True}
    queued = client.post(root + "/workflows/gbp.sync/runs", headers=HEADERS, json=command)
    assert queued.status_code == 201, queued.text
    run_id = queued.json()["data"]["workflow_run_id"]
    assert (
        client.post(root + "/workflows/gbp.sync/runs", headers=HEADERS, json=command).json()[
            "data"
        ]["workflow_run_id"]
        == run_id
    )
    detail = client.get(workspace + f"/runs/{run_id}", headers=HEADERS).json()
    assert detail["run"]["status"] == "queued"
    assert detail["run"]["outcome"] == "execution_only"
    assert len(detail["jobs"]) == 1 and detail["jobs"][0]["status"] == "queued"
    assert detail["idempotency_key"] == command["idempotency_key"]
    assert detail["history"]
    assert not detail["can_stop"] and detail["recovery"] == "domain_controls_only"

    async def set_state(session: AsyncSession, status: str) -> None:
        run = await session.get(WorkflowRun, UUID(run_id))
        job = await session.scalar(select(Job).where(Job.workflow_run_id == UUID(run_id)))
        assert run and job
        run.status = status
        run.output_reference = "canonical-result:test"
        run.completed_at = datetime.now(UTC) if status == "completed" else None
        run.failure_code = "TEST_FAILURE" if status == "failed" else None
        job.status = "retry_scheduled" if status == "retry_scheduled" else status
        await session.commit()

    for status in ("running", "failed", "retry_scheduled", "completed"):
        canonical.run_db(postgresql_test_url, partial(set_state, status=status))
        result = client.get(workspace, headers=HEADERS).json()
        assert result["runs"][0]["status"] == status
        assert len(result["outcomes"]) == (1 if status == "completed" else 0)
        if status == "failed":
            assert result["attention"][0]["attention"] == "failure"
        if status == "retry_scheduled":
            assert result["attention"][0]["retry_at"] is not None
        if status == "completed":
            assert result["outcomes"][0]["outcome"] == "recorded_result"

    async def disable_definition(session: AsyncSession) -> None:
        row = await session.scalar(
            select(WorkflowDefinition).where(WorkflowDefinition.key == "gbp.sync")
        )
        assert row
        row.status = "disabled"
        await session.commit()

    canonical.run_db(postgresql_test_url, disable_definition)
    assert (
        next(
            d
            for d in client.get(workspace, headers=HEADERS).json()["definitions"]
            if d["key"] == "gbp.sync"
        )["definition_status"]
        == "disabled"
    )


def test_scope_auth_permission_and_stale(
    p5_client: canonical.P5Context, postgresql_test_url: str
) -> None:
    client, ids = p5_client.client, p5_client.ids
    root = f"/api/v1/organizations/{ids['organization']}"
    workspace = root + "/command-center/automations"
    assert client.get(workspace).status_code == 401
    assert (
        client.get(
            f"/api/v1/organizations/{ids['other_org']}/command-center/automations", headers=HEADERS
        ).status_code
        == 403
    )
    assert client.get(workspace + f"?location_id={uuid4()}", headers=HEADERS).status_code == 404
    assert client.get(workspace + f"/runs/{uuid4()}", headers=HEADERS).status_code == 404
    result = client.post(
        root + "/workflows/reviews.ingest/runs",
        headers=HEADERS,
        json={"idempotency_key": "phase6-stale-run", "execute": True},
    )
    assert result.status_code == 201, result.text
    run_id = UUID(result.json()["data"]["workflow_run_id"])

    async def stale(session: AsyncSession) -> None:
        row = await session.get(WorkflowRun, run_id)
        assert row
        row.updated_at = datetime.now(UTC) - timedelta(days=2)
        await session.commit()

    canonical.run_db(postgresql_test_url, stale)
    response = client.get(workspace, headers=HEADERS).json()
    assert response["attention"][0]["attention"] == "stale"
    assert response["quality"] == "partial"
    assert (
        client.get(
            f"/api/v1/organizations/{ids['other_org']}/command-center/automations/runs/{run_id}",
            headers=HEADERS,
        ).status_code
        == 403
    )
    p5_client.verifier.result = p5_client.no_permission_claims
    assert client.get(workspace, headers=HEADERS).status_code == 403


def test_reconciliation_precedes_publication_success() -> None:
    """Exercise the actual projection with domain read-back records, never provider calls."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from apps.api.app.products.content.models import ContentPublication
    from apps.api.app.routes.command_center_automations import project_runs

    async def scenario() -> None:
        now = datetime.now(UTC)
        org, version, run_id = uuid4(), uuid4(), uuid4()
        run = WorkflowRun(
            id=run_id,
            organization_id=org,
            workflow_version_id=version,
            status="completed",
            created_at=now,
            updated_at=now,
            completed_at=now,
            started_at=now,
            correlation_id="phase6-reconciliation",
            output_reference="publication:evidence",
        )
        job = Job(id=uuid4(), workflow_run_id=run_id, status="completed")
        for state in (
            "reserved",
            "checks_running",
            "deployment_pending",
            "deployed",
            "reconciliation_required",
            "failed",
            "verified",
        ):
            publication = ContentPublication(
                workflow_run_id=run_id,
                status=state,
                verified_at=now if state == "verified" else None,
            )
            keys = MagicMock()
            keys.all.return_value = [(version, "content.publish", "Governed publication")]
            session = AsyncMock(spec=AsyncSession)
            session.execute.return_value = keys
            session.scalars.side_effect = [[job], [], [publication]]
            projected = (await project_runs(session, org, [run], now))[0]
            assert projected.outcome == (
                "verified_publication" if state == "verified" else "unconfirmed_publication"
            )
            if state in ("reconciliation_required", "failed"):
                assert projected.attention == "reconciliation"
        # Even a status string 'verified' without persisted read-back time is unconfirmed.
        publication.verified_at = None
        session.scalars.side_effect = [[job], [], [publication]]
        assert (await project_runs(session, org, [run], now))[
            0
        ].outcome == "unconfirmed_publication"
        # Missing write reconciliation source cannot be inferred from a completed job.
        session.scalars.side_effect = [[job], [], []]
        assert (await project_runs(session, org, [run], now))[
            0
        ].outcome == "unconfirmed_publication"

    asyncio.run(scenario())
