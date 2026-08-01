from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api.app.config import EnvironmentName, LogLevel, Settings
from apps.api.app.main import create_app


@pytest.mark.parametrize("environment", list(EnvironmentName))
def test_every_explicit_environment_name_is_valid(environment: EnvironmentName) -> None:
    settings = Settings(environment=environment)

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
