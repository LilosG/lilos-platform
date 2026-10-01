"""Negative configuration cases must fail before any external I/O."""

import hashlib
from typing import Any

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from apps.api.app.config import Settings
from apps.api.app.staging.write_boundary import (
    ProviderWriteDeniedError,
    require_github_scope,
    require_google_write,
)
from scripts.validate_staging_console import validate

STAGING_PROJECT = "abcdefghijklmnopqrst"
PRODUCTION_PROJECT = "uvwxyzabcdefghijklmn"


def staging_values() -> dict[str, Any]:
    return dict(
        _env_file=None,
        environment="staging",
        google_provider_mode="fixture",
        staging_supabase_project_ref=STAGING_PROJECT,
        production_supabase_project_ref=PRODUCTION_PROJECT,
        database_url=f"postgresql://postgres:test@db.{STAGING_PROJECT}.supabase.co/postgres",
        migration_database_url=f"postgresql://postgres:test@db.{STAGING_PROJECT}.supabase.co/postgres",
        supabase_auth_issuer=f"https://{STAGING_PROJECT}.supabase.co/auth/v1",
        supabase_auth_jwks_url=f"https://{STAGING_PROJECT}.supabase.co/auth/v1/.well-known/jwks.json",
        secret_encryption_key=Fernet.generate_key().decode(),
        staging_forbidden_secret_sha256=hashlib.sha256(b"synthetic production secret").hexdigest(),
        provider_writes_enabled=True,
        staging_github_repository="SyntheticOwner/staging-test",
        staging_github_installation_id="1001",
        staging_github_path_prefix="src/content/test/",
    )


@pytest.mark.parametrize(
    "change",
    [
        {
            "database_url": f"postgresql://postgres:test@db.{PRODUCTION_PROJECT}.supabase.co/postgres"
        },
        {
            "migration_database_url": f"postgresql://postgres.{PRODUCTION_PROJECT}:test@aws-0-us-west-2.pooler.supabase.com/postgres"
        },
        {"database_url": "postgresql://postgres:test@unapproved.invalid/postgres"},
        {"staging_supabase_project_ref": PRODUCTION_PROJECT},
        {"supabase_auth_issuer": f"https://{PRODUCTION_PROJECT}.supabase.co/auth/v1"},
        {
            "supabase_auth_jwks_url": f"https://{PRODUCTION_PROJECT}.supabase.co/auth/v1/.well-known/jwks.json"
        },
        {"staging_github_repository": "LilosG/lilos-growth"},
        {"staging_github_path_prefix": "src/../"},
        {"staging_forbidden_secret_sha256": ""},
        {"staging_github_installation_id": None},
    ],
)
def test_staging_rejects_unsafe_config(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Settings(**(staging_values() | change))


def test_staging_rejects_production_encryption_key() -> None:
    values = staging_values()
    values["staging_forbidden_secret_sha256"] = hashlib.sha256(
        values["secret_encryption_key"].encode()
    ).hexdigest()
    with pytest.raises(ValidationError, match="production secret reuse"):
        Settings(**values)


def test_production_rejects_fixtures() -> None:
    with pytest.raises(ValidationError, match="fixture"):
        values: dict[str, Any] = dict(
            _env_file=None,
            environment="production",
            release="test-sha",
            telemetry_export_endpoint="https://telemetry.invalid",
            google_provider_mode="fixture",
        )
        Settings(**values)


@pytest.mark.parametrize(
    "repository,installation,path,branch",
    [
        ("OtherOwner/staging-test", "1001", "src/content/test/page.md", None),
        ("SyntheticOwner/client-repo", "1001", "src/content/test/page.md", None),
        ("SyntheticOwner/staging-test", "9999", "src/content/test/page.md", None),
        ("SyntheticOwner/staging-test", "1001", "src/pages/index.astro", None),
        ("SyntheticOwner/staging-test", "1001", "src/content/test/../../index.astro", None),
        ("SyntheticOwner/staging-test", "1001", "src/content/test/%2e%2e/index.astro", None),
        ("SyntheticOwner/staging-test", "1001", "src/content/test/page.md", "main"),
    ],
)
def test_staging_write_scope_denies(
    repository: str, installation: str, path: str, branch: str | None
) -> None:
    with pytest.raises(ProviderWriteDeniedError):
        require_github_scope(
            Settings(**staging_values()),
            repository,
            installation=installation,
            path=path,
            branch=branch,
        )


def test_only_github_scope_can_write() -> None:
    settings = Settings(**staging_values())
    require_github_scope(
        settings,
        "SyntheticOwner/staging-test",
        installation="1001",
        path="src/content/test/page.md",
        branch="lilos-content-00000000-0000-0000-0000-000000000001",
    )
    with pytest.raises(ProviderWriteDeniedError):
        require_google_write(settings)
    values = staging_values() | {"provider_writes_enabled": False}
    with pytest.raises(ProviderWriteDeniedError):
        require_github_scope(Settings(**values), "SyntheticOwner/staging-test")


def preview_values() -> dict[str, str]:
    return {
        "VERCEL_ENV": "preview",
        "VERCEL_URL": "console-123.vercel.app",
        "CONSOLE_EXPECTED_HOST": "console-123.vercel.app",
        "CONSOLE_DEPLOYMENT_PROTECTED": "true",
        "CONSOLE_API_ORIGIN": "https://approved-staging-api.invalid",
        "CONSOLE_APPROVED_STAGING_API_ORIGIN": "https://approved-staging-api.invalid",
        "CONSOLE_PRODUCTION_API_ORIGIN": "https://production-api.invalid",
        "CONSOLE_SUPABASE_URL": f"https://{STAGING_PROJECT}.supabase.co",
        "CONSOLE_STAGING_SUPABASE_PROJECT_REF": STAGING_PROJECT,
        "CONSOLE_PRODUCTION_SUPABASE_PROJECT_REF": PRODUCTION_PROJECT,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"CONSOLE_API_ORIGIN": "https://production-api.invalid"},
        {"CONSOLE_SUPABASE_URL": f"https://{PRODUCTION_PROJECT}.supabase.co"},
        {"CONSOLE_DEPLOYMENT_PROTECTED": "false"},
        {"CONSOLE_EXPECTED_HOST": "*.vercel.app"},
        {"CONSOLE_EXPECTED_HOST": "attacker.vercel.app"},
        {"CONSOLE_APPROVED_STAGING_API_ORIGIN": "https://production-api.invalid"},
    ],
)
def test_preview_refuses_unsafe_resources(change: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        validate(preview_values() | change)


def test_preview_and_stable_staging_exact_config_pass() -> None:
    validate(preview_values())
    validate(
        preview_values()
        | {"VERCEL_ENV": "production", "CONSOLE_EXPECTED_HOST": "console-staging.lilosgrowth.com"}
    )


def test_staging_refuses_known_production_provider_token() -> None:
    values = staging_values()
    values["staging_forbidden_secret_sha256"] = hashlib.sha256(
        b"synthetic-production-refresh"
    ).hexdigest()
    settings = Settings(**values)
    with pytest.raises(ValueError, match="production secret reuse"):
        settings.reject_production_secret("synthetic-production-refresh")
