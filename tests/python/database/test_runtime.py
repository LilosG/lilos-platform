import pytest
from pydantic import PostgresDsn, TypeAdapter
from sqlalchemy import text
from starlette.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.database.runtime import DatabaseRuntime, create_database_runtime
from apps.api.app.errors import DatabaseUnavailableError
from apps.api.app.main import create_app

POSTGRES_DSN_ADAPTER = TypeAdapter(PostgresDsn)


def database_settings(database_url: str) -> Settings:
    return Settings(
        environment=EnvironmentName.TEST,
        database_url=POSTGRES_DSN_ADAPTER.validate_python(database_url),
    )


def test_unconfigured_runtime_fails_clearly_when_database_is_invoked() -> None:
    runtime = DatabaseRuntime.unconfigured()

    assert not runtime.configured
    with pytest.raises(DatabaseUnavailableError):
        runtime.require_session_factory()


@pytest.mark.integration
@pytest.mark.anyio
async def test_async_engine_connects_to_postgresql(postgresql_test_url: str) -> None:
    runtime = create_database_runtime(database_settings(postgresql_test_url))

    try:
        async with runtime.require_engine().connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
    finally:
        await runtime.dispose()


@pytest.mark.integration
def test_readiness_reports_postgresql_healthy(postgresql_test_url: str) -> None:
    app = create_app(database_settings(postgresql_test_url))

    with TestClient(app) as client:
        live_response = client.get("/health/live")
        ready_response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert ready_response.status_code == 200
    assert ready_response.json()["data"] == {
        "service": "lilos-api",
        "status": "ready",
        "dependencies": [{"name": "postgresql", "status": "healthy"}],
    }
