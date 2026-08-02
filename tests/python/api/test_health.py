from starlette.testclient import TestClient

from apps.api.app.middleware import CORRELATION_ID_HEADER


def test_liveness_reports_only_process_health(client: TestClient) -> None:
    response = client.get("/health/live")
    correlation_id = response.headers[CORRELATION_ID_HEADER]

    assert response.status_code == 200
    assert response.json() == {
        "data": {"service": "lilos-api", "status": "alive"},
        "meta": {"correlation_id": correlation_id},
    }


def test_readiness_reports_postgresql_unavailable_without_configuration(
    client: TestClient,
) -> None:
    response = client.get("/health/ready")
    correlation_id = response.headers[CORRELATION_ID_HEADER]

    assert response.status_code == 503
    assert response.json() == {
        "data": {
            "service": "lilos-api",
            "status": "not_ready",
            "dependencies": [{"name": "postgresql", "status": "unavailable"}],
        },
        "meta": {"correlation_id": correlation_id},
    }


def test_readiness_connection_failure_does_not_leak_database_details() -> None:
    from pydantic import PostgresDsn, TypeAdapter

    from apps.api.app.config import EnvironmentName, Settings
    from apps.api.app.main import create_app

    settings = Settings(
        environment=EnvironmentName.TEST,
        database_url=TypeAdapter(PostgresDsn).validate_python(
            "postgresql+asyncpg://secret-user:secret-password@127.0.0.1:1/secret-database"
        ),
    )

    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/health/ready")

    serialized_response = response.text
    assert response.status_code == 503
    assert response.json()["data"]["dependencies"] == [
        {"name": "postgresql", "status": "unavailable"}
    ]
    assert "secret-user" not in serialized_response
    assert "secret-password" not in serialized_response
    assert "secret-database" not in serialized_response
