"""OAuth intent and secret-boundary primitives."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.integrations.models import OAuthAuthorizationIntent


class SecretStore(Protocol):
    async def put(self, value: str) -> str: ...
    async def get(self, reference: str) -> str: ...
    async def delete(self, reference: str) -> None: ...


class OAuthIntentService:
    async def create(
        self,
        session: AsyncSession,
        organization_id: UUID,
        connection_id: UUID,
        redirect_uri: str,
        verifier_reference: str | None = None,
    ) -> tuple[OAuthAuthorizationIntent, str]:
        state = secrets.token_urlsafe(32)
        digest = hashlib.sha256(state.encode()).hexdigest()
        item = OAuthAuthorizationIntent(
            organization_id=organization_id,
            connection_id=connection_id,
            state_hash=digest,
            pkce_verifier_reference=verifier_reference,
            exact_redirect_uri=redirect_uri,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        session.add(item)
        await session.flush()
        return item, state

    async def consume(
        self, session: AsyncSession, organization_id: UUID, state: str, redirect_uri: str
    ) -> OAuthAuthorizationIntent:
        digest = hashlib.sha256(state.encode()).hexdigest()
        item = await session.scalar(
            select(OAuthAuthorizationIntent)
            .where(
                OAuthAuthorizationIntent.organization_id == organization_id,
                OAuthAuthorizationIntent.state_hash == digest,
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        if (
            not item
            or item.status != "pending"
            or item.expires_at <= now
            or item.exact_redirect_uri != redirect_uri
        ):
            raise ValueError("invalid authorization response")
        item.status = "consumed"
        item.consumed_at = now
        await session.flush()
        return item
