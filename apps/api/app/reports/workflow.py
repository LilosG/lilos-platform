"""The monthly report job: a draft for the month that just ended, for one organization.

Scheduled by ``scripts/ensure_client_schedules.py`` at 8:00 AM Pacific on the 1st. Deterministic:
it reads stored data and writes one draft revision, nothing else. If Google's data lag leaves the
month partial, the draft says so with a note code and a person can regenerate before approving.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.reports.errors import ReportAlreadyApprovedError
from apps.api.app.reports.reads import organization_is_reportable
from apps.api.app.reports.service import ReportService
from apps.api.app.reports.snapshot import last_ended_month

logger = logging.getLogger(__name__)
GENERATION_FAILED = "REPORT_GENERATION_FAILED"


def utc_now() -> datetime:
    return datetime.now(UTC)


def scheduled_moment(input_document: dict[str, Any], fallback: datetime) -> datetime:
    """When the schedule fired: the month to report is the one before that moment."""
    raw = input_document.get("scheduled_for")
    try:
        moment = datetime.fromisoformat(str(raw)) if raw else fallback
    except ValueError:
        return fallback
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def handle_monthly_report_generation(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """`reports.generate_monthly`: write the draft for the month that ended before the run."""
    del location_id, workflow_run_id
    # An archived, removed or paused client, or one whose locations no longer run a profile,
    # has nothing to report. The run still completes: there is nothing to retry.
    if not await organization_is_reportable(session, organization_id):
        return JobOutcome(result="succeeded", result_reference="report-skipped:not-reportable")
    now = utc_now()
    month = last_ended_month(scheduled_moment(input_document, now))
    try:
        stored, created = await ReportService().generate(
            session,
            organization_id,
            month,
            actor_id=None,
            correlation_id=correlation_id,
            now=now,
        )
    except ReportAlreadyApprovedError:
        # Someone already approved this exact data; a second draft would say nothing new.
        return JobOutcome(result="succeeded", result_reference=f"report-unchanged:{month}")
    except Exception:
        await session.rollback()
        logger.exception(
            "Monthly report generation failed",
            extra={"event_name": "reports.generate.failed", "month": str(month)},
        )
        return JobOutcome(result="retryable_failure", safe_error=GENERATION_FAILED)
    await session.flush()
    return JobOutcome(
        result="succeeded",
        result_reference=(
            f"report:{month}:{stored.revision.revision}:{'created' if created else 'existing'}"
        ),
    )
