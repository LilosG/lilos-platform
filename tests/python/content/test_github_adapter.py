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

    assert await publisher.checks("owner/repo", "revision") == {
        "state": "success",
        "gate": "repository_ci",
    }
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

    assert await publisher.checks("owner/repo", "revision") == {"state": "none", "gate": "none"}


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

    assert await publisher.checks("owner/repo", "revision") == {
        "state": "failed",
        "gate": "vercel_preview",
    }


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
async def test_rate_limited_vercel_status_without_production_deployment_is_not_a_failure() -> None:
    target_url = "https://vercel.com/team?upgradeToPro=build-rate-limit"
    publisher = StubGitHubPublisher(
        check_pages=[],
        deployment_pages=[[{"id": 9, "environment": "Preview"}]],
        commit_status={
            "statuses": [{"context": "Vercel", "state": "failure", "target_url": target_url}]
        },
    )

    assert await publisher.deployment("owner/repo", "revision") == {
        "state": "rate_limited",
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


PREVIEW_COMMENTS = {"name": "Vercel Preview Comments", "conclusion": "success"}


def _checks_publisher(
    runs: list[dict[str, Any]], statuses: list[dict[str, Any]]
) -> StubGitHubPublisher:
    return StubGitHubPublisher(
        check_pages=[{"check_runs": runs, "total_count": len(runs)}],
        deployment_pages=[],
        commit_status={"statuses": statuses},
    )


@pytest.mark.anyio
async def test_checks_requires_repository_ci_when_present() -> None:
    # The client's own CI is the gate: a green Vercel preview cannot outvote a red check.
    failing = _checks_publisher(
        [{"name": "validate", "conclusion": "failure"}, PREVIEW_COMMENTS],
        [{"context": "Vercel", "state": "success"}],
    )
    assert await failing.checks("owner/repo", "sha") == {
        "state": "failed",
        "gate": "repository_ci",
    }

    # A passing CI run still waits on a Vercel preview that is not finished.
    waiting = _checks_publisher(
        [{"name": "validate", "conclusion": "success"}],
        [{"context": "Vercel", "state": "pending"}],
    )
    assert await waiting.checks("owner/repo", "sha") == {
        "state": "pending",
        "gate": "repository_ci",
    }

    passing = _checks_publisher(
        [{"name": "validate", "conclusion": "success"}],
        [{"context": "Vercel", "state": "success"}],
    )
    assert await passing.checks("owner/repo", "sha") == {
        "state": "success",
        "gate": "repository_ci",
    }


@pytest.mark.anyio
async def test_checks_falls_back_to_vercel_preview_status() -> None:
    # No CI of its own (Louisiana Purchase's shape): only a preview-deployment
    # commit status on the head commit can stand in for a build.
    green = _checks_publisher([PREVIEW_COMMENTS], [{"context": "Vercel", "state": "success"}])
    assert await green.checks("owner/repo", "sha") == {
        "state": "success",
        "gate": "vercel_preview",
    }

    building = _checks_publisher([PREVIEW_COMMENTS], [{"context": "Vercel", "state": "pending"}])
    assert await building.checks("owner/repo", "sha") == {
        "state": "pending",
        "gate": "vercel_preview",
    }

    # Vercel names the status after the project ("Vercel – project"); still Vercel.
    named = _checks_publisher([], [{"context": "Vercel \u2013 site", "state": "success"}])
    assert (await named.checks("owner/repo", "sha"))["gate"] == "vercel_preview"


@pytest.mark.anyio
async def test_get_file_decodes_content_and_reports_missing_file() -> None:
    import base64

    class FilePublisher(GitHubRepositoryPublisher):
        def __init__(self, payload: Any) -> None:
            super().__init__(access_token="token")
            self.payload = payload
            self.params: dict[str, Any] = {}

        async def _request_json(
            self, method: str, path: str, *, expected_status: Any = 200, **kwargs: Any
        ) -> Any:
            del method, path, expected_status
            self.params = kwargs["params"]
            return self.payload

    text = '{"title": "Caf\u00e9 \u2014 Brunch"}'
    found = FilePublisher(
        {"type": "file", "encoding": "base64", "content": base64.b64encode(text.encode()).decode()}
    )
    assert await found.get_file("owner/repo", "abc123", "src/content/page.json") == text
    assert found.params == {"ref": "abc123"}
    assert await FilePublisher(None).get_file("owner/repo", "abc123", "missing.json") is None
    with pytest.raises(RuntimeError):
        await FilePublisher({"type": "dir"}).get_file("owner/repo", "abc123", "src")


@pytest.mark.anyio
async def test_vercel_build_rate_limit_is_reported_apart_from_a_failed_deployment() -> None:
    limited = StubGitHubPublisher(
        check_pages=[],
        deployment_pages=[[]],
        commit_status={
            "statuses": [
                {
                    "context": "Vercel",
                    "state": "failure",
                    "description": "Deployment rate limited — retry in 24 hours.",
                    "target_url": "https://vercel.com/team?upgradeToPro=build-rate-limit",
                }
            ]
        },
    )
    failed = StubGitHubPublisher(
        check_pages=[],
        deployment_pages=[[]],
        commit_status={
            "statuses": [
                {
                    "context": "Vercel",
                    "state": "failure",
                    "description": "Deployment has failed",
                    "target_url": "https://vercel.com/team/site/dpl_123",
                }
            ]
        },
    )

    assert (await limited.deployment("owner/repo", "revision"))["state"] == "rate_limited"
    assert (await failed.deployment("owner/repo", "revision"))["state"] == "failure"


@pytest.mark.anyio
async def test_integration_permission_403_is_typed_and_other_403s_are_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from apps.api.app.products.content import github_adapter

    bodies = {
        "permission": {"message": "Resource not accessible by integration", "status": "403"},
        "rate": {"message": "You have exceeded a secondary rate limit.", "status": "403"},
    }
    real_client = httpx.AsyncClient

    def client_for(body: dict[str, str]) -> Any:
        def factory(**kwargs: Any) -> httpx.AsyncClient:
            return real_client(
                transport=httpx.MockTransport(lambda request: httpx.Response(403, json=body)),
                **kwargs,
            )

        return factory

    publisher = GitHubRepositoryPublisher(access_token="token")
    monkeypatch.setattr(httpx, "AsyncClient", client_for(bodies["permission"]))
    with pytest.raises(github_adapter.GitHubPermissionError):
        await publisher.checks("owner/repo", "revision")

    monkeypatch.setattr(httpx, "AsyncClient", client_for(bodies["rate"]))
    with pytest.raises(RuntimeError) as other:
        await publisher.checks("owner/repo", "revision")
    assert not isinstance(other.value, github_adapter.GitHubPermissionError)
