"""Temporary internal organization API contract tests."""

from collections.abc import Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.main import create_app
from apps.api.app.middleware import CORRELATION_ID_HEADER


def payload(slug: str = "fabricated-api-org") -> dict[str, str]:
    return {
        # Derived from the slug: creation refuses a second client whose name
        # matches an existing one, and these fixtures share a database.
        "name": f"Fabricated API Organization {slug}",
        "slug": slug,
        "organization_type": "test",
        "timezone": "UTC",
        "default_currency": "USD",
    }


@pytest.fixture
def internal_client(
    postgresql_test_url: str,
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[TestClient]:
    del organization_session_factory
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "database_url": postgresql_test_url,
            "internal_admin_routes_enabled": True,
        }
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def test_internal_routes_are_not_registered_by_default() -> None:
    with TestClient(
        create_app(Settings(environment=EnvironmentName.TEST)),
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/internal/organizations")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.integration
def test_create_get_list_and_transition_contracts(internal_client: TestClient) -> None:
    correlation_id = "organization-api-contract"
    created = internal_client.post(
        "/internal/organizations",
        json=payload("  FABRICATED-API-ORG  "),
        headers={CORRELATION_ID_HEADER: correlation_id},
    )
    assert created.status_code == 201
    assert created.headers[CORRELATION_ID_HEADER] == correlation_id
    assert created.json()["meta"] == {"correlation_id": correlation_id}
    organization = created.json()["data"]
    organization_id = organization["id"]
    assert organization["slug"] == "fabricated-api-org"
    assert organization["status"] == "prospect"
    assert organization["version"] == 1

    retrieved = internal_client.get(f"/internal/organizations/{organization_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["id"] == organization_id

    listed = internal_client.get("/internal/organizations", params={"limit": 1, "offset": 0})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["data"]] == [organization_id]
    assert listed.json()["pagination"] == {
        "limit": 1,
        "offset": 0,
        "next_offset": None,
        "has_more": False,
    }

    onboarding = internal_client.post(
        f"/internal/organizations/{organization_id}/start-onboarding",
        json={"expected_version": 1},
    )
    assert onboarding.status_code == 200
    assert onboarding.json()["data"]["status"] == "onboarding"
    assert onboarding.json()["data"]["version"] == 2

    activated = internal_client.post(
        f"/internal/organizations/{organization_id}/activate",
        json={"expected_version": 2},
    )
    assert activated.status_code == 200
    assert activated.json()["data"]["status"] == "active"


@pytest.mark.integration
def test_api_returns_stable_duplicate_version_transition_and_not_found_errors(
    internal_client: TestClient,
) -> None:
    created = internal_client.post("/internal/organizations", json=payload())
    organization_id = created.json()["data"]["id"]

    duplicate = internal_client.post("/internal/organizations", json=payload())
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ORGANIZATION_SLUG_CONFLICT"

    invalid = internal_client.post(
        f"/internal/organizations/{organization_id}/pause",
        json={"expected_version": 1},
    )
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "ORGANIZATION_TRANSITION_CONFLICT"

    onboarding = internal_client.post(
        f"/internal/organizations/{organization_id}/start-onboarding",
        json={"expected_version": 1},
    )
    assert onboarding.status_code == 200

    stale = internal_client.post(
        f"/internal/organizations/{organization_id}/activate",
        json={"expected_version": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "ORGANIZATION_VERSION_CONFLICT"

    missing = internal_client.get("/internal/organizations/00000000-0000-4000-8000-000000000099")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"


@pytest.mark.integration
def test_api_rejects_reserved_slug_without_echoing_submitted_values(
    internal_client: TestClient,
) -> None:
    response = internal_client.post("/internal/organizations", json=payload("internal"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert "internal" not in str(response.json())
