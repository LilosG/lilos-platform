"""Automations API: the attention rule on real rows, run now, tenant isolation and audit."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.models import (
    Job,
    Schedule,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from leads import test_leads_api as canonical

HEADERS = canonical.HEADERS
run_db = canonical.run_db
canonical_leads_client = canonical.leads_client
AUTOMATIONS = "/api/v1/command-center/automations"
PORTFOLIO = "/api/v1/command-center/portfolio"
NOW = datetime.now(UTC)


async def version_of(session: AsyncSession, key: str) -> UUID:
    definition = await session.scalar(
        select(WorkflowDefinition).where(WorkflowDefinition.key == key)
    )
    if definition is None:
        definition = WorkflowDefinition(key=key, name=key, owner="test")
        session.add(definition)
        await session.flush()
    version = await session.scalar(
        select(WorkflowVersion.id).where(WorkflowVersion.definition_id == definition.id)
    )
    if version is None:
        created = WorkflowVersion(
            definition_id=definition.id,
            version=1,
            status="approved",
            input_schema={},
            output_schema={},
            step_specification=[],
            retry_policy={},
            timeout_seconds=60,
        )
        session.add(created)
        await session.flush()
        return created.id
    return version


async def schedule(
    session: AsyncSession,
    org: UUID,
    key: str,
    *,
    cron: str = "0 5 * * *",
    status: str = "active",
    location: UUID | None = None,
) -> UUID:
    row = Schedule(
        organization_id=org,
        location_id=location,
        workflow_version_id=await version_of(session, key),
        key=f"test:{key}:{uuid4().hex[:6]}",
        cron_expression=cron,
        timezone="America/Los_Angeles",
        status=status,
        next_run_at=NOW + timedelta(hours=3),
    )
    session.add(row)
    await session.flush()
    return row.id


async def run(
    session: AsyncSession,
    org: UUID,
    key: str,
    status: str,
    hours_ago: int,
    code: str | None = None,
    location: UUID | None = None,
) -> UUID:
    at = NOW - timedelta(hours=hours_ago)
    row = WorkflowRun(
        organization_id=org,
        location_id=location,
        workflow_version_id=await version_of(session, key),
        product_key="gbp",
        trigger_type="schedule",
        idempotency_key=f"seed-{uuid4().hex}",
        request_hash="h",
        input_document={},
        correlation_id="seed",
        status=status,
        failure_code=code,
        started_at=at,
        completed_at=at if status == "completed" else None,
        created_at=at,
        updated_at=at,
    )
    session.add(row)
    await session.flush()
    return row.id


def by_type(body: dict[str, object]) -> dict[str, dict[str, object]]:
    data = body["data"]
    assert isinstance(data, list)
    return {item["workflow_type"]: item for item in data}


def seed_scenario(client: TestClient, ids: dict[str, UUID], url: str) -> dict[str, UUID]:
    org, location, other = ids["organization"], ids["location"], ids["other_organization"]
    made: dict[str, UUID] = {}

    async def seed(session: AsyncSession) -> None:
        # Recovered: failed, then completed. Not attention.
        made["recovered"] = await schedule(session, org, "reviews.ingest")
        await run(session, org, "reviews.ingest", "failed", 30, "REVIEWS_INGEST_FAILED")
        await run(session, org, "reviews.ingest", "completed", 6)
        # Still failing: access denied on the latest run.
        made["denied"] = await schedule(session, org, "gbp.sync_performance", location=location)
        await run(session, org, "gbp.sync_performance", "completed", 40, location=location)
        await run(
            session,
            org,
            "gbp.sync_performance",
            "failed",
            5,
            "GBP_PERFORMANCE_ACCESS_DENIED",
            location=location,
        )
        # Paused, whatever its last run did.
        made["paused"] = await schedule(session, org, "gbp.sync", status="paused")
        await run(session, org, "gbp.sync", "failed", 4, "GBP_SYNC_FAILED")
        # Never run.
        made["never"] = await schedule(session, org, "seo.crawl_or_analysis", cron="0 7 * * 1")
        # Rate limited: will retry, not a failure.
        made["limited"] = await schedule(session, org, "insights.sync_analytics")
        await run(
            session,
            org,
            "insights.sync_analytics",
            "retry_scheduled",
            2,
            "GBP_PERFORMANCE_RATE_LIMITED",
        )
        # Publishing is on demand: a completed run with a dead-lettered verification job.
        reply = await run(session, org, "reviews.publish_response", "completed", 3)
        session.add(
            Job(
                organization_id=org,
                workflow_run_id=reply,
                job_type="workflow.execute",
                status="dead_lettered",
                idempotency_key=f"seed-job-{uuid4().hex}",
                payload={},
                attempt_count=3,
                max_attempts=3,
                last_error_category="VERIFICATION_CONTENT_PENDING",
            )
        )
        # A scheduled post generator exists but is not allowed to run on demand.
        made["post"] = await schedule(session, org, "gbp.generate_post", location=location)
        # Another client's automation must never appear.
        made["other"] = await schedule(session, other, "reviews.ingest")
        await run(session, other, "reviews.ingest", "failed", 1, "REVIEWS_INGEST_FAILED")
        await session.commit()

    run_db(url, seed)
    return made


def test_attention_rules_on_real_rows_and_tenant_isolation(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    made = seed_scenario(client, ids, postgresql_test_url)
    response = client.get(AUTOMATIONS, headers=HEADERS)
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    body = response.json()
    items = by_type(body)
    # Only scheduled workflows are automations; the on-demand reply workflow is not listed.
    assert "reviews.publish_response" not in items
    assert (
        str(made["other"]) not in response.text
        and str(ids["other_organization"]) not in response.text
    )
    assert items["reviews.ingest"]["status"] == "healthy"
    assert items["reviews.ingest"]["attention"] is None
    denied = items["gbp.sync_performance"]
    assert denied["status"] == "needs_attention"
    assert denied["attention"]["reason"] == "GBP_PERFORMANCE_ACCESS_DENIED"
    assert denied["attention"]["recovery_actions"] == ["reconnect_google_business_profile"]
    assert denied["latest_run"]["outcome"] == "failed"
    assert denied["source"] == "google_business_profile"
    assert items["gbp.sync"]["status"] == "paused"
    assert items["gbp.sync"]["attention"] is None and items["gbp.sync"]["next_run_at"] is None
    assert items["seo.crawl_or_analysis"]["status"] == "not_run_yet"
    assert items["seo.crawl_or_analysis"]["latest_run"] is None
    assert items["seo.crawl_or_analysis"]["frequency"]["kind"] == "weekly"
    limited = items["insights.sync_analytics"]
    assert limited["status"] == "healthy" and limited["latest_run"]["outcome"] == "will_retry"
    assert limited["latest_run"]["reason"] == "GBP_PERFORMANCE_RATE_LIMITED"
    assert items["gbp.generate_post"]["run_now_allowed"] is False
    assert items["reviews.ingest"]["run_now_allowed"] is True
    assert items["gbp.sync"]["run_now_allowed"] is False  # paused
    assert body["counts"] == {
        "total": 6,
        "healthy": 2,
        "needs_attention": 1,
        "running": 0,
        "paused": 1,
        "not_run_yet": 2,
    }
    # The dashboard's automations health is the same rule: one client, one automation.
    portfolio = client.get(PORTFOLIO, headers=HEADERS).json()
    health = next(s for s in portfolio["systems"] if s["key"] == "automations")
    assert health["affected_clients"] == 1 and health["status"] == "needs_attention"
    row = next(s for s in portfolio["clients"] if s["organization_id"] == str(ids["organization"]))
    assert row is not None
    overview = client.get(
        f"/api/v1/command-center/clients/{ids['organization']}/overview", headers=HEADERS
    ).json()
    assert (
        next(s for s in overview["systems"] if s["key"] == "automations")["status"]
        == "needs_attention"
    )

    # Filtering to a client the caller cannot see is a plain not found.
    assert (
        client.get(
            AUTOMATIONS, params={"organization_id": str(ids["other_organization"])}, headers=HEADERS
        ).status_code
        == 404
    )
    assert client.get(AUTOMATIONS).status_code == 401


def test_dead_lettered_verification_job_does_not_change_any_automation(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    seed_scenario(client, ids, postgresql_test_url)

    async def jobs(session: AsyncSession) -> int:
        return int(
            await session.scalar(
                select(func.count()).select_from(Job).where(Job.status == "dead_lettered")
            )
            or 0
        )

    assert run_db(postgresql_test_url, jobs) == 1
    body = client.get(AUTOMATIONS, headers=HEADERS).json()
    assert "VERIFICATION_CONTENT_PENDING" not in str(body)
    assert body["counts"]["needs_attention"] == 1


def test_detail_has_history_and_hides_other_tenants(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    made = seed_scenario(client, ids, postgresql_test_url)
    detail = client.get(f"{AUTOMATIONS}/{made['denied']}?runs=10", headers=HEADERS)
    assert detail.status_code == 200, detail.text
    runs = detail.json()["runs"]
    assert [r["outcome"] for r in runs] == ["failed", "succeeded"]
    assert runs[0]["reason"] == "GBP_PERFORMANCE_ACCESS_DENIED"
    assert runs[0]["duration_seconds"] is not None
    assert client.get(f"{AUTOMATIONS}/{made['other']}", headers=HEADERS).status_code == 404
    assert client.get(f"{AUTOMATIONS}/{uuid4()}", headers=HEADERS).status_code == 404


def run_now(client: TestClient, schedule_id: UUID, key: str | None = "key-one-12345"):
    headers = dict(HEADERS)
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.post(f"{AUTOMATIONS}/{schedule_id}/run", headers=headers)


def test_run_now_is_idempotent_audited_and_one_at_a_time(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    made = seed_scenario(client, ids, postgresql_test_url)
    target = made["recovered"]

    assert run_now(client, target, None).status_code == 422
    first = run_now(client, target)
    assert first.status_code == 202, first.text
    assert first.json()["replayed"] is False and first.json()["run_status"] == "queued"
    # A double submit with the same key starts nothing new.
    again = run_now(client, target)
    assert again.status_code == 202 and again.json()["replayed"] is True
    assert again.json()["run_id"] == first.json()["run_id"]
    # A different key while the first run is queued is refused with a typed code.
    busy = run_now(client, target, "key-two-12345")
    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "AUTOMATION_RUN_IN_PROGRESS"
    assert client.get(AUTOMATIONS, headers=HEADERS).json()["data"] is not None
    status = by_type(client.get(AUTOMATIONS, headers=HEADERS).json())["reviews.ingest"]["status"]
    assert status == "running"

    async def facts(session: AsyncSession) -> tuple[int, int, str]:
        runs = await session.scalar(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.idempotency_key.like(f"run-now:{target}:%"))
        )
        audits = list(
            await session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "automation.run_now.requested")
            )
        )
        run_row = await session.get(WorkflowRun, UUID(first.json()["run_id"]))
        assert run_row is not None
        return int(runs or 0), len(audits), str(run_row.input_document["schedule_id"])

    runs, audits, schedule_in_input = run_db(postgresql_test_url, facts)
    assert (runs, audits) == (1, 1)
    # The scheduled handlers resolve their scope from the schedule, so it must be carried.
    assert schedule_in_input == str(target)


def test_run_now_refuses_anything_that_publishes_and_paused_and_other_tenants(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    made = seed_scenario(client, ids, postgresql_test_url)
    post = run_now(client, made["post"])
    assert post.status_code == 403 and post.json()["error"]["code"] == "AUTOMATION_RUN_NOT_ALLOWED"
    paused = run_now(client, made["paused"])
    assert paused.status_code == 409 and paused.json()["error"]["code"] == "AUTOMATION_PAUSED"
    assert run_now(client, made["other"]).status_code == 404

    async def started(session: AsyncSession) -> int:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(WorkflowRun)
                .where(WorkflowRun.idempotency_key.like("run-now:%"))
            )
            or 0
        )

    assert run_db(postgresql_test_url, started) == 0
