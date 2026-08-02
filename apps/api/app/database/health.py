"""Sanitized PostgreSQL readiness checks."""

import logging
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import text

from apps.api.app.database.runtime import DatabaseRuntime

logger = logging.getLogger("lilos.api.database")


class DatabaseHealthReason(StrEnum):
    """Internal, non-sensitive readiness outcomes."""

    AVAILABLE = "available"
    CONFIGURATION_MISSING = "configuration_missing"
    CONNECTION_FAILED = "connection_failed"


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    """Internal result used to construct the public readiness schema."""

    available: bool
    reason: DatabaseHealthReason


async def check_database_health(runtime: DatabaseRuntime) -> DatabaseHealth:
    """Execute a bounded PostgreSQL connectivity check without exposing details."""
    if not runtime.configured:
        logger.warning(
            "PostgreSQL readiness configuration is missing",
            extra={
                "event_name": "database.readiness.unavailable",
                "outcome": "failure",
                "normalized_error_code": "DATABASE_CONFIGURATION_MISSING",
            },
        )
        return DatabaseHealth(False, DatabaseHealthReason.CONFIGURATION_MISSING)

    try:
        async with runtime.require_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning(
            "PostgreSQL readiness check failed",
            extra={
                "event_name": "database.readiness.unavailable",
                "outcome": "failure",
                "normalized_error_code": "DATABASE_UNAVAILABLE",
                "exception_type": type(exc).__name__,
            },
        )
        return DatabaseHealth(False, DatabaseHealthReason.CONNECTION_FAILED)

    return DatabaseHealth(True, DatabaseHealthReason.AVAILABLE)
