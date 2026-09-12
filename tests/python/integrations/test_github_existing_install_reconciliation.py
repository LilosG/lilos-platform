"""Regression coverage for pre-existing GitHub App installation recovery."""

from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.github_app_service import GitHubAppService
from apps.api.app.products.content.github_install_reconciliation import (
    GitHubOwnerInstallationReconciler,
)


def make_test_private_key() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")


def make_settings() -> Settings:
    return Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "github_app_id": "123456",
            "github_app_client_id": "Iv1.testclient",
            "github_app_private_key": make_test_private_key(),
            "github_app_installation_redirect_uri": (
                "https://api.example.invalid/api/v1/integrations/github/callback"
            ),
        }
    )


def client_factory(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Callable[[], httpx.AsyncClient]:
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def make_organization(session: AsyncSession) -> Organization:
    organization = Organization(
        name="Existing GitHub Installation Test",
        slug=f"github-existing-install-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(organization)
    await session.flush()
    return organization


def owner_installation_handler(
    *,
    installation_account_id: int = 42,
    suspended_at: str | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/app":
            return httpx.Response(
                200,
                json={"id": 123456, "owner": {"id": 42, "login": "LilosG"}},
            )
        if request.url.path == "/app/installations":
            assert request.url.params["page"] == "1"
            assert request.url.params["per_page"] == "100"
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 99999,
                        "account": {
                            "id": installation_account_id,
                            "login": "LilosG",
                        },
                        "suspended_at": suspended_at,
                    }
                ],
            )
        return httpx.Response(404, text=f"unexpected: {request.url.path}")

    return handler


@pytest.mark.integration
@pytest.mark.anyio
async def test_reconciles_preexisting_installation_owned_by_github_app_owner(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        github = GitHubAppService(http_client_factory=client_factory(owner_installation_handler()))
        reconciler = GitHubOwnerInstallationReconciler(github=github)

        result = await reconciler.reconcile(
            session,
            make_settings(),
            organization.id,
            actor_id=None,
            correlation_id="existing-install",
        )

        assert result is not None
        assert result.installation_id == "99999"
        assert result.connection.organization_id == organization.id
        assert result.connection.status == "connected"
        assert result.connection.external_account_reference == "installation:99999"
        assert result.connection.credential_reference is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_does_not_claim_installation_owned_by_another_github_account(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        github = GitHubAppService(
            http_client_factory=client_factory(
                owner_installation_handler(installation_account_id=77)
            )
        )
        reconciler = GitHubOwnerInstallationReconciler(github=github)

        result = await reconciler.reconcile(
            session,
            make_settings(),
            organization.id,
            actor_id=None,
            correlation_id="foreign-install",
        )

        assert result is None
        assert await github.find_connection(session, organization.id) is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_does_not_reconcile_suspended_owner_installation(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        github = GitHubAppService(
            http_client_factory=client_factory(
                owner_installation_handler(suspended_at="2026-09-12T12:00:00Z")
            )
        )
        reconciler = GitHubOwnerInstallationReconciler(github=github)

        result = await reconciler.reconcile(
            session,
            make_settings(),
            organization.id,
            actor_id=None,
            correlation_id="suspended-install",
        )

        assert result is None
        assert await github.find_connection(session, organization.id) is None
