from uuid import UUID

import pytest
from starlette.testclient import TestClient

from apps.api.app.middleware import (
    CORRELATION_ID_HEADER,
    MAX_CORRELATION_ID_LENGTH,
    is_valid_correlation_id,
)


def test_absent_correlation_id_generates_uuid4(client: TestClient) -> None:
    response = client.get("/health/live")

    correlation_id = response.headers[CORRELATION_ID_HEADER]
    parsed = UUID(correlation_id)
    assert parsed.version == 4
    assert str(parsed) == correlation_id
    assert response.json()["meta"]["correlation_id"] == correlation_id


def test_valid_incoming_correlation_id_is_preserved(client: TestClient) -> None:
    supplied = "client.request_01:retry-2"

    response = client.get("/health/ready", headers={CORRELATION_ID_HEADER: supplied})

    assert response.headers[CORRELATION_ID_HEADER] == supplied
    assert response.json()["meta"]["correlation_id"] == supplied


@pytest.mark.parametrize(
    "invalid_value",
    [
        "",
        "contains spaces",
        "slash/is/not/allowed",
        "x" * (MAX_CORRELATION_ID_LENGTH + 1),
    ],
)
def test_invalid_incoming_correlation_id_is_replaced(
    client: TestClient,
    invalid_value: str,
) -> None:
    response = client.get("/health/live", headers={CORRELATION_ID_HEADER: invalid_value})

    replacement = response.headers[CORRELATION_ID_HEADER]
    assert replacement != invalid_value
    assert UUID(replacement).version == 4
    assert response.json()["meta"]["correlation_id"] == replacement


def test_non_ascii_correlation_id_is_invalid() -> None:
    assert not is_valid_correlation_id("non-ascii-é")


def test_correlation_id_is_available_to_request_handler(client: TestClient) -> None:
    supplied = "handler-context-123"

    response = client.get("/_test/context", headers={CORRELATION_ID_HEADER: supplied})

    assert response.json() == {"correlation_id": supplied}
    assert response.headers[CORRELATION_ID_HEADER] == supplied
