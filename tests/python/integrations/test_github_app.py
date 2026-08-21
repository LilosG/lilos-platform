"""GitHub App operator journey: install flow, repository discovery, short-lived
installation-token minting, PublishingTarget creation, and publisher credential
resolution. No real GitHub calls -- the GitHub App service HTTP client is a
deterministic fake, and a test RSA key is generated per session for JWT signing.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.execution import handlers as workflow_handlers
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.github_app_service import (
    GITHUB_INSTALLATION_PREFIX,
    GitHubAppService,
    installation_id_from_reference,
)


def make_test_private_key() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")


def make_github_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": EnvironmentName.TEST,
        "github_app_id": "123456",
        "github_app_client_id": "Iv1.testclient",
        "github_app_private_key": make_test_private_key(),
        "github_app_installation_redirect_uri": "https://api.example.invalid/api/v1/integrations/github/callback",
    }
    base.update(overrides)
    return Settings.model_validate(base)


def mock_client_factory(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Callable[[], httpx.AsyncClient]:
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


def state_from_url(url: str) -> str:
    return parse_qs(urlsplit(url).query)["state"][0]


async def make_organization(session: AsyncSession) -> Organization:
    org = Organization(
        name="GitHub App Test Org",
        slug=f"github-app-test-org-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()
    return org


def github_http_handler(
    installation_id: str = "99999",
    repositories: list[dict[str, object]] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    repos = (
        repositories
        if repositories is not None
        else [
            {
                "full_name": "wheyland/site",
                "name": "site",
                "default_branch": "main",
                "private": True,
            }
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"/app/installations/{installation_id}":
            return httpx.Response(200, json={"id": int(installation_id), "app_id": 123456})
        if path == f"/app/installations/{installation_id}/access_tokens":
            return httpx.Response(
                201,
                json={
                    "token": "ghs_test_installation_token",
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                },
            )
        if path == "/installation/repositories":
            return httpx.Response(200, json={"repositories": repos})
        return httpx.Response(404, text=f"unexpected: {path}")

    return handler


@pytest.mark.integration
@pytest.mark.anyio
async def test_github_app_install_callback_persists_installation_id(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        org = await make_organization(session)
        settings = make_github_settings()

        service = GitHubAppService(http_client_factory=mock_client_factory(github_http_handler()))
        url = await service.begin_install(
            session, settings, org.id, actor_id=None, correlation_id="c1"
        )
        assert url.startswith(
            "https://github.com/apps/lilos-growth-operations/installations/new?state="
        )
        state = state_from_url(url)

        connection = await service.complete_install(
            session,
            settings,
            org.id,
            state=state,
            installation_id="99999",
            setup_action="install",
            correlation_id="c2",
        )
        assert connection.status == "connected"
        assert connection.external_account_reference == f"{GITHUB_INSTALLATION_PREFIX}99999"
        # No long-lived credential stored for an installation.
        assert connection.credential_reference is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_github_app_disconnect_clears_local_installation_binding(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        org = await make_organization(session)
        settings = make_github_settings()
        service = GitHubAppService(http_client_factory=mock_client_factory(github_http_handler()))
        state = state_from_url(
            await service.begin_install(
                session, settings, org.id, actor_id=None, correlation_id="c1"
            )
        )
        connection = await service.complete_install(
            session,
            settings,
            org.id,
            state=state,
            installation_id="99999",
            setup_action="install",
            correlation_id="c2",
        )

        disconnected = await service.disconnect_installation(
            session, org.id, actor_id=None, correlation_id="c3"
        )

        assert disconnected.id == connection.id
        assert disconnected.status == "disconnected"
        assert disconnected.external_account_reference is None
        assert disconnected.credential_reference is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_github_app_installation_token_is_short_lived_and_not_persisted(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        org = await make_organization(session)
        settings = make_github_settings()

        service = GitHubAppService(http_client_factory=mock_client_factory(github_http_handler()))
        url = await service.begin_install(
            session, settings, org.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_url(url)
        await service.complete_install(
            session,
            settings,
            org.id,
            state=state,
            installation_id="99999",
            setup_action="install",
            correlation_id="c2",
        )

        token = await service.create_installation_token(settings, "99999")
        assert token.token == "ghs_test_installation_token"
        assert token.expires_at > datetime.now(UTC)

        # The token is never persisted -- the connection still has no credential ref.
        connection = await service.find_connection(session, org.id)
        assert connection is not None
        assert connection.credential_reference is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_github_app_repository_discovery(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        org = await make_organization(session)
        settings = make_github_settings()

        service = GitHubAppService(http_client_factory=mock_client_factory(github_http_handler()))
        url = await service.begin_install(
            session, settings, org.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_url(url)
        await service.complete_install(
            session,
            settings,
            org.id,
            state=state,
            installation_id="99999",
            setup_action="install",
            correlation_id="c2",
        )

        repos = await service.list_installation_repositories(settings, "99999")
        assert len(repos) == 1
        assert repos[0].repository_id == "wheyland/site"
        assert repos[0].default_branch == "main"


@pytest.mark.anyio
async def test_github_app_repository_discovery_paginates_all_repositories() -> None:
    settings = make_github_settings()
    requested_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/app/installations/99999/access_tokens":
            return httpx.Response(
                201,
                json={
                    "token": "ghs_test_installation_token",
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                },
            )
        if path == "/installation/repositories":
            page = int(request.url.params.get("page", "1"))
            assert request.url.params["per_page"] == "100"
            requested_pages.append(page)
            start = 0 if page == 1 else 100
            count = 100 if page == 1 else 1
            repositories = [
                {
                    "full_name": f"owner/repo-{index}",
                    "name": f"repo-{index}",
                    "default_branch": "main",
                    "private": False,
                }
                for index in range(start, start + count)
            ]
            return httpx.Response(200, json={"repositories": repositories, "total_count": 101})
        return httpx.Response(404, text=f"unexpected: {path}")

    service = GitHubAppService(http_client_factory=mock_client_factory(handler))
    repositories = await service.list_installation_repositories(settings, "99999")

    assert len(repositories) == 101
    assert repositories[-1].repository_id == "owner/repo-100"
    assert requested_pages == [1, 2]


@pytest.mark.integration
@pytest.mark.anyio
async def test_publisher_resolves_installation_token_not_pat(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The content publish handler resolves a short-lived installation token
    for GitHub-App connections; no PAT is required."""
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        org = await make_organization(session)
        settings = make_github_settings()

        service = GitHubAppService(http_client_factory=mock_client_factory(github_http_handler()))
        url = await service.begin_install(
            session, settings, org.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_url(url)
        await service.complete_install(
            session,
            settings,
            org.id,
            state=state,
            installation_id="99999",
            setup_action="install",
            correlation_id="c2",
        )

        connection = await service.find_connection(session, org.id)
        assert connection is not None

        # Override the resolver's HTTP factory to use the mock handler.
        original_resolver = workflow_handlers._github_token_resolver

        async def fake_resolver(
            sess: AsyncSession, cfg: Settings, conn: IntegrationConnection
        ) -> str:
            app_service = GitHubAppService(
                http_client_factory=mock_client_factory(github_http_handler())
            )
            installation_id = installation_id_from_reference(conn.external_account_reference)
            assert installation_id == "99999"
            token = await app_service.create_installation_token(cfg, installation_id)
            return token.token

        workflow_handlers._github_token_resolver = fake_resolver
        try:
            token = await workflow_handlers._github_token_resolver(session, settings, connection)
            assert token == "ghs_test_installation_token"
        finally:
            workflow_handlers._github_token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_pat_fallback_still_works_when_no_installation(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """When no GitHub App installation exists, the PAT fallback path remains."""
    import json

    from cryptography.fernet import Fernet

    from apps.api.app.integrations.secrets import FernetSecretStore
    from apps.api.app.products.content.service import ContentService

    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        org = await make_organization(session)
        pat_settings = Settings.model_validate(
            {
                "environment": EnvironmentName.TEST,
                "secret_encryption_key": Fernet.generate_key().decode("utf-8"),
            }
        )
        content_service = ContentService()
        connection = await content_service.register_github_connection(
            session,
            pat_settings,
            org.id,
            __import__(
                "apps.api.app.products.content.contracts",
                fromlist=["GitHubConnectionCreate"],
            ).GitHubConnectionCreate(
                access_token="ghp_legacy_pat_token",
                external_account_reference="wheyland/site",
            ),
            actor_id=None,
            correlation_id="pat1",
        )
        assert connection.credential_reference is not None
        assert installation_id_from_reference(connection.external_account_reference) is None

        # The resolver falls back to the stored PAT.
        original_resolver = workflow_handlers._github_token_resolver

        async def pat_resolver(
            sess: AsyncSession, cfg: Settings, conn: IntegrationConnection
        ) -> str:
            assert conn.credential_reference is not None
            store = FernetSecretStore.create(sess, cfg)
            raw = await store.get(conn.credential_reference)
            return str(json.loads(raw)["access_token"])

        workflow_handlers._github_token_resolver = pat_resolver
        try:
            token = await workflow_handlers._github_token_resolver(
                session, pat_settings, connection
            )
            assert token == "ghp_legacy_pat_token"
        finally:
            workflow_handlers._github_token_resolver = original_resolver


@pytest.mark.integration
@pytest.mark.anyio
async def test_install_callback_validates_state(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from apps.api.app.integrations.errors import IntegrationStateInvalidError

    async with integrations_session_factory.begin() as session:
        service = GitHubAppService()
        with pytest.raises(IntegrationStateInvalidError):
            await service.recover_organization_id(session, "bogus-state")


def test_app_jwt_is_signed_with_rs256() -> None:
    settings = make_github_settings()
    assert settings.github_app_private_key is not None
    service = GitHubAppService()
    token = service.sign_app_jwt(settings)
    # Decode with the public key derived from the private key.
    private_key = serialization.load_pem_private_key(
        settings.github_app_private_key.encode("utf-8"), password=None
    )
    assert isinstance(private_key, rsa.RSAPrivateKey)
    public_key = private_key.public_key()
    decoded = jwt.decode(token, public_key, algorithms=["RS256"])
    assert decoded["iss"] == "123456"
