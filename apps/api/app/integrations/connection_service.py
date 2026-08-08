"""Google OAuth connection lifecycle: connect, callback, refresh, disconnect.

A single organization-scoped Google ``IntegrationConnection`` (anchored on the
``google_business_profile`` provider row) supports multiple Google products --
Business Profile, Search Console, and Analytics -- through incremental OAuth
authorization. The set of OAuth scopes a connection has actually granted is
recorded on ``IntegrationConnection.granted_capabilities``; requesting an
additional product re-consents (``prompt=consent``) and reuses the *same*
connection row so existing GBP mappings are never disturbed and no duplicate
Google connection records are created.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.integrations.contracts import MappingCreate
from apps.api.app.integrations.errors import (
    IntegrationNotConfiguredError,
    IntegrationNotFoundError,
    IntegrationReconnectRequiredError,
    IntegrationStateInvalidError,
    IntegrationTokenExchangeFailedError,
)
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.integrations.secrets import FernetSecretStore, SecretUnavailableError
from apps.api.app.integrations.service import OAuthIntentService

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
GBP_PROVIDER_KEY = "google_business_profile"
BUSINESS_MANAGE_SCOPE = "https://www.googleapis.com/auth/business.manage"
SEARCH_CONSOLE_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

# Product key -> OAuth scopes that product requires. A single Google connection
# accumulates granted scopes through incremental re-consent; this mapping drives
# which scopes a "connect <product>" action requests.
GOOGLE_PRODUCT_SCOPES: dict[str, tuple[str, ...]] = {
    "gbp": (BUSINESS_MANAGE_SCOPE,),
    "search_console": (SEARCH_CONSOLE_SCOPE,),
    "analytics": (ANALYTICS_SCOPE,),
}
GOOGLE_SCOPE_PRODUCTS: dict[str, str] = {
    BUSINESS_MANAGE_SCOPE: "gbp",
    SEARCH_CONSOLE_SCOPE: "search_console",
    ANALYTICS_SCOPE: "analytics",
}
REFRESH_SKEW = timedelta(minutes=5)
DEFAULT_TOKEN_LIFETIME_SECONDS = 3600


def granted_scopes(connection: IntegrationConnection) -> frozenset[str]:
    """Return the OAuth scopes a connection has actually granted.

    ``granted_capabilities`` is a JSONB list populated from Google's token
    response ``scope`` field on every successful authorization. Empty/missing
    for legacy connections that predate multi-scope tracking; those are treated
    as GBP-only for backward compatibility.
    """
    raw = connection.granted_capabilities
    if not raw:
        return frozenset()
    return frozenset(str(item) for item in raw)


def granted_services(connection: IntegrationConnection) -> dict[str, bool]:
    """Service-level booleans (gbp/search_console/analytics) for status display.

    Never exposes raw OAuth scopes to the UI; this is the safe projection.
    Legacy connections with no recorded scopes are assumed GBP-only.
    """
    scopes = granted_scopes(connection)
    if not scopes:
        return {"gbp": True, "search_console": False, "analytics": False}
    return {
        product: any(scope in scopes for scope in scopes_for_product(product))
        for product in ("gbp", "search_console", "analytics")
    }


def scopes_for_product(product: str) -> tuple[str, ...]:
    return GOOGLE_PRODUCT_SCOPES.get(product, ())


def connection_has_scope(connection: IntegrationConnection, scope: str) -> bool:
    return scope in granted_scopes(connection)


def missing_scopes_for(
    connection: IntegrationConnection, products: Sequence[str]
) -> tuple[str, ...]:
    wanted: set[str] = set()
    for product in products:
        wanted.update(scopes_for_product(product))
    granted = granted_scopes(connection)
    return tuple(sorted(wanted - granted))


@dataclass(slots=True)
class GBPConnectionService:
    """Establish, exchange, refresh, and tear down GBP OAuth connections."""

    intents: OAuthIntentService = field(default_factory=OAuthIntentService)
    audit: AuditEventService = field(default_factory=AuditEventService)
    timeout_seconds: float = 20.0
    http_client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient

    # -- configuration -----------------------------------------------------

    def require_configured(self, settings: Settings) -> tuple[str, str, str]:
        client_id = settings.google_oauth_client_id
        client_secret = settings.google_oauth_client_secret
        redirect_uri = settings.google_oauth_redirect_uri
        if not client_id or not client_secret or not redirect_uri:
            raise IntegrationNotConfiguredError
        return client_id, client_secret, str(redirect_uri)

    def authorization_url(
        self,
        client_id: str,
        redirect_uri: str,
        state: str,
        scopes: Sequence[str] = (BUSINESS_MANAGE_SCOPE,),
    ) -> str:
        # Google accepts a space-delimited scope list. ``prompt=consent`` forces
        # the consent screen so incremental authorization of an additional
        # product returns a fresh refresh token covering the union of granted
        # scopes (Google merges previously granted scopes server-side).
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    # -- provider / connection bookkeeping ----------------------------------

    async def get_provider(self, session: AsyncSession) -> Provider:
        """Look up the already-seeded provider row.

        The provider catalog is platform configuration, not organization-owned
        data, and is registered exclusively through the explicit, idempotent,
        audited seed at `apps.api.app.integrations.provider_seed` (run via
        `scripts/seed_integration_providers.py`) -- never created implicitly
        here. An unseeded provider is treated the same as an unconfigured
        OAuth client: the integration is not available yet.
        """
        provider = await session.scalar(select(Provider).where(Provider.key == GBP_PROVIDER_KEY))
        if provider is None:
            raise IntegrationNotConfiguredError
        return provider

    async def get_or_create_pending_connection(
        self, session: AsyncSession, organization_id: UUID, provider: Provider
    ) -> IntegrationConnection:
        connection = await session.scalar(
            select(IntegrationConnection)
            .where(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.provider_id == provider.id,
                IntegrationConnection.status != "disconnected",
            )
            .order_by(IntegrationConnection.created_at.desc())
        )
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

    async def get_connection(
        self, session: AsyncSession, organization_id: UUID
    ) -> IntegrationConnection:
        connection = await session.scalar(
            select(IntegrationConnection)
            .join(Provider, Provider.id == IntegrationConnection.provider_id)
            .where(
                IntegrationConnection.organization_id == organization_id,
                Provider.key == GBP_PROVIDER_KEY,
            )
            .order_by(IntegrationConnection.created_at.desc())
        )
        if connection is None:
            raise IntegrationNotFoundError
        return connection

    async def find_connection(
        self, session: AsyncSession, organization_id: UUID
    ) -> IntegrationConnection | None:
        """Same lookup as `get_connection`, but returns `None` instead of raising.

        Used by the read-only status route, where "no connection yet" is a
        normal, expected outcome rather than an error.
        """
        connection: IntegrationConnection | None = await session.scalar(
            select(IntegrationConnection)
            .join(Provider, Provider.id == IntegrationConnection.provider_id)
            .where(
                IntegrationConnection.organization_id == organization_id,
                Provider.key == GBP_PROVIDER_KEY,
            )
            .order_by(IntegrationConnection.created_at.desc())
        )
        return connection

    # -- token exchange (real Google HTTP calls) ----------------------------

    async def exchange_code(self, settings: Settings, code: str) -> dict[str, object]:
        client_id, client_secret, redirect_uri = self.require_configured(settings)
        return await self._post_token_endpoint(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        )

    async def refresh_token_pair(self, settings: Settings, refresh_token: str) -> dict[str, object]:
        client_id, client_secret, _ = self.require_configured(settings)
        return await self._post_token_endpoint(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        )

    async def revoke_token(self, token: str) -> bool:
        """Best-effort revocation at Google. Returns whether the call succeeded.

        Never raises: revocation is attempted during disconnect, which must
        proceed regardless of whether Google's revoke call succeeds (the token
        may already be invalid, expired, or Google may be unreachable).
        """
        try:
            async with self.http_client_factory() as client:
                response = await client.post(
                    GOOGLE_REVOKE_ENDPOINT, data={"token": token}, timeout=self.timeout_seconds
                )
        except httpx.HTTPError:
            return False
        return response.status_code < 400

    async def _post_token_endpoint(self, data: dict[str, str]) -> dict[str, object]:
        try:
            async with self.http_client_factory() as client:
                response = await client.post(
                    GOOGLE_TOKEN_ENDPOINT,
                    data=data,
                    headers={"Accept": "application/json"},
                    timeout=self.timeout_seconds,
                )
        except httpx.HTTPError as exc:
            raise IntegrationTokenExchangeFailedError from exc
        if response.status_code >= 400:
            raise IntegrationTokenExchangeFailedError
        payload = response.json()
        if not isinstance(payload, dict) or "access_token" not in payload:
            raise IntegrationTokenExchangeFailedError
        return cast(dict[str, object], payload)

    # -- secret storage helpers ----------------------------------------------

    async def _store_tokens(
        self, session: AsyncSession, settings: Settings, *, access_token: str, refresh_token: str
    ) -> str:
        store = FernetSecretStore.create(session, settings)
        blob = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
        return await store.put(blob)

    async def _read_tokens(
        self, session: AsyncSession, settings: Settings, reference: str
    ) -> dict[str, str]:
        store = FernetSecretStore.create(session, settings)
        raw = await store.get(reference)
        payload = json.loads(raw)
        return {
            "access_token": str(payload["access_token"]),
            "refresh_token": str(payload["refresh_token"]),
        }

    # -- audit ----------------------------------------------------------------

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
                product_key="gbp",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    # -- connect / callback / disconnect --------------------------------------

    async def begin_connection(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        products: Sequence[str] = ("gbp",),
    ) -> str:
        """Begin (or re-consent) a Google OAuth connection for the given products.

        Reuses the organization's existing Google connection row -- never creates
        a duplicate -- so incremental authorization of Search Console or Analytics
        on top of an existing GBP connection preserves all GBP mappings. The
        requested product scopes are unioned with already-granted scopes so a
        re-consent always asks for the minimal additional authorization while
        Google retains the previously granted ones.
        """
        client_id, _, redirect_uri = self.require_configured(settings)
        provider = await self.get_provider(session)
        connection = await self.get_or_create_pending_connection(session, organization_id, provider)
        wanted_scopes: set[str] = set()
        for product in products:
            wanted_scopes.update(scopes_for_product(product))
        # Union with already-granted scopes so re-consent requests the full set
        # Google needs to issue a refresh token covering every product.
        wanted_scopes.update(granted_scopes(connection))
        scopes = tuple(sorted(wanted_scopes)) or (BUSINESS_MANAGE_SCOPE,)
        _, state = await self.intents.create(session, organization_id, connection.id, redirect_uri)
        url = self.authorization_url(client_id, redirect_uri, state, scopes)
        await self._audit(
            session,
            event="gbp.connection.started",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary="Google OAuth connection started.",
            metadata={"status": connection.status, "products": list(products)},
        )
        return url

    async def recover_organization_id(self, session: AsyncSession, state: str) -> UUID:
        """Resolve the organization a callback's `state` belongs to.

        Google's redirect carries only `state`; every subsequent step
        (`complete_connection`/failing an intent) needs the organization it was
        issued for. This is read-only -- `OAuthIntentService.consume`/`fail`
        each independently re-validate hash, status, expiry, and exact
        redirect URI under a row lock before making any change.
        """
        intent = await self.intents.find_by_state(session, state)
        if intent is None:
            raise IntegrationStateInvalidError
        return intent.organization_id

    async def complete_connection(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        state: str,
        code: str,
        correlation_id: str,
    ) -> IntegrationConnection:
        _, _, redirect_uri = self.require_configured(settings)
        try:
            intent = await self.intents.consume(session, organization_id, state, redirect_uri)
        except ValueError as exc:
            raise IntegrationStateInvalidError from exc
        try:
            tokens = await self.exchange_code(settings, code)
            access_token = str(tokens["access_token"])
            refresh_token = tokens.get("refresh_token")
            if not refresh_token:
                raise IntegrationTokenExchangeFailedError
        except IntegrationTokenExchangeFailedError:
            await self._audit(
                session,
                event="gbp.connection.failed",
                organization_id=organization_id,
                actor_id=None,
                resource_type="integration_connection",
                resource_id=intent.connection_id,
                correlation_id=correlation_id,
                summary="GBP OAuth connection failed.",
                metadata={"provider_error": "token_exchange_failed"},
                result=AuditResult.FAILED,
            )
            raise
        expires_in = int(cast(int, tokens.get("expires_in", DEFAULT_TOKEN_LIFETIME_SECONDS)))
        reference = await self._store_tokens(
            session, settings, access_token=access_token, refresh_token=str(refresh_token)
        )
        connection = await session.get(IntegrationConnection, intent.connection_id)
        if connection is None:
            raise IntegrationNotFoundError
        now = datetime.now(UTC)
        connection.credential_reference = reference
        connection.status = "connected"
        connection.token_expires_at = now + timedelta(seconds=expires_in)
        connection.last_verified_at = now
        # Record the OAuth scopes Google actually granted. Google's token
        # response carries a space-delimited ``scope`` field; legacy GBP-only
        # connections upgraded through re-consent accumulate the new scopes
        # here without disturbing any existing GBP mappings.
        granted = tokens.get("scope")
        if isinstance(granted, str) and granted:
            connection.granted_capabilities = cast(list[object], sorted(granted.split()))
        await session.flush()
        await self._audit(
            session,
            event="gbp.connection.connected",
            organization_id=organization_id,
            actor_id=None,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary="GBP OAuth connection established.",
            metadata={"status": connection.status},
        )
        return connection

    async def fail_connection(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        state: str,
        provider_error: str,
        correlation_id: str,
    ) -> None:
        """Record a provider-side denial or error from the callback redirect."""
        intent = await self.intents.fail(session, organization_id, state)
        resource_id = intent.connection_id if intent is not None else organization_id
        await self._audit(
            session,
            event="gbp.connection.failed",
            organization_id=organization_id,
            actor_id=None,
            resource_type="integration_connection",
            resource_id=resource_id,
            correlation_id=correlation_id,
            summary="GBP OAuth connection failed.",
            metadata={"provider_error": provider_error},
            result=AuditResult.FAILED,
        )

    async def disconnect(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> IntegrationConnection:
        connection = await self.get_connection(session, organization_id)
        if connection.credential_reference:
            try:
                tokens = await self._read_tokens(session, settings, connection.credential_reference)
            except SecretUnavailableError:
                tokens = None
            if tokens is not None:
                await self.revoke_token(tokens["refresh_token"])
            try:
                store = FernetSecretStore.create(session, settings)
                await store.delete(connection.credential_reference)
            except SecretUnavailableError:
                pass
        connection.status = "disconnected"
        connection.credential_reference = None
        connection.token_expires_at = None
        await session.flush()
        await self._audit(
            session,
            event="gbp.connection.disconnected",
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary="GBP connection disconnected.",
            metadata={"status": connection.status},
        )
        return connection

    # -- token refresh ----------------------------------------------------------

    async def ensure_fresh_token(
        self, session: AsyncSession, settings: Settings, connection: IntegrationConnection
    ) -> str:
        """Return a valid access token, refreshing via Google if it is near expiry."""
        if not connection.credential_reference:
            raise IntegrationReconnectRequiredError
        tokens = await self._read_tokens(session, settings, connection.credential_reference)
        now = datetime.now(UTC)
        if (
            connection.token_expires_at is not None
            and connection.token_expires_at - now > REFRESH_SKEW
        ):
            return tokens["access_token"]
        try:
            payload = await self.refresh_token_pair(settings, tokens["refresh_token"])
        except IntegrationTokenExchangeFailedError:
            connection.status = "reconnect_required"
            await session.flush()
            await self._audit(
                session,
                event="gbp.connection.reconnect_required",
                organization_id=connection.organization_id,
                actor_id=None,
                resource_type="integration_connection",
                resource_id=connection.id,
                correlation_id="gbp.connection.reconnect_required",
                summary="GBP token refresh failed; reconnect required.",
                metadata={"status": connection.status},
                result=AuditResult.FAILED,
            )
            raise IntegrationReconnectRequiredError from None
        new_access_token = str(payload["access_token"])
        new_refresh_token = str(payload.get("refresh_token") or tokens["refresh_token"])
        expires_in = int(cast(int, payload.get("expires_in", DEFAULT_TOKEN_LIFETIME_SECONDS)))
        refreshed_scope = payload.get("scope")
        old_reference = connection.credential_reference
        new_reference = await self._store_tokens(
            session,
            settings,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )
        store = FernetSecretStore.create(session, settings)
        await store.delete(old_reference)
        connection.credential_reference = new_reference
        connection.token_expires_at = now + timedelta(seconds=expires_in)
        connection.last_verified_at = now
        connection.status = "connected"
        if isinstance(refreshed_scope, str) and refreshed_scope:
            connection.granted_capabilities = cast(list[object], sorted(refreshed_scope.split()))
        await session.flush()
        await self._audit(
            session,
            event="gbp.connection.refreshed",
            organization_id=connection.organization_id,
            actor_id=None,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id="gbp.connection.refreshed",
            summary="GBP access token refreshed.",
            metadata={"status": connection.status},
        )
        return new_access_token

    # -- resource mapping ---------------------------------------------------

    async def upsert_mapping(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: MappingCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> ProviderResourceMapping:
        existing = await session.scalar(
            select(ProviderResourceMapping).where(
                ProviderResourceMapping.organization_id == organization_id,
                ProviderResourceMapping.connection_id == command.connection_id,
                ProviderResourceMapping.resource_type == "location",
                ProviderResourceMapping.external_resource_id == command.external_resource_id,
            )
        )
        event = "gbp.mapping.updated"
        if existing is not None:
            existing.platform_resource_id = command.platform_resource_id
            existing.status = "active"
            await session.flush()
            item = existing
        else:
            item = ProviderResourceMapping(
                organization_id=organization_id,
                connection_id=command.connection_id,
                resource_type="location",
                external_resource_id=command.external_resource_id,
                platform_resource_id=command.platform_resource_id,
                status="active",
            )
            session.add(item)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise IntegrationNotFoundError from exc
            event = "gbp.mapping.created"
        await self._audit(
            session,
            event=event,
            organization_id=organization_id,
            actor_id=actor_id,
            resource_type="provider_resource_mapping",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary="GBP provider resource mapping recorded.",
            metadata={"external_resource_id": item.external_resource_id},
        )
        return item
