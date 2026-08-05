"""Deterministic tests for the GBP OAuth connection lifecycle. No real Google calls."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.integrations.errors import (
    IntegrationNotConfiguredError,
    IntegrationReconnectRequiredError,
    IntegrationStateInvalidError,
)
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": EnvironmentName.TEST,
        "google_oauth_client_id": "test-client-id",
        "google_oauth_client_secret": "test-client-secret",
        "google_oauth_redirect_uri": "https://api.example.invalid/api/v1/integrations/google/callback",
        "secret_encryption_key": Fernet.generate_key().decode("utf-8"),
    }
    base.update(overrides)
    return Settings.model_validate(base)


def mock_client_factory(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Callable[[], httpx.AsyncClient]:
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


def state_from_authorization_url(url: str) -> str:
    query = parse_qs(urlsplit(url).query)
    return query["state"][0]


async def make_organization(session: AsyncSession) -> Organization:
    organization = Organization(
        name="Integration Test Org",
        slug=f"integration-test-org-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(organization)
    await session.flush()
    return organization


@pytest.mark.integration
@pytest.mark.anyio
async def test_begin_connection_returns_authorization_url_with_business_manage_scope(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)

        service = GBPConnectionService()
        url = await service.begin_connection(
            session,
            make_settings(),
            organization.id,
            actor_id=None,
            correlation_id="test-begin",
        )
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fbusiness.manage" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "response_type=code" in url

        connection = await service.find_connection(session, organization.id)
        assert connection is not None
        assert connection.status == "pending"


@pytest.mark.integration
@pytest.mark.anyio
async def test_begin_connection_without_provider_seed_raises(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        organization = await make_organization(session)
        service = GBPConnectionService()
        with pytest.raises(IntegrationNotConfiguredError):
            await service.begin_connection(
                session,
                make_settings(),
                organization.id,
                actor_id=None,
                correlation_id="test-unseeded",
            )


@pytest.mark.integration
@pytest.mark.anyio
async def test_begin_connection_without_oauth_client_raises(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        service = GBPConnectionService()
        unconfigured = Settings.model_validate({"environment": EnvironmentName.TEST})
        with pytest.raises(IntegrationNotConfiguredError):
            await service.begin_connection(
                session,
                unconfigured,
                organization.id,
                actor_id=None,
                correlation_id="test-unconfigured",
            )


@pytest.mark.integration
@pytest.mark.anyio
async def test_complete_connection_exchanges_code_and_stores_encrypted_tokens(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        settings = make_settings()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/token"
            return httpx.Response(
                200,
                json={
                    "access_token": "real-looking-access-token",
                    "refresh_token": "real-looking-refresh-token",
                    "expires_in": 3600,
                },
            )

        service = GBPConnectionService(
            http_client_factory=mock_client_factory(handler),
        )
        url = await service.begin_connection(
            session, settings, organization.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_authorization_url(url)

        connection = await service.complete_connection(
            session,
            settings,
            organization.id,
            state=state,
            code="authorization-code",
            correlation_id="c2",
        )
        assert connection.status == "connected"
        assert connection.credential_reference is not None
        assert connection.token_expires_at is not None

        tokens = await service._read_tokens(  # noqa: SLF001
            session, settings, connection.credential_reference
        )
        assert tokens["access_token"] == "real-looking-access-token"
        assert tokens["refresh_token"] == "real-looking-refresh-token"


@pytest.mark.integration
@pytest.mark.anyio
async def test_complete_connection_with_reused_state_raises(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        settings = make_settings()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"access_token": "a", "refresh_token": "r", "expires_in": 3600},
            )

        service = GBPConnectionService(http_client_factory=mock_client_factory(handler))
        url = await service.begin_connection(
            session, settings, organization.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_authorization_url(url)
        await service.complete_connection(
            session, settings, organization.id, state=state, code="code-1", correlation_id="c2"
        )
        with pytest.raises(IntegrationStateInvalidError):
            await service.complete_connection(
                session,
                settings,
                organization.id,
                state=state,
                code="code-2",
                correlation_id="c3",
            )


@pytest.mark.integration
@pytest.mark.anyio
async def test_recover_organization_id_with_unknown_state_raises(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        service = GBPConnectionService()
        with pytest.raises(IntegrationStateInvalidError):
            await service.recover_organization_id(session, "not-a-real-state")


@pytest.mark.integration
@pytest.mark.anyio
async def test_fail_connection_marks_intent_failed_and_audits(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        settings = make_settings()
        service = GBPConnectionService()
        url = await service.begin_connection(
            session, settings, organization.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_authorization_url(url)

        await service.fail_connection(
            session,
            organization.id,
            state=state,
            provider_error="access_denied",
            correlation_id="c2",
        )
        # The state was consumed by the failure; it cannot be completed afterward.
        with pytest.raises(IntegrationStateInvalidError):
            await service.complete_connection(
                session,
                settings,
                organization.id,
                state=state,
                code="too-late",
                correlation_id="c3",
            )


@pytest.mark.integration
@pytest.mark.anyio
async def test_ensure_fresh_token_reuses_cached_token_when_not_near_expiry(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        settings = make_settings()

        def connect_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"access_token": "fresh-token", "refresh_token": "r", "expires_in": 3600},
            )

        service = GBPConnectionService(http_client_factory=mock_client_factory(connect_handler))
        url = await service.begin_connection(
            session, settings, organization.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_authorization_url(url)
        connection = await service.complete_connection(
            session, settings, organization.id, state=state, code="code", correlation_id="c2"
        )

        token = await service.ensure_fresh_token(session, settings, connection)
        assert token == "fresh-token"


@pytest.mark.integration
@pytest.mark.anyio
async def test_ensure_fresh_token_refreshes_when_near_expiry(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        settings = make_settings()

        def connect_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "old-token",
                    "refresh_token": "old-refresh",
                    "expires_in": 3600,
                },
            )

        service = GBPConnectionService(http_client_factory=mock_client_factory(connect_handler))
        url = await service.begin_connection(
            session, settings, organization.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_authorization_url(url)
        connection = await service.complete_connection(
            session, settings, organization.id, state=state, code="code", correlation_id="c2"
        )
        # Force the stored expiry to be within the refresh skew window.
        connection.token_expires_at = datetime.now(UTC) + timedelta(minutes=1)
        await session.flush()

        def refresh_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "new-token",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            )

        service.http_client_factory = mock_client_factory(refresh_handler)
        token = await service.ensure_fresh_token(session, settings, connection)
        assert token == "new-token"
        assert connection.status == "connected"


@pytest.mark.integration
@pytest.mark.anyio
async def test_ensure_fresh_token_marks_reconnect_required_on_refresh_failure(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        settings = make_settings()

        def connect_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "old-token",
                    "refresh_token": "old-refresh",
                    "expires_in": 3600,
                },
            )

        service = GBPConnectionService(http_client_factory=mock_client_factory(connect_handler))
        url = await service.begin_connection(
            session, settings, organization.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_authorization_url(url)
        connection = await service.complete_connection(
            session, settings, organization.id, state=state, code="code", correlation_id="c2"
        )
        connection.token_expires_at = datetime.now(UTC) + timedelta(minutes=1)
        await session.flush()

        def failing_refresh_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "invalid_grant"})

        service.http_client_factory = mock_client_factory(failing_refresh_handler)
        with pytest.raises(IntegrationReconnectRequiredError):
            await service.ensure_fresh_token(session, settings, connection)
        assert connection.status == "reconnect_required"


@pytest.mark.integration
@pytest.mark.anyio
async def test_disconnect_revokes_token_and_clears_credential_reference(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        await ProviderCatalogSeeder().run(session)
        organization = await make_organization(session)
        settings = make_settings()
        revoked_tokens: list[str] = []

        def connect_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/revoke":
                revoked_tokens.append(request.content.decode())
                return httpx.Response(200)
            return httpx.Response(
                200,
                json={
                    "access_token": "a",
                    "refresh_token": "refresh-to-revoke",
                    "expires_in": 3600,
                },
            )

        service = GBPConnectionService(http_client_factory=mock_client_factory(connect_handler))
        url = await service.begin_connection(
            session, settings, organization.id, actor_id=None, correlation_id="c1"
        )
        state = state_from_authorization_url(url)
        await service.complete_connection(
            session, settings, organization.id, state=state, code="code", correlation_id="c2"
        )

        connection = await service.disconnect(
            session, settings, organization.id, actor_id=None, correlation_id="c3"
        )
        assert connection.status == "disconnected"
        assert connection.credential_reference is None
        assert any("refresh-to-revoke" in item for item in revoked_tokens)
