"""FastAPI database-session dependency."""

import logging
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.runtime import DatabaseRuntime
from apps.api.app.errors import DatabaseUnavailableError

logger = logging.getLogger("lilos.api.database")


def database_runtime_from_request(request: Request) -> DatabaseRuntime:
    """Return the process-owned database runtime attached to the application."""
    runtime = request.app.state.database
    if not isinstance(runtime, DatabaseRuntime):
        raise DatabaseUnavailableError
    return runtime


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one transaction-bound session and safely close it after the request."""
    session_factory = database_runtime_from_request(request).require_session_factory()
    async with session_factory() as session:
        try:
            async with session.begin():
                yield session
        except SQLAlchemyError as exc:
            if session.in_transaction():
                await session.rollback()
            logger.error(
                "Database operation failed",
                extra={
                    "event_name": "database.operation.failed",
                    "outcome": "failure",
                    "normalized_error_code": "DATABASE_UNAVAILABLE",
                    "exception_type": type(exc).__name__,
                },
            )
            raise DatabaseUnavailableError from None
