"""Typed runtime configuration for the LILOs API."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, ClassVar

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentName(StrEnum):
    """Supported application environments."""

    LOCAL = "local"
    TEST = "test"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported application log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Validated settings loaded from environment variables and an optional `.env` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        env_prefix="LILOS_",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    environment: EnvironmentName = Field(
        default=EnvironmentName.LOCAL,
        validation_alias="LILOS_ENV",
    )
    log_level: LogLevel = LogLevel.INFO
    api_title: Annotated[str, Field(min_length=1, max_length=100)] = "LILOs Platform API"
    api_version: Annotated[
        str,
        Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z][0-9A-Za-z.+-]*$"),
    ] = "0.1.0"
    database_url: PostgresDsn | None = None
    migration_database_url: PostgresDsn | None = None
    test_database_url: PostgresDsn | None = None
    database_connect_timeout_seconds: Annotated[float, Field(gt=0, le=30)] = 5.0
    internal_admin_routes_enabled: bool = False
    service_name: ClassVar[str] = "lilos-api"

    @model_validator(mode="after")
    def reject_unsafe_internal_admin_routes(self) -> "Settings":
        """Allow temporary bootstrap routes only in explicitly enabled local or test runtimes."""
        if self.internal_admin_routes_enabled and self.environment not in {
            EnvironmentName.LOCAL,
            EnvironmentName.TEST,
        }:
            raise ValueError(
                "Internal administrative routes may be enabled only in local or test environments"
            )
        return self

    def application_database_url(self) -> str | None:
        """Return the application URL using SQLAlchemy's asyncpg dialect."""
        return _normalize_postgresql_url(self.database_url)

    def alembic_database_url(self) -> str | None:
        """Return the migration URL, falling back to the application URL."""
        return _normalize_postgresql_url(self.migration_database_url or self.database_url)

    def integration_test_database_url(self) -> str | None:
        """Return the isolated PostgreSQL URL reserved for integration tests."""
        return _normalize_postgresql_url(self.test_database_url)


def _normalize_postgresql_url(value: PostgresDsn | None) -> str | None:
    if value is None:
        return None
    url = value.unicode_string()
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    raise ValueError("PostgreSQL URLs must use the asyncpg driver")


@lru_cache
def get_settings() -> Settings:
    """Load and cache process settings."""
    return Settings()
