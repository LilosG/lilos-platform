"""Typed runtime configuration for the LILOs API."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, ClassVar

from pydantic import Field, HttpUrl, PostgresDsn, field_validator, model_validator
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
    release: Annotated[str, Field(min_length=1, max_length=64)] = "development"
    trace_sample_rate: Annotated[float, Field(ge=0, le=1)] = 0.1
    telemetry_export_endpoint: HttpUrl | None = None
    database_url: PostgresDsn | None = None
    migration_database_url: PostgresDsn | None = None
    test_database_url: PostgresDsn | None = None
    database_connect_timeout_seconds: Annotated[float, Field(gt=0, le=30)] = 5.0
    internal_admin_routes_enabled: bool = False
    supabase_auth_issuer: HttpUrl | None = None
    supabase_auth_audience: Annotated[str, Field(min_length=1, max_length=128)] = "authenticated"
    supabase_auth_jwks_url: HttpUrl | None = None
    supabase_auth_allowed_algorithms: str = "ES256,RS256"
    supabase_auth_jwks_cache_seconds: Annotated[int, Field(ge=60, le=86_400)] = 900
    supabase_auth_jwks_stale_seconds: Annotated[int, Field(ge=60, le=86_400)] = 3_600
    supabase_auth_clock_skew_seconds: Annotated[int, Field(ge=0, le=300)] = 60
    supabase_auth_max_token_bytes: Annotated[int, Field(ge=1_024, le=65_536)] = 16_384
    service_name: ClassVar[str] = "lilos-api"

    @field_validator("supabase_auth_allowed_algorithms")
    @classmethod
    def validate_auth_algorithms(cls, value: str) -> str:
        algorithms = tuple(item.strip() for item in value.split(",") if item.strip())
        if not algorithms or set(algorithms) - {"ES256", "RS256"}:
            raise ValueError("Supabase authentication algorithms must be ES256 and/or RS256")
        return ",".join(dict.fromkeys(algorithms))

    @model_validator(mode="after")
    def validate_authentication_configuration(self) -> "Settings":
        if self.supabase_auth_jwks_stale_seconds < self.supabase_auth_jwks_cache_seconds:
            raise ValueError("JWKS stale allowance must not be shorter than its fresh cache")
        for value, name in (
            (self.supabase_auth_issuer, "SUPABASE_AUTH_ISSUER"),
            (self.supabase_auth_jwks_url, "SUPABASE_AUTH_JWKS_URL"),
        ):
            if value is not None and value.scheme != "https":
                raise ValueError(f"{name} must use HTTPS")
        return self

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

    @model_validator(mode="after")
    def validate_production_observability(self) -> "Settings":
        if self.environment is EnvironmentName.PRODUCTION:
            if self.release == "development":
                raise ValueError("production requires an immutable release identifier")
            if self.telemetry_export_endpoint is None:
                raise ValueError("production requires a telemetry export endpoint")
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

    def authentication_algorithms(self) -> tuple[str, ...]:
        return tuple(self.supabase_auth_allowed_algorithms.split(","))

    def require_authentication_urls(self) -> tuple[str, str]:
        if self.supabase_auth_issuer is None or self.supabase_auth_jwks_url is None:
            raise ValueError("Supabase authentication issuer and JWKS URL must be configured")
        return str(self.supabase_auth_issuer).rstrip("/"), str(self.supabase_auth_jwks_url)


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
