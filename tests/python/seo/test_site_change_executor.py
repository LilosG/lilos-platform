"""`seo.apply_site_change`: approved change set -> PR -> checks -> merge -> live proof.

Runs the real handler, the real publication state machine and a real database
against a fake GitHub publisher and a fake live-site fetch, so the only things
stubbed are the two external systems.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.execution.errors import WorkflowRunTypeMismatchError
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content import publish_handler
from apps.api.app.products.content.models import ContentPublication, PublishingTarget
from apps.api.app.products.seo import site_change_handler
from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeItem, SiteChangeSet
from apps.api.app.products.seo.contracts import ImplementationTaskCreate
from apps.api.app.products.seo.decision import SEOEvidenceInvalidError
from apps.api.app.products.seo.models import (
    SEOImplementationTask,
    SEOOpportunity,
    SEOPage,
    SEORecommendationRevision,
    SEOWebsite,
)
from apps.api.app.products.seo.service import SEOService
from apps.api.app.products.seo.verification import LivePage, read_implementation_truth
from scripts.seed_publishing_target_contracts import full_contract

REPOSITORY = "LilosG/coco-maya"
BRUNCH_PATH = "src/content/brunchPage.json"
OLD_TITLE = "Best Daily Brunch in Little Italy San Diego | Coco Maya"
OLD_DESCRIPTION = "Best brunch in Little Italy, San Diego at Coco Maya. Served daily until 3PM."
NEW_TITLE = "Best Brunch in San Diego | Daily Until 3PM"
NEW_DESCRIPTION = (
    "Daily brunch with a rooftop patio, craft cocktails and a full menu. Reserve today."
)

# The real singleton shape of LilosG/coco-maya:src/content/brunchPage.json (trimmed).
BRUNCH_JSON = (
    "{\n"
    '  "singleton": {\n'
    '    "breadcrumbLabel": "Brunch",\n'
    f'    "seo": {{ "title": "{OLD_TITLE}", "descriptionTemplate": "{OLD_DESCRIPTION}", '
    '"image": "/images/food-tacos-patio.jpg" },\n'
    '    "hero": { "title": "Daily Brunch", "subtitle": "Served every day." }\n'
    "  }\n"
    "}\n"
)


class FakeGitHub:
    """Just enough of a repository publisher to record what the executor does."""

    def __init__(
        self,
        files: dict[str, str],
        *,
        checks: dict[str, str] | None = None,
    ) -> None:
        self.files = dict(files)
        self.checks_result = checks or {"state": "success", "gate": "repository_ci"}
        self.calls: list[str] = []
        self.branches: list[str] = []
        self.puts: dict[str, str] = {}
        self.merged = False

    async def get_base_commit(self, repository_id: str, base_branch: str) -> str:
        self.calls.append("get_base_commit")
        return "base-sha"

    async def get_file(self, repository_id: str, ref: str, path: str) -> str | None:
        self.calls.append(f"get_file:{ref}:{path}")
        return self.files.get(path)

    async def create_branch(
        self, repository_id: str, base_branch: str, base_commit: str, branch_name: str
    ) -> str:
        self.calls.append("create_branch")
        self.branches.append(branch_name)
        return base_commit

    async def put_file(
        self,
        repository_id: str,
        branch_name: str,
        path: str,
        content: str,
        expected_blob_sha: str | None,
    ) -> str:
        self.calls.append(f"put_file:{path}")
        self.puts[path] = content
        return "blob-sha"

    async def create_pull_request(
        self,
        repository_id: str,
        branch_name: str,
        base_branch: str,
        title: str,
        idempotency_key: str,
    ) -> str:
        self.calls.append("create_pull_request")
        self.title = title
        return "42"

    async def get_pull_request(self, repository_id: str, pr_number: str) -> dict[str, object]:
        return {
            "head": {"sha": "head-sha"},
            "state": "closed" if self.merged else "open",
            "merged": self.merged,
            "merge_commit_sha": "merge-sha" if self.merged else None,
            "created_at": datetime.now(UTC).isoformat(),
        }

    async def checks(self, repository_id: str, revision_id: str) -> dict[str, str]:
        self.calls.append("checks")
        return self.checks_result

    async def merge_pull_request(
        self, repository_id: str, pr_number: str, expected_head_sha: str
    ) -> str:
        self.calls.append("merge_pull_request")
        self.merged = True
        return "merge-sha"

    async def deployment(self, repository_id: str, revision_id: str) -> dict[str, str]:
        self.calls.append("deployment")
        return {"state": "success", "url": "https://coco.example.invalid"}


def live_html(title: str, description: str) -> str:
    return (
        f'<html><head><title>{title}</title><meta name="description" content="{description}">'
        "</head><body><h1>Daily Brunch</h1></body></html>"
    )


@dataclass
class Scenario:
    organization_id: UUID
    revision_id: UUID
    page_id: UUID
    run_id: UUID
    task_id: UUID
    publication_id: UUID
    fake: FakeGitHub
    live: dict[str, str] = field(default_factory=dict)


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch the two external systems; hand tests a mutable holder for the fakes."""
    holder: dict[str, Any] = {"live_title": NEW_TITLE, "live_description": NEW_DESCRIPTION}

    async def token(*_args: object) -> str:
        return "token"

    async def fetch(url: str, *, cache_buster: str, client: object = None) -> LivePage:
        del client
        holder["fetched"] = (url, cache_buster)
        return LivePage(
            url=url,
            http_status=200,
            html=live_html(holder["live_title"], holder["live_description"]),
        )

    monkeypatch.setattr(publish_handler, "_provider_writes_enabled", lambda: True)
    monkeypatch.setattr(publish_handler, "_github_token_resolver", token)
    monkeypatch.setattr(publish_handler, "_content_publisher_factory", lambda _t: holder["fake"])
    monkeypatch.setattr(site_change_handler, "fetch_live_page", fetch)
    return holder


async def seed_scenario(
    session: AsyncSession,
    *,
    workflow_key: str = "seo.apply_site_change",
    repository_files: dict[str, str] | None = None,
    tamper_after_approval: bool = False,
    create_task: bool = True,
) -> Scenario:
    """An approved, fingerprinted change set on a mapped page, with its task created."""
    organization = Organization(
        name="Site change executor",
        slug=f"site-change-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    provider = Provider(
        key=f"github-{uuid4().hex[:8]}",
        name="GitHub",
        status="active",
        capabilities=["content.publish"],
        manifest_version=1,
    )
    session.add_all([organization, provider])
    await session.flush()
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider_id=provider.id,
        external_account_reference=REPOSITORY,
        status="connected",
        version=1,
    )
    session.add(connection)
    await session.flush()
    contract = full_contract(REPOSITORY)
    assert contract is not None
    session.add(
        PublishingTarget(
            organization_id=organization.id,
            connection_id=connection.id,
            key="primary",
            target_type="github_astro",
            repository_id=REPOSITORY,
            base_branch="main",
            allowed_path_prefix="src/content/blog",
            allowed_site_change_prefixes=["src/content"],
            frontmatter_contract=contract,
            status="active",
            version=1,
        )
    )
    website = SEOWebsite(
        organization_id=organization.id,
        location_id=None,
        key="primary",
        name="Coco",
        canonical_origin="https://coco.example.invalid",
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add(website)
    await session.flush()
    page = SEOPage(
        organization_id=organization.id,
        website_id=website.id,
        normalized_url="https://coco.example.invalid/brunch",
        observed_url="https://coco.example.invalid/brunch",
        canonical_url="https://coco.example.invalid/brunch",
        normalization_reasons=[],
        http_status=200,
        content_type="text/html",
        title=OLD_TITLE,
        meta_description=OLD_DESCRIPTION,
        h1="Daily Brunch",
        robots_directives=[],
        internal_links=[],
        external_links=[],
        word_count=400,
        structured_data_present=False,
        content_hash="c" * 64,
        indexability="indexable",
        technical_issues=[],
        crawl_depth=1,
        redirect_destination=None,
        quality_status="valid",
        body_text="Brunch",
        observed_at=datetime.now(UTC),
    )
    session.add(page)
    await session.flush()
    opportunity = SEOOpportunity(
        organization_id=organization.id,
        location_id=None,
        website_id=website.id,
        page_id=page.id,
        opportunity_type="gsc_low_ctr",
        deduplication_key=uuid4().hex + uuid4().hex,
        active_marker="active",
        evidence={"source": "google_search_console", "query": "brunch san diego"},
        source_versions=["gsc.v1"],
        score_version=2,
        priority_score=80,
        score_explanation={"score_policy_version": "opportunity_score.v2"},
        status="approved",
        version=1,
        attribution_state="attributed",
    )
    session.add(opportunity)
    await session.flush()

    change_set = SiteChangeSet(
        items=[
            SiteChangeItem(
                page_id=page.id,
                field=SiteChangeField.SEO_TITLE,
                current_value=OLD_TITLE,
                proposed_value=NEW_TITLE,
                rationale="Lead with the query and the daily hours.",
            ),
            SiteChangeItem(
                page_id=page.id,
                field=SiteChangeField.META_DESCRIPTION,
                current_value=OLD_DESCRIPTION,
                proposed_value=NEW_DESCRIPTION,
                rationale="Mention the patio and the call to action.",
            ),
        ]
    )
    stored = change_set.model_dump(mode="json")
    if tamper_after_approval:
        # The stored change set differs from the one whose digest a human approved.
        stored["items"][0]["proposed_value"] = "Buy cheap pills | Coco Maya"
    revision = SEORecommendationRevision(
        organization_id=organization.id,
        opportunity_id=opportunity.id,
        revision_number=1,
        proposed_action="Rewrite the brunch title and description.",
        evidence_references=[
            {
                "decision_context": {
                    "organization_id": str(organization.id),
                    "website_id": str(website.id),
                    "location_id": None,
                    "page_id": str(page.id),
                    "recommendation_class": "growth_change",
                }
            }
        ],
        expected_result_hypothesis="More clicks from brunch searches.",
        risk="low",
        effort="low",
        status="approved",
        created_at=datetime.now(UTC),
        change_set=stored,
        change_set_fingerprint=change_set.fingerprint(),
    )
    session.add(revision)
    await session.flush()

    service = ExecutionService()
    run = await service.start_named(
        session,
        organization.id,
        workflow_key,
        f"site-change-{uuid4().hex}",
        correlation_id="site-change-test",
        enqueue_job=False,
    )
    task_id = publication_id = uuid4()
    if create_task:
        task = await SEOService().create_implementation_task(
            session,
            organization.id,
            revision.id,
            ImplementationTaskCreate(
                workflow_run_id=run.id,
                target_type="page",
                target_reference=f"seo-page:{page.id}",
            ),
            actor_id=None,
            correlation_id="site-change-test",
        )
        task_id = task.id
        publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.organization_id == organization.id,
                ContentPublication.seo_recommendation_revision_id == revision.id,
            )
        )
        assert publication is not None
        publication_id = publication.id
    fake = FakeGitHub(repository_files or {BRUNCH_PATH: BRUNCH_JSON})
    return Scenario(
        organization_id=organization.id,
        revision_id=revision.id,
        page_id=page.id,
        run_id=run.id,
        task_id=task_id,
        publication_id=publication_id,
        fake=fake,
    )


async def run_handler(session_factory: async_sessionmaker[AsyncSession], scenario: Scenario) -> Any:
    async with session_factory() as session:
        return await site_change_handler.handle_seo_apply_site_change(
            session,
            organization_id=scenario.organization_id,
            location_id=None,
            input_document={"publication_id": str(scenario.publication_id)},
            correlation_id="site-change-test",
            workflow_run_id=scenario.run_id,
        )


async def load_publication(
    session_factory: async_sessionmaker[AsyncSession], scenario: Scenario
) -> ContentPublication:
    async with session_factory() as session:
        publication = await session.get(ContentPublication, scenario.publication_id)
        assert publication is not None
        return publication


@pytest.mark.integration
@pytest.mark.anyio
async def test_apply_site_change_opens_pr_touching_only_approved_values(
    seo_session_factory: async_sessionmaker[AsyncSession], wired: dict[str, Any]
) -> None:
    async with seo_session_factory.begin() as session:
        scenario = await seed_scenario(session)
    wired["fake"] = scenario.fake

    outcome = await run_handler(seo_session_factory, scenario)

    assert outcome.result == "succeeded"
    fake = scenario.fake
    # Exactly one file carried the change, and it is branch-namespaced for site changes.
    assert list(fake.puts) == [BRUNCH_PATH]
    assert fake.branches and fake.branches[0].startswith("lilos-site-change-")
    assert (
        fake.title
        == "SEO: update meta_description, seo_title on https://coco.example.invalid/brunch"
    )
    # Inverse proof: put the two original values back and the file must be
    # byte-identical to the repository's -- nothing else moved.
    restored = fake.puts[BRUNCH_PATH].replace(json.dumps(NEW_TITLE), json.dumps(OLD_TITLE))
    restored = restored.replace(json.dumps(NEW_DESCRIPTION), json.dumps(OLD_DESCRIPTION))
    assert restored == BRUNCH_JSON
    assert NEW_TITLE in fake.puts[BRUNCH_PATH] and NEW_DESCRIPTION in fake.puts[BRUNCH_PATH]
    # The pull request merged only after the build gate passed, and before verification.
    assert fake.calls.index("checks") < fake.calls.index("merge_pull_request")

    publication = await load_publication(seo_session_factory, scenario)
    assert publication.publication_kind == "site_change"
    assert publication.status == "verified"
    assert publication.external_pull_request_id == "42"
    assert publication.build_status == "repository_ci:success"
    assert publication.verification_status == "verified"
    assert publication.verification_evidence is not None
    assert publication.verification_evidence["result"] == "verified"
    assert wired["fetched"][1] == "merge-sha"[:12]


@pytest.mark.integration
@pytest.mark.anyio
async def test_apply_site_change_refuses_fingerprint_mismatch(
    seo_session_factory: async_sessionmaker[AsyncSession], wired: dict[str, Any]
) -> None:
    async with seo_session_factory.begin() as session:
        scenario = await seed_scenario(session)
        # Approved revisions are frozen by a database trigger, so model an out-of-band
        # edit (a superuser or a bad restore) by switching triggers off for this one
        # statement. The reserved publication and the recorded approval keep the
        # approved digest; only the stored change set moves.
        revision = await session.get(SEORecommendationRevision, scenario.revision_id)
        assert revision is not None and revision.change_set is not None
        edited = json.loads(json.dumps(revision.change_set))
        edited["items"][0]["proposed_value"] = "Buy cheap pills | Coco Maya"
        await session.execute(text("SET LOCAL session_replication_role = replica"))
        await session.execute(
            update(SEORecommendationRevision)
            .where(SEORecommendationRevision.id == scenario.revision_id)
            .values(change_set=edited)
        )
    wired["fake"] = scenario.fake

    outcome = await run_handler(seo_session_factory, scenario)

    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == "SITE_CHANGE_FINGERPRINT_MISMATCH"
    assert scenario.fake.calls == []  # refused before any provider contact
    publication = await load_publication(seo_session_factory, scenario)
    assert publication.status == "failed"
    assert publication.safe_error_code == "SITE_CHANGE_FINGERPRINT_MISMATCH"


@pytest.mark.integration
@pytest.mark.anyio
async def test_create_implementation_task_refuses_a_tampered_change_set(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        with pytest.raises(SEOEvidenceInvalidError) as raised:
            await seed_scenario(session, tamper_after_approval=True)
    assert raised.value.limitation_code == "SITE_CHANGE_FINGERPRINT_MISMATCH"


@pytest.mark.integration
@pytest.mark.anyio
async def test_apply_site_change_repo_drift_is_site_mapping_required(
    seo_session_factory: async_sessionmaker[AsyncSession], wired: dict[str, Any]
) -> None:
    drifted = BRUNCH_JSON.replace(OLD_TITLE, "A title someone edited by hand")
    async with seo_session_factory.begin() as session:
        scenario = await seed_scenario(session, repository_files={BRUNCH_PATH: drifted})
    wired["fake"] = scenario.fake

    outcome = await run_handler(seo_session_factory, scenario)

    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == "SITE_MAPPING_REQUIRED"
    # Nothing was written: no branch, no file, no pull request, no merge.
    assert scenario.fake.branches == []
    assert scenario.fake.puts == {}
    assert "merge_pull_request" not in scenario.fake.calls
    publication = await load_publication(seo_session_factory, scenario)
    assert publication.status == "failed"
    assert publication.safe_error_code == "SITE_MAPPING_REQUIRED"


@pytest.mark.integration
@pytest.mark.anyio
async def test_create_implementation_task_selects_site_change_workflow(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        # A run started for any other workflow cannot be consumed by a change set.
        with pytest.raises(WorkflowRunTypeMismatchError):
            await seed_scenario(session, workflow_key="seo.crawl_or_analysis")

    async with seo_session_factory.begin() as session:
        scenario = await seed_scenario(session)

    async with seo_session_factory() as session:
        publication = await session.get(ContentPublication, scenario.publication_id)
        assert publication is not None
        assert publication.publication_kind == "site_change"
        assert publication.status == "reserved"
        assert publication.content_item_id is None and publication.content_revision_id is None
        assert publication.seo_recommendation_revision_id == scenario.revision_id
        assert publication.change_set_fingerprint is not None
        run = await session.get(WorkflowRun, scenario.run_id)
        assert run is not None
        assert run.input_document["publication_id"] == str(publication.id)
        job = await session.scalar(select(Job).where(Job.idempotency_key == f"run:{run.id}"))
        assert job is not None and job.max_attempts == 30
        task = await session.get(SEOImplementationTask, scenario.task_id)
        assert task is not None and task.workflow_run_id == run.id


@pytest.mark.integration
@pytest.mark.anyio
async def test_live_verification_mismatch_reports_observed_value(
    seo_session_factory: async_sessionmaker[AsyncSession], wired: dict[str, Any]
) -> None:
    async with seo_session_factory.begin() as session:
        scenario = await seed_scenario(session)
    wired["fake"] = scenario.fake
    wired["live_title"] = "Still the old cached title"  # production did not pick up the change

    outcome = await run_handler(seo_session_factory, scenario)

    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == "SITE_CHANGE_VERIFICATION_FAILED"
    publication = await load_publication(seo_session_factory, scenario)
    assert publication.status == "failed"
    assert publication.verification_status == "failed"
    assert publication.verification_evidence is not None
    checks: Any = publication.verification_evidence["checks"]
    title_check = next(check for check in checks if check["field"] == "seo_title")
    assert title_check["state"] == "mismatch"
    assert title_check["expected"] == NEW_TITLE
    assert title_check["observed"] == "Still the old cached title"


@pytest.mark.integration
@pytest.mark.anyio
async def test_implementation_truth_uses_site_change_proof(
    seo_session_factory: async_sessionmaker[AsyncSession], wired: dict[str, Any]
) -> None:
    async with seo_session_factory.begin() as session:
        scenario = await seed_scenario(session)
    wired["fake"] = scenario.fake

    async def truth() -> dict[str, object]:
        async with seo_session_factory.begin() as session:
            run = await session.get(WorkflowRun, scenario.run_id)
            assert run is not None
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            task = await session.get(SEOImplementationTask, scenario.task_id)
            revision = await session.get(SEORecommendationRevision, scenario.revision_id)
            assert task is not None and revision is not None
            opportunity = await session.get(SEOOpportunity, revision.opportunity_id)
            assert opportunity is not None
            return await read_implementation_truth(session, task, revision, opportunity)

    # Before the executor has run there is nothing to verify yet.
    assert (await truth())["result"] == "pending"

    assert (await run_handler(seo_session_factory, scenario)).result == "succeeded"
    proof = await truth()
    assert proof["result"] == "verified"
    assert proof["verification_method"] == "site_change_live_read_back"
    actual = proof["actual"]
    assert isinstance(actual, dict)
    assert actual["pull_request"] == "42"
    assert {check["field"]: check["observed"] for check in actual["live_checks"]} == {
        "seo_title": NEW_TITLE,
        "meta_description": NEW_DESCRIPTION,
    }
