"""Test-only `TransactionScope` that reuses the session a test already has open.

Production sync code opens its own short transactions from an `async_sessionmaker`.
Most existing sync tests build their fixtures and assert inside one transaction, so
this yields that same session for every phase (flushing on exit) and lets them keep
testing persistence behaviour unchanged. The transaction-discipline guarantee --
no transaction open during provider HTTP -- is tested separately, against a real
session factory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from apps.api.app.config import Settings
from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.integrations.errors import IntegrationTokenRejectedError


class SharedSessionScope:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        yield self._session
        await self._session.flush()


OPEN_TRANSACTIONS = """
    SELECT count(*) FROM pg_stat_activity
    WHERE datname = current_database()
      AND pid <> pg_backend_pid()
      AND state LIKE 'idle in transaction%'
"""


class TransactionProbe:
    """Counts `idle in transaction` sessions, observed from outside the sync."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, poolclass=NullPool)
        self.open_during_provider_calls: list[int] = []

    async def record(self) -> None:
        async with self._engine.connect() as connection:
            self.open_during_provider_calls.append(
                int(await connection.scalar(text(OPEN_TRANSACTIONS)) or 0)
            )

    async def close(self) -> None:
        await self._engine.dispose()


class ProbedConnectionService(GBPConnectionService):
    """Refresh the token for real, but observe the database while Google is called."""

    def __init__(self, probe: TransactionProbe, *, reject: bool = False) -> None:
        super().__init__()
        self.probe = probe
        self.reject = reject

    async def refresh_token_pair(self, settings: Settings, refresh_token: str) -> dict[str, object]:
        await self.probe.record()
        if self.reject:
            raise IntegrationTokenRejectedError
        return {
            "access_token": "refreshed-access",
            "refresh_token": refresh_token,
            "expires_in": 3600,
        }
