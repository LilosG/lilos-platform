"""Permanent removal of an archived organization's data.

``OrganizationRemovalService`` backs the ``organization.remove`` worker workflow. It is
resumable and idempotent: every phase can be run again after a crash and picks up what is
left, and deleted-row counts are kept on the workflow run so the final audit event reports
the whole removal, not just the last attempt.

What is deleted is derived from the SQLAlchemy metadata, never from a hand-written list, so a
table added later is purged by default. ``purge_plan`` selects every table that has an
``organization_id`` column plus every table that references one of those through a foreign
key, and orders them children first (the reverse of ``metadata.sorted_tables``); many of the
foreign keys are ``ON DELETE RESTRICT``, which is why the order matters.

Only ``audit_events`` (append-only) and the ``organizations`` row survive. Two consequences
of that are handled explicitly:

* a ``locations`` row that an audit event still points at cannot be deleted either, so it
  stays as a scrubbed tombstone (its slug is immutable by trigger and is kept);
* the removal's own workflow run and job stay until the worker has finished them.

Governed history (approved revisions, entitlements, recommendations) is protected by BEFORE
DELETE triggers. They let a delete through only when the database itself finds the row's
organization archived with a removal requested and not yet finished
(``lilos_organization_removal_in_progress``, see the ``20261006_0001`` migration); nothing this
module sets on a session can open them. If a trigger still refuses, the removal fails with
``ORGANIZATION_REMOVAL_BLOCKED_BY_PROTECTED_HISTORY`` and the failure is shown to the operator.

Nothing here calls Google, GitHub or Vercel. Provider accounts, the client's website and its
repository are never touched.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    MetaData,
    Table,
    and_,
    delete,
    exists,
    func,
    literal,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.engine import CursorResult, Result
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.database.base import Base
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.models import Job, Schedule, WorkflowRun
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.integrations.secrets import ProviderSecret
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.repository import OrganizationRepository
from apps.api.app.storage.objects import (
    GBP_MEDIA_BUCKET,
    ObjectStorage,
    StorageNotConfiguredError,
    object_storage,
)

logger = logging.getLogger(__name__)

REMOVAL_REQUESTED_EVENT = "organization.removal_requested"
REMOVED_EVENT = "organization.removed"

# The only tables that outlive a removal. ``audit_events`` is append-only; ``organizations`` is
# kept as the tombstone every audit event's foreign key points at.
RETAINED_TABLES = frozenset({"audit_events", "organizations"})
BATCH_SIZE = 5_000
# Largest number of table counts one audit metadata object may carry (the audit policy allows
# 50 entries per object); the removed-event spreads the per-table counts over several.
AUDIT_COUNTS_PER_PART = 40

# Buckets keyed ``{organization_id}/...``. Rows that record their own bucket and path (any table
# with ``storage_bucket`` and ``storage_path`` columns) are removed as well.
ORGANIZATION_STORAGE_BUCKETS = (GBP_MEDIA_BUCKET,)

ACTIVE_RUN_STATUSES = (
    "created",
    "queued",
    "running",
    "waiting",
    "waiting_approval",
    "retry_scheduled",
)
ACTIVE_JOB_STATUSES = ("queued", "claimed", "running", "retry_scheduled", "waiting_approval")

# Work that is waiting for a person's approval or a provider write, mapped to the state that
# retires it: (table, statuses that are still pending, status that ends them). Nothing waits to
# be applied to Google or a client site once the matching jobs are cancelled, but an approval
# that stayed open could still be clicked while the data is being deleted.
PENDING_APPROVALS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("gbp_profile_change_revisions", ("awaiting_approval",), "rejected"),
    ("gbp_profile_change_revisions", ("approved",), "superseded"),
    ("review_response_revisions", ("awaiting_approval",), "rejected"),
    ("review_response_revisions", ("approved",), "superseded"),
    ("content_revisions", ("awaiting_editorial", "awaiting_client"), "rejected"),
    ("seo_recommendation_revisions", ("awaiting_approval", "approved"), "withdrawn"),
    ("gbp_post_publications", ("reserved", "scheduled"), "cancelled"),
    ("gbp_publications", ("reserved", "queued"), "cancelled"),
)


def _rows(result: Result[Any]) -> int:
    """Rows a DELETE or UPDATE touched."""
    return cast(CursorResult[Any], result).rowcount or 0


class RemovalCode:
    """Safe, typed outcome codes the removal workflow reports."""

    NOT_REQUESTED = "ORGANIZATION_REMOVAL_NOT_REQUESTED"
    NOT_ARCHIVED = "ORGANIZATION_REMOVAL_NOT_ARCHIVED"
    WAITING_FOR_ACTIVE_JOBS = "ORGANIZATION_REMOVAL_WAITING_FOR_ACTIVE_JOBS"
    STORAGE_UNAVAILABLE = "ORGANIZATION_REMOVAL_STORAGE_UNAVAILABLE"
    BLOCKED = "ORGANIZATION_REMOVAL_BLOCKED"
    # A governed-history trigger still refused a delete the database guard should have allowed.
    PROTECTED_HISTORY = "ORGANIZATION_REMOVAL_BLOCKED_BY_PROTECTED_HISTORY"
    STALLED = "ORGANIZATION_REMOVAL_STALLED"
    SCHEMA_INCOMPLETE = "ORGANIZATION_REMOVAL_SCHEMA_INCOMPLETE"


class RemovalBlockedError(Exception):
    """A table could not be emptied; carries only the table name, never client data."""

    def __init__(self, code: str, table: str) -> None:
        super().__init__(f"{code}: {table}")
        self.code = code
        self.table = table


def purge_plan(metadata: MetaData = Base.metadata) -> list[Table]:
    """Every table a removal must empty, children before parents.

    That is each table with an ``organization_id`` column plus, transitively, each table that
    references one of those through a foreign key, minus ``RETAINED_TABLES``.
    """
    plan: set[Table] = {
        table
        for table in metadata.tables.values()
        if "organization_id" in table.c and table.name not in RETAINED_TABLES
    }
    grew = True
    while grew:
        grew = False
        for table in metadata.tables.values():
            if table in plan or table.name in RETAINED_TABLES:
                continue
            if any(
                fk.referred_table in plan and fk.referred_table is not table
                for fk in table.foreign_key_constraints
            ):
                plan.add(table)
                grew = True
    return [table for table in reversed(metadata.sorted_tables) if table in plan]


def _scope(table: Table, organization_id: UUID, plan: set[Table]) -> ColumnElement[bool]:
    """Rows of ``table`` that belong to the organization, following foreign keys if needed."""
    if "organization_id" in table.c:
        return table.c.organization_id == organization_id
    for constraint in table.foreign_key_constraints:
        parent = constraint.referred_table
        if parent in plan and parent is not table:
            local = [element.parent for element in constraint.elements]
            remote = [element.column for element in constraint.elements]
            owned = select(*remote).where(_scope(parent, organization_id, plan))
            if len(local) == 1:
                return local[0].in_(owned)
            return tuple_(*local).in_(owned)
    raise RuntimeError(f"table {table.name} has no path to an organization")


def _leaf_only(table: Table) -> list[ColumnElement[bool]]:
    """Rows nothing else in the same table still points at (tree leaves), for self references."""
    conditions: list[ColumnElement[bool]] = []
    for constraint in table.foreign_key_constraints:
        if constraint.referred_table is not table:
            continue
        child = table.alias()
        match = and_(
            *(
                child.c[element.parent.name] == table.c[element.column.name]
                for element in constraint.elements
            )
        )
        conditions.append(~exists(select(literal(1)).select_from(child).where(match)))
    return conditions


def _kept(table: Table, run_id: UUID) -> list[ColumnElement[bool]]:
    """Rows that must outlive the purge: the executing removal run and its own job."""
    if table.name == "workflow_runs":
        return [table.c.id != run_id]
    if table.name in {"jobs", "workflow_steps"}:
        return [table.c.workflow_run_id != run_id]
    if table.name == "job_attempts":
        own_jobs = select(Job.id).where(Job.workflow_run_id == run_id)
        return [table.c.job_id.notin_(own_jobs)]
    if table.name == "locations":
        audit = Base.metadata.tables["audit_events"]
        return [
            ~exists(select(literal(1)).select_from(audit).where(audit.c.location_id == table.c.id))
        ]
    return []


@dataclass(slots=True)
class RemovalProgress:
    """Counts accumulated across every attempt of one removal."""

    deleted_rows: Counter[str] = field(default_factory=Counter)
    storage_objects: int = 0
    secrets: int = 0
    locations_tombstoned: int = 0

    @classmethod
    def from_document(cls, document: object) -> RemovalProgress:
        progress = cls()
        if isinstance(document, dict):
            rows = document.get("deleted_rows")
            if isinstance(rows, dict):
                progress.deleted_rows.update({str(k): int(v) for k, v in rows.items()})
            progress.storage_objects = int(document.get("storage_objects", 0))
            progress.secrets = int(document.get("secrets", 0))
            progress.locations_tombstoned = int(document.get("locations_tombstoned", 0))
        return progress

    def to_document(self) -> dict[str, Any]:
        return {
            "deleted_rows": dict(self.deleted_rows),
            "storage_objects": self.storage_objects,
            "secrets": self.secrets,
            "locations_tombstoned": self.locations_tombstoned,
        }


def _production_object_storage() -> ObjectStorage:
    return object_storage(Settings())


@dataclass(slots=True)
class OrganizationRemovalService:
    """Run, and re-run, the permanent removal of one archived organization."""

    batch_size: int = BATCH_SIZE
    # Tests replace this to avoid the network; production builds the Supabase client.
    storage_factory: Callable[[], ObjectStorage] = _production_object_storage
    organizations: OrganizationRepository = field(default_factory=OrganizationRepository)
    audit: AuditEventService = field(default_factory=AuditEventService)

    async def run(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        workflow_run_id: UUID,
        input_document: dict[str, Any],
        correlation_id: str,
    ) -> JobOutcome:
        """Execute every phase in order, committing as it goes."""
        organization = await session.get(Organization, organization_id)
        if organization is None:
            return JobOutcome(result="succeeded", result_reference="organization-removal:absent")
        if organization.removed_at is not None:
            return JobOutcome(result="succeeded", result_reference="organization-removal:done")
        if organization.status is not OrganizationStatus.ARCHIVED:
            return JobOutcome(result="permanent_failure", safe_error=RemovalCode.NOT_ARCHIVED)
        if not await self._was_requested(session, organization_id, input_document):
            return JobOutcome(result="permanent_failure", safe_error=RemovalCode.NOT_REQUESTED)

        progress = await self._load_progress(session, workflow_run_id)
        try:
            if await self._stop_activity(session, organization_id, workflow_run_id, progress):
                return JobOutcome(
                    result="retryable_failure", safe_error=RemovalCode.WAITING_FOR_ACTIVE_JOBS
                )
            await self._delete_provider_secrets(session, organization_id, workflow_run_id, progress)
            if not await self._delete_storage(session, organization_id, workflow_run_id, progress):
                return JobOutcome(
                    result="retryable_failure", safe_error=RemovalCode.STORAGE_UNAVAILABLE
                )
            await self._assert_schema_complete(session)
            await self._purge(session, organization_id, workflow_run_id, progress)
            await self._finish(session, organization, workflow_run_id, correlation_id, progress)
        except RemovalBlockedError as error:
            await session.rollback()
            logger.error(
                "Organization removal stopped",
                extra={
                    "event_name": "organization.removal.blocked",
                    "organization_id": str(organization_id),
                    "workflow_run_id": str(workflow_run_id),
                    "error_code": error.code,
                    "table": error.table,
                },
            )
            return JobOutcome(result="permanent_failure", safe_error=error.code)
        return JobOutcome(
            result="succeeded", result_reference=f"organization-removal:{organization_id}"
        )

    # -- guards -----------------------------------------------------------------------------

    async def _was_requested(
        self, session: AsyncSession, organization_id: UUID, input_document: dict[str, Any]
    ) -> bool:
        """The run must carry the id of the audited request an administrator made."""
        raw = input_document.get("request_audit_event_id")
        try:
            event_id = UUID(str(raw))
        except ValueError:
            return False
        audit = Base.metadata.tables["audit_events"]
        found = await session.scalar(
            select(audit.c.id).where(
                audit.c.id == event_id,
                audit.c.organization_id == organization_id,
                audit.c.event_type == REMOVAL_REQUESTED_EVENT,
            )
        )
        return found is not None

    async def _assert_schema_complete(self, session: AsyncSession) -> None:
        """Fail closed if the database holds an organization-scoped table the plan lacks.

        The plan comes from the registered ORM metadata. A model module the process never
        imported would otherwise leave its table untouched and break the purge at the first
        foreign key, or worse, finish while client rows survive.
        """
        rows = await session.execute(
            text(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND column_name = 'organization_id'"
            )
        )
        known = {table.name for table in Base.metadata.tables.values()}
        unknown = sorted({str(name) for (name,) in rows} - known)
        if unknown:
            raise RemovalBlockedError(RemovalCode.SCHEMA_INCOMPLETE, unknown[0])

    # -- progress ---------------------------------------------------------------------------

    async def _load_progress(self, session: AsyncSession, workflow_run_id: UUID) -> RemovalProgress:
        document = await session.scalar(
            select(WorkflowRun.input_document).where(WorkflowRun.id == workflow_run_id)
        )
        return RemovalProgress.from_document((document or {}).get("progress"))

    async def _save_progress(
        self, session: AsyncSession, workflow_run_id: UUID, progress: RemovalProgress
    ) -> None:
        document = await session.scalar(
            select(WorkflowRun.input_document).where(WorkflowRun.id == workflow_run_id)
        )
        merged = {**(document or {}), "progress": progress.to_document()}
        await session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == workflow_run_id)
            .values(input_document=merged)
        )

    # -- a. stop everything -----------------------------------------------------------------

    async def _stop_activity(
        self,
        session: AsyncSession,
        organization_id: UUID,
        workflow_run_id: UUID,
        progress: RemovalProgress,
    ) -> bool:
        """Cancel schedules, runs, jobs and pending approvals. True while a job is still running.

        Cancelling a queued job or run is immediate. A job a worker is executing right now
        cannot be stopped from here, so the removal waits for it rather than delete rows out
        from under a provider write.
        """
        now = datetime.now(UTC)
        await session.execute(
            update(Schedule)
            .where(Schedule.organization_id == organization_id)
            .values(status="cancelled", updated_at=now)
        )
        deleted = await session.execute(
            delete(Schedule).where(Schedule.organization_id == organization_id)
        )
        progress.deleted_rows["workflow_schedules"] += _rows(deleted)

        own_run = Job.workflow_run_id == workflow_run_id
        await session.execute(
            update(Job)
            .where(
                Job.organization_id == organization_id,
                ~own_run,
                Job.status.in_(ACTIVE_JOB_STATUSES),
                ~((Job.status == "claimed") & (Job.lease_expires_at > now)),
            )
            .values(
                status="cancelled",
                cancellation_requested_at=now,
                lease_owner=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        await session.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.id != workflow_run_id,
                WorkflowRun.status.in_(ACTIVE_RUN_STATUSES),
            )
            .values(status="cancelled", cancelled_at=now, updated_at=now)
        )
        for table_name, pending, retired in PENDING_APPROVALS:
            table = Base.metadata.tables[table_name]
            values: dict[str, object] = {"status": retired}
            if "updated_at" in table.c:
                values["updated_at"] = now
            await session.execute(
                update(table)
                .where(table.c.organization_id == organization_id, table.c.status.in_(pending))
                .values(**values)
            )
        running = await session.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.organization_id == organization_id,
                ~own_run,
                Job.status == "claimed",
                Job.lease_expires_at > now,
            )
        )
        await self._save_progress(session, workflow_run_id, progress)
        await session.commit()
        return bool(running)

    # -- c. integrations --------------------------------------------------------------------

    async def _delete_provider_secrets(
        self,
        session: AsyncSession,
        organization_id: UUID,
        workflow_run_id: UUID,
        progress: RemovalProgress,
    ) -> None:
        """Delete stored tokens, but only those no other organization's connection uses.

        The connections, resource mappings and discovered resources themselves are
        organization-owned rows and go with the purge. Nothing is revoked or called at the
        provider: the Google, GitHub and Vercel side is left exactly as it is.
        """
        references = {
            reference
            for reference in await session.scalars(
                select(IntegrationConnection.credential_reference).where(
                    IntegrationConnection.organization_id == organization_id,
                    IntegrationConnection.credential_reference.is_not(None),
                )
            )
            if reference
        }
        if references:
            shared = set(
                await session.scalars(
                    select(IntegrationConnection.credential_reference).where(
                        IntegrationConnection.organization_id != organization_id,
                        IntegrationConnection.credential_reference.in_(references),
                    )
                )
            )
            owned: list[UUID] = []
            for reference in references - shared:
                try:
                    owned.append(UUID(reference))
                except ValueError:
                    continue
            if owned:
                result = await session.execute(
                    delete(ProviderSecret).where(ProviderSecret.id.in_(owned))
                )
                progress.secrets += _rows(result)
        await self._save_progress(session, workflow_run_id, progress)
        await session.commit()

    # -- d. storage -------------------------------------------------------------------------

    async def _delete_storage(
        self,
        session: AsyncSession,
        organization_id: UUID,
        workflow_run_id: UUID,
        progress: RemovalProgress,
    ) -> bool:
        """Delete this organization's objects. False when storage is needed but unreachable.

        A missing object, prefix or bucket counts as deleted. This runs before the purge so the
        rows that name stored objects are still there to be read.
        """
        referenced: set[tuple[str, str]] = set()
        for table in Base.metadata.tables.values():
            if {"organization_id", "storage_bucket", "storage_path"} <= set(table.c.keys()):
                rows = await session.execute(
                    select(table.c.storage_bucket, table.c.storage_path).where(
                        table.c.organization_id == organization_id,
                        table.c.storage_path.is_not(None),
                    )
                )
                referenced.update((bucket, path) for bucket, path in rows if bucket and path)
        try:
            storage = self.storage_factory()
        except StorageNotConfiguredError:
            return not referenced
        try:
            for bucket in ORGANIZATION_STORAGE_BUCKETS:
                progress.storage_objects += await storage.delete_prefix(
                    bucket, str(organization_id)
                )
            for bucket, path in sorted(referenced):
                await storage.delete(bucket, path)
        except Exception:
            logger.warning(
                "Organization removal could not reach object storage",
                extra={
                    "event_name": "organization.removal.storage_unavailable",
                    "organization_id": str(organization_id),
                },
                exc_info=True,
            )
            return False
        await self._save_progress(session, workflow_run_id, progress)
        await session.commit()
        return True

    # -- b. purge ---------------------------------------------------------------------------

    async def _purge(
        self,
        session: AsyncSession,
        organization_id: UUID,
        workflow_run_id: UUID,
        progress: RemovalProgress,
    ) -> None:
        tables = purge_plan()
        plan = set(tables)
        for table in tables:
            scope = and_(_scope(table, organization_id, plan), *_kept(table, workflow_run_id))
            await self._empty_table(session, table, scope, workflow_run_id, progress)
        await self._tombstone_locations(session, organization_id, workflow_run_id, progress)

    async def _empty_table(
        self,
        session: AsyncSession,
        table: Table,
        scope: ColumnElement[bool],
        workflow_run_id: UUID,
        progress: RemovalProgress,
    ) -> None:
        keys = list(table.primary_key.columns)
        if not keys:
            raise RemovalBlockedError(RemovalCode.BLOCKED, table.name)
        batch = select(*keys).where(scope, *_leaf_only(table)).limit(self.batch_size)
        statement = delete(table).where(
            keys[0].in_(batch) if len(keys) == 1 else tuple_(*keys).in_(batch)
        )
        while True:
            try:
                result = await session.execute(statement)
            except DBAPIError as error:
                await session.rollback()
                # A trigger refusing the delete raises check_violation (23514); anything else is
                # a constraint or connection problem.
                refused = getattr(error.orig, "sqlstate", None) == "23514"
                raise RemovalBlockedError(
                    RemovalCode.PROTECTED_HISTORY if refused else RemovalCode.BLOCKED,
                    table.name,
                ) from error
            deleted = _rows(result)
            if deleted == 0:
                break
            progress.deleted_rows[table.name] += deleted
            await self._save_progress(session, workflow_run_id, progress)
            await session.commit()
        remaining = await session.scalar(select(func.count()).select_from(table).where(scope))
        if remaining:
            # A trigger that skips the delete, or a reference cycle, leaves rows behind. Report
            # it instead of looping, and never claim a removal that did not happen.
            raise RemovalBlockedError(RemovalCode.STALLED, table.name)

    async def _tombstone_locations(
        self,
        session: AsyncSession,
        organization_id: UUID,
        workflow_run_id: UUID,
        progress: RemovalProgress,
    ) -> None:
        """Scrub the locations audit events still reference; everything else was deleted."""
        locations = Base.metadata.tables["locations"]
        audit = Base.metadata.tables["audit_events"]
        referenced = exists(
            select(literal(1)).select_from(audit).where(audit.c.location_id == locations.c.id)
        )
        result = await session.execute(
            update(locations)
            .where(locations.c.organization_id == organization_id, referenced)
            .values(
                name="Removed location",
                location_type="service_area",
                status="archived",
                archived_at=func.coalesce(locations.c.archived_at, func.now()),
                timezone="UTC",
                address_line_1=None,
                address_line_2=None,
                city=None,
                region=None,
                postal_code=None,
                country_code="ZZ",
                latitude=None,
                longitude=None,
                service_area_description="Removed",
                phone=None,
                email=None,
                website_url=None,
                external_reference=None,
                is_primary=False,
                updated_at=func.now(),
            )
        )
        progress.locations_tombstoned = max(progress.locations_tombstoned, _rows(result))
        await self._save_progress(session, workflow_run_id, progress)
        await session.commit()

    # -- e. finish --------------------------------------------------------------------------

    async def _finish(
        self,
        session: AsyncSession,
        organization: Organization,
        workflow_run_id: UUID,
        correlation_id: str,
        progress: RemovalProgress,
    ) -> None:
        """Turn the organization into a tombstone and record what was deleted, in one commit."""
        removed = await self.organizations.mark_removed(session, organization.id)
        if removed is None:
            raise RemovalBlockedError(RemovalCode.NOT_ARCHIVED, "organizations")
        counts = sorted((name, count) for name, count in progress.deleted_rows.items() if count)
        parts: dict[str, JsonValue] = {
            f"part_{index + 1}": dict(counts[start : start + AUDIT_COUNTS_PER_PART])
            for index, start in enumerate(range(0, len(counts), AUDIT_COUNTS_PER_PART))
        }
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=REMOVED_EVENT,
                action="organization.remove",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.WORKFLOW,
                organization_id=organization.id,
                resource_type="organization",
                resource_id=organization.id,
                correlation_id=correlation_id[:64],
                workflow_execution_id=workflow_run_id,
                summary="Organization data permanently removed.",
                metadata={
                    "deleted_rows": parts,
                    "rows_deleted": sum(count for _, count in counts),
                    "tables_purged": len(counts),
                    "storage_objects_deleted": progress.storage_objects,
                    "provider_secrets_deleted": progress.secrets,
                    "locations_tombstoned": progress.locations_tombstoned,
                },
            ),
        )
        await session.commit()


async def handle_organization_remove(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """``organization.remove`` workflow handler."""
    del location_id
    return await OrganizationRemovalService().run(
        session,
        organization_id=organization_id,
        workflow_run_id=workflow_run_id,
        input_document=input_document,
        correlation_id=correlation_id,
    )
