"""Temporary internal profile route contracts and safety tests."""

from collections.abc import Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.main import create_app
from apps.api.app.middleware import CORRELATION_ID_HEADER


@pytest.fixture
def internal_client(
    postgresql_test_url: str,
    profile_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[TestClient]:
    del profile_session_factory
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
            "name": "Fabricated Profile Organization",
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
            "name": "Fabricated Profile Location",
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


def test_profile_routes_are_unregistered_by_default() -> None:
    with TestClient(
        create_app(Settings(environment=EnvironmentName.TEST)),
        raise_server_exceptions=False,
    ) as client:
        assert (
            client.get(
                "/internal/organizations/00000000-0000-4000-8000-000000000001/profile"
            ).status_code
            == 404
        )


@pytest.mark.integration
def test_organization_profile_create_get_replace_and_errors(
    internal_client: TestClient,
) -> None:
    organization_id = create_organization(internal_client, "profile-api-org")
    path = f"/internal/organizations/{organization_id}/profile"
    correlation_id = "organization-profile-api"
    created = internal_client.post(
        path,
        json={
            "brand_name": "Fabricated Brand",
            "approved_claims": ["Approved claim"],
            "prohibited_claims": ["Prohibited claim"],
        },
        headers={CORRELATION_ID_HEADER: correlation_id},
    )
    assert created.status_code == 201
    assert created.headers[CORRELATION_ID_HEADER] == correlation_id
    assert created.json()["data"]["version"] == 1
    assert internal_client.get(path).status_code == 200
    duplicate = internal_client.post(path, json={"brand_name": "Duplicate"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ORGANIZATION_PROFILE_CONFLICT"
    invalid = internal_client.put(
        path,
        json={
            "expected_version": 1,
            "approved_claims": ["Conflict"],
            "prohibited_claims": ["conflict"],
        },
    )
    assert invalid.status_code == 422
    replaced = internal_client.put(
        path,
        json={"expected_version": 1, "brand_name": "Replacement Brand"},
    )
    assert replaced.status_code == 200
    assert replaced.json()["data"]["version"] == 2
    stale = internal_client.put(
        path,
        json={"expected_version": 1, "brand_name": "Stale Brand"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "ORGANIZATION_PROFILE_VERSION_CONFLICT"


@pytest.mark.integration
def test_location_profile_routes_are_scoped_and_do_not_leak_ownership(
    internal_client: TestClient,
) -> None:
    first_org = create_organization(internal_client, "profile-location-org-one")
    second_org = create_organization(internal_client, "profile-location-org-two")
    location_id = create_location(internal_client, first_org, "profile-location-one")
    path = f"/internal/organizations/{first_org}/locations/{location_id}/profile"
    created = internal_client.post(
        path,
        json={
            "local_description": "Controlled local description",
            "local_references": ["Approved local reference"],
        },
    )
    assert created.status_code == 201
    assert internal_client.get(path).status_code == 200
    replaced = internal_client.put(
        path,
        json={"expected_version": 1, "local_description": "Replacement local context"},
    )
    assert replaced.status_code == 200
    cross_scope = internal_client.get(
        f"/internal/organizations/{second_org}/locations/{location_id}/profile"
    )
    missing = internal_client.get(
        f"/internal/organizations/{second_org}/locations/"
        "00000000-0000-4000-8000-000000000099/profile"
    )
    assert cross_scope.status_code == missing.status_code == 404
    assert cross_scope.json()["error"] == missing.json()["error"]
    assert cross_scope.json()["error"]["code"] == "LOCATION_PROFILE_NOT_FOUND"
