"""Unit coverage for paginated GitHub read-side status collections."""

from typing import Any

import pytest

from apps.api.app.products.content.github_adapter import GitHubRepositoryPublisher


class StubGitHubPublisher(GitHubRepositoryPublisher):
    def __init__(
        self, check_pages: list[dict[str, Any]], deployment_pages: list[list[dict[str, Any]]]
    ) -> None:
        super().__init__(access_token="token")
        self.check_pages = list(check_pages)
        self.deployment_pages = list(deployment_pages)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def _request(
        self, method: str, path: str, *, expected_status: int = 200, **kwargs: Any
    ) -> dict[str, Any]:
        del expected_status
        self.calls.append((method, path, kwargs))
        return self.check_pages.pop(0)

    async def _request_json(
        self, method: str, path: str, *, expected_status: int = 200, **kwargs: Any
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
            [{"id": index, "state": "success"} for index in range(100)],
            [{"id": 100, "state": "success"}],
        ],
    )

    assert await publisher.checks("owner/repo", "revision") == {"state": "success"}
    assert await publisher.deployment("owner/repo", "revision") == {
        "state": "success",
        "url": "0",
    }
    assert publisher.calls[0][2]["params"] == {"page": 1, "per_page": 100}
    assert publisher.calls[1][2]["params"] == {"page": 2, "per_page": 100}
    assert publisher.calls[2][2]["params"] == {
        "sha": "revision",
        "page": 1,
        "per_page": 100,
    }
    assert publisher.calls[3][2]["params"]["page"] == 2
