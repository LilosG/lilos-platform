"""Guarded business-identity API contract and isolation tests."""

from collections.abc import Generator

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.main import create_app
from apps.api.app.middleware import CORRELATION_ID_HEADER


@pytest.fixture
def internal_client(
    postgresql_test_url: str,
    business_identity_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[TestClient]:
    del business_identity_session_factory
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "database_url": postgresql_test_url,
            "internal_admin_routes_enabled": True,
        }
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def create_organization(client: TestClient, slug: str) -> str:
    response = client.post(
        "/internal/organizations",
        json={
            "name": "Fabricated Identity Organization",
            "slug": slug,
            "organization_type": "test",
            "timezone": "UTC",
            "default_currency": "USD",
        },
    )
    assert response.status_code == 201
    return str(response.json()["data"]["id"])


def create_location(client: TestClient, organization_id: str, slug: str) -> str:
    response = client.post(
        f"/internal/organizations/{organization_id}/locations",
        json={
            "name": "Fabricated Identity Location",
            "slug": slug,
            "location_type": "physical",
            "timezone": "UTC",
            "address_line_1": "1 Fabricated Way",
            "city": "Example",
            "region": "CA",
            "postal_code": "00000",
            "country_code": "US",
        },
    )
    assert response.status_code == 201
    return str(response.json()["data"]["id"])


def test_routes_are_unregistered_by_default() -> None:
    with TestClient(create_app(Settings(environment=EnvironmentName.TEST))) as client:
        response = client.get(
            "/internal/organizations/00000000-0000-4000-8000-000000000001/business-identity"
        )
        assert response.status_code == 404


@pytest.mark.parametrize("environment", [EnvironmentName.LOCAL, EnvironmentName.TEST])
def test_routes_register_only_with_explicit_safe_enablement(environment: EnvironmentName) -> None:
    app = create_app(Settings(environment=environment, internal_admin_routes_enabled=True))
    paths = app.openapi()["paths"]
    assert "/internal/organizations/{organization_id}/business-identity" in paths
    assert (
        "/internal/organizations/{organization_id}/locations/{location_id}/business-identity"
        in paths
    )


@pytest.mark.parametrize(
    "environment",
    [EnvironmentName.DEVELOPMENT, EnvironmentName.STAGING, EnvironmentName.PRODUCTION],
)
def test_unsafe_enablement_is_rejected(environment: EnvironmentName) -> None:
    with pytest.raises(ValidationError):
        Settings(environment=environment, internal_admin_routes_enabled=True)


@pytest.mark.integration
def test_routes_resolve_with_correlation_and_preserve_scope(internal_client: TestClient) -> None:
    first = create_organization(internal_client, "identity-api-one")
    second = create_organization(internal_client, "identity-api-two")
    location = create_location(internal_client, first, "identity-api-location")
    correlation_id = "business-identity-api"
    organization_response = internal_client.get(
        f"/internal/organizations/{first}/business-identity",
        headers={CORRELATION_ID_HEADER: correlation_id},
    )
    assert organization_response.status_code == 200
    assert organization_response.headers[CORRELATION_ID_HEADER] == correlation_id
    assert organization_response.json()["meta"]["correlation_id"] == correlation_id
    location_response = internal_client.get(
        f"/internal/organizations/{first}/locations/{location}/business-identity"
    )
    assert location_response.status_code == 200
    assert location_response.json()["data"]["location"]["id"] == location
    cross = internal_client.get(
        f"/internal/organizations/{second}/locations/{location}/business-identity"
    )
    missing = internal_client.get(
        f"/internal/organizations/{second}/locations/"
        "00000000-0000-4000-8000-000000000099/business-identity"
    )
    assert cross.status_code == missing.status_code == 404
    assert cross.json()["error"] == missing.json()["error"]
