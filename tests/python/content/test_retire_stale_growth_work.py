"""scripts.retire_stale_growth_work: stale pre-attribution work is retired, live work is not."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.agents.models import AgentRun, AgentSession
from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.growth.models import GrowthAction, GrowthInitiative
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentOpportunity,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)
from apps.api.app.products.content.publish_handler import PullRequestObservation
from apps.api.app.products.seo.models import SEOOpportunity, SEOPage, SEOWebsite
from scripts import retire_stale_growth_work as script

OLD = datetime(2026, 9, 1, tzinfo=UTC)  # before the attribution cutoff
NEW = datetime(2026, 10, 1, tzinfo=UTC)  # after it


@dataclass
class World:
    org: UUID
    inactive_org: UUID
    rows: dict[str, UUID]


def _org(name: str, status: OrganizationStatus) -> Organization:
    return Organization(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{uuid4().hex[:6]}",
        organization_type=OrganizationType.TEST,
        status=status,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )


async def _seed_org(
    session: AsyncSession, org: Organization, *, with_live_work: bool
) -> dict[str, UUID]:
    """Stale work for one organization; live attributed work too when asked."""
    rows: dict[str, UUID] = {}
    location = Location(
        organization_id=org.id,
        name="Main",
        slug=f"main-{uuid4().hex[:6]}",
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        website_url="https://example.invalid",
        is_primary=True,
        version=1,
    )
    session.add(location)
    await session.flush()
    website = SEOWebsite(
        organization_id=org.id,
        location_id=location.id,
        key=f"site-{uuid4().hex[:6]}",
        name="Test site",
        canonical_origin="https://example.invalid",
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add(website)
    await session.flush()
    page = SEOPage(
        organization_id=org.id,
        website_id=website.id,
        normalized_url="https://example.invalid/real",
        observed_url="https://example.invalid/real",
        normalization_reasons=[],
        robots_directives=[],
        internal_links=[],
        external_links=[],
        structured_data_present=False,
        indexability="indexable",
        technical_issues=[],
        quality_status="clean",
    )
    session.add(page)
    await session.flush()

    def seo(
        key: str, *, state: str, archived: bool = False, query: str | None = None
    ) -> SEOOpportunity:
        return SEOOpportunity(
            organization_id=org.id,
            location_id=location.id,
            website_id=website.id,
            page_id=page.id if state == "attributed" else None,
            attribution_state=state,
            opportunity_type="gsc_low_ctr",
            deduplication_key=key,
            active_marker="dead0001" if archived else "active",
            evidence={"query": query or key},
            source_versions=["gsc.v1"],
            score_version=1,
            priority_score=50,
            score_explanation={},
            status="archived" if archived else "identified",
            version=1,
        )

    seo_rows = {
        "archived": seo("archived", state="query_only", archived=True),
        "query_old": seo("query-old", state="query_only"),
        "query_new": seo("query-new", state="query_only"),
        "attributed": seo("attributed", state="attributed"),
    }
    session.add_all(seo_rows.values())
    await session.flush()

    def work(name: str, source: str, created: datetime, item_status: str) -> None:
        opportunity = ContentOpportunity(
            organization_id=org.id,
            location_id=location.id,
            product_key="seo",
            target_reference=source,
            opportunity_type="seo",
            source_type="seo_analysis",
            source_reference=source,
            evidence_document={},
            evidence_hash=uuid4().hex + uuid4().hex,
            priority_score=10,
            status="accepted",
            created_at=created,
        )
        session.add(opportunities_pending.setdefault(name, opportunity))

    opportunities_pending: dict[str, ContentOpportunity] = {}
    for name, row in seo_rows.items():
        created = NEW if name == "query_new" else OLD
        work(name, f"seo-opportunity:{row.id}", created, "brief_ready")
    await session.flush()
    for name, pending in opportunities_pending.items():
        rows[f"{name}_opportunity"] = pending.id
    opportunities = {
        key.removesuffix("_opportunity"): value
        for key, value in rows.items()
        if key.endswith("_opportunity")
    }
    for name, opportunity_id in opportunities.items():
        item = ContentItem(
            organization_id=org.id,
            location_id=location.id,
            opportunity_id=opportunity_id,
            content_type="blog",
            title=f"Item {name}",
            slug=f"item-{name}",
            status="brief_ready",
            version=1,
            created_at=NEW if name == "query_new" else OLD,
        )
        session.add(item)
        await session.flush()
        rows[f"{name}_item"] = item.id
        brief = ContentBrief(
            organization_id=org.id,
            content_item_id=item.id,
            revision_number=1,
            audience="Locals",
            intent="research",
            target_kind="new_page",
            target_reference=f"/{name}",
            approved_fact_revision_ids=[],
            required_claims=[],
            prohibited_claims=[],
            required_local_references=[],
            source_evidence_references=[f"seo-opportunity:{seo_rows[name].id}"],
            validation_requirements={},
            status="ready",
            created_at=NEW if name == "query_new" else OLD,
        )
        session.add(brief)
        await session.flush()
        rows[f"{name}_brief"] = brief.id
    rows["seo_archived"] = seo_rows["archived"].id
    rows["seo_attributed"] = seo_rows["attributed"].id

    # Publishing items whose source is archived: one per pull request state.
    provider = Provider(
        key=f"github-{uuid4().hex[:6]}", name="GitHub", status="active", capabilities=[]
    )
    session.add(provider)
    await session.flush()
    connection = IntegrationConnection(
        organization_id=org.id,
        provider_id=provider.id,
        external_account_reference="org/site",
        status="connected",
    )
    session.add(connection)
    await session.flush()
    target = PublishingTarget(
        organization_id=org.id,
        connection_id=connection.id,
        key="primary",
        target_type="github_astro",
        repository_id="org/site",
        base_branch="main",
        allowed_path_prefix="src/content",
        status="active",
        version=1,
    )
    definition = WorkflowDefinition(
        key=f"content.publish.{uuid4().hex[:6]}", name="Publish", owner="content"
    )
    session.add_all([target, definition])
    await session.flush()
    version = WorkflowVersion(
        definition_id=definition.id,
        version=1,
        status="approved",
        input_schema={},
        output_schema={},
        step_specification=[],
        retry_policy={},
        timeout_seconds=60,
    )
    session.add(version)
    await session.flush()
    workflow_run = WorkflowRun(
        organization_id=org.id,
        location_id=location.id,
        workflow_version_id=version.id,
        product_key="content",
        trigger_type="manual",
        idempotency_key=f"run-{uuid4().hex}",
        request_hash="hash",
        input_document={},
        correlation_id="retire-test",
    )
    session.add(workflow_run)
    await session.flush()
    for number in ("1", "2", "3"):
        item = ContentItem(
            organization_id=org.id,
            location_id=location.id,
            opportunity_id=opportunities["archived"],
            content_type="blog",
            title=f"Publishing {number}",
            slug=f"publishing-{number}",
            status="publishing",
            version=1,
        )
        session.add(item)
        await session.flush()
        revision = ContentRevision(
            organization_id=org.id,
            content_item_id=item.id,
            revision_number=1,
            body="Body",
            frontmatter={},
            content_hash=uuid4().hex + uuid4().hex,
            created_by_type="ai",
            approved_fact_revision_ids=[],
            status="approved",
            validation_document={},
        )
        session.add(revision)
        await session.flush()
        session.add(
            ContentPublication(
                organization_id=org.id,
                publication_kind="content",
                content_item_id=item.id,
                content_revision_id=revision.id,
                publishing_target_id=target.id,
                workflow_run_id=workflow_run.id,
                idempotency_key=f"pub-{number}-{uuid4().hex[:8]}",
                status="pull_request_created",
                target_path=f"src/content/{number}.md",
                external_pull_request_id=number,
            )
        )
        rows[f"publishing_{number}"] = item.id

    # An empty-source ready brief on a live attributed opportunity is regenerated; one
    # whose opportunity has no SEO source at all is blocked.
    for name, source in (
        ("empty_live", f"seo-opportunity:{seo_rows['attributed'].id}"),
        ("empty_manual", "manual:note"),
    ):
        opportunity = ContentOpportunity(
            organization_id=org.id,
            location_id=location.id,
            product_key="seo" if name == "empty_live" else "content",
            target_reference=source,
            opportunity_type="seo",
            source_type="seo_analysis",
            source_reference=source,
            evidence_document={},
            evidence_hash=uuid4().hex + uuid4().hex,
            priority_score=10,
            status="accepted",
        )
        session.add(opportunity)
        await session.flush()
        item = ContentItem(
            organization_id=org.id,
            location_id=location.id,
            opportunity_id=opportunity.id,
            content_type="blog",
            title=name,
            slug=name.replace("_", "-"),
            status="brief_ready",
            version=1,
        )
        session.add(item)
        await session.flush()
        brief = ContentBrief(
            organization_id=org.id,
            content_item_id=item.id,
            revision_number=1,
            audience="Locals",
            intent="research",
            target_kind="existing_page",
            target_reference="https://example.invalid/real",
            approved_fact_revision_ids=[],
            required_claims=[],
            prohibited_claims=[],
            required_local_references=[],
            source_evidence_references=[],
            validation_requirements={},
            status="ready",
        )
        session.add(brief)
        await session.flush()
        rows[f"{name}_brief"] = brief.id
        rows[f"{name}_item"] = item.id

    agent_session = AgentSession(
        organization_id=org.id,
        location_id=location.id,
        skill_key="growth.planner",
        namespace_hash=uuid4().hex + uuid4().hex,
        hermes_session_key=uuid4().hex,
        status="active",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        version=1,
    )
    session.add(agent_session)
    await session.flush()
    planner_run = AgentRun(
        organization_id=org.id,
        location_id=location.id,
        workflow_run_id=workflow_run.id,
        agent_session_id=agent_session.id,
        skill_key="growth.planner",
        skill_version=6,
        hermes_session_id=agent_session.hermes_session_key,
        correlation_id="retire-test",
        status="completed",
        capability_snapshot={},
        output_references=[],
        source_references=[],
        event_count=0,
    )
    session.add(planner_run)
    await session.flush()

    # Growth: an initiative of stale actions, and one with live attributed work.
    async def initiative(name: str, actions: list[tuple[str, str, list[str]]]) -> None:
        row = GrowthInitiative(
            organization_id=org.id,
            location_id=location.id,
            planner_agent_run_id=planner_run.id,
            idempotency_key=f"growth-{name}-{uuid4().hex[:8]}",
            objective=name,
            rationale="r",
            source_references=[],
            priority_score=10,
            confidence=Decimal("0.5"),
            status="executing" if name == "stale" else "approved",
        )
        session.add(row)
        await session.flush()
        rows[f"initiative_{name}"] = row.id
        for position, (status, target_reference, evidence) in enumerate(actions):
            action = GrowthAction(
                organization_id=org.id,
                initiative_id=row.id,
                action_key=f"{name}-{position}",
                product_key="seo",
                action_type="site_implementation",
                target_reference=target_reference,
                execution_mode="workflow",
                executor_workflow_key="seo.apply_site_change",
                dependency_keys=[],
                evidence_references=evidence,
                expected_result_hypothesis="h",
                verification_plan={},
                risk="low",
                effort="low",
                position=position,
                status=status,
                safe_error_code="BOOM" if status == "failed" else None,
                created_at=OLD,
            )
            session.add(action)
            await session.flush()
            rows[f"action_{name}_{position}"] = action.id

    archived_ref = f"seo-opportunity:{seo_rows['archived'].id}"
    await initiative(
        "stale",
        [
            ("proposed", archived_ref, [archived_ref]),
            ("failed", archived_ref, []),
            ("waiting_approval", f"seo-opportunity:{seo_rows['query_old'].id}", []),
        ],
    )
    if with_live_work:
        await initiative(
            "live",
            [("proposed", f"seo-page:{page.id}", [f"seo-opportunity:{seo_rows['attributed'].id}"])],
        )
    return rows


@pytest.fixture
def world(content_session_factory: async_sessionmaker[AsyncSession]) -> World:
    async def seed() -> World:
        async with content_session_factory.begin() as session:
            active = _org("Retire Active", OrganizationStatus.ACTIVE)
            inactive = _org("Retire Paused", OrganizationStatus.PAUSED)
            session.add_all([active, inactive])
            await session.flush()
            rows = await _seed_org(session, active, with_live_work=True)
            inactive_rows = await _seed_org(session, inactive, with_live_work=False)
            rows.update({f"inactive_{key}": value for key, value in inactive_rows.items()})
            return World(active.id, inactive.id, rows)

    return asyncio.run(seed())


@pytest.fixture(autouse=True)
def pull_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    states = {
        "1": PullRequestObservation("merged", "mergesha"),
        "2": PullRequestObservation("closed", None),
        "3": PullRequestObservation("open", None),
    }

    async def observe(
        _session: object, _org: UUID, publication: ContentPublication
    ) -> PullRequestObservation:
        return states[str(publication.external_pull_request_id)]

    monkeypatch.setattr(script, "observe_publication_pull_request", observe)


async def _statuses(factory: async_sessionmaker[AsyncSession], world: World) -> dict[str, str]:
    async with factory() as session:
        out: dict[str, str] = {}
        for key, row_id in world.rows.items():
            for model in (
                ContentOpportunity,
                ContentItem,
                ContentBrief,
                GrowthAction,
                GrowthInitiative,
            ):
                row = await session.get(model, row_id)
                if row is not None:
                    out[key] = str(getattr(row, "status"))  # noqa: B009
                    break
        return out


def _run(factory: async_sessionmaker[AsyncSession], *, apply: bool) -> script.RetirementReport:
    return asyncio.run(script.retire_stale_growth_work(factory, apply=apply))


def _audit_count(factory: async_sessionmaker[AsyncSession], org: UUID) -> int:
    async def count() -> int:
        async with factory() as session:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.organization_id == org,
                        AuditEvent.event_type.like("%retired")
                        | AuditEvent.event_type.like("%cancelled")
                        | AuditEvent.event_type.like("content.brief.%")
                        | AuditEvent.event_type.like("content.item.publishing_reconciled"),
                    )
                )
                or 0
            )

    return asyncio.run(count())


@pytest.mark.integration
def test_dry_run_changes_nothing_and_prints_the_same_table_as_apply(
    content_session_factory: async_sessionmaker[AsyncSession], world: World
) -> None:
    before = asyncio.run(_statuses(content_session_factory, world))
    dry = _run(content_session_factory, apply=False)
    assert asyncio.run(_statuses(content_session_factory, world)) == before
    assert _audit_count(content_session_factory, world.org) == 0

    applied = _run(content_session_factory, apply=True)
    assert script.format_report(dry) == script.format_report(applied)
    assert [plan.organization_id for plan in dry.plans] == [world.org]  # paused org excluded


@pytest.mark.integration
def test_stale_work_is_retired_and_live_attributed_work_is_untouched(
    content_session_factory: async_sessionmaker[AsyncSession], world: World
) -> None:
    report = _run(content_session_factory, apply=True)
    rows = world.rows
    status = asyncio.run(_statuses(content_session_factory, world))

    # Archived and pre-attribution query-only sources are retired.
    for name in ("archived", "query_old"):
        assert status[f"{name}_opportunity"] == "archived"
        assert status[f"{name}_item"] == "archived"
        assert status[f"{name}_brief"] == "retired"
    # Newer query-only work is valid new_page content; live attributed work is untouched.
    for name in ("query_new", "attributed"):
        assert status[f"{name}_opportunity"] == "accepted"
        assert status[f"{name}_item"] == "brief_ready"
        assert status[f"{name}_brief"] == "ready"
    # Growth: stale actions cancelled (the failed one keeps its error), live untouched.
    assert [status[f"action_stale_{i}"] for i in range(3)] == ["cancelled"] * 3
    assert status["initiative_stale"] == "cancelled"
    assert status["action_live_0"] == "proposed"
    assert status["initiative_live"] == "approved"
    assert status["empty_manual_brief"] == "blocked"
    assert status["empty_live_brief"] == "superseded"

    async def failed_action_keeps_code() -> str | None:
        async with content_session_factory() as session:
            action = await session.get(GrowthAction, rows["action_stale_1"])
            assert action is not None
            return action.safe_error_code

    assert asyncio.run(failed_action_keeps_code()) == "BOOM"
    skipped = {(item.model, item.reason) for plan in report.plans for item in plan.skipped}
    assert ("content_opportunity", "eligible_for_new_page") in skipped
    assert ("content_item", "pull_request_open") in skipped
    # One audit event per changed row.
    changes = sum(len(plan.changes) for plan in report.plans)
    assert _audit_count(content_session_factory, world.org) == changes > 0


@pytest.mark.integration
def test_publishing_items_are_reconciled_against_the_pull_request_never_blind_cancelled(
    content_session_factory: async_sessionmaker[AsyncSession], world: World
) -> None:
    _run(content_session_factory, apply=True)
    status = asyncio.run(_statuses(content_session_factory, world))
    assert status["publishing_1"] == "published"  # merged
    assert status["publishing_2"] == "archived"  # closed without merge
    assert status["publishing_3"] == "publishing"  # still open: left alone


@pytest.mark.integration
def test_second_apply_changes_nothing_and_inactive_orgs_are_untouched(
    content_session_factory: async_sessionmaker[AsyncSession], world: World
) -> None:
    _run(content_session_factory, apply=True)
    after_first = asyncio.run(_statuses(content_session_factory, world))
    audit_after_first = _audit_count(content_session_factory, world.org)

    second = _run(content_session_factory, apply=True)

    assert sum(len(plan.changes) for plan in second.plans) == 0
    assert asyncio.run(_statuses(content_session_factory, world)) == after_first
    assert _audit_count(content_session_factory, world.org) == audit_after_first
    # The paused organization's identical stale work was never processed.
    for key, value in after_first.items():
        if key.startswith("inactive_"):
            assert value in {
                "accepted",
                "brief_ready",
                "ready",
                "proposed",
                "failed",
                "waiting_approval",
                "publishing",
                "executing",
                "approved",
            }, key
    assert after_first["inactive_archived_opportunity"] == "accepted"
    assert after_first["inactive_action_stale_0"] == "proposed"


@pytest.mark.integration
def test_one_organization_can_be_targeted_but_only_when_active(
    content_session_factory: async_sessionmaker[AsyncSession], world: World
) -> None:
    only_inactive = asyncio.run(
        script.retire_stale_growth_work(
            content_session_factory, apply=True, organization_id=world.inactive_org
        )
    )
    assert only_inactive.plans == []
