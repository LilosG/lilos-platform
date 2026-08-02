"""Guarded authentication and user-profile HTTP contracts."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from starlette.testclient import TestClient

from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authentication.errors import (
    TokenVerificationError,
    TokenVerificationUnavailableError,
)
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.main import create_app
from apps.api.app.middleware import CORRELATION_ID_HEADER


class FakeVerifier:
    def __init__(self, result: VerifiedProviderClaims | Exception) -> None:
        self.result = result
        self.tokens: list[str] = []

    async def verify(self, token: str) -> VerifiedProviderClaims:
        self.tokens.append(token)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def verified(subject: UUID) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=subject,
        session_id=UUID("20000000-0000-4000-8000-000000000001"),
        assurance_level=AssuranceLevel.AAL2,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        algorithm="ES256",
        key_id="test-key",
    )


@pytest.fixture
def enabled_client(
    postgresql_test_url: str, authentication_session_factory: object
) -> Generator[tuple[TestClient, FakeVerifier]]:
    del authentication_session_factory
    subject = UUID("10000000-0000-4000-8000-000000000001")
    verifier = FakeVerifier(verified(subject))
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "database_url": postgresql_test_url,
            "internal_admin_routes_enabled": True,
        }
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, verifier


def test_routes_are_unregistered_by_default_and_unsafe_enablement_is_rejected() -> None:
    with TestClient(create_app(Settings(environment=EnvironmentName.TEST))) as client:
        assert client.get("/internal/auth/me").status_code == 404
        assert client.post("/internal/user-profiles", json={}).status_code == 404
    for environment in (
        EnvironmentName.DEVELOPMENT,
        EnvironmentName.STAGING,
        EnvironmentName.PRODUCTION,
    ):
        with pytest.raises(ValueError, match="local or test"):
            Settings(environment=environment, internal_admin_routes_enabled=True)


def test_missing_bearer_fails_before_provider_or_database_availability() -> None:
    settings = Settings(
        environment=EnvironmentName.TEST,
        internal_admin_routes_enabled=True,
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/internal/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.integration
def test_bootstrap_lifecycle_and_authenticated_principal_contract(
    enabled_client: tuple[TestClient, FakeVerifier],
) -> None:
    client, verifier = enabled_client
    subject = str(verifier.result.auth_user_id)  # type: ignore[union-attr]
    created = client.post(
        "/internal/user-profiles",
        json={"auth_user_id": subject, "email": "FABRICATED@EXAMPLE.INVALID"},
    )
    assert created.status_code == 201
    profile = created.json()["data"]
    assert profile["email"] == "fabricated@example.invalid"

    correlation_id = "auth-me-contract"
    response = client.get(
        "/internal/auth/me",
        headers={
            "Authorization": "Bearer fabricated.signed.token",
            CORRELATION_ID_HEADER: correlation_id,
        },
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers[CORRELATION_ID_HEADER] == correlation_id
    assert set(response.json()["data"]) == {
        "platform_user_id",
        "auth_user_id",
        "user_status",
        "session_id",
        "assurance_level",
        "token_issued_at",
        "token_expires_at",
    }
    assert "organization_id" not in str(response.json())

    user_id = profile["id"]
    deactivated = client.post(
        f"/internal/user-profiles/{user_id}/deactivate", json={"expected_version": 1}
    )
    assert deactivated.status_code == 200
    rejected = client.get(
        "/internal/auth/me", headers={"Authorization": "Bearer fabricated.signed.token"}
    )
    assert rejected.status_code == 401
    reactivated = client.post(
        f"/internal/user-profiles/{user_id}/reactivate", json={"expected_version": 2}
    )
    assert reactivated.status_code == 200


@pytest.mark.integration
def test_all_authentication_failures_are_generic_and_no_store(
    enabled_client: tuple[TestClient, FakeVerifier],
) -> None:
    client, verifier = enabled_client
    cases = [
        {},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer " + "x" * 16_385},
    ]
    for headers in cases:
        response = client.get("/internal/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.headers["Cache-Control"] == "no-store"
        assert "x" * 100 not in response.text

    verifier.result = TokenVerificationError()
    invalid = client.get("/internal/auth/me", headers={"Authorization": "Bearer hidden-token"})
    assert invalid.status_code == 401
    assert "hidden-token" not in invalid.text
    verifier.result = TokenVerificationUnavailableError()
    unavailable = client.get("/internal/auth/me", headers={"Authorization": "Bearer hidden-token"})
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "AUTHENTICATION_UNAVAILABLE"
    assert unavailable.headers["Cache-Control"] == "no-store"


@pytest.mark.integration
def test_unknown_user_and_duplicate_subject_do_not_enumerate(
    enabled_client: tuple[TestClient, FakeVerifier],
) -> None:
    client, verifier = enabled_client
    unknown = client.get(
        "/internal/auth/me", headers={"Authorization": "Bearer fabricated.signed.token"}
    )
    assert unknown.status_code == 401
    subject = str(verifier.result.auth_user_id)  # type: ignore[union-attr]
    assert client.post("/internal/user-profiles", json={"auth_user_id": subject}).status_code == 201
    duplicate = client.post("/internal/user-profiles", json={"auth_user_id": subject})
    assert duplicate.status_code == 409
    assert client.get(f"/internal/user-profiles/{uuid4()}").status_code == 404
