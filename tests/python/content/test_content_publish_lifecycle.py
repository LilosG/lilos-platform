"""Provider-state acceptance for recoverable Content publication."""

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.content.adapter import RepositoryPublisher
from apps.api.app.products.content.models import ContentPublication
from apps.api.app.products.content.publish_handler import (
    _reconcile_phase,
    _verify_deployment,
    _wait_for_pull_request_checks,
)


class SessionStub:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class ProviderStub:
    def __init__(self, *, pr: dict[str, object] | None = None, deployment: dict[str, str]) -> None:
        self.pr = pr or {}
        self.deployment_state = deployment

    async def get_pull_request(self, repository_id: str, pr_number: str) -> dict[str, object]:
        assert repository_id == "owner/repo"
        assert pr_number == "17"
        return self.pr

    async def deployment(self, repository_id: str, revision_id: str) -> dict[str, str]:
        assert repository_id == "owner/repo"
        assert revision_id == "merged-commit"
        return self.deployment_state

    async def checks(self, repository_id: str, revision_id: str) -> dict[str, str]:
        assert repository_id == "owner/repo"
        assert revision_id == "branch-commit"
        return {"state": "none"}


@pytest.mark.anyio
async def test_ambiguous_merge_recovers_from_provider_without_merging_twice() -> None:
    session = SessionStub()
    publication = SimpleNamespace(
        external_pull_request_id="17",
        approved_head_sha="branch-commit",
        external_revision_id="branch-commit",
        status="reconciliation_required",
        safe_error_code="PULL_REQUEST_MERGE_FAILED",
    )
    provider = ProviderStub(
        pr={
            "head": {"sha": "branch-commit"},
            "merged": True,
            "merge_commit_sha": "merged-commit",
        },
        deployment={"state": "none"},
    )

    result = await _reconcile_phase(
        cast(AsyncSession, session),
        cast(ContentPublication, publication),
        cast(RepositoryPublisher, provider),
        "owner/repo",
    )

    assert result is None
    assert publication.status == "merged"
    assert publication.external_revision_id == "merged-commit"
    assert session.commits == 1


@pytest.mark.anyio
async def test_changed_pull_request_head_cannot_publish_unapproved_content() -> None:
    session = SessionStub()
    publication = SimpleNamespace(
        external_pull_request_id="17",
        approved_head_sha="approved-commit",
        external_revision_id="approved-commit",
        status="reconciliation_required",
        safe_error_code=None,
    )
    provider = ProviderStub(
        pr={
            "head": {"sha": "unapproved-commit"},
            "merged": True,
            "merge_commit_sha": "merged-commit",
        },
        deployment={"state": "none"},
    )

    outcome = await _reconcile_phase(
        cast(AsyncSession, session),
        cast(ContentPublication, publication),
        cast(RepositoryPublisher, provider),
        "owner/repo",
    )

    assert outcome is not None and outcome.result == "permanent_failure"
    assert publication.status == "failed"
    assert publication.safe_error_code == "CONTENT_PR_HEAD_CHANGED"


@pytest.mark.anyio
async def test_missing_production_deployment_never_marks_item_published() -> None:
    session = SessionStub()
    publication: Any = SimpleNamespace(
        id=uuid4(),
        external_revision_id="merged-commit",
        status="merged",
        deployment_status=None,
        safe_error_code=None,
    )
    revision: Any = SimpleNamespace(id=uuid4(), status="approved")
    item: Any = SimpleNamespace(status="publishing")
    provider = ProviderStub(deployment={"state": "none", "url": ""})

    outcome = await _verify_deployment(
        cast(AsyncSession, session),
        publication,
        revision,
        item,
        cast(RepositoryPublisher, provider),
        "owner/repo",
    )

    assert outcome.result == "retryable_failure"
    assert publication.status == "deployment_pending"
    assert revision.status == "approved"
    assert item.status == "publishing"


@pytest.mark.anyio
async def test_repository_without_checks_does_not_auto_merge() -> None:
    session = SessionStub()
    publication: Any = SimpleNamespace(
        external_pull_request_id="17",
        approved_head_sha="branch-commit",
        external_revision_id="branch-commit",
        status="pull_request_created",
        safe_error_code=None,
        build_status=None,
    )
    provider = ProviderStub(
        pr={"head": {"sha": "branch-commit"}},
        deployment={"state": "none"},
    )

    outcome = await _wait_for_pull_request_checks(
        cast(AsyncSession, session),
        publication,
        cast(RepositoryPublisher, provider),
        "owner/repo",
    )

    assert outcome is not None and outcome.result == "retryable_failure"
    assert publication.status == "checks_running"
    assert publication.safe_error_code == "CONTENT_CHECKS_UNAVAILABLE"


@pytest.mark.anyio
async def test_matching_production_deployment_marks_approved_revision_published() -> None:
    session = SessionStub()
    revision: Any = SimpleNamespace(id=uuid4(), status="approved")
    item: Any = SimpleNamespace(status="publishing", approved_revision_id=None)
    publication: Any = SimpleNamespace(
        id=uuid4(),
        external_revision_id="merged-commit",
        publishing_target_id=uuid4(),
        status="merged",
        deployment_status=None,
        safe_error_code=None,
        published_url=None,
    )
    provider = ProviderStub(
        deployment={"state": "success", "url": "https://production.example.com"},
    )

    outcome = await _verify_deployment(
        cast(AsyncSession, session),
        publication,
        revision,
        item,
        cast(RepositoryPublisher, provider),
        "owner/repo",
    )

    assert outcome.result == "succeeded"
    assert publication.status == "verified"
    assert publication.published_url == "https://production.example.com"
    assert revision.status == "published"
    assert item.status == "published"
    assert item.approved_revision_id == revision.id
