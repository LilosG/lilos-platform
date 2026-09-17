"""Unit coverage for paginated GitHub read-side status collections."""

import hashlib
from typing import Any

import pytest

from apps.api.app.products.content.github_adapter import GitHubRepositoryPublisher


class StubGitHubPublisher(GitHubRepositoryPublisher):
    def __init__(
        self,
        check_pages: list[dict[str, Any]],
        deployment_pages: list[list[dict[str, Any]]],
        commit_status: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(access_token="token")
        self.check_pages = list(check_pages)
        self.deployment_pages = list(deployment_pages)
        self.commit_status = commit_status or {"statuses": [{"state": "success"}]}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def _request(
        self, method: str, path: str, *, expected_status: int | tuple[int, ...] = 200, **kwargs: Any
    ) -> dict[str, Any]:
        del expected_status
        self.calls.append((method, path, kwargs))
        if path.endswith("/status"):
            return self.commit_status
        return self.check_pages.pop(0)

    async def _request_json(
        self, method: str, path: str, *, expected_status: int | tuple[int, ...] = 200, **kwargs: Any
    ) -> Any:
        del expected_status
        self.calls.append((method, path, kwargs))
        return self.deployment_pages.pop(0)


@pytest.mark.anyio
async def test_checks_and_deployments_read_all_github_pages() -> None:
    publisher = StubGitHubPublisher(
        check_pages=[
            {"check_runs": [{"conclusion": "success"}] * 100, "total_count": 101},
            {"check_runs": [{"conclusion": "success"}], "total_count": 101},
        ],
        deployment_pages=[
            [{"id": index, "environment": "Preview"} for index in range(100)],
            [{"id": 100, "environment": "production"}],
            [{"state": "success", "environment_url": "https://example.com"}],
        ],
    )

    assert await publisher.checks("owner/repo", "revision") == {"state": "success"}
    assert await publisher.deployment("owner/repo", "revision") == {
        "state": "success",
        "url": "https://example.com",
    }
    assert publisher.calls[0][2]["params"] == {"page": 1, "per_page": 100}
    assert publisher.calls[1][2]["params"] == {"page": 2, "per_page": 100}
    assert publisher.calls[2][1].endswith("/status")
    assert publisher.calls[3][2]["params"] == {
        "sha": "revision",
        "page": 1,
        "per_page": 100,
    }
    assert publisher.calls[4][2]["params"]["page"] == 2


@pytest.mark.anyio
async def test_vercel_preview_comment_cannot_authorize_a_merge() -> None:
    publisher = StubGitHubPublisher(
        check_pages=[
            {
                "check_runs": [{"name": "Vercel Preview Comments", "conclusion": "success"}],
                "total_count": 1,
            }
        ],
        deployment_pages=[],
        commit_status={"statuses": []},
    )

    assert await publisher.checks("owner/repo", "revision") == {"state": "none"}


@pytest.mark.anyio
async def test_failed_vercel_commit_status_blocks_merge() -> None:
    publisher = StubGitHubPublisher(
        check_pages=[
            {
                "check_runs": [{"name": "Vercel Preview Comments", "conclusion": "success"}],
                "total_count": 1,
            }
        ],
        deployment_pages=[],
        commit_status={"statuses": [{"context": "Vercel", "state": "failure"}]},
    )

    assert await publisher.checks("owner/repo", "revision") == {"state": "failed"}


@pytest.mark.anyio
async def test_preview_only_deployment_does_not_satisfy_production_publish() -> None:
    publisher = StubGitHubPublisher(
        check_pages=[],
        deployment_pages=[[{"id": 9, "environment": "Preview"}]],
    )

    assert await publisher.deployment("owner/repo", "revision") == {
        "state": "none",
        "url": "",
    }
    assert len(publisher.calls) == 2
    assert publisher.calls[1][1].endswith("/status")


@pytest.mark.anyio
async def test_failed_vercel_status_without_production_deployment_is_terminal() -> None:
    target_url = "https://vercel.com/team?upgradeToPro=build-rate-limit"
    publisher = StubGitHubPublisher(
        check_pages=[],
        deployment_pages=[[{"id": 9, "environment": "Preview"}]],
        commit_status={
            "statuses": [
                {"context": "Vercel", "state": "failure", "target_url": target_url}
            ]
        },
    )

    assert await publisher.deployment("owner/repo", "revision") == {
        "state": "failure",
        "url": target_url,
    }


@pytest.mark.anyio
async def test_retry_with_identical_file_does_not_create_another_commit() -> None:
    content = "---\ntitle: Example\n---\n# Example"
    encoded = content.encode()
    existing_sha = hashlib.sha1(f"blob {len(encoded)}\0".encode() + encoded).hexdigest()

    class ExistingFilePublisher(GitHubRepositoryPublisher):
        writes = 0

        async def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
            assert method == "GET"
            return {"sha": existing_sha}

        async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
            self.writes += 1
            return {}

    publisher = ExistingFilePublisher(access_token="token")
    assert (
        await publisher.put_file("owner/repo", "branch", "src/content/post.md", content, None)
        == existing_sha
    )
    assert publisher.writes == 0


@pytest.mark.anyio
async def test_merge_binds_to_the_content_head_that_passed_checks() -> None:
    class MergePublisher(GitHubRepositoryPublisher):
        async def get_pull_request(self, repository_id: str, pr_number: str) -> dict[str, object]:
            return {"head": {"sha": "approved-head"}, "merged": False}

        async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
            assert kwargs["json"] == {"merge_method": "squash", "sha": "approved-head"}
            return {"merged": True, "sha": "merged-commit"}

    publisher = MergePublisher(access_token="token")
    assert (
        await publisher.merge_pull_request("owner/repo", "17", "approved-head") == "merged-commit"
    )
    with pytest.raises(RuntimeError, match="head has changed"):
        await publisher.merge_pull_request("owner/repo", "17", "different-head")