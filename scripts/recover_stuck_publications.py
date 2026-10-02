"""Resolve publications stuck after an ambiguous provider outcome, through the canonical services.

Four kinds of work are stuck in production, and each already has a canonical way out. This script
finds them, asks the provider what is true, and reports the action it would take. With
`--apply` it takes exactly that action and nothing else; it never edits a row directly.

* Google Business Profile posts in `reconciliation_required` (and their `gbp.publish_post` run,
  escalated `PROVIDER_WRITE_AMBIGUOUS`): `GBPOperationsService.recover_post_publication`. It
  reads Google's Local Posts, matches the dispatched revision, and only then resumes the
  durable run; an ambiguous result stays with an operator.
* Governed site changes (`seo.apply_site_change`) in `reconciliation_required`: the pull
  request and its checks are read from GitHub, and the run is resumed through
  `ExecutionService.enqueue_recovery_run`, as Content publication recovery does. While GitHub
  still refuses the checks read (`GITHUB_APP_PERMISSION_MISSING`) nothing is resumed.
* Review replies in `reconciliation_required`: Google is read, and when it shows the approved
  reply the `reviews.publish_response` run is resumed. That run only verifies; it never sends
  `updateReply` again.

A dry run does everything except keep it: the same code runs against the same provider reads
inside a transaction that is rolled back, so what it prints is what `--apply` would do.
Only ACTIVE organizations are touched. Archived organizations and Wheyland Electric are listed
as skipped, with no provider call.

Run (Render shell):

    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.recover_stuck_publications
    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.recover_stuck_publications \\
        --apply --actor-id <your platform user id>
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.execution.service import ExecutionService
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import ContentPublication
from apps.api.app.products.content.publish_handler import (
    PullRequestUnavailableError,
    observe_publication_checks,
    observe_publication_pull_request,
)
from apps.api.app.products.gbp.models import GBPLocation
from apps.api.app.products.gbp.operations_models import GBPPostPublication, GBPPostRevision
from apps.api.app.products.gbp.operations_service import GBPOperationsService
from apps.api.app.products.reviews.models import ReviewResponseRevision
from apps.api.app.products.reviews.publish_handler import (
    ReviewReplyUnavailableError,
    observe_review_reply,
)
from scripts._cli import run_script

logger = logging.getLogger(__name__)

EXCLUDED_ORGANIZATION_NAMES = frozenset({"wheyland electric"})
EXIT_BAD_ARGUMENTS = 2
EXIT_ITEM_ERRORS = 4
NIL_ACTOR = UUID(int=0)  # a dry run records nothing, so it needs no real actor


class Kind(StrEnum):
    GBP_POST = "gbp_post_publication"
    GBP_RUN = "gbp_publish_post_run"
    SITE_CHANGE = "site_change_publication"
    REVIEW_REPLY = "review_response"


class Action(StrEnum):
    RESUME = "resume"  # a canonical recovery is (or, with --apply, was) enqueued
    WAIT = "wait"  # nothing can be done yet; the reason is the code
    OPERATOR = "operator_attention"  # the provider truth is ambiguous or terminal
    SKIPPED = "skipped"  # never touched
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Item:
    kind: Kind
    organization_id: UUID
    organization: str
    subject_id: UUID
    status: str
    provider_truth: str
    action: Action
    detail: str


@dataclass(slots=True)
class Report:
    items: list[Item]
    applied: bool


@dataclass(frozen=True, slots=True)
class Candidate:
    """One stuck thing, before the provider is asked."""

    kind: Kind
    organization: Organization
    subject_id: UUID
    status: str
    inspect: Callable[[AsyncSession], Awaitable[tuple[str, Action, str]]]


def _skipped(organization: Organization) -> str | None:
    if organization.status is not OrganizationStatus.ACTIVE:
        return f"ORGANIZATION_{organization.status.value.upper()}"
    if organization.name.strip().lower() in EXCLUDED_ORGANIZATION_NAMES:
        return "ORGANIZATION_EXCLUDED"
    return None


# --- Google Business Profile posts -------------------------------------------------------------


def _gbp_inspector(
    settings: Settings,
    organization: Organization,
    publication: GBPPostPublication,
    actor_id: UUID,
    correlation_id: str,
) -> Callable[[AsyncSession], Awaitable[tuple[str, Action, str]]]:
    async def inspect(session: AsyncSession) -> tuple[str, Action, str]:
        row = (
            await session.execute(
                select(GBPPostRevision, GBPLocation)
                .join(
                    GBPLocation,
                    (GBPLocation.organization_id == GBPPostRevision.organization_id)
                    & (GBPLocation.id == GBPPostRevision.gbp_location_id),
                )
                .where(
                    GBPPostRevision.organization_id == organization.id,
                    GBPPostRevision.id == publication.post_revision_id,
                )
            )
        ).one_or_none()
        if row is None or row[1].location_id is None:
            return (
                "GBP location is not linked to a platform location",
                Action.OPERATOR,
                "GBP_LOCATION_NOT_LINKED",
            )
        result = await GBPOperationsService().recover_post_publication(
            session,
            settings,
            organization.id,
            row[1].location_id,
            publication.id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        if result.accepted:
            truth = (
                f"provider post {result.publication.provider_post_id}"
                if result.publication.provider_post_id
                else "no provider post; the write is provably not applied"
            )
            return truth, Action.RESUME, f"recovery_mode={result.recovery_mode}"
        return (
            "Google does not show exactly one post for this revision",
            Action.OPERATOR,
            f"denial={result.denial_code}",
        )

    return inspect


# --- Governed site changes ---------------------------------------------------------------------


def _site_change_inspector(
    organization: Organization,
    publication: ContentPublication,
    actor_id: UUID,
    correlation_id: str,
) -> Callable[[AsyncSession], Awaitable[tuple[str, Action, str]]]:
    async def inspect(session: AsyncSession) -> tuple[str, Action, str]:
        try:
            pull_request = await observe_publication_pull_request(
                session, organization.id, publication
            )
            truth = f"pull request {publication.external_pull_request_id} {pull_request.state}"
            if pull_request.state == "closed":
                return truth, Action.OPERATOR, "CONTENT_PR_CLOSED"
            if pull_request.state == "open":
                checks = await observe_publication_checks(session, organization.id, publication)
                truth += f"; checks {checks.get('state')} ({checks.get('gate')})"
        except PullRequestUnavailableError as exc:
            return "pull request or checks could not be read", Action.WAIT, exc.code
        run_id = publication.workflow_run_id
        job = await ExecutionService().enqueue_recovery_run(
            session,
            organization.id,
            run_id,
            recovery_reference=f"content-publication:{publication.id}",
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        job.max_attempts = 30  # the same bound Content publication recovery uses
        return truth, Action.RESUME, f"workflow_run={run_id}"

    return inspect


# --- Review replies ----------------------------------------------------------------------------


def _review_inspector(
    organization: Organization,
    response: ReviewResponseRevision,
    actor_id: UUID,
    correlation_id: str,
) -> Callable[[AsyncSession], Awaitable[tuple[str, Action, str]]]:
    async def inspect(session: AsyncSession) -> tuple[str, Action, str]:
        try:
            observation = await observe_review_reply(session, organization.id, response)
        except ReviewReplyUnavailableError as exc:
            return "Google's reply state could not be read", Action.WAIT, exc.code
        if observation is None:
            return "Google shows no reply yet", Action.WAIT, "VERIFICATION_CONTENT_PENDING"
        if observation.comment.strip() != response.response_text.strip():
            return (
                f"Google shows a different reply ({observation.state})",
                Action.OPERATOR,
                "VERIFICATION_CONTENT_MISMATCH",
            )
        run_id = await session.scalar(
            select(WorkflowRun.id)
            .join(WorkflowVersion, WorkflowVersion.id == WorkflowRun.workflow_version_id)
            .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
            .where(
                WorkflowRun.organization_id == organization.id,
                WorkflowDefinition.key == "reviews.publish_response",
                WorkflowRun.input_document["response_id"].as_string() == str(response.id),
            )
            .order_by(WorkflowRun.created_at.desc())
            .limit(1)
        )
        truth = f"Google shows the approved reply ({observation.state})"
        if run_id is None:
            return truth, Action.OPERATOR, "NO_PUBLISH_RUN_FOUND"
        await ExecutionService().enqueue_recovery_run(
            session,
            organization.id,
            run_id,
            recovery_reference=f"review-response:{response.id}",
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        return truth, Action.RESUME, f"workflow_run={run_id} (verification only)"

    return inspect


# --- Collection and execution ------------------------------------------------------------------


async def collect(
    session: AsyncSession,
    settings: Settings,
    actor_id: UUID,
    correlation_id: str,
    organization_id: UUID | None,
) -> tuple[list[Candidate], list[Item]]:
    """Everything stuck, whichever organization it belongs to."""
    candidates: list[Candidate] = []
    skipped: list[Item] = []

    def add(
        kind: Kind,
        organization: Organization,
        subject_id: UUID,
        status: str,
        inspect: Callable[[AsyncSession], Awaitable[tuple[str, Action, str]]],
    ) -> None:
        reason = _skipped(organization)
        if reason is not None:
            skipped.append(
                Item(
                    kind,
                    organization.id,
                    organization.name,
                    subject_id,
                    status,
                    "not read",
                    Action.SKIPPED,
                    reason,
                )
            )
        else:
            candidates.append(Candidate(kind, organization, subject_id, status, inspect))

    def scoped(statement: Any, column: Any) -> Any:
        return statement.where(column == organization_id) if organization_id else statement

    posts = (
        await session.execute(
            scoped(
                select(GBPPostPublication, Organization)
                .join(Organization, Organization.id == GBPPostPublication.organization_id)
                .where(GBPPostPublication.status == "reconciliation_required")
                .order_by(GBPPostPublication.created_at),
                GBPPostPublication.organization_id,
            )
        )
    ).all()
    handled_runs: set[UUID] = set()
    for publication, organization in posts:
        handled_runs.add(publication.workflow_run_id)
        add(
            Kind.GBP_POST,
            organization,
            publication.id,
            f"{publication.status}/{publication.safe_error_code}",
            _gbp_inspector(settings, organization, publication, actor_id, correlation_id),
        )

    escalated = (
        await session.execute(
            scoped(
                select(WorkflowRun, Organization)
                .join(Organization, Organization.id == WorkflowRun.organization_id)
                .join(WorkflowVersion, WorkflowVersion.id == WorkflowRun.workflow_version_id)
                .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
                .where(
                    WorkflowDefinition.key == "gbp.publish_post",
                    WorkflowRun.status == "escalated",
                )
                .order_by(WorkflowRun.created_at),
                WorkflowRun.organization_id,
            )
        )
    ).all()
    for run, organization in escalated:
        if run.id in handled_runs:
            continue  # resolved together with its publication above

        async def orphan(session: AsyncSession) -> tuple[str, Action, str]:
            return (
                "its publication is not awaiting reconciliation",
                Action.OPERATOR,
                "RUN_ESCALATED_WITHOUT_RECONCILIATION",
            )

        add(Kind.GBP_RUN, organization, run.id, f"{run.status}/{run.failure_code}", orphan)

    site_changes = (
        await session.execute(
            scoped(
                select(ContentPublication, Organization)
                .join(Organization, Organization.id == ContentPublication.organization_id)
                .where(
                    ContentPublication.publication_kind == "site_change",
                    ContentPublication.status == "reconciliation_required",
                )
                .order_by(ContentPublication.created_at),
                ContentPublication.organization_id,
            )
        )
    ).all()
    for publication, organization in site_changes:
        add(
            Kind.SITE_CHANGE,
            organization,
            publication.id,
            f"{publication.status}/{publication.safe_error_code}",
            _site_change_inspector(organization, publication, actor_id, correlation_id),
        )

    responses = (
        await session.execute(
            scoped(
                select(ReviewResponseRevision, Organization)
                .join(Organization, Organization.id == ReviewResponseRevision.organization_id)
                .where(ReviewResponseRevision.status == "reconciliation_required")
                .order_by(ReviewResponseRevision.created_at),
                ReviewResponseRevision.organization_id,
            )
        )
    ).all()
    for response, organization in responses:
        add(
            Kind.REVIEW_REPLY,
            organization,
            response.id,
            f"{response.status}/{response.safe_error_code}",
            _review_inspector(organization, response, actor_id, correlation_id),
        )
    return candidates, skipped


async def recover_stuck_publications(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    apply: bool,
    actor_id: UUID | None = None,
    organization_id: UUID | None = None,
) -> Report:
    """Inspect every stuck item; with ``apply`` keep the recovery each inspection performed."""
    correlation_id = f"recover-stuck-publications:{uuid4().hex[:12]}"
    effective_actor = actor_id if apply and actor_id is not None else NIL_ACTOR
    async with session_factory() as session:
        candidates, items = await collect(
            session, settings, effective_actor, correlation_id, organization_id
        )
    for candidate in candidates:
        # One transaction per item. The inspection performs the canonical recovery, so a dry
        # run is the same code with the transaction rolled back, and one provider failure
        # leaves every other item untouched.
        async with session_factory() as session:
            try:
                truth, action, detail = await candidate.inspect(session)
            except Exception as exc:
                await session.rollback()
                logger.warning("Stuck item inspection failed", exc_info=exc)
                truth, action, detail = "not read", Action.ERROR, type(exc).__name__
            else:
                if apply and action is Action.RESUME:
                    await session.commit()
                else:
                    await session.rollback()
        items.append(
            Item(
                candidate.kind,
                candidate.organization.id,
                candidate.organization.name,
                candidate.subject_id,
                candidate.status,
                truth,
                action,
                detail,
            )
        )
    return Report(items=items, applied=apply)


def format_report(report: Report) -> list[str]:
    verb = "resumed" if report.applied else "would resume"
    lines: list[str] = []
    for item in report.items:
        lines.append(f"{item.kind.value} {item.subject_id}  {item.organization} ({item.status})")
        lines.append(f"    provider truth: {item.provider_truth}")
        action = verb if item.action is Action.RESUME else item.action.value
        lines.append(f"    action: {action}  [{item.detail}]")
    resumed = sum(item.action is Action.RESUME for item in report.items)
    lines.append(
        f"items={len(report.items)} {verb}={resumed} "
        f"wait={sum(i.action is Action.WAIT for i in report.items)} "
        f"operator={sum(i.action is Action.OPERATOR for i in report.items)} "
        f"skipped={sum(i.action is Action.SKIPPED for i in report.items)} "
        f"errors={sum(i.action is Action.ERROR for i in report.items)}"
    )
    return lines


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--organization-id", type=UUID, help="limit to one organization")
    parser.add_argument("--actor-id", type=UUID, help="platform user id recorded on --apply")
    parser.add_argument(
        "--apply", action="store_true", help="keep the recoveries (default: dry run)"
    )
    return parser.parse_args(argv)


async def main() -> int:
    args = _parse_args()
    if args.apply and args.actor_id is None:
        print("error: --apply needs --actor-id, the platform user id the audit trail records")
        return EXIT_BAD_ARGUMENTS
    runtime = create_database_runtime(Settings())
    try:
        factory = runtime.require_session_factory()
        if args.apply:
            async with factory() as session:
                if await session.get(UserProfile, args.actor_id) is None:
                    print("error: --actor-id is not a platform user")
                    return EXIT_BAD_ARGUMENTS
        report = await recover_stuck_publications(
            factory,
            Settings(),
            apply=args.apply,
            actor_id=args.actor_id,
            organization_id=args.organization_id,
        )
    finally:
        await runtime.dispose()
    print("APPLIED" if report.applied else "DRY RUN (re-run with --apply to execute)")
    for line in format_report(report):
        print(line)
    return EXIT_ITEM_ERRORS if any(i.action is Action.ERROR for i in report.items) else 0


if __name__ == "__main__":
    raise SystemExit(run_script("recover_stuck_publications", main))
