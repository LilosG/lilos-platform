"""GitHub App installation flow and short-lived installation access tokens.

The normal production Content publishing path authenticates to GitHub as a
GitHub App installation -- not with a long-lived user PAT. This service:

- builds the GitHub OAuth/App authorization URL to install the LILOs GitHub App
  for an organization, carrying a one-time, hashed, tenant-bound ``state``;
- exchanges nothing for a long-lived token on the callback -- only the
  ``installation_id`` is captured and persisted (the state binds it to the
  LILOs organization);
- mints short-lived (1h) installation access tokens server-side, on demand,
  from the app private key + installation id -- these tokens are NEVER persisted;
- discovers the repositories the installation can access.

The app private key is read from configuration (``LILOS_GITHUB_APP_PRIVATE_KEY``)
and never logged or returned. PAT-based publishing remains available only as an
explicit advanced/developer fallback (``GitHubConnectionCreate``).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.integrations.errors import (
    IntegrationNotConfiguredError,
    IntegrationNotFoundError,
    IntegrationStateInvalidError,
)
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.integrations.service import OAuthIntentService

GITHUB_API = "https://api.github.com"
GITHUB_AUTHORIZE_ENDPOINT = "https://github.com/login/oauth/authorize"
GITHUB_INSTALLATION_PREFIX = "installation:"
INSTALLATION_TOKEN_LIFETIME = timedelta(hours=1)
APP_JWT_LIFETIME = timedelta(minutes=10)
GITHUB_PAGE_SIZE = 100
MAX_GITHUB_PAGES = 1_000


@dataclass(frozen=True, slots=True)
class DiscoveredRepository:
    repository_id: str  # "owner/name"
    name: str
    default_branch: str
    private: bool


@dataclass(frozen=True, slots=True)
class InstallationToken:
    token: str
    expires_at: datetime


class GitHubAppNotConfiguredError(IntegrationNotConfiguredError):
    """GitHub App configuration (app id, client id, private key) is missing."""


def installation_id_from_reference(reference: str | None) -> str | None:
    """Extract the installation id stored on a connection's external_account_reference."""
    if not reference or not reference.startswith(GITHUB_INSTALLATION_PREFIX):
        return None
    return reference.removeprefix(GITHUB_INSTALLATION_PREFIX)


@dataclass(slots=True)
class GitHubAppService:
    """GitHub App installation authorization, token minting, and discovery."""

    intents: OAuthIntentService = field(default_factory=OAuthIntentService)
    audit: AuditEventService = field(default_factory=AuditEventService)
    timeout_seconds: float = 20.0
    http_client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient

    # -- configuration --------------------------------------------------------

    def require_configured(self, settings: Settings) -> tuple[str, str, str, str]:
        app_id = settings.github_app_id
        client_id = settings.github_app_client_id
        private_key = settings.github_app_private_key
        redirect_uri = settings.github_app_installation_redirect_uri
        if not app_id or not client_id or not private_key or not redirect_uri:
            raise GitHubAppNotConfiguredError
        return app_id, client_id, private_key, str(redirect_uri)

    async def get_provider(self, session: AsyncSession) -> Provider:
        provider = await session.scalar(select(Provider).where(Provider.key == "github"))
        if provider is None:
            raise IntegrationNotConfiguredError
        return provider

    # -- app authentication (JWT) --------------------------------------------

    def sign_app_jwt(self, settings: Settings) -> str:
        _, _, private_key, _ = self.require_configured(settings)
        now = datetime.now(UTC)
        payload = {
            "iat": int(now.timestamp()),
            "exp": int((now + APP_JWT_LIFETIME).timestamp()),
            "iss": str(settings.github_app_id),
        }
        return jwt.encode(payload, private_key, algorithm="RS256")

    # -- install flow --------------------------------------------------------

    async def begin_install(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> str:
        """Build the GitHub authorization URL to install the LILOs GitHub App.

        Reuses the organization's existing GitHub connection row (creating a
        pending one if needed) and a one-time OAuth intent bound to it, so the
        callback can recover the LILOs organization from ``state`` alone.
        """
        _, _, _, redirect_uri = self.require_configured(settings)
        provider = await self.get_provider(session)
        connection = await self._get_or_create_pending_connection(
            session, organization_id, provider
        )
        _, state = await self.intents.create(session, organization_id, connection.id, redirect_uri)
        params = {"state": state}
        url = (
            f"https://github.com/apps/{settings.github_app_slug}/installations/new"
            f"?{urlencode(params)}"
        )
        await self._audit(
            session,
            event="content.github_app.install_started",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary="GitHub App installation started.",
            metadata={},
        )
        return url

    async def recover_organization_id(self, session: AsyncSession, state: str) -> UUID:
        intent = await self.intents.find_by_state(session, state)
        if intent is None:
            raise IntegrationStateInvalidError
        return intent.organization_id

    async def complete_install(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        state: str,
        installation_id: str,
        setup_action: str | None,
        correlation_id: str,
    ) -> IntegrationConnection:
        """Persist the GitHub App installation for this organization.

        Validates the installation is a real installation of this app by
        fetching it with the app JWT, then stores the stable installation id on
        the organization's GitHub connection (never an access token). Reuses
        the existing connection row so PAT fallback configuration is preserved.
        """
        _, _, _, redirect_uri = self.require_configured(settings)
        intent = await self.intents.consume(session, organization_id, state, redirect_uri)
        connection = await session.get(IntegrationConnection, intent.connection_id)
        if connection is None:
            raise IntegrationNotFoundError
        # Validate the installation exists and belongs to this app.
        await self._get_installation(settings, installation_id)
        connection.external_account_reference = f"{GITHUB_INSTALLATION_PREFIX}{installation_id}"
        connection.status = "connected"
        # A GitHub App installation holds no long-lived credential; clear any
        # prior PAT reference so normal publishing uses installation tokens.
        connection.credential_reference = None
        await session.flush()
        await self._audit(
            session,
            event="content.github_app.installed",
            organization_id=organization_id,
            actor_id=None,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary="GitHub App installation recorded.",
            metadata={"setup_action": setup_action or ""},
        )
        return connection

    async def fail_install(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        state: str,
        provider_error: str,
        correlation_id: str,
    ) -> None:
        intent = await self.intents.fail(session, organization_id, state)
        resource_id = intent.connection_id if intent is not None else organization_id
        await self._audit(
            session,
            event="content.github_app.install_failed",
            organization_id=organization_id,
            actor_id=None,
            resource_type="integration_connection",
            resource_id=resource_id,
            correlation_id=correlation_id,
            summary="GitHub App installation failed.",
            metadata={"provider_error": provider_error},
            result=AuditResult.FAILED,
        )

    # -- installation access tokens (short-lived, never persisted) -----------

    async def create_installation_token(
        self, settings: Settings, installation_id: str
    ) -> InstallationToken:
        app_jwt = self.sign_app_jwt(settings)
        async with self.http_client_factory() as client:
            response = await client.post(
                f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=self.timeout_seconds,
            )
        if response.status_code != 201:
            raise RuntimeError(
                f"GitHub installation token request returned {response.status_code}: "
                f"{response.text[:200]}"
            )
        payload = response.json()
        token = str(payload["token"])
        expires_at = datetime.fromisoformat(str(payload["expires_at"]).replace("Z", "+00:00"))
        return InstallationToken(token=token, expires_at=expires_at)

    async def _get_installation(self, settings: Settings, installation_id: str) -> dict[str, Any]:
        app_jwt = self.sign_app_jwt(settings)
        async with self.http_client_factory() as client:
            response = await client.get(
                f"{GITHUB_API}/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=self.timeout_seconds,
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"GitHub installation lookup returned {response.status_code}: {response.text[:200]}"
            )
        return cast(dict[str, Any], response.json())

    # -- repository discovery ------------------------------------------------

    async def list_installation_repositories(
        self, settings: Settings, installation_id: str
    ) -> list[DiscoveredRepository]:
        token = await self.create_installation_token(settings, installation_id)
        url = f"{GITHUB_API}/installation/repositories"
        results: list[DiscoveredRepository] = []
        raw_count = 0
        provider_total: int | None = None
        for page_number in range(1, MAX_GITHUB_PAGES + 1):
            async with self.http_client_factory() as client:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token.token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"page": page_number, "per_page": GITHUB_PAGE_SIZE},
                    timeout=self.timeout_seconds,
                )
            if response.status_code != 200:
                raise RuntimeError(
                    f"GitHub installation repositories returned {response.status_code}: "
                    f"{response.text[:200]}"
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("invalid GitHub installation repositories response")
            repositories = payload.get("repositories", [])
            if not isinstance(repositories, list) or not all(
                isinstance(repo, dict) for repo in repositories
            ):
                raise RuntimeError("invalid GitHub repositories page")
            raw_repositories = cast(list[dict[str, Any]], repositories)
            raw_count += len(raw_repositories)

            raw_total = payload.get("total_count")
            if raw_total is not None:
                if isinstance(raw_total, bool) or not isinstance(raw_total, int) or raw_total < 0:
                    raise RuntimeError("invalid GitHub repository total_count")
                provider_total = max(provider_total or 0, raw_total)
            if provider_total is not None and raw_count > provider_total:
                raise RuntimeError("GitHub repository pagination exceeded provider total")

            for repo in raw_repositories:
                full_name = str(repo.get("full_name", ""))
                if not full_name:
                    continue
                results.append(
                    DiscoveredRepository(
                        repository_id=full_name,
                        name=str(repo.get("name", "")),
                        default_branch=str(repo.get("default_branch", "main")),
                        private=bool(repo.get("private", False)),
                    )
                )

            if provider_total is not None and raw_count == provider_total:
                return results
            if provider_total is None and len(raw_repositories) < GITHUB_PAGE_SIZE:
                return results
            if provider_total is not None and len(raw_repositories) < GITHUB_PAGE_SIZE:
                raise RuntimeError("GitHub repository pagination is incomplete")

        raise RuntimeError("GitHub repository pagination exceeded safety limit")

    # -- connection lookup ---------------------------------------------------

    async def find_connection(
        self, session: AsyncSession, organization_id: UUID
    ) -> IntegrationConnection | None:
        result: IntegrationConnection | None = await session.scalar(
            select(IntegrationConnection)
            .join(Provider, Provider.id == IntegrationConnection.provider_id)
            .where(
                IntegrationConnection.organization_id == organization_id,
                Provider.key == "github",
                IntegrationConnection.status != "disconnected",
            )
            .order_by(IntegrationConnection.created_at.desc())
        )
        return result

    async def disconnect_installation(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> IntegrationConnection:
        """Revoke the local installation binding without a GitHub write.

        GitHub App uninstall is controlled by GitHub and can affect other
        organizations using the same installation. LILOs therefore removes
        its local authorization immediately; the operator can uninstall the
        App in GitHub separately when remote revocation is desired.
        """
        connection = await self.find_connection(session, organization_id)
        if connection is None:
            raise IntegrationNotFoundError
        connection.external_account_reference = None
        connection.credential_reference = None
        connection.status = "disconnected"
        await session.flush()
        await self._audit(
            session,
            event="content.github_app.disconnected",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary="GitHub App installation disconnected locally.",
            metadata={"remote_uninstall_required": True},
        )
        return connection

    async def _get_or_create_pending_connection(
        self, session: AsyncSession, organization_id: UUID, provider: Provider
    ) -> IntegrationConnection:
        connection = await self.find_connection(session, organization_id)
        if connection is not None:
            return connection
        connection = IntegrationConnection(
            organization_id=organization_id,
            provider_id=provider.id,
            status="pending",
        )
        session.add(connection)
        await session.flush()
        return connection

    # -- audit ---------------------------------------------------------------

    async def _audit(
        self,
        session: AsyncSession,
        *,
        event: str,
        organization_id: UUID,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        correlation_id: str,
        summary: str,
        metadata: dict[str, object],
        result: AuditResult = AuditResult.SUCCEEDED,
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=result,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                product_key="content",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )
