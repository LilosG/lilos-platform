"""The GitHub App install returns to the app the person started it from."""

import asyncio
from typing import cast
from urllib.parse import urlparse
from uuid import UUID

import httpx
import pytest
from authorization.fixtures import add_effective_product_entitlement
from fastapi import FastAPI
from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.products.content.github_app_service import GitHubAppService
from apps.api.app.products.content.github_install_reconciliation import (
    GitHubOwnerInstallationReconciler,
)
from apps.api.app.products.content.publishing_target_reconciliation import (
    GitHubPublishingTargetReconciler,
)

from .test_api import HEADERS, FakeVerifier, integrations_client

__all__ = ["integrations_client"]

Fixture = tuple[TestClient, FakeVerifier, dict[str, object]]


@pytest.fixture
def github_client(
    integrations_client: Fixture,
    integrations_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> Fixture:
    client, _, ids = integrations_client

    async def entitle() -> None:
        async with integrations_session_factory.begin() as session:
            await add_effective_product_entitlement(
                session, cast(UUID, ids["organization_id"]), "content", correlation_id="github"
            )

    asyncio.run(entitle())
    app = cast(FastAPI, client.app)
    app.state.settings = app.state.settings.model_copy(
        update={
            "console_origin": HttpUrl("https://console.example.invalid"),
            "github_app_id": "123456",
            "github_app_slug": "lilos-test-app",
            "github_app_client_id": "Iv1.testclient",
            "github_app_private_key": "unused-in-this-test",
            "github_app_installation_redirect_uri": (
                "https://api.example.invalid/api/v1/integrations/github/callback"
            ),
        }
    )

    async def no_existing_installation(*_args: object, **_kwargs: object) -> None:
        return None

    async def installation_is_real(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"id": 4242}

    async def nothing_to_reconcile(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(GitHubOwnerInstallationReconciler, "reconcile", no_existing_installation)
    monkeypatch.setattr(GitHubAppService, "_get_installation", installation_is_real)
    monkeypatch.setattr(GitHubPublishingTargetReconciler, "reconcile", nothing_to_reconcile)
    return integrations_client


def begin(client: TestClient, ids: dict[str, object], body: dict[str, str] | None) -> str:
    response = client.post(
        f"/api/v1/organizations/{ids['organization_id']}/integrations/github/install",
        headers=HEADERS,
        **({"json": body} if body is not None else {}),
    )
    assert response.status_code == 200, response.text
    return str(httpx.URL(response.json()["data"]["authorization_url"]).params["state"])


@pytest.mark.integration
def test_a_console_install_returns_to_the_console_integrations_screen(
    github_client: Fixture,
) -> None:
    client, _, ids = github_client
    org = ids["organization_id"]
    state = begin(client, ids, {"return_app": "console"})
    assert state.startswith("console.")

    finished = client.get(
        "/api/v1/integrations/github/callback",
        params={"state": state, "installation_id": "4242", "setup_action": "install"},
        follow_redirects=False,
    )
    assert finished.status_code == 302
    location = finished.headers["location"]
    assert location.startswith("https://console.example.invalid/integrations/?")
    assert "installed=1" in location
    assert f"org={org}" in location


@pytest.mark.integration
def test_a_console_install_that_fails_still_returns_to_the_console(
    github_client: Fixture,
) -> None:
    client, _, ids = github_client
    state = begin(client, ids, {"return_app": "console"})
    failed = client.get(
        "/api/v1/integrations/github/callback",
        params={"state": state, "error": "access_denied"},
        follow_redirects=False,
    )
    assert failed.headers["location"].startswith("https://console.example.invalid/integrations/?")
    assert "installed=0" in failed.headers["location"]


@pytest.mark.integration
def test_an_install_started_without_a_marker_still_returns_to_the_older_app(
    github_client: Fixture,
) -> None:
    client, _, ids = github_client
    for body in (None, {"return_app": "web"}):
        state = begin(client, ids, body)
        assert not state.startswith("console.")
        finished = client.get(
            "/api/v1/integrations/github/callback",
            params={"state": state, "installation_id": "4242"},
            follow_redirects=False,
        )
        assert urlparse(finished.headers["location"]).netloc == "app.example.invalid"
        assert "/integrations?" in finished.headers["location"]


@pytest.mark.integration
def test_the_marker_cannot_be_added_to_an_existing_install_or_point_elsewhere(
    github_client: Fixture,
) -> None:
    client, _, ids = github_client
    state = begin(client, ids, None)
    forged = client.get(
        "/api/v1/integrations/github/callback",
        params={"state": f"console.{state}", "installation_id": "4242"},
        follow_redirects=False,
    )
    assert "invalid_state" in forged.headers["location"]
    assert urlparse(forged.headers["location"]).netloc == "app.example.invalid"
    rejected = client.post(
        f"/api/v1/organizations/{ids['organization_id']}/integrations/github/install",
        headers=HEADERS,
        json={"return_app": "https://evil.test"},
    )
    assert rejected.status_code == 422
