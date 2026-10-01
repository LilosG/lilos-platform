"""Denied mutations never reach the HTTP client or credential minting boundary."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from apps.api.app import config
from apps.api.app.config import Settings
from apps.api.app.execution.handlers import _production_github_token_resolver
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.content.github_adapter import GitHubRepositoryPublisher
from apps.api.app.products.gbp.adapter import GoogleBusinessProfileAdapter
from apps.api.app.staging.write_boundary import ProviderWriteDeniedError

from .test_isolation import staging_values


def configured(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(**staging_values())
    monkeypatch.setattr(config, "Settings", lambda: settings)
    return settings


@pytest.mark.parametrize(
    "method,path,document",
    [
        ("POST", "/repos/OtherOwner/staging-test/git/refs", {}),
        ("POST", "/repos/SyntheticOwner/client-repo/git/refs", {}),
        (
            "PUT",
            "/repos/SyntheticOwner/staging-test/contents/src/pages/index.astro",
            {"branch": "lilos-content-00000000-0000-0000-0000-000000000001"},
        ),
        ("POST", "/repos/SyntheticOwner/staging-test/git/refs", {"ref": "refs/heads/main"}),
        ("DELETE", "/repos/SyntheticOwner/staging-test/git/refs/heads/main", {}),
    ],
)
def test_github_denies_before_http(
    monkeypatch: pytest.MonkeyPatch, method: str, path: str, document: dict[str, Any]
) -> None:
    configured(monkeypatch)

    def forbidden_client(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Denied write reached HTTP")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden_client)

    async def run() -> None:
        publisher = GitHubRepositoryPublisher("synthetic-token")
        with pytest.raises(ProviderWriteDeniedError):
            await publisher._request_json(method, path, json=document)

    asyncio.run(run())


@pytest.mark.parametrize("method", ["PATCH", "PUT", "POST", "DELETE"])
def test_google_denies_all_mutation_methods(monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    configured(monkeypatch)

    async def run() -> None:
        with pytest.raises(ProviderWriteDeniedError, match="GOOGLE_WRITES_DISABLED"):
            await GoogleBusinessProfileAdapter()._request(
                method,
                "https://mybusiness.googleapis.com/v4/accounts/1001/locations/1001",
                "synthetic-token",
            )

    asyncio.run(run())


@pytest.mark.parametrize("reference", ["installation:9999", None, "pat-fallback"])
def test_wrong_installation_denied_before_token_mint(
    monkeypatch: pytest.MonkeyPatch, reference: str | None
) -> None:
    settings = configured(monkeypatch)

    async def run() -> None:
        connection = IntegrationConnection(external_account_reference=reference)
        with pytest.raises(ProviderWriteDeniedError, match="INSTALLATION_DENIED"):
            await _production_github_token_resolver(AsyncMock(), settings, connection)

    asyncio.run(run())


def test_premerge_rejects_outside_path(monkeypatch: pytest.MonkeyPatch) -> None:
    configured(monkeypatch)

    async def run() -> None:
        publisher = GitHubRepositoryPublisher("synthetic-token")
        branch = "lilos-content-00000000-0000-0000-0000-000000000001"
        reads: list[str] = []

        async def request(method: str, path: str, **kwargs: Any) -> Any:
            assert method == "GET", "Denied merge reached provider write"
            reads.append(path)
            if path.endswith("/files"):
                return [{"filename": "src/pages/index.astro"}]
            return {
                "head": {
                    "sha": "approved",
                    "ref": branch,
                    "repo": {"full_name": "SyntheticOwner/staging-test"},
                },
                "base": {"ref": "main", "repo": {"full_name": "SyntheticOwner/staging-test"}},
                "changed_files": 1,
            }

        monkeypatch.setattr(
            GitHubRepositoryPublisher,
            "_request_json",
            lambda self, *args, **kwargs: request(*args, **kwargs),
        )
        with pytest.raises(ProviderWriteDeniedError, match="PATH_DENIED"):
            await publisher.merge_pull_request("SyntheticOwner/staging-test", "1", "approved")
        assert len(reads) == 2

    asyncio.run(run())


def test_allowed_github_branch_and_path_reach_only_fixed_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured(monkeypatch)
    client_class = httpx.AsyncClient
    calls: list[tuple[str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path.startswith("/repos/SyntheticOwner/staging-test/")
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(404, json={})
        return httpx.Response(201, json={"content": {"sha": "synthetic-blob"}})

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(respond))
    )

    async def run() -> None:
        publisher = GitHubRepositoryPublisher("synthetic-token")
        branch = "lilos-content-00000000-0000-0000-0000-000000000001"
        await publisher.create_branch(
            "SyntheticOwner/staging-test", "main", "synthetic-base", branch
        )
        await publisher.put_file(
            "SyntheticOwner/staging-test",
            branch,
            "src/content/test/page.md",
            "synthetic body",
            None,
        )
        assert [method for method, _ in calls] == ["GET", "POST", "GET", "PUT"]

    asyncio.run(run())


def test_google_media_delete_denied_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    configured(monkeypatch)

    async def run() -> None:
        with pytest.raises(ProviderWriteDeniedError, match="GOOGLE_WRITES_DISABLED"):
            await GoogleBusinessProfileAdapter().delete_media(
                "synthetic-token", "accounts/1001/locations/1001/media/1001"
            )

    asyncio.run(run())
