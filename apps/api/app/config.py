"""Typed runtime configuration for the LILOs API."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, ClassVar

from cryptography.fernet import Fernet
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
    provider_writes_enabled: bool = False
    web_origins: Annotated[str, Field(max_length=2_048)] = ""
    supabase_auth_issuer: HttpUrl | None = None
    supabase_auth_audience: Annotated[str, Field(min_length=1, max_length=128)] = "authenticated"
    supabase_auth_jwks_url: HttpUrl | None = None
    supabase_auth_allowed_algorithms: str = "ES256,RS256"
    supabase_auth_jwks_cache_seconds: Annotated[int, Field(ge=60, le=86_400)] = 900
    supabase_auth_jwks_stale_seconds: Annotated[int, Field(ge=60, le=86_400)] = 3_600
    supabase_auth_clock_skew_seconds: Annotated[int, Field(ge=0, le=300)] = 60
    supabase_auth_max_token_bytes: Annotated[int, Field(ge=1_024, le=65_536)] = 16_384

    google_oauth_client_id: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    google_oauth_client_secret: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    google_oauth_redirect_uri: HttpUrl | None = None
    google_pagespeed_api_key: Annotated[str, Field(min_length=1, max_length=512)] | None = None
    google_drive_service_account_json: (
        Annotated[str, Field(min_length=2, max_length=50_000)] | None
    ) = None

    # Optional external SEO enrichment provider. LILOs remains operational
    # without it; when configured it can enrich deterministic crawl/GSC data.
    dataforseo_login: Annotated[str, Field(min_length=1, max_length=512)] | None = None
    dataforseo_password: Annotated[str, Field(min_length=1, max_length=512)] | None = None
    dataforseo_base_url: Annotated[str, Field(min_length=1, max_length=512)] = (
        "https://api.dataforseo.com/v3"
    )

    secret_encryption_key: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    secret_encryption_key_version: Annotated[int, Field(ge=1)] = 1

    # GitHub App (normal production publishing). The private key is the PEM
    # string configured in the secret manager; it is never committed and never
    # returned by any API. Installation access tokens are minted server-side
    # from the installation id and never persisted.
    github_app_id: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    github_app_client_id: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    github_app_slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ] = "lilos-growth-operations"
    github_app_private_key: Annotated[str, Field(min_length=1, max_length=20_000)] | None = None
    github_app_installation_redirect_uri: HttpUrl | None = None

    # ── AI Gateway ──────────────────────────────────────────────────────
    ai_provider: Annotated[str, Field(min_length=1, max_length=64)] = "deterministic"
    ai_openrouter_api_key: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=255,
            validation_alias="LILOS_OPENROUTER_API_KEY",
        ),
    ] = None
    ai_openrouter_base_url: Annotated[
        str,
        Field(min_length=1, max_length=512, validation_alias="LILOS_OPENROUTER_BASE_URL"),
    ] = "https://openrouter.ai/api/v1"
    ai_default_model: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    ai_task_model_overrides: Annotated[str, Field(max_length=4_096)] = ""
    ai_timeout_seconds: Annotated[float, Field(gt=0, le=300)] = 60.0
    ai_max_output_tokens: Annotated[int, Field(ge=1, le=32_768)] = 2_000
    ai_maximum_cost_microunits: Annotated[int, Field(ge=0, le=10_000_000)] = 200_000
    service_name: ClassVar[str] = "lilos-api"

    @field_validator("web_origins")
    @classmethod
    def validate_web_origins(cls, value: str) -> str:
        origins = tuple(item.strip() for item in value.split(",") if item.strip())
        for origin in origins:
            parsed = HttpUrl(origin)
            if parsed.path not in (None, "", "/") or parsed.query or parsed.fragment:
                raise ValueError("LILOS_WEB_ORIGINS entries must be bare origins, not URLs")
        return ",".join(dict.fromkeys(origins))

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
    def validate_production_web_origins(self) -> "Settings":
        if self.environment is EnvironmentName.PRODUCTION:
            for origin in self.allowed_web_origins():
                if not origin.startswith("https://"):
                    raise ValueError("LILOS_WEB_ORIGINS entries must use HTTPS in production")
        return self

    @model_validator(mode="after")
    def validate_production_observability(self) -> "Settings":
        if self.environment is EnvironmentName.PRODUCTION:
            if self.release == "development":
                raise ValueError("production requires an immutable release identifier")
            if self.telemetry_export_endpoint is None:
                raise ValueError("production requires a telemetry export endpoint")
        return self

    @field_validator("secret_encryption_key")
    @classmethod
    def validate_secret_encryption_key(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            Fernet(value.encode("utf-8"))
        except ValueError as exc:
            raise ValueError(
                "LILOS_SECRET_ENCRYPTION_KEY must be a base64 urlsafe 32-byte Fernet key"
            ) from exc
        return value

    def application_database_url(self) -> str | None:
        """Return the application URL using SQLAlchemy's asyncpg dialect."""
        return _normalize_postgresql_url(self.database_url)

    def alembic_database_url(self) -> str | None:
        """Return the migration URL, falling back to the application URL."""
        return _normalize_postgresql_url(self.migration_database_url or self.database_url)

    def integration_test_database_url(self) -> str | None:
        """Return the isolated PostgreSQL URL reserved for integration tests."""
        return _normalize_postgresql_url(self.test_database_url)

    def allowed_web_origins(self) -> tuple[str, ...]:
        return tuple(origin for origin in self.web_origins.split(",") if origin)

    def authentication_algorithms(self) -> tuple[str, ...]:
        return tuple(self.supabase_auth_allowed_algorithms.split(","))

    def require_authentication_urls(self) -> tuple[str, str]:
        if self.supabase_auth_issuer is None or self.supabase_auth_jwks_url is None:
            raise ValueError("Supabase authentication issuer and JWKS URL must be configured")
        return str(self.supabase_auth_issuer).rstrip("/"), str(self.supabase_auth_jwks_url)

    def ai_task_model_map(self) -> dict[str, str]:
        """Parse LILOS_AI_TASK_MODEL_OVERRIDES as a JSON map of task_key → model."""
        raw = self.ai_task_model_overrides.strip()
        if not raw:
            return {}
        import json

        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("LILOS_AI_TASK_MODEL_OVERRIDES must be a JSON object")
        return {str(k): str(v) for k, v in parsed.items()}


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
