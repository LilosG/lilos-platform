# ruff: noqa: E501
"""Orphaned pre-attribution Growth and Content work is retired; live and newer work is not."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.agents.models import AgentRun, AgentSession
from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.growth.models import GrowthAction, GrowthInitiative
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.products.content.models import (
    ContentItem,
    ContentOpportunity,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)
from apps.api.app.products.seo.models import SEOOpportunity, SEOPage, SEOWebsite
from scripts import retire_stale_growth_work as script

from .test_retire_stale_growth_work import NEW, OLD, _org


async def _seed(session: AsyncSession, org_id: UUID) -> dict[str, UUID]:
    rows: dict[str, UUID] = {}
    location = Location(
        organization_id=org_id,
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
        organization_id=org_id,
        location_id=location.id,
        key=f"site-{uuid4().hex[:6]}",
        name="Site",
        canonical_origin="https://example.invalid",
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add(website)
    await session.flush()
    page = SEOPage(
        organization_id=org_id,
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

    def seo(key: str, state: str) -> SEOOpportunity:
        return SEOOpportunity(
            organization_id=org_id,
            location_id=location.id,
            website_id=website.id,
            page_id=page.id if state == "attributed" else None,
            attribution_state=state,
            opportunity_type="gsc_low_ctr",
            deduplication_key=key,
            active_marker="active",
            evidence={"query": key},
            source_versions=["gsc.v1"],
            score_version=1,
            priority_score=50,
            score_explanation={},
            status="identified",
            version=1,
        )

    live_seo, query_new = seo("live", "attributed"), seo("query-new", "query_only")
    session.add_all([live_seo, query_new])
    await session.flush()

    def content_opportunity(source: str, created: datetime) -> ContentOpportunity:
        return ContentOpportunity(
            organization_id=org_id,
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

    ghost = f"growth-action:{uuid4()}"  # no such action
    opportunities = {
        "orphan_old": content_opportunity(ghost, OLD),
        "orphan_new": content_opportunity(f"growth-action:{uuid4()}", NEW),
        "live": content_opportunity(f"seo-opportunity:{live_seo.id}", OLD),
        "eligible": content_opportunity(f"seo-opportunity:{query_new.id}", NEW),
    }
    session.add_all(opportunities.values())
    await session.flush()

    def item(name: str, status: str, created: datetime, opportunity: str | None) -> ContentItem:
        row = ContentItem(
            organization_id=org_id,
            location_id=location.id,
            opportunity_id=opportunities[opportunity].id if opportunity else None,
            content_type="blog",
            title=name,
            slug=name.replace("_", "-"),
            status=status,
            version=1,
            created_at=created,
        )
        session.add(row)
        return row

    items = {
        "orphan_old": item("orphan_old", "brief_ready", OLD, "orphan_old"),
        "orphan_new": item("orphan_new", "brief_ready", NEW, "orphan_new"),
        "eligible": item("eligible", "brief_ready", NEW, "eligible"),
        "pub_none_old": item("pub_none_old", "publishing", OLD, None),
        "pub_nopr_old": item("pub_nopr_old", "publishing", OLD, None),
        "pub_none_new": item("pub_none_new", "publishing", NEW, None),
        "pub_live_old": item("pub_live_old", "publishing", OLD, "live"),
    }
    await session.flush()
    rows.update({f"item_{k}": v.id for k, v in items.items()})
    rows.update({f"opportunity_{k}": v.id for k, v in opportunities.items()})

    # A publication that never opened a pull request.
    provider = Provider(
        key=f"github-{uuid4().hex[:6]}", name="GitHub", status="active", capabilities=[]
    )
    session.add(provider)
    await session.flush()
    connection = IntegrationConnection(
        organization_id=org_id,
        provider_id=provider.id,
        external_account_reference="org/site",
        status="connected",
    )
    session.add(connection)
    await session.flush()
    target = PublishingTarget(
        organization_id=org_id,
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
        key=f"content.publish.{uuid4().hex[:6]}", name="P", owner="content"
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
        organization_id=org_id,
        location_id=location.id,
        workflow_version_id=version.id,
        product_key="content",
        trigger_type="manual",
        idempotency_key=f"run-{uuid4().hex}",
        request_hash="hash",
        input_document={},
        correlation_id="orphan-test",
    )
    session.add(workflow_run)
    await session.flush()
    revision = ContentRevision(
        organization_id=org_id,
        content_item_id=items["pub_nopr_old"].id,
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
            organization_id=org_id,
            publication_kind="content",
            content_item_id=items["pub_nopr_old"].id,
            content_revision_id=revision.id,
            publishing_target_id=target.id,
            workflow_run_id=workflow_run.id,
            idempotency_key=f"pub-{uuid4().hex[:8]}",
            status="reserved",
            target_path="src/content/x.md",
        )
    )

    # Growth.
    agent_session = AgentSession(
        organization_id=org_id,
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
    planner = AgentRun(
        organization_id=org_id,
        location_id=location.id,
        workflow_run_id=workflow_run.id,
        agent_session_id=agent_session.id,
        skill_key="growth.planner",
        skill_version=6,
        hermes_session_id=agent_session.hermes_session_key,
        correlation_id="orphan-test",
        status="completed",
        capability_snapshot={},
        output_references=[],
        source_references=[],
        event_count=0,
    )
    session.add(planner)
    await session.flush()

    live_ref = f"seo-opportunity:{live_seo.id}"

    async def initiative(
        name: str, created: datetime, actions: list[tuple[str, str, str, list[str], datetime]]
    ) -> None:
        row = GrowthInitiative(
            organization_id=org_id,
            location_id=location.id,
            planner_agent_run_id=planner.id,
            idempotency_key=f"g-{name}-{uuid4().hex[:8]}",
            objective=name,
            rationale="r",
            source_references=[],
            priority_score=10,
            confidence=Decimal("0.5"),
            status="executing",
            created_at=created,
        )
        session.add(row)
        await session.flush()
        rows[f"initiative_{name}"] = row.id
        for position, (key, status, action_type, evidence, made) in enumerate(actions):
            action = GrowthAction(
                organization_id=org_id,
                initiative_id=row.id,
                action_key=key,
                product_key="seo",
                action_type=action_type,
                target_reference="the page",
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
                created_at=made,
            )
            session.add(action)
            await session.flush()
            rows[f"action_{key}"] = action.id

    known = "site_implementation"
    await initiative("orphan", OLD, [("orphan_old", "proposed", known, [], OLD)])
    await initiative("unknown", NEW, [("unknown_new", "proposed", "made_up_type", [], NEW)])
    await initiative("newer", NEW, [("orphan_new", "proposed", known, [], NEW)])
    await initiative(
        "live",
        OLD,
        [
            ("live_known", "proposed", known, [live_ref], OLD),
            ("live_unknown", "proposed", "made_up_type", [live_ref], OLD),
        ],
    )
    await initiative("done", OLD, [("done_old", "completed", known, [], OLD)])
    return rows


@pytest.fixture
def world(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, dict[str, UUID], dict[str, UUID]]:
    async def seed() -> tuple[UUID, dict[str, UUID], dict[str, UUID]]:
        async with content_session_factory.begin() as session:
            active = _org("Orphan Active", OrganizationStatus.ACTIVE)
            paused = _org("Orphan Paused", OrganizationStatus.PAUSED)
            session.add_all([active, paused])
            await session.flush()
            return active.id, await _seed(session, active.id), await _seed(session, paused.id)

    return asyncio.run(seed())


async def _status(
    factory: async_sessionmaker[AsyncSession], rows: dict[str, UUID]
) -> dict[str, str]:
    out: dict[str, str] = {}
    async with factory() as session:
        for key, row_id in rows.items():
            for model in (ContentItem, ContentOpportunity, GrowthAction, GrowthInitiative):
                row = await session.get(model, row_id)
                if row is not None:
                    out[key] = str(getattr(row, "status"))  # noqa: B009
                    break
    return out


def _apply(factory: async_sessionmaker[AsyncSession]) -> script.RetirementReport:
    return asyncio.run(script.retire_stale_growth_work(factory, apply=True))


@pytest.mark.integration
def test_each_orphan_rule_retires_only_what_it_should(
    content_session_factory: async_sessionmaker[AsyncSession],
    world: tuple[UUID, dict[str, UUID], dict[str, UUID]],
) -> None:
    org, rows, _ = world
    report = _apply(content_session_factory)
    status = asyncio.run(_status(content_session_factory, rows))
    reasons = {
        (change.model, change.row_id): change.reason
        for plan in report.plans
        for change in plan.changes
    }

    # 1. No SEO source before the cutoff, or an action type outside the enum at any age.
    assert status["action_orphan_old"] == "cancelled"
    assert reasons[("growth_action", rows["action_orphan_old"])] == "pre_attribution_orphan"
    assert status["action_unknown_new"] == "cancelled"
    assert reasons[("growth_action", rows["action_unknown_new"])] == "unknown_action_type"
    # 2. Initiatives with no live actions left.
    assert status["initiative_orphan"] == status["initiative_unknown"] == "cancelled"
    assert reasons[("growth_initiative", rows["initiative_orphan"])] == "no_live_actions"
    # 3. Publishing with no pull request, created before the cutoff.
    assert status["item_pub_none_old"] == status["item_pub_nopr_old"] == "archived"
    assert reasons[("content_item", rows["item_pub_none_old"])] == "PUBLICATION_HAS_NO_PULL_REQUEST"
    assert reasons[("content_item", rows["item_pub_nopr_old"])] == "PUBLICATION_HAS_NO_PULL_REQUEST"
    # 4. Orphaned source (the Growth action no longer exists), created before the cutoff.
    assert status["item_orphan_old"] == "archived"
    assert status["opportunity_orphan_old"] == "archived"
    assert reasons[("content_item", rows["item_orphan_old"])] == "orphaned_source"
    assert reasons[("content_opportunity", rows["opportunity_orphan_old"])] == "orphaned_source"

    # 5. Newer work, live attributed work and eligible_for_new_page stay untouched.
    assert status["action_orphan_new"] == "proposed" and status["initiative_newer"] == "executing"
    assert status["item_pub_none_new"] == "publishing"
    assert (
        status["item_orphan_new"] == "brief_ready"
        and status["opportunity_orphan_new"] == "accepted"
    )
    assert status["item_eligible"] == "brief_ready" and status["opportunity_eligible"] == "accepted"
    # Live attributed work wins over an unknown action type; completed work keeps its initiative.
    assert status["action_live_known"] == status["action_live_unknown"] == "proposed"
    assert status["initiative_live"] == "executing"
    assert status["action_done_old"] == "completed" and status["initiative_done"] == "executing"
    assert status["item_pub_live_old"] == "publishing" and status["opportunity_live"] == "accepted"
    assert org in {plan.organization_id for plan in report.plans}


@pytest.mark.integration
def test_second_apply_changes_nothing_and_inactive_org_is_untouched(
    content_session_factory: async_sessionmaker[AsyncSession],
    world: tuple[UUID, dict[str, UUID], dict[str, UUID]],
) -> None:
    org, rows, inactive_rows = world
    before_inactive = asyncio.run(_status(content_session_factory, inactive_rows))
    first = _apply(content_session_factory)
    after_first = asyncio.run(_status(content_session_factory, rows))
    assert sum(len(plan.changes) for plan in first.plans) > 0

    async def audit_total() -> int:
        async with content_session_factory() as session:
            return len(
                list(
                    await session.scalars(
                        select(AuditEvent.id).where(AuditEvent.organization_id == org)
                    )
                )
            )

    audits = asyncio.run(audit_total())
    second = _apply(content_session_factory)

    assert sum(len(plan.changes) for plan in second.plans) == 0
    assert asyncio.run(_status(content_session_factory, rows)) == after_first
    assert asyncio.run(audit_total()) == audits
    assert asyncio.run(_status(content_session_factory, inactive_rows)) == before_inactive
    assert before_inactive["item_pub_none_old"] == "publishing"  # never processed


@pytest.mark.integration
def test_dry_run_reports_the_same_table_without_writing(
    content_session_factory: async_sessionmaker[AsyncSession],
    world: tuple[UUID, dict[str, UUID], dict[str, UUID]],
) -> None:
    _, rows, _ = world
    before = asyncio.run(_status(content_session_factory, rows))
    dry = asyncio.run(script.retire_stale_growth_work(content_session_factory, apply=False))
    assert asyncio.run(_status(content_session_factory, rows)) == before
    applied = _apply(content_session_factory)
    assert script.format_report(dry) == script.format_report(applied)
