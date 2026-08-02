"""Database engine, session factory, and connection lifecycle."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api.app.config import Settings
from apps.api.app.errors import DatabaseUnavailableError


@dataclass(slots=True)
class DatabaseRuntime:
    """Optional process-owned database resources."""

    engine: AsyncEngine | None
    session_factory: async_sessionmaker[AsyncSession] | None

    @classmethod
    def unconfigured(cls) -> "DatabaseRuntime":
        """Create a runtime that supports liveness but no database operations."""
        return cls(engine=None, session_factory=None)

    @property
    def configured(self) -> bool:
        """Return whether database resources were configured."""
        return self.engine is not None and self.session_factory is not None

    def require_engine(self) -> AsyncEngine:
        """Return the engine or fail with a safe application error."""
        if self.engine is None:
            raise DatabaseUnavailableError
        return self.engine

    def require_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Return the session factory or fail with a safe application error."""
        if self.session_factory is None:
            raise DatabaseUnavailableError
        return self.session_factory

    async def dispose(self) -> None:
        """Close the process-owned connection pool if one exists."""
        if self.engine is not None:
            await self.engine.dispose()


def create_database_runtime(settings: Settings) -> DatabaseRuntime:
    """Create lazy async database resources from validated settings."""
    database_url = settings.application_database_url()
    if database_url is None:
        return DatabaseRuntime.unconfigured()

    engine = create_async_engine(
        database_url,
        connect_args={"timeout": settings.database_connect_timeout_seconds},
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return DatabaseRuntime(engine=engine, session_factory=session_factory)
