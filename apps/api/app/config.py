"""Typed runtime configuration for the LILOs API."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, ClassVar

from pydantic import Field
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
    service_name: ClassVar[str] = "lilos-api"


@lru_cache
def get_settings() -> Settings:
    """Load and cache process settings."""
    return Settings()
