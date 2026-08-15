"""Reconcile orphaned jobs, attempts, and crawl runs to truthful terminal state.

Packet 9B: before ``claim()`` enforced ``attempt_count < max_attempts``, a job
that failed inside ``claim()`` (a deterministic database error) could be
re-claimed forever. Each reclaim left a ``job_attempts`` row ``running`` while
the job cycled to ``max_attempts``, at which point ``claim()`` attempted to
increment ``attempt_count`` past ``max_attempts`` and poisoned the worker poll
loop. The downstream ``seo_crawl_runs`` rows (and their workflow runs) were
left ``queued`` with ``started_at`` NULL and no live job.

The runtime now self-heals (see ``ExecutionService.claim`` and
``ExecutionService.sweep_abandoned_leases``). This migration performs the
one-time repair of the rows already poisoned:

1. Close ``running`` attempts for jobs whose lease expired with no live owner.
2. Requeue jobs that still have attempts remaining, and dead-letter jobs at or
   past ``max_attempts``.
3. Mark orphaned crawl runs (``queued``, never started, no live job) as
   ``error``.
4. Mark workflow runs whose job is dead-lettered as ``failed`` so they no
   longer report a false ``queued`` state.

Every statement is idempotent and only touches rows matching the orphaned
condition, so re-running is a no-op once the repair has been applied.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0001"
down_revision: str | Sequence[str] | None = "20260813_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE job_attempts AS a
            SET status = 'timed_out',
                completed_at = CURRENT_TIMESTAMP,
                error_category = 'lease_expired',
                safe_error = 'LEASE_EXPIRED'
            FROM jobs AS j
            WHERE a.job_id = j.id
              AND a.status = 'running'
              AND j.status = 'claimed'
              AND j.lease_expires_at IS NOT NULL
              AND j.lease_expires_at < CURRENT_TIMESTAMP
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE jobs
            SET status = CASE
                    WHEN attempt_count >= max_attempts THEN 'dead_lettered'
                    ELSE 'retry_scheduled'
                END,
                available_at = CURRENT_TIMESTAMP,
                lease_owner = NULL,
                lease_expires_at = NULL
            WHERE status = 'claimed'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at < CURRENT_TIMESTAMP
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE seo_crawl_runs AS cr
            SET status = 'error',
                stop_reason = 'Orphaned crawl reconciled: no live execution job',
                completed_at = CURRENT_TIMESTAMP
            WHERE cr.status = 'queued'
              AND cr.started_at IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM jobs AS j
                  WHERE j.workflow_run_id = cr.workflow_run_id
                    AND j.status IN (
                        'queued', 'claimed', 'running', 'retry_scheduled', 'waiting_approval'
                    )
              )
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE workflow_runs AS wr
            SET status = 'failed',
                failure_code = 'JOB_DEAD_LETTERED',
                completed_at = CURRENT_TIMESTAMP
            FROM jobs AS j
            WHERE j.workflow_run_id = wr.id
              AND j.status = 'dead_lettered'
              AND wr.status IN ('created', 'queued')
            """
        )
    )


def downgrade() -> None:
    """Data repair has no meaningful reverse; nothing to do."""
