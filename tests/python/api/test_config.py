from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.app.config import EnvironmentName, LogLevel, Settings
from apps.api.app.main import create_app


@pytest.mark.parametrize("environment", list(EnvironmentName))
def test_every_explicit_environment_name_is_valid(environment: EnvironmentName) -> None:
    production_values: dict[str, object] = (
        {"release": "release-test", "telemetry_export_endpoint": "https://telemetry.invalid"}
        if environment is EnvironmentName.PRODUCTION
        else {}
    )
    settings = Settings.model_validate({"environment": environment, **production_values})

    assert settings.environment is environment


def test_settings_load_prefixed_environment_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LILOS_ENV", "staging")
    monkeypatch.setenv("LILOS_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("LILOS_API_TITLE", "Configured LILOs API")
    monkeypatch.setenv("LILOS_API_VERSION", "1.2.3-rc.1")

    settings = Settings()

    assert settings.environment is EnvironmentName.STAGING
    assert settings.log_level is LogLevel.WARNING
    assert settings.api_title == "Configured LILOs API"
    assert settings.api_version == "1.2.3-rc.1"
    assert settings.application_database_url() is None


def test_provider_writes_fail_closed_and_require_explicit_enablement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert Settings().provider_writes_enabled is False

    monkeypatch.setenv("LILOS_PROVIDER_WRITES_ENABLED", "true")
    assert Settings().provider_writes_enabled is True


def test_invalid_environment_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LILOS_ENV", "preview")

    with pytest.raises(ValidationError):
        Settings()


def test_application_metadata_comes_from_settings() -> None:
    settings = Settings(
        environment=EnvironmentName.TEST,
        api_title="Metadata Test API",
        api_version="2.0.0",
    )

    app = create_app(settings)

    assert app.title == "Metadata Test API"
    assert app.version == "2.0.0"


def test_authentication_defaults_and_https_configuration() -> None:
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "supabase_auth_issuer": "https://fabricated.supabase.co/auth/v1",
            "supabase_auth_jwks_url": "https://fabricated.supabase.co/auth/v1/.well-known/jwks.json",
        }
    )
    assert settings.authentication_algorithms() == ("ES256", "RS256")
    assert settings.supabase_auth_audience == "authenticated"
    assert settings.supabase_auth_jwks_cache_seconds == 900
    assert settings.supabase_auth_jwks_stale_seconds == 3_600
    assert settings.supabase_auth_clock_skew_seconds == 60
    assert settings.supabase_auth_max_token_bytes == 16_384


@pytest.mark.parametrize(
    "values",
    [
        {"supabase_auth_allowed_algorithms": "HS256"},
        {"supabase_auth_issuer": "http://fabricated.invalid/auth/v1"},
        {"supabase_auth_jwks_url": "http://fabricated.invalid/jwks"},
        {"supabase_auth_jwks_cache_seconds": 900, "supabase_auth_jwks_stale_seconds": 100},
    ],
)
def test_unsafe_authentication_configuration_is_rejected(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"environment": EnvironmentName.TEST, **values})


def test_web_origins_default_to_disabled_cors() -> None:
    settings = Settings(environment=EnvironmentName.TEST)
    assert settings.allowed_web_origins() == ()

    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"Origin": "https://unconfigured.invalid"})
        assert "access-control-allow-origin" not in {key.lower() for key in response.headers}


def test_configured_web_origin_enables_cors_for_that_origin_only() -> None:
    settings = Settings(
        environment=EnvironmentName.TEST,
        web_origins="https://app.lilos.invalid,https://admin.lilos.invalid",
    )
    assert settings.allowed_web_origins() == (
        "https://app.lilos.invalid",
        "https://admin.lilos.invalid",
    )

    with TestClient(create_app(settings)) as client:
        allowed = client.options(
            "/health/live",
            headers={
                "Origin": "https://app.lilos.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.headers["access-control-allow-origin"] == "https://app.lilos.invalid"

        blocked = client.options(
            "/health/live",
            headers={
                "Origin": "https://not-allowed.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in {key.lower() for key in blocked.headers}


@pytest.mark.parametrize(
    "web_origins",
    ["not-a-url", "https://app.lilos.invalid/path", "https://app.lilos.invalid?query=1"],
)
def test_malformed_web_origins_are_rejected(web_origins: str) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"environment": EnvironmentName.TEST, "web_origins": web_origins})


def test_production_requires_https_web_origins() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings.model_validate(
            {
                "environment": EnvironmentName.PRODUCTION,
                "release": "release-test",
                "telemetry_export_endpoint": "https://telemetry.invalid",
                "web_origins": "http://insecure.invalid",
            }
        )
