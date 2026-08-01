import json
import logging
from io import StringIO

import pytest
from _pytest.logging import LogCaptureFixture
from starlette.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.context import bind_correlation_id, reset_correlation_id
from apps.api.app.logging_config import JsonFormatter
from apps.api.app.middleware import CORRELATION_ID_HEADER


@pytest.mark.parametrize(
    ("path", "status_code", "code", "category"),
    [
        ("/_test/not-found", 404, "RESOURCE_NOT_FOUND", "not_found"),
        ("/_test/authorization", 403, "PERMISSION_DENIED", "authorization"),
        ("/_test/conflict", 409, "RESOURCE_CONFLICT", "conflict"),
    ],
)
def test_application_errors_use_standard_envelope(
    client: TestClient,
    path: str,
    status_code: int,
    code: str,
    category: str,
) -> None:
    response = client.get(path)
    correlation_id = response.headers[CORRELATION_ID_HEADER]

    assert response.status_code == status_code
    assert response.json() == {
        "error": {
            "code": code,
            "message": response.json()["error"]["message"],
            "category": category,
            "retryable": False,
            "details": [],
        },
        "meta": {"correlation_id": correlation_id},
    }


def test_framework_404_uses_standard_envelope(client: TestClient) -> None:
    response = client.get("/route-that-does-not-exist")
    correlation_id = response.headers[CORRELATION_ID_HEADER]

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "The requested resource was not found.",
            "category": "not_found",
            "retryable": False,
            "details": [],
        },
        "meta": {"correlation_id": correlation_id},
    }


def test_validation_error_is_sanitized(client: TestClient) -> None:
    response = client.post("/_test/validate", json={"name": "sensitive-invalid-value-too-long"})
    payload = response.json()

    assert response.status_code == 422
    assert payload["error"]["code"] == "VALIDATION_FAILED"
    assert payload["error"]["category"] == "validation"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["details"] == [
        {
            "field": "body.name",
            "code": "string_too_long",
            "message": "String should have at most 20 characters",
        }
    ]
    assert "sensitive-invalid-value-too-long" not in json.dumps(payload)
    assert payload["meta"]["correlation_id"] == response.headers[CORRELATION_ID_HEADER]


def test_unexpected_error_is_safe_and_logged_with_correlation_id(
    client: TestClient,
    caplog: LogCaptureFixture,
) -> None:
    supplied = "unexpected-error-test"
    application_logger = logging.getLogger("lilos")
    application_logger.propagate = True

    try:
        with caplog.at_level(logging.ERROR):
            response = client.get(
                "/_test/unexpected",
                headers={CORRELATION_ID_HEADER: supplied},
            )
    finally:
        application_logger.propagate = False

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred.",
            "category": "system",
            "retryable": False,
            "details": [],
        },
        "meta": {"correlation_id": supplied},
    }
    assert response.headers[CORRELATION_ID_HEADER] == supplied
    error_record = next(
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "api.request.unhandled_error"
    )
    assert getattr(error_record, "correlation_id", None) == supplied
    assert getattr(error_record, "normalized_error_code", None) == "INTERNAL_SERVER_ERROR"
    assert "internal-value-must-not-leak" not in error_record.getMessage()


def test_json_logging_includes_runtime_and_request_context() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(Settings(environment=EnvironmentName.TEST)))
    test_logger = logging.getLogger("tests.lilos.structured")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False
    token = bind_correlation_id("structured-log-test")

    try:
        test_logger.info(
            "Request completed",
            extra={
                "event_name": "api.request.completed",
                "status_code": 200,
                "outcome": "success",
            },
        )
    finally:
        reset_correlation_id(token)
        test_logger.handlers.clear()

    payload = json.loads(stream.getvalue())
    assert payload["severity"] == "INFO"
    assert payload["environment"] == "test"
    assert payload["service"] == "lilos-api"
    assert payload["deployment_version"] == "0.1.0"
    assert payload["event_name"] == "api.request.completed"
    assert payload["correlation_id"] == "structured-log-test"
    assert payload["status_code"] == 200
    assert payload["outcome"] == "success"
