"""Focused unit coverage for production worker execution policy."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.api.app.agents.hermes_client import HermesRuntimeError
from apps.api.app.execution.models import Job
from apps.worker.recovery import _hermes_run_missing, _job_is_active


def _job(
    status: str,
    *,
    attempt_count: int = 0,
    max_attempts: int = 3,
    lease_expires_at: datetime | None = None,
) -> Job:
    now = datetime.now(UTC)
    return Job(
        organization_id=uuid4(),
        workflow_run_id=uuid4(),
        job_type="workflow.execute",
        status=status,
        idempotency_key=f"test-{uuid4()}",
        payload={},
        available_at=now,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        timeout_seconds=300,
        lease_expires_at=lease_expires_at,
    )


def test_exhausted_retry_is_not_active_work() -> None:
    assert not _job_is_active(
        _job("retry_scheduled", attempt_count=3, max_attempts=3),
        datetime.now(UTC),
    )


def test_retry_with_attempts_remaining_is_active_work() -> None:
    assert _job_is_active(
        _job("retry_scheduled", attempt_count=2, max_attempts=3),
        datetime.now(UTC),
    )


def test_expired_claim_is_not_active_work() -> None:
    now = datetime.now(UTC)
    assert not _job_is_active(
        _job("claimed", attempt_count=1, lease_expires_at=now - timedelta(seconds=1)),
        now,
    )


def test_live_claim_is_active_work() -> None:
    now = datetime.now(UTC)
    assert _job_is_active(
        _job("claimed", attempt_count=1, lease_expires_at=now + timedelta(seconds=30)),
        now,
    )


def test_purged_hermes_run_is_safe_to_release() -> None:
    error = HermesRuntimeError("HERMES_HTTP_ERROR", "Hermes request failed with 404")
    assert _hermes_run_missing(error)


def test_other_hermes_http_errors_do_not_release_session() -> None:
    error = HermesRuntimeError("HERMES_HTTP_ERROR", "Hermes request failed with 500")
    assert not _hermes_run_missing(error)
