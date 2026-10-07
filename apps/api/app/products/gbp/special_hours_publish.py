"""Publish approved special hours to Google, exactly as approved.

Google replaces the whole ``specialHours`` list on every patch. A publication therefore never
sends one date: it sends every approved, not-yet-past date of the location (the latest approved
revision per date), merged with the future dates Google already holds that LILOs does not manage.
Sending a partial list would delete the other dates.

The write is idempotent by content, so any re-entry (a retry, or a person pressing "Try again")
reads Google first, writes only when it differs from what was approved, and then re-reads to
verify. Outcomes are typed: ``verified``, ``failed`` (Google was not changed) and
``reconciliation_required`` (Google may have changed and is not yet confirmed).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.integrations.errors import (
    IntegrationNotFoundError,
    IntegrationReconnectRequiredError,
)
from apps.api.app.integrations.secrets import SecretUnavailableError
from apps.api.app.locations.models import Location
from apps.api.app.products.gbp.adapter import SPECIAL_HOURS_FIELD, GBPAdapter
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.operations import special_hour_periods
from apps.api.app.products.gbp.operations_models import (
    GBPSpecialHours,
    GBPSpecialHoursPublication,
)
from apps.api.app.products.gbp.provider_write_outcome import (
    classify_provider_write_failure,
    provider_error_log_fields,
)
from apps.api.app.products.gbp.resource_names import v1_location_name
from apps.api.app.products.gbp.service import GBPService

logger = logging.getLogger(__name__)

# A date that was approved and has not been superseded or rejected. Its content belongs on Google.
APPROVED_STATUSES = ("approved", "publishing", "published", "failed", "reconciliation_required")
# Not yet confirmed on Google by any publication.
PENDING_STATUSES = ("approved", "publishing")
# Another write for the same location that started this recently is still in flight.
IN_FLIGHT_WINDOW_SECONDS = 600

PROVIDER_WRITES_DISABLED = "PROVIDER_WRITES_DISABLED"
SERVICE_DATE_PASSED = "SERVICE_DATE_PASSED"
NOTHING_TO_PUBLISH = "NOTHING_TO_PUBLISH"
PROVIDER_READ_FAILED = "PROVIDER_READ_FAILED"
VERIFICATION_REREAD_FAILED = "VERIFICATION_REREAD_FAILED"
VERIFICATION_CONTENT_MISMATCH = "VERIFICATION_CONTENT_MISMATCH"
PUBLISH_IN_PROGRESS = "SPECIAL_HOURS_PUBLISH_IN_PROGRESS"

AdapterFactory = Callable[[], GBPAdapter]
TokenResolver = Callable[[AsyncSession, UUID], Any]
ProviderWriteGate = Callable[[], bool]

# Canonical form of one Google entry: (start, end, closed, opens, closes). Google omits zero
# fields of a time of day and a false ``closed``, so everything is normalized before comparing.
EntryKey = tuple[
    tuple[int, int, int], tuple[int, int, int], bool, tuple[int, int] | None, tuple[int, int] | None
]


def _date_parts(raw: object) -> tuple[int, int, int] | None:
    if not isinstance(raw, dict):
        return None
    try:
        return (int(raw["year"]), int(raw["month"]), int(raw["day"]))
    except (KeyError, TypeError, ValueError):
        return None


def _time_parts(raw: object) -> tuple[int, int]:
    if not isinstance(raw, dict):
        return (0, 0)
    try:
        return (int(raw.get("hours", 0) or 0), int(raw.get("minutes", 0) or 0))
    except (TypeError, ValueError):
        return (0, 0)


def entry_key(entry: object) -> EntryKey | None:
    """The canonical identity of one ``specialHourPeriods`` entry, or None if it is malformed."""
    if not isinstance(entry, dict):
        return None
    start = _date_parts(entry.get("startDate"))
    if start is None:
        return None
    end = _date_parts(entry.get("endDate")) or start
    if entry.get("closed") is True:
        return (start, end, True, None, None)
    return (
        start,
        end,
        False,
        _time_parts(entry.get("openTime")),
        _time_parts(entry.get("closeTime")),
    )


def entries_of(raw_location: dict[str, Any]) -> list[dict[str, Any]]:
    """The special-hours entries of a Google location, as a list (empty when it has none)."""
    special = raw_location.get(SPECIAL_HOURS_FIELD)
    entries = special.get("specialHourPeriods") if isinstance(special, dict) else None
    return [entry for entry in entries or [] if isinstance(entry, dict)]


def _is_future(entry: dict[str, Any], today: date) -> bool:
    start = _date_parts(entry.get("startDate"))
    return start is not None and date(*start) >= today


def merge_special_hours(
    google_entries: list[dict[str, Any]], approved_entries: list[dict[str, Any]], today: date
) -> list[dict[str, Any]]:
    """The full list to send: approved dates, plus future Google dates LILOs does not manage."""
    managed = {key[0] for entry in approved_entries if (key := entry_key(entry)) is not None}
    kept = [
        entry
        for entry in google_entries
        if _is_future(entry, today)
        and (key := entry_key(entry)) is not None
        and key[0] not in managed
    ]
    merged = [*kept, *approved_entries]
    return sorted(merged, key=lambda entry: repr(entry_key(entry)))


def same_special_hours(
    expected: list[dict[str, Any]], observed: list[dict[str, Any]], today: date
) -> bool:
    """Whether Google holds exactly the expected future dates. Past dates never matter."""
    return {entry_key(entry) for entry in expected if _is_future(entry, today)} == {
        entry_key(entry) for entry in observed if _is_future(entry, today)
    }


def entries_for_row(row: GBPSpecialHours) -> list[dict[str, object]]:
    """Google's entries for one approved date, built by the canonical builder."""
    periods = [
        (time.fromisoformat(str(p["opens"])), time.fromisoformat(str(p["closes"])))
        for p in row.periods
        if isinstance(p, dict)
    ]
    return special_hour_periods(row.service_date, periods, closed=row.closed)


def latest_approved_per_date(rows: list[GBPSpecialHours]) -> list[GBPSpecialHours]:
    """The latest approved revision of each date; a later rejected one never hides it."""
    latest: dict[date, GBPSpecialHours] = {}
    for row in rows:
        if row.status in APPROVED_STATUSES and (
            row.service_date not in latest or row.revision > latest[row.service_date].revision
        ):
            latest[row.service_date] = row
    return sorted(latest.values(), key=lambda row: row.service_date)


def _today(timezone: str) -> date:
    try:
        return datetime.now(ZoneInfo(timezone)).date()
    except ZoneInfoNotFoundError:
        return datetime.now(UTC).date()


async def _audit(
    session: AsyncSession,
    publication: GBPSpecialHoursPublication,
    *,
    event: str,
    result: AuditResult,
    summary: str,
    code: str | None = None,
) -> None:
    await AuditEventService().record(
        session,
        AuditEventCreate(
            event_type=event,
            action=event,
            result=result,
            actor_type=AuditActorType.WORKFLOW,
            organization_id=publication.organization_id,
            product_key="gbp",
            resource_type="gbp_special_hours_publication",
            resource_id=publication.id,
            correlation_id=f"gbp.special_hours.publish:{publication.id}",
            summary=summary,
            metadata={"code": code} if code else {},
        ),
    )


async def _settle(
    session: AsyncSession,
    publication: GBPSpecialHoursPublication,
    included: list[UUID],
    *,
    status: str,
    code: str | None,
    row_status: str | None,
    only_pending: bool,
    verified: bool = False,
) -> None:
    """Record one outcome on the publication and on the dates it was responsible for."""
    publication.status = status
    publication.safe_error_code = code
    if verified:
        publication.verified_at = datetime.now(UTC)
    if row_status is not None:
        statement = (
            update(GBPSpecialHours)
            .where(
                GBPSpecialHours.organization_id == publication.organization_id,
                GBPSpecialHours.id.in_(included),
            )
            .values(
                status=row_status,
                safe_error_code=code,
                publication_id=publication.id,
                verified_at=datetime.now(UTC) if verified else None,
            )
        )
        if only_pending:
            statement = statement.where(GBPSpecialHours.status.in_(PENDING_STATUSES))
        await session.execute(statement)
    event_result = AuditResult.SUCCEEDED if status == "verified" else AuditResult.FAILED
    await _audit(
        session,
        publication,
        event=f"gbp.special_hours.publication_{status}",
        result=event_result,
        summary=f"Special hours publication {status.replace('_', ' ')}.",
        code=code,
    )
    await session.commit()


async def handle_gbp_publish_special_hours(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
    adapter_factory: AdapterFactory,
    token_resolver: TokenResolver,
    provider_writes_enabled: ProviderWriteGate,
) -> JobOutcome:
    """Send the location's full approved special-hours list to Google and verify it."""
    publication_id_raw = input_document.get("publication_id")
    if not publication_id_raw:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_PUBLICATION_ID")
    try:
        publication_id = UUID(str(publication_id_raw))
    except (TypeError, ValueError):
        return JobOutcome(result="permanent_failure", safe_error="INVALID_PUBLICATION_ID")

    publication = await session.scalar(
        select(GBPSpecialHoursPublication)
        .where(
            GBPSpecialHoursPublication.organization_id == organization_id,
            GBPSpecialHoursPublication.id == publication_id,
        )
        .with_for_update()
    )
    if publication is None:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_FOUND")
    if publication.workflow_run_id != workflow_run_id:
        return JobOutcome(result="permanent_failure", safe_error="WORKFLOW_SCOPE_MISMATCH")
    if publication.status == "verified":
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    if publication.status not in ("reserved", "dispatched", "reconciliation_required"):
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_RESERVABLE")

    resuming = publication.status != "reserved"
    gbp_location = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.id == publication.gbp_location_id,
        )
    )
    code: str | None = None
    if gbp_location is None:
        code = "GBP_LOCATION_NOT_FOUND"
    elif location_id is not None and gbp_location.location_id != location_id:
        code = "GBP_LOCATION_SCOPE_MISMATCH"
    elif not gbp_location.write_enabled or gbp_location.mapping_status != "confirmed":
        code = "WRITE_NOT_ENABLED"
    elif not resuming and not provider_writes_enabled():
        code = PROVIDER_WRITES_DISABLED
    account = (
        await session.get(GBPAccount, gbp_location.account_id) if gbp_location is not None else None
    )
    if code is None and (account is None or account.organization_id != organization_id):
        code = "ACCOUNT_NOT_FOUND"
    if code is not None or gbp_location is None or account is None:
        await _settle(
            session,
            publication,
            await _pending_ids(session, publication),
            status="failed",
            code=code,
            row_status="failed",
            only_pending=True,
        )
        return JobOutcome(result="permanent_failure", safe_error=code)

    # Another publish for this location that is mid-flight would race this read-modify-write.
    in_flight = await session.scalar(
        select(GBPSpecialHoursPublication.id)
        .where(
            GBPSpecialHoursPublication.organization_id == organization_id,
            GBPSpecialHoursPublication.gbp_location_id == gbp_location.id,
            GBPSpecialHoursPublication.id != publication.id,
            GBPSpecialHoursPublication.status == "dispatched",
            GBPSpecialHoursPublication.dispatched_at
            > datetime.now(UTC) - timedelta(seconds=IN_FLIGHT_WINDOW_SECONDS),
        )
        .limit(1)
    )
    if in_flight is not None:
        await session.rollback()
        return JobOutcome(result="retryable_failure", safe_error=PUBLISH_IN_PROGRESS)

    location = await session.get(Location, gbp_location.location_id)
    today = _today(location.timezone if location is not None else "UTC")
    rows = list(
        await session.scalars(
            select(GBPSpecialHours).where(
                GBPSpecialHours.organization_id == organization_id,
                GBPSpecialHours.gbp_location_id == gbp_location.id,
            )
        )
    )
    latest = latest_approved_per_date(rows)
    passed = [
        row.id for row in latest if row.service_date < today and row.status in PENDING_STATUSES
    ]
    if passed:
        await session.execute(
            update(GBPSpecialHours)
            .where(
                GBPSpecialHours.organization_id == organization_id, GBPSpecialHours.id.in_(passed)
            )
            .values(
                status="failed", safe_error_code=SERVICE_DATE_PASSED, publication_id=publication.id
            )
        )
    included_rows = [row for row in latest if row.service_date >= today]
    included = [row.id for row in included_rows]
    approved_entries = [entry for row in included_rows for entry in entries_for_row(row)]
    if not included:
        await _settle(
            session,
            publication,
            [],
            status="failed",
            code=NOTHING_TO_PUBLISH,
            row_status=None,
            only_pending=True,
        )
        return JobOutcome(result="permanent_failure", safe_error=NOTHING_TO_PUBLISH)

    location_name = v1_location_name(gbp_location.external_location_id)
    gbp_location_pk = gbp_location.id
    idempotency_key = publication.idempotency_key
    # Release every lock before OAuth and Google I/O.
    await session.commit()

    try:
        token, _connection = await token_resolver(session, organization_id)
    except (IntegrationNotFoundError, IntegrationReconnectRequiredError, SecretUnavailableError):
        token_code = "NO_CONNECTED_INTEGRATION"
        await _fail_before_write(session, publication_id, included, token_code)
        return JobOutcome(result="permanent_failure", safe_error=token_code)
    except Exception as exc:
        logger.warning(
            "Special hours token resolution failed", extra=provider_error_log_fields(exc)
        )
        await _fail_before_write(session, publication_id, included, "TOKEN_RESOLUTION_FAILED")
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_RESOLUTION_FAILED")
    await session.commit()
    adapter = adapter_factory()

    try:
        current = await adapter.get_location(token, location_name)
    except Exception as exc:
        logger.warning("Special hours read failed", extra=provider_error_log_fields(exc))
        if resuming:
            await _mark(
                session, publication_id, included, "reconciliation_required", PROVIDER_READ_FAILED
            )
            return JobOutcome(result="retryable_failure", safe_error=PROVIDER_READ_FAILED)
        await _fail_before_write(session, publication_id, included, PROVIDER_READ_FAILED)
        return JobOutcome(result="permanent_failure", safe_error=PROVIDER_READ_FAILED)

    desired = merge_special_hours(entries_of(current), approved_entries, today)
    if not same_special_hours(desired, entries_of(current), today):
        if not provider_writes_enabled():
            await _mark(session, publication_id, included, "failed", PROVIDER_WRITES_DISABLED)
            return JobOutcome(result="permanent_failure", safe_error=PROVIDER_WRITES_DISABLED)
        publication = await _lock(session, organization_id, publication_id)
        publication.status = "dispatched"
        publication.dispatched_at = datetime.now(UTC)
        publication.sent_periods = list(desired)
        publication.safe_error_code = None
        await session.execute(
            update(GBPSpecialHours)
            .where(
                GBPSpecialHours.organization_id == organization_id,
                GBPSpecialHours.id.in_(included),
                GBPSpecialHours.status == "approved",
            )
            .values(status="publishing", publication_id=publication_id)
        )
        await session.commit()
        try:
            await adapter.patch_location(
                token,
                location_name,
                {SPECIAL_HOURS_FIELD: {"specialHourPeriods": desired}},
                [SPECIAL_HOURS_FIELD],
                idempotency_key,
            )
        except Exception as exc:
            outcome = classify_provider_write_failure(exc)
            logger.warning(
                "Special hours publish failed",
                extra={
                    "event_name": "gbp.special_hours.publish_failed",
                    "publication_id": str(publication_id),
                    "provider_write_applied": outcome.applied,
                    "safe_error_code": outcome.safe_error_code,
                    **provider_error_log_fields(exc),
                },
            )
            if outcome.requires_reconciliation:
                await _mark(
                    session,
                    publication_id,
                    included,
                    "reconciliation_required",
                    outcome.safe_error_code,
                )
            else:
                await _mark(session, publication_id, included, "failed", outcome.safe_error_code)
            return JobOutcome(result=outcome.job_result, safe_error=outcome.safe_error_code)

        try:
            current = await adapter.get_location(token, location_name)
        except Exception as exc:
            logger.warning(
                "Special hours verification read failed", extra=provider_error_log_fields(exc)
            )
            await _mark(
                session,
                publication_id,
                included,
                "reconciliation_required",
                VERIFICATION_REREAD_FAILED,
            )
            return JobOutcome(result="retryable_failure", safe_error=VERIFICATION_REREAD_FAILED)

    verified = same_special_hours(desired, entries_of(current), today)
    gbp_location = await session.get(GBPLocation, gbp_location_pk)
    if gbp_location is not None and gbp_location.organization_id == organization_id:
        await GBPService().store_snapshot(session, gbp_location, current, partial=False)
    if not verified:
        await _mark(
            session,
            publication_id,
            included,
            "reconciliation_required",
            VERIFICATION_CONTENT_MISMATCH,
        )
        return JobOutcome(result="retryable_failure", safe_error=VERIFICATION_CONTENT_MISMATCH)
    publication = await _lock(session, organization_id, publication_id)
    publication.sent_periods = publication.sent_periods or list(desired)
    await _settle(
        session,
        publication,
        included,
        status="verified",
        code=None,
        row_status="published",
        only_pending=False,
        verified=True,
    )
    return JobOutcome(result="succeeded", result_reference=f"publication:{publication_id}")


async def _lock(
    session: AsyncSession, organization_id: UUID, publication_id: UUID
) -> GBPSpecialHoursPublication:
    publication = await session.scalar(
        select(GBPSpecialHoursPublication)
        .where(
            GBPSpecialHoursPublication.organization_id == organization_id,
            GBPSpecialHoursPublication.id == publication_id,
        )
        .with_for_update()
    )
    if publication is None:  # pragma: no cover - the row was locked earlier in this run
        raise LookupError("special hours publication vanished mid-run")
    return publication


async def _pending_ids(
    session: AsyncSession, publication: GBPSpecialHoursPublication
) -> list[UUID]:
    return list(
        await session.scalars(
            select(GBPSpecialHours.id).where(
                GBPSpecialHours.organization_id == publication.organization_id,
                GBPSpecialHours.gbp_location_id == publication.gbp_location_id,
                GBPSpecialHours.status.in_(PENDING_STATUSES),
            )
        )
    )


async def _fail_before_write(
    session: AsyncSession, publication_id: UUID, included: list[UUID], code: str
) -> None:
    """Nothing was sent: only the dates waiting on this publish fail; live dates stay live."""
    await _mark(session, publication_id, included, "failed", code)


async def _mark(
    session: AsyncSession,
    publication_id: UUID,
    included: list[UUID],
    status: str,
    code: str,
) -> None:
    publication = await session.get(GBPSpecialHoursPublication, publication_id)
    if publication is None:
        return
    # A failure that changed nothing on Google must not downgrade dates that are already live;
    # an unconfirmed write puts every date in the list into doubt.
    await _settle(
        session,
        publication,
        included,
        status=status,
        code=code,
        row_status=status,
        only_pending=status == "failed",
    )
