"""scripts.recover_stuck_publications: a governed site change stuck on a GitHub read."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.github_adapter import GitHubPermissionError
from scripts.recover_stuck_publications import Action, Kind, recover_stuck_publications

from .test_site_change_executor import (  # noqa: F401 - `wired` is a fixture
    FakeGitHub,
    Scenario,
    load_publication,
    run_handler,
    seed_scenario,
    wired,
)


class ForbiddenChecks(FakeGitHub):
    """GitHub answers 403 'Resource not accessible by integration' to the status read."""

    def __init__(self, files: dict[str, str]) -> None:
        super().__init__(files)
        self.permission_granted = False

    async def checks(self, repository_id: str, revision_id: str) -> dict[str, str]:
        if not self.permission_granted:
            raise GitHubPermissionError("403: the app installation lacks permission")
        return await super().checks(repository_id, revision_id)


async def _stuck_scenario(
    factory: async_sessionmaker[AsyncSession],
    wired: dict[str, Any],  # noqa: F811
) -> tuple[Scenario, ForbiddenChecks]:
    async with factory.begin() as session:
        scenario = await seed_scenario(session)
    fake = ForbiddenChecks(scenario.fake.files)
    wired["fake"] = fake
    outcome = await run_handler(factory, scenario)
    assert (outcome.result, outcome.safe_error) == (
        "permanent_failure",
        "GITHUB_APP_PERMISSION_MISSING",
    )
    publication = await load_publication(factory, scenario)
    assert publication.status == "reconciliation_required"
    async with factory.begin() as session:
        run = await session.get(WorkflowRun, scenario.run_id)
        assert run is not None
        run.status = "failed"
        run.failure_code = "GITHUB_APP_PERMISSION_MISSING"
        # Its earlier job is spent, as in production after thirty attempts.
        for job in await session.scalars(select(Job).where(Job.workflow_run_id == run.id)):
            job.status = "dead_lettered"
    return scenario, fake


async def _jobs(factory: async_sessionmaker[AsyncSession], scenario: Scenario) -> list[Job]:
    async with factory() as session:
        return list(
            await session.scalars(select(Job).where(Job.workflow_run_id == scenario.run_id))
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_site_change_waits_while_github_refuses_the_checks_read(
    seo_session_factory: async_sessionmaker[AsyncSession],
    wired: dict[str, Any],  # noqa: F811
) -> None:
    scenario, _fake = await _stuck_scenario(seo_session_factory, wired)

    report = await recover_stuck_publications(
        seo_session_factory,
        Settings(),
        apply=True,
        actor_id=uuid4(),
        organization_id=scenario.organization_id,
    )

    [item] = report.items
    assert (item.kind, item.action) == (Kind.SITE_CHANGE, Action.WAIT)
    assert item.detail == "GITHUB_APP_PERMISSION_MISSING"
    assert "pull request" in item.provider_truth or "could not be read" in item.provider_truth
    assert {job.status for job in await _jobs(seo_session_factory, scenario)} <= {"dead_lettered"}
    run = None
    async with seo_session_factory() as session:
        run = await session.get(WorkflowRun, scenario.run_id)
    assert run is not None and run.status == "failed"


@pytest.mark.integration
@pytest.mark.anyio
async def test_dry_run_reports_the_resume_and_changes_nothing_then_apply_resumes_the_run(
    seo_session_factory: async_sessionmaker[AsyncSession],
    wired: dict[str, Any],  # noqa: F811
) -> None:
    scenario, fake = await _stuck_scenario(seo_session_factory, wired)
    fake.permission_granted = True  # someone granted Commit statuses: read

    dry = await recover_stuck_publications(
        seo_session_factory,
        Settings(),
        apply=False,
        organization_id=scenario.organization_id,
    )

    [item] = dry.items
    assert (item.kind, item.action) == (Kind.SITE_CHANGE, Action.RESUME)
    assert "open" in item.provider_truth and "checks success" in item.provider_truth
    spent = await _jobs(seo_session_factory, scenario)
    assert {job.status for job in spent} <= {"dead_lettered"}  # nothing was kept

    actor = uuid4()
    applied = await recover_stuck_publications(
        seo_session_factory,
        Settings(),
        apply=True,
        actor_id=actor,
        organization_id=scenario.organization_id,
    )

    assert [i.action for i in applied.items] == [Action.RESUME]
    job = next(j for j in await _jobs(seo_session_factory, scenario) if j.status == "queued")
    assert job.max_attempts == 30
    async with seo_session_factory() as session:
        run = await session.get(WorkflowRun, scenario.run_id)
    assert run is not None and (run.status, run.failure_code) == ("queued", None)

    # The resumed run continues from the existing pull request: checks, merge, live proof.
    outcome = await run_handler(seo_session_factory, scenario)
    assert outcome.result == "succeeded"
    assert fake.calls.count("create_pull_request") == 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_archived_and_excluded_organizations_are_skipped_without_a_provider_call(
    seo_session_factory: async_sessionmaker[AsyncSession],
    wired: dict[str, Any],  # noqa: F811
) -> None:
    scenario, fake = await _stuck_scenario(seo_session_factory, wired)
    fake.permission_granted = True
    async with seo_session_factory.begin() as session:
        organization = await session.get(Organization, scenario.organization_id)
        assert organization is not None
        organization.status = OrganizationStatus.ARCHIVED
        organization.archived_at = organization.created_at
    calls_before = list(fake.calls)

    report = await recover_stuck_publications(
        seo_session_factory, Settings(), apply=True, actor_id=uuid4()
    )

    [item] = report.items
    assert (item.action, item.detail) == (Action.SKIPPED, "ORGANIZATION_ARCHIVED")
    assert fake.calls == calls_before
    assert {job.status for job in await _jobs(seo_session_factory, scenario)} <= {"dead_lettered"}

    async with seo_session_factory.begin() as session:
        organization = await session.get(Organization, scenario.organization_id)
        assert organization is not None
        organization.status = OrganizationStatus.ACTIVE
        organization.archived_at = None
        organization.name = "Wheyland Electric"
    report = await recover_stuck_publications(
        seo_session_factory, Settings(), apply=True, actor_id=uuid4()
    )
    assert [(i.action, i.detail) for i in report.items] == [
        (Action.SKIPPED, "ORGANIZATION_EXCLUDED")
    ]
