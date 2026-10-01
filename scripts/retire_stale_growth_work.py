"""Retire Content and Growth work that predates SEO page attribution and is now stale.

Much of the Content and Growth backlog was created before opportunities carried page
attribution (PR #136) and still points at SEO opportunities that have since been archived
or superseded, at recommendations that were withdrawn, or at query-only opportunities that
never had a page. Nothing retires that work on its own, so it keeps competing with live
work. This script retires it through the same services and status transitions the product
uses, with one audit event per row.

Active organizations only. Dry run by default: it prints exactly what `--apply` would do.

What counts as stale (work tied to a live attributed opportunity is never touched):

* its source SEO opportunity is archived or superseded, or its source recommendation was
  withdrawn or superseded;
* its source opportunity is live but `query_only`/`unresolved`, it has no live attributed
  successor, and the work was created before the attribution cutoff (newer work on such an
  opportunity is valid `new_page` content and is only reported);
* a `failed` Growth action that is not tied to live attributed work.

What happens to it:

* Content opportunities and items -> `archived`; Content briefs -> `retired`; a `ready`
  brief with no sources is regenerated from the opportunity's evidence or `blocked`.
* Growth actions and initiatives -> `cancelled` (a failed action keeps its error code).
* A Content item stuck in `publishing` is reconciled against its pull request first:
  merged -> `published`, closed -> `archived`, still open -> left alone and reported.

Run (Render shell):

    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.retire_stale_growth_work
    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.retire_stale_growth_work --apply
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.growth.models import GrowthAction, GrowthInitiative
from apps.api.app.growth.service import (
    CANCELLABLE_ACTION_STATUSES,
    CANCELLABLE_INITIATIVE_STATUSES,
    GrowthService,
)
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.evidence import content_opportunity_evidence_references
from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentOpportunity,
    ContentPublication,
)
from apps.api.app.products.content.publish_handler import (
    PullRequestUnavailableError,
    observe_publication_pull_request,
)
from apps.api.app.products.content.service import ContentService
from apps.api.app.products.seo.models import SEOOpportunity, SEORecommendationRevision
from scripts._cli import run_script

# PR #136 (page attribution) merged 2026-09-29T20:27:38-07:00. Work created before this
# moment never saw an attributed page.
ATTRIBUTION_CUTOFF = datetime(2026, 9, 30, 3, 27, 38, tzinfo=UTC)

EXIT_NOT_RESOLVED = 4

RETIRABLE_ITEM_STATUSES = frozenset(
    {
        "idea",
        "briefing",
        "brief_ready",
        "drafting",
        "draft_ready",
        "reviewing",
        "revision_requested",
    }
)
RETIRABLE_OPPORTUNITY_STATUSES = frozenset({"identified", "validated", "accepted"})
LIVE_ATTRIBUTION = frozenset({"attributed", "shared"})


@dataclass(frozen=True, slots=True)
class Verdict:
    """Whether the work behind one source is stale, live, or must be left and reported."""

    stale: bool = False
    live: bool = False
    reason: str = ""


LIVE = Verdict(live=True)
UNKNOWN_SOURCE = Verdict(reason="no_seo_source")


@dataclass(frozen=True, slots=True)
class Change:
    organization_id: UUID
    model: str
    row_id: UUID
    from_state: str
    to_state: str
    reason: str


@dataclass(frozen=True, slots=True)
class Skipped:
    organization_id: UUID
    model: str
    row_id: UUID
    reason: str


Step = Callable[[AsyncSession, str], Awaitable[None]]


@dataclass(slots=True)
class OrganizationPlan:
    organization_id: UUID
    name: str
    changes: list[Change] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)

    def add(self, change: Change, step: Step) -> None:
        self.changes.append(change)
        self.steps.append(step)


def _ref_id(reference: str, prefix: str) -> UUID | None:
    head, _, raw = reference.partition(":")
    if head != prefix:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


async def _seo_verdict(
    session: AsyncSession,
    organization_id: UUID,
    opportunity_id: UUID,
    created_at: datetime,
) -> Verdict:
    opportunity = await session.scalar(
        select(SEOOpportunity).where(
            SEOOpportunity.organization_id == organization_id,
            SEOOpportunity.id == opportunity_id,
        )
    )
    if opportunity is None:
        return Verdict(reason="source_not_found")
    if opportunity.status == "archived" or opportunity.active_marker != "active":
        return Verdict(stale=True, reason="seo_opportunity_archived")
    if opportunity.attribution_state in LIVE_ATTRIBUTION:
        return LIVE
    query = opportunity.evidence.get("query") if opportunity.evidence else None
    if isinstance(query, str) and query:
        successor = await session.scalar(
            select(SEOOpportunity.id)
            .where(
                SEOOpportunity.organization_id == organization_id,
                SEOOpportunity.website_id == opportunity.website_id,
                SEOOpportunity.opportunity_type == opportunity.opportunity_type,
                SEOOpportunity.active_marker == "active",
                SEOOpportunity.attribution_state.in_(tuple(LIVE_ATTRIBUTION)),
                SEOOpportunity.evidence["query"].as_string() == query,
                SEOOpportunity.id != opportunity.id,
            )
            .limit(1)
        )
        if successor is not None:
            return Verdict(reason="live_attributed_successor_exists")
    if created_at < ATTRIBUTION_CUTOFF:
        return Verdict(stale=True, reason="query_only_pre_attribution")
    return Verdict(reason="eligible_for_new_page")


async def _revision_verdict(
    session: AsyncSession, organization_id: UUID, revision_id: UUID, created_at: datetime
) -> Verdict:
    revision = await session.scalar(
        select(SEORecommendationRevision).where(
            SEORecommendationRevision.organization_id == organization_id,
            SEORecommendationRevision.id == revision_id,
        )
    )
    if revision is None:
        return Verdict(reason="source_not_found")
    if revision.status in {"withdrawn", "superseded"}:
        return Verdict(stale=True, reason=f"recommendation_{revision.status}")
    return await _seo_verdict(session, organization_id, revision.opportunity_id, created_at)


async def _action_verdict(session: AsyncSession, action: GrowthAction) -> Verdict:
    """Combine every SEO source the action cites; any live source keeps it."""
    references = [str(ref) for ref in action.evidence_references]
    references.append(action.target_reference)
    verdicts: list[Verdict] = []
    for reference in references:
        revision_id = _ref_id(reference, "seo-recommendation")
        opportunity_id = _ref_id(reference, "seo-opportunity")
        if revision_id is not None:
            verdicts.append(
                await _revision_verdict(
                    session, action.organization_id, revision_id, action.created_at
                )
            )
        elif opportunity_id is not None:
            verdicts.append(
                await _seo_verdict(
                    session, action.organization_id, opportunity_id, action.created_at
                )
            )
        elif reference.startswith("seo-page:"):
            verdicts.append(LIVE)  # a mapped page: the attributed target
    if any(verdict.live for verdict in verdicts):
        return LIVE
    stale = next((verdict for verdict in verdicts if verdict.stale), None)
    if stale is not None:
        return stale
    if action.status == "failed":
        return Verdict(stale=True, reason="failed_action_retired")
    return next(iter(verdicts), UNKNOWN_SOURCE)


async def plan_organization(
    session: AsyncSession,
    organization: Organization,
    *,
    content: ContentService,
    growth: GrowthService,
) -> OrganizationPlan:
    """Read everything and decide; nothing is written here."""
    org_id = organization.id
    plan = OrganizationPlan(organization_id=org_id, name=organization.name)

    # --- Growth actions first: Content work sourced from an action follows its verdict.
    actions = list(
        await session.scalars(
            select(GrowthAction)
            .where(GrowthAction.organization_id == org_id)
            .order_by(GrowthAction.created_at, GrowthAction.id)
        )
    )
    action_verdicts: dict[UUID, Verdict] = {}
    planned_actions: set[UUID] = set()
    for action in actions:
        if action.status not in CANCELLABLE_ACTION_STATUSES and action.status != "cancelled":
            continue
        verdict = await _action_verdict(session, action)
        action_verdicts[action.id] = verdict
        if action.status == "cancelled":
            continue
        if not verdict.stale:
            if not verdict.live:
                plan.skipped.append(Skipped(org_id, "growth_action", action.id, verdict.reason))
            continue
        planned_actions.add(action.id)
        plan.add(
            Change(org_id, "growth_action", action.id, action.status, "cancelled", verdict.reason),
            _cancel_action(growth, action, verdict.reason),
        )

    # --- Content opportunities: verdict per opportunity, reused by briefs and items.
    opportunities = list(
        await session.scalars(
            select(ContentOpportunity).where(ContentOpportunity.organization_id == org_id)
        )
    )
    opportunity_verdicts: dict[UUID, Verdict] = {}
    for opportunity in opportunities:
        source = opportunity.source_reference or ""
        seo_id = _ref_id(source, "seo-opportunity")
        action_id = _ref_id(source, "growth-action")
        if seo_id is not None:
            verdict = await _seo_verdict(session, org_id, seo_id, opportunity.created_at)
        elif action_id is not None:
            action_verdict = action_verdicts.get(action_id)
            if action_verdict is None:
                verdict = Verdict(reason="source_action_not_found")
            elif action_verdict.stale:
                verdict = Verdict(stale=True, reason=f"growth_action:{action_verdict.reason}")
            else:
                verdict = action_verdict
        else:
            verdict = UNKNOWN_SOURCE
        opportunity_verdicts[opportunity.id] = verdict

    items = list(
        await session.scalars(
            select(ContentItem)
            .where(ContentItem.organization_id == org_id)
            .order_by(ContentItem.created_at, ContentItem.id)
        )
    )
    items_by_id = {item.id: item for item in items}
    retired_items: set[UUID] = set()

    def item_verdict(item: ContentItem) -> Verdict:
        if item.opportunity_id is None:
            return UNKNOWN_SOURCE
        return opportunity_verdicts.get(item.opportunity_id, UNKNOWN_SOURCE)

    # --- Publishing items: reconcile with the provider before anything else.
    for item in items:
        if item.status != "publishing":
            continue
        verdict = item_verdict(item)
        if not verdict.stale:
            continue
        publication = await session.scalar(
            select(ContentPublication)
            .where(
                ContentPublication.organization_id == org_id,
                ContentPublication.content_item_id == item.id,
            )
            .order_by(ContentPublication.created_at.desc())
            .limit(1)
        )
        if publication is None:
            plan.skipped.append(Skipped(org_id, "content_item", item.id, "no_publication"))
            continue
        try:
            observed = await observe_publication_pull_request(session, org_id, publication)
        except PullRequestUnavailableError as exc:
            plan.skipped.append(Skipped(org_id, "content_item", item.id, exc.code))
            continue
        if observed.state == "open":
            plan.skipped.append(Skipped(org_id, "content_item", item.id, "pull_request_open"))
            continue
        target = "published" if observed.state == "merged" else "archived"
        retired_items.add(item.id)
        plan.add(
            Change(
                org_id,
                "content_item",
                item.id,
                "publishing",
                target,
                f"pull_request_{observed.state}",
            ),
            _reconcile_publishing(
                content, item, publication, observed.state, observed.merge_commit_sha
            ),
        )

    # --- Briefs.
    briefs = list(
        await session.scalars(
            select(ContentBrief)
            .where(ContentBrief.organization_id == org_id, ContentBrief.status == "ready")
            .order_by(ContentBrief.created_at, ContentBrief.id)
        )
    )
    for brief in briefs:
        brief_item = items_by_id.get(brief.content_item_id)
        if brief_item is None:
            continue
        item = brief_item
        verdict = item_verdict(item)
        if verdict.stale:
            plan.add(
                Change(org_id, "content_brief", brief.id, "ready", "retired", verdict.reason),
                _retire_brief(content, brief, item, verdict.reason),
            )
        elif not brief.source_evidence_references and item.status not in {"publishing"}:
            regenerable = await content_opportunity_evidence_references(
                session, org_id, item.opportunity_id
            )
            plan.add(
                Change(
                    org_id,
                    "content_brief",
                    brief.id,
                    "ready",
                    "superseded" if regenerable else "blocked",
                    "empty_sources_regenerated" if regenerable else "empty_sources_blocked",
                ),
                _repair_brief(content, brief, item),
            )

    # --- Items.
    for item in items:
        if item.id in retired_items:
            continue
        verdict = item_verdict(item)
        if item.status == "approved" and verdict.stale:
            plan.skipped.append(
                Skipped(org_id, "content_item", item.id, "approved_awaiting_human_decision")
            )
            continue
        if item.status not in RETIRABLE_ITEM_STATUSES:
            continue
        if verdict.stale:
            plan.add(
                Change(org_id, "content_item", item.id, item.status, "archived", verdict.reason),
                _retire_item(content, item, verdict.reason),
            )
        elif not verdict.live:
            plan.skipped.append(Skipped(org_id, "content_item", item.id, verdict.reason))

    # --- Opportunities.
    for opportunity in opportunities:
        if opportunity.status not in RETIRABLE_OPPORTUNITY_STATUSES:
            continue
        verdict = opportunity_verdicts[opportunity.id]
        if verdict.stale:
            plan.add(
                Change(
                    org_id,
                    "content_opportunity",
                    opportunity.id,
                    opportunity.status,
                    "archived",
                    verdict.reason,
                ),
                _retire_opportunity(content, opportunity, verdict.reason),
            )
        elif not verdict.live:
            plan.skipped.append(
                Skipped(org_id, "content_opportunity", opportunity.id, verdict.reason)
            )

    # --- Initiatives: cancelled once every one of their actions is cancelled or planned.
    initiatives = list(
        await session.scalars(
            select(GrowthInitiative)
            .where(GrowthInitiative.organization_id == org_id)
            .order_by(GrowthInitiative.created_at, GrowthInitiative.id)
        )
    )
    for initiative in initiatives:
        if initiative.status not in CANCELLABLE_INITIATIVE_STATUSES:
            continue
        siblings = [a for a in actions if a.initiative_id == initiative.id]
        if not siblings or not any(a.id in planned_actions for a in siblings):
            continue
        remaining = [a for a in siblings if a.status != "cancelled" and a.id not in planned_actions]
        if remaining:
            plan.skipped.append(
                Skipped(org_id, "growth_initiative", initiative.id, "has_live_actions")
            )
            continue
        plan.add(
            Change(
                org_id,
                "growth_initiative",
                initiative.id,
                initiative.status,
                "cancelled",
                "all_actions_stale",
            ),
            _cancel_initiative(growth, initiative),
        )
    return plan


def _cancel_action(growth: GrowthService, action: GrowthAction, reason: str) -> Step:
    async def run(session: AsyncSession, correlation_id: str) -> None:
        await growth.cancel_action(
            session, action, reason_code=reason, correlation_id=correlation_id
        )

    return run


def _cancel_initiative(growth: GrowthService, initiative: GrowthInitiative) -> Step:
    async def run(session: AsyncSession, correlation_id: str) -> None:
        await growth.cancel_initiative(
            session, initiative, reason_code="all_actions_stale", correlation_id=correlation_id
        )

    return run


def _retire_opportunity(
    content: ContentService, opportunity: ContentOpportunity, reason: str
) -> Step:
    async def run(session: AsyncSession, correlation_id: str) -> None:
        await content.retire_opportunity(
            session, opportunity, reason_code=reason, correlation_id=correlation_id
        )

    return run


def _retire_item(content: ContentService, item: ContentItem, reason: str) -> Step:
    async def run(session: AsyncSession, correlation_id: str) -> None:
        await content.retire_item(session, item, reason_code=reason, correlation_id=correlation_id)

    return run


def _retire_brief(
    content: ContentService, brief: ContentBrief, item: ContentItem, reason: str
) -> Step:
    async def run(session: AsyncSession, correlation_id: str) -> None:
        await content.retire_brief(
            session, brief, item, reason_code=reason, correlation_id=correlation_id
        )

    return run


def _repair_brief(content: ContentService, brief: ContentBrief, item: ContentItem) -> Step:
    async def run(session: AsyncSession, correlation_id: str) -> None:
        await content.repair_brief_sources(session, brief, item, correlation_id=correlation_id)

    return run


def _reconcile_publishing(
    content: ContentService,
    item: ContentItem,
    publication: ContentPublication,
    state: str,
    merge_commit_sha: str | None,
) -> Step:
    async def run(session: AsyncSession, correlation_id: str) -> None:
        await content.reconcile_publishing_item(
            session,
            item,
            publication,
            pull_request_state=state,
            merge_commit_sha=merge_commit_sha,
            correlation_id=correlation_id,
        )

    return run


@dataclass(slots=True)
class RetirementReport:
    plans: list[OrganizationPlan]
    applied: bool


async def retire_stale_growth_work(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    apply: bool,
    organization_id: UUID | None = None,
    content: ContentService | None = None,
    growth: GrowthService | None = None,
) -> RetirementReport:
    """Plan (and with ``apply`` execute) retirement for every active organization."""
    content = content or ContentService()
    growth = growth or GrowthService()
    async with session_factory() as session:
        statement = select(Organization).where(Organization.status == OrganizationStatus.ACTIVE)
        if organization_id is not None:
            statement = statement.where(Organization.id == organization_id)
        organizations = list(
            await session.scalars(statement.order_by(Organization.created_at, Organization.id))
        )
    correlation_id = f"retire-stale-growth-work:{uuid4().hex[:12]}"
    plans: list[OrganizationPlan] = []
    for organization in organizations:
        # One transaction per organization: a failure leaves other organizations
        # untouched, and a dry run is the same code path with the writes skipped.
        async with session_factory.begin() as session:
            plan = await plan_organization(session, organization, content=content, growth=growth)
            if apply:
                for step in plan.steps:
                    await step(session, correlation_id)
            plans.append(plan)
    return RetirementReport(plans=plans, applied=apply)


def format_report(report: RetirementReport) -> list[str]:
    """The same table for a dry run and for an apply."""
    lines: list[str] = []
    for plan in report.plans:
        lines.append(f"organization {plan.name} ({plan.organization_id})")
        counts = Counter((c.model, c.from_state, c.to_state, c.reason) for c in plan.changes)
        if not counts:
            lines.append("  no stale work")
        for (model, from_state, to_state, reason), count in sorted(counts.items()):
            lines.append(f"  {model:<20} {from_state:<18} -> {to_state:<12} {count:>4}  [{reason}]")
        for item in plan.skipped:
            lines.append(f"  SKIPPED {item.model} {item.row_id} reason={item.reason}")
    total = sum(len(plan.changes) for plan in report.plans)
    skipped = sum(len(plan.skipped) for plan in report.plans)
    lines.append(f"organizations={len(report.plans)} changes={total} skipped={skipped}")
    return lines


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--organization-id", type=UUID, help="limit to one active organization")
    parser.add_argument(
        "--apply", action="store_true", help="perform the changes (default: dry run)"
    )
    return parser.parse_args(argv)


async def main() -> int:
    args = _parse_args()
    settings = Settings()
    runtime = create_database_runtime(settings)
    try:
        report = await retire_stale_growth_work(
            runtime.require_session_factory(),
            apply=args.apply,
            organization_id=args.organization_id,
        )
        if args.organization_id is not None and not report.plans:
            print("error: no active organization with that id")
            return EXIT_NOT_RESOLVED
        print("APPLIED" if report.applied else "DRY RUN (re-run with --apply to execute)")
        for line in format_report(report):
            print(line)
        return 0
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    raise SystemExit(run_script("retire_stale_growth_work", main))
