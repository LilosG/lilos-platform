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


def test_readiness_reports_no_unimplemented_dependencies(client: TestClient) -> None:
    response = client.get("/health/ready")
    correlation_id = response.headers[CORRELATION_ID_HEADER]

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "service": "lilos-api",
            "status": "ready",
            "dependencies": [],
        },
        "meta": {"correlation_id": correlation_id},
    }
