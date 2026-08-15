"""Packet 9B — migration reconciliation of orphaned jobs and crawl runs.

Proves the one-time data repair in ``20260815_0001`` brings the poisoned
state (a job at ``max_attempts`` with open ``running`` attempts, and an
orphaned ``seo_crawl_runs`` row never started) to a truthful terminal state.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def alembic_config() -> Config:
    return Config(REPOSITORY_ROOT / "alembic.ini")


@pytest.mark.integration
def test_reconcile_orphaned_jobs_and_crawls(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = alembic_config()
    engine = create_async_engine(postgresql_test_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    command.downgrade(config, "base")
    command.upgrade(config, "20260813_0001")

    org_id = uuid.uuid4()
    definition_id = uuid.uuid4()
    version_id = uuid.uuid4()
    run_id = uuid.uuid4()
    job_id = uuid.uuid4()
    website_id = uuid.uuid4()
    crawl_run_id = uuid.uuid4()
    expired = datetime.now(UTC) - timedelta(minutes=5)

    async def _seed() -> None:
        async with session_factory.begin() as s:
            await s.execute(
                text(
                    "INSERT INTO organizations "
                    "(id, name, slug, organization_type, status, timezone, default_currency) "
                    "VALUES (:id, 'Mig Test', :slug, 'test', 'active', 'UTC', 'USD')"
                ),
                {"id": org_id, "slug": f"mig-{org_id.hex[:12]}"},
            )
            await s.execute(
                text(
                    "INSERT INTO workflow_definitions (id, key, name, owner, status) "
                    "VALUES (:id, :key, 'Mig Test', 'platform', 'active')"
                ),
                {"id": definition_id, "key": f"mig.def.{definition_id.hex}"},
            )
            await s.execute(
                text(
                    "INSERT INTO workflow_versions "
                    "(id, definition_id, version, status, input_schema, output_schema, "
                    " step_specification, retry_policy, timeout_seconds) "
                    "VALUES (:id, :definition_id, 1, 'approved', '{}'::jsonb, '{}'::jsonb, "
                    " '[]'::jsonb, '{}'::jsonb, 30)"
                ),
                {"id": version_id, "definition_id": definition_id},
            )
            await s.execute(
                text(
                    "INSERT INTO workflow_runs "
                    "(id, organization_id, workflow_version_id, status, trigger_type, "
                    " idempotency_key, request_hash, input_document, correlation_id) "
                    "VALUES (:id, :organization_id, :version_id, 'queued', 'api', :run_key, "
                    " repeat('a', 64), '{}'::jsonb, 'mig-test')"
                ),
                {
                    "id": run_id,
                    "organization_id": org_id,
                    "version_id": version_id,
                    "run_key": f"mig-run-{run_id.hex[:12]}",
                },
            )
            await s.execute(
                text(
                    "INSERT INTO jobs "
                    "(id, organization_id, workflow_run_id, job_type, status, idempotency_key, "
                    " payload, available_at, attempt_count, max_attempts, lease_owner, "
                    " lease_expires_at) "
                    "VALUES (:id, :organization_id, :run_id, 'workflow.execute', 'claimed', "
                    " :job_key, '{}'::jsonb, :available_at, 3, 3, 'old-worker', :expired)"
                ),
                {
                    "id": job_id,
                    "organization_id": org_id,
                    "run_id": run_id,
                    "job_key": f"mig-job-{job_id.hex[:12]}",
                    "available_at": expired,
                    "expired": expired,
                },
            )
            for attempt_number in (1, 2, 3):
                await s.execute(
                    text(
                        "INSERT INTO job_attempts "
                        "(id, organization_id, job_id, attempt_number, status, worker_id) "
                        "VALUES (:id, :organization_id, :job_id, :attempt_number, 'running', "
                        " :worker_id)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "organization_id": org_id,
                        "job_id": job_id,
                        "attempt_number": attempt_number,
                        "worker_id": f"old-worker-{attempt_number}",
                    },
                )
            await s.execute(
                text(
                    "INSERT INTO seo_websites "
                    "(id, organization_id, key, name, canonical_origin, status, "
                    " ownership_status, version) "
                    "VALUES (:id, :organization_id, :key, 'Mig Website', "
                    " 'https://example.invalid', 'active', 'verified', 1)"
                ),
                {
                    "id": website_id,
                    "organization_id": org_id,
                    "key": f"mig-site-{website_id.hex[:8]}",
                },
            )
            await s.execute(
                text(
                    "INSERT INTO seo_crawl_runs "
                    "(id, organization_id, website_id, workflow_run_id, idempotency_key, "
                    " status, max_pages, safe_result) "
                    "VALUES (:id, :organization_id, :website_id, :run_id, :key, "
                    " 'queued', 100, '{}'::jsonb)"
                ),
                {
                    "id": crawl_run_id,
                    "organization_id": org_id,
                    "website_id": website_id,
                    "run_id": run_id,
                    "key": f"mig-crawl-{crawl_run_id.hex[:12]}",
                },
            )

    asyncio.run(_seed())
    command.upgrade(config, "head")

    async def _state() -> dict[str, object]:
        async with session_factory() as s:
            job_status = await s.scalar(
                text("SELECT status FROM jobs WHERE id = :id"), {"id": job_id}
            )
            attempts = list(
                (
                    await s.execute(
                        text(
                            "SELECT status, safe_error FROM job_attempts "
                            "WHERE job_id = :id ORDER BY attempt_number"
                        ),
                        {"id": job_id},
                    )
                ).all()
            )
            run_status = await s.scalar(
                text("SELECT status FROM workflow_runs WHERE id = :id"), {"id": run_id}
            )
            crawl = (
                await s.execute(
                    text("SELECT status, stop_reason FROM seo_crawl_runs WHERE id = :id"),
                    {"id": crawl_run_id},
                )
            ).one()
            return {
                "job_status": job_status,
                "attempts": attempts,
                "run_status": run_status,
                "crawl_status": crawl[0],
                "crawl_stop_reason": crawl[1],
            }

    result = asyncio.run(_state())
    assert result["job_status"] == "dead_lettered"
    assert result["attempts"] == [("timed_out", "LEASE_EXPIRED")] * 3
    assert result["run_status"] == "failed"
    assert result["crawl_status"] == "error"
    assert result["crawl_stop_reason"] == "Orphaned crawl reconciled: no live execution job"

    command.upgrade(config, "head")
