"""Replays of the production `content.publish` failures against PostgreSQL.

Each case is the exact shape of a failed production run (2026-09-16 to 2026-09-21) driven
through the real handler and the real schema, with only the GitHub adapter faked.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content import publish_handler
from apps.api.app.products.content.github_adapter import GitHubPermissionError
from apps.api.app.products.content.models import (
    ContentItem,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)

# The Coco Maya and Louisiana Purchase contracts as recorded in production.
COCO_MAYA_CONTRACT: dict[str, object] = {
    "required": ["title", "seoTitle", "description", "date", "image", "imageAlt"],
    "field_names": {"image_alt": "imageAlt", "seo_title": "seoTitle", "publish_date": "date"},
    "file_extensions": [".mdx"],
}
LOUISIANA_PURCHASE_CONTRACT: dict[str, object] = {
    "required": ["title", "description", "date", "category"],
    "field_names": {"image_alt": "imageAlt", "publish_date": "date"},
    "enums": {
        "category": [
            "Events",
            "Private Events",
            "North Park Guide",
            "Cocktails",
            "Brunch",
            "Dinner",
        ]
    },
    "defaults": {"category": "Events"},
    "file_extensions": [".mdx"],
}


class FakeRepository:
    """A GitHub repository whose pull request is checked, merged and deployed on demand."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.calls: list[str] = []
        self.deployment_state: dict[str, str] = {"state": "success", "url": "https://site.test"}
        self.checks_error: Exception | None = None

    async def get_base_commit(self, repository_id: str, base_branch: str) -> str:
        return "base-commit"

    async def create_branch(
        self, repository_id: str, base_branch: str, base_commit: str, branch_name: str
    ) -> str:
        self.calls.append("create_branch")
        return branch_name

    async def put_file(
        self,
        repository_id: str,
        branch_name: str,
        path: str,
        content: str,
        expected_blob_sha: str | None,
    ) -> str:
        self.calls.append("put_file")
        self.files[path] = content
        return "blob"

    async def create_pull_request(
        self, repository_id: str, branch_name: str, base_branch: str, title: str, key: str
    ) -> str:
        self.calls.append("create_pull_request")
        return "8"

    async def get_pull_request(self, repository_id: str, pr_number: str) -> dict[str, object]:
        return {"head": {"sha": "head-sha"}, "merged": False, "state": "open"}

    async def checks(self, repository_id: str, revision_id: str) -> dict[str, str]:
        if self.checks_error is not None:
            raise self.checks_error
        return {"state": "success", "gate": "vercel_preview"}

    async def merge_pull_request(
        self, repository_id: str, pr_number: str, expected_head_sha: str
    ) -> str:
        self.calls.append("merge")
        return "merge-sha"

    async def deployment(self, repository_id: str, revision_id: str) -> dict[str, str]:
        return self.deployment_state


@pytest.fixture
def repository(monkeypatch: pytest.MonkeyPatch) -> FakeRepository:
    repo = FakeRepository()

    async def token(*args: object, **kwargs: object) -> str:
        return "token"

    monkeypatch.setattr(publish_handler, "_provider_writes_enabled", lambda: True)
    monkeypatch.setattr(publish_handler, "_github_token_resolver", token)
    monkeypatch.setattr(publish_handler, "_content_publisher_factory", lambda _token: repo)
    return repo


async def _seed(
    session: AsyncSession,
    *,
    contract: dict[str, object],
    target_path: str,
    frontmatter: dict[str, object],
) -> tuple[UUID, UUID, UUID, UUID]:
    org = Organization(
        name="Publish replay",
        slug=f"publish-replay-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()
    provider = Provider(
        key=f"github-{uuid4().hex[:6]}", name="GitHub", status="active", capabilities=[]
    )
    session.add(provider)
    await session.flush()
    connection = IntegrationConnection(
        organization_id=org.id,
        provider_id=provider.id,
        external_account_reference="installation:1",
        status="connected",
    )
    session.add(connection)
    await session.flush()
    target = PublishingTarget(
        organization_id=org.id,
        connection_id=connection.id,
        key="primary",
        target_type="github_astro",
        repository_id="LilosG/site",
        base_branch="main",
        allowed_path_prefix="src/content",
        frontmatter_contract=contract,
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
    run = WorkflowRun(
        organization_id=org.id,
        workflow_version_id=version.id,
        product_key="content",
        trigger_type="api",
        idempotency_key=f"run-{uuid4().hex}",
        request_hash="hash",
        input_document={},
        correlation_id="publish-replay",
    )
    session.add(run)
    item = ContentItem(
        organization_id=org.id,
        content_type="blog",
        title=str(frontmatter["title"]),
        slug="replay",
        status="publishing",
        version=1,
    )
    session.add(item)
    await session.flush()
    revision = ContentRevision(
        organization_id=org.id,
        content_item_id=item.id,
        revision_number=1,
        body="Looking for a place?\n\nCome by.",
        frontmatter=frontmatter,
        content_hash=uuid4().hex + uuid4().hex,
        created_by_type="ai",
        approved_fact_revision_ids=[],
        status="approved",
        validation_document={},
    )
    session.add(revision)
    await session.flush()
    publication = ContentPublication(
        organization_id=org.id,
        publication_kind="content",
        content_item_id=item.id,
        content_revision_id=revision.id,
        publishing_target_id=target.id,
        workflow_run_id=run.id,
        idempotency_key=f"pub-{uuid4().hex[:8]}",
        status="reserved",
        target_path=target_path,
    )
    session.add(publication)
    await session.flush()
    return org.id, publication.id, item.id, revision.id


async def _publish(
    factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    publication_id: UUID,
    overrides: dict[str, str],
) -> tuple[str, str | None]:
    async with factory() as session:
        outcome = await publish_handler.handle_content_publish(
            session,
            organization_id=organization_id,
            location_id=None,
            input_document={
                "publication_id": str(publication_id),
                "frontmatter_overrides": overrides,
            },
            correlation_id="publish-replay",
            workflow_run_id=uuid4(),
        )
        return outcome.result, outcome.safe_error


async def _states(
    factory: async_sessionmaker[AsyncSession], publication_id: UUID, item_id: UUID, rev_id: UUID
) -> tuple[Any, Any, Any]:
    async with factory() as session:
        publication = await session.get(ContentPublication, publication_id)
        item = await session.get(ContentItem, item_id)
        revision = await session.get(ContentRevision, rev_id)
        assert publication and item and revision
        return publication, item, revision


@pytest.mark.integration
@pytest.mark.anyio
async def test_coco_maya_content_publishes_end_to_end_and_leaves_the_approved_revision_alone(
    content_session_factory: async_sessionmaker[AsyncSession], repository: FakeRepository
) -> None:
    # Run 19f65054 / acb2d660: revision frontmatter is only title + description, with an image
    # supplied by the operator. It used to fail CONTENT_FRONTMATTER_INCOMPLETE.
    async with content_session_factory.begin() as session:
        org_id, pub_id, item_id, rev_id = await _seed(
            session,
            contract=COCO_MAYA_CONTRACT,
            target_path="src/content/blog/brunch.mdx",
            frontmatter={
                "title": "Daily Brunch in Little Italy, San Diego | Coco Maya",
                "description": "Find daily brunch in Little Italy, San Diego at Coco Maya.",
            },
        )

    result = await _publish(
        content_session_factory,
        org_id,
        pub_id,
        {"image": "/images/elevated-patio.webp", "image_alt": "Coco Maya Little Italy Brunch"},
    )

    # Run 82045938: reaching `verified` used to raise HANDLER_EXCEPTION, because the handler
    # moved the approved revision to `published` and the immutability trigger rejects that.
    assert result == ("succeeded", None)
    publication, item, revision = await _states(content_session_factory, pub_id, item_id, rev_id)
    assert publication.status == "verified"
    assert publication.published_url == "https://site.test"
    assert item.status == "published"
    assert item.approved_revision_id == rev_id
    assert revision.status == "approved"
    written = repository.files["src/content/blog/brunch.mdx"]
    for line in (
        'seoTitle: "Daily Brunch in Little Italy, San Diego | Coco Maya"',
        'image: "/images/elevated-patio.webp"',
        'imageAlt: "Coco Maya Little Italy Brunch"',
    ):
        assert line in written
    assert "date:" in written


@pytest.mark.integration
@pytest.mark.anyio
async def test_coco_maya_content_without_an_image_is_blocked_before_any_branch_exists(
    content_session_factory: async_sessionmaker[AsyncSession], repository: FakeRepository
) -> None:
    # Run 5f6730e6 (PR 8): no overrides, so the file shipped without seoTitle/date/image and
    # the site build failed on the merged commit (CONTENT_DEPLOYMENT_FAILED).
    async with content_session_factory.begin() as session:
        org_id, pub_id, item_id, rev_id = await _seed(
            session,
            contract=COCO_MAYA_CONTRACT,
            target_path="src/content/blog/little-italy-restaurants.mdx",
            frontmatter={
                "title": "Restaurants in Little Italy, San Diego | Coco Maya",
                "description": "Discover Coco Maya in Little Italy, San Diego at 1660 India St.",
            },
        )

    result = await _publish(content_session_factory, org_id, pub_id, {})

    assert result == ("permanent_failure", "CONTENT_FRONTMATTER_INCOMPLETE")
    assert repository.calls == []
    publication, item, _ = await _states(content_session_factory, pub_id, item_id, rev_id)
    assert publication.status == "failed"
    assert publication.safe_error_code == "CONTENT_FRONTMATTER_INCOMPLETE"


@pytest.mark.integration
@pytest.mark.anyio
async def test_louisiana_purchase_content_gets_the_required_category(
    content_session_factory: async_sessionmaker[AsyncSession], repository: FakeRepository
) -> None:
    # Run d3406d52 (PR 9): the file had no `category`, which the site schema requires, so the
    # Vercel check failed (CONTENT_CHECKS_FAILED). The recorded contract now supplies it.
    async with content_session_factory.begin() as session:
        org_id, pub_id, item_id, rev_id = await _seed(
            session,
            contract=LOUISIANA_PURCHASE_CONTRACT,
            target_path="src/content/blog/blog.mdx",
            frontmatter={
                "title": "Explore the Louisiana Purchase blog",
                "description": "North Park San Diego dining guides and cocktail ideas.",
            },
        )

    result = await _publish(content_session_factory, org_id, pub_id, {})

    assert result == ("succeeded", None)
    written = repository.files["src/content/blog/blog.mdx"]
    assert 'category: "Events"' in written
    assert "date:" in written


@pytest.mark.integration
@pytest.mark.anyio
async def test_build_rate_limited_deployment_keeps_the_publication_resumable(
    content_session_factory: async_sessionmaker[AsyncSession], repository: FakeRepository
) -> None:
    # Run edcdedf9 (PR 11): the host refused to build the merged commit ("Deployment rate
    # limited"). The change was fine and merged; it must not end as a failed publication.
    async with content_session_factory.begin() as session:
        org_id, pub_id, item_id, rev_id = await _seed(
            session,
            contract=COCO_MAYA_CONTRACT,
            target_path="src/content/blog/happy-hour.mdx",
            frontmatter={
                "title": "Happy Hour in Little Italy, San Diego | Coco Maya",
                "description": "Find a weekday happy hour in Little Italy at Coco Maya.",
            },
        )
    overrides = {"image": "/images/hh-chefs-wim-pizza.webp", "image_alt": "Happy Hour"}
    repository.deployment_state = {"state": "rate_limited", "url": "https://vercel.test"}

    first = await _publish(content_session_factory, org_id, pub_id, overrides)

    assert first == ("permanent_failure", "CONTENT_DEPLOYMENT_RATE_LIMITED")
    publication, item, _ = await _states(content_session_factory, pub_id, item_id, rev_id)
    assert publication.status == "deployment_pending"
    assert publication.safe_error_code == "CONTENT_DEPLOYMENT_RATE_LIMITED"
    assert item.status == "publishing"

    repository.deployment_state = {"state": "success", "url": "https://site.test"}
    again = await _publish(content_session_factory, org_id, pub_id, overrides)

    assert again == ("succeeded", None)
    assert repository.calls.count("merge") == 1
    publication, item, _ = await _states(content_session_factory, pub_id, item_id, rev_id)
    assert (publication.status, item.status) == ("verified", "published")


@pytest.mark.integration
@pytest.mark.anyio
async def test_missing_github_app_permission_stops_retrying_and_resumes_once_granted(
    content_session_factory: async_sessionmaker[AsyncSession], repository: FakeRepository
) -> None:
    # Production run 9056999c (site change, PR 26): GET /commits/{sha}/status answered 403
    # "Resource not accessible by integration" on all 30 attempts over 19 hours.
    async with content_session_factory.begin() as session:
        org_id, pub_id, item_id, rev_id = await _seed(
            session,
            contract=COCO_MAYA_CONTRACT,
            target_path="src/content/blog/brunch.mdx",
            frontmatter={"title": "Brunch | Coco Maya", "description": "Daily brunch."},
        )
    overrides = {"image": "/a.webp", "image_alt": "a"}
    repository.checks_error = GitHubPermissionError("403: the app installation lacks permission")

    first = await _publish(content_session_factory, org_id, pub_id, overrides)

    assert first == ("permanent_failure", "GITHUB_APP_PERMISSION_MISSING")
    publication, item, _ = await _states(content_session_factory, pub_id, item_id, rev_id)
    assert publication.status == "reconciliation_required"
    assert publication.safe_error_code == "GITHUB_APP_PERMISSION_MISSING"
    assert repository.calls.count("create_pull_request") == 1

    repository.checks_error = None  # the permission was granted
    again = await _publish(content_session_factory, org_id, pub_id, overrides)

    assert again == ("succeeded", None)
    assert repository.calls.count("create_pull_request") == 1  # resumed, never recreated
    publication, item, _ = await _states(content_session_factory, pub_id, item_id, rev_id)
    assert (publication.status, item.status) == ("verified", "published")


@pytest.mark.integration
@pytest.mark.anyio
async def test_deployment_that_really_failed_still_fails_the_publication(
    content_session_factory: async_sessionmaker[AsyncSession], repository: FakeRepository
) -> None:
    async with content_session_factory.begin() as session:
        org_id, pub_id, item_id, rev_id = await _seed(
            session,
            contract=COCO_MAYA_CONTRACT,
            target_path="src/content/blog/happy-hour.mdx",
            frontmatter={"title": "Happy Hour | Coco Maya", "description": "Weekday happy hour."},
        )
    repository.deployment_state = {"state": "failure", "url": "https://vercel.test"}

    result = await _publish(
        content_session_factory, org_id, pub_id, {"image": "/a.webp", "image_alt": "a"}
    )

    assert result == ("permanent_failure", "CONTENT_DEPLOYMENT_FAILED")
    publication, item, _ = await _states(content_session_factory, pub_id, item_id, rev_id)
    assert (publication.status, item.status) == ("failed", "failed")
