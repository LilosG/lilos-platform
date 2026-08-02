"""Temporary location bootstrap API tests."""

from collections.abc import Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.main import create_app


@pytest.fixture
def internal_client(
    postgresql_test_url: str, location_session_factory: async_sessionmaker[AsyncSession]
) -> Generator[TestClient]:
    del location_session_factory
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "database_url": postgresql_test_url,
            "internal_admin_routes_enabled": True,
        }
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def organization_payload(slug: str) -> dict[str, str]:
    return {
        "name": "Fabricated Organization",
        "slug": slug,
        "organization_type": "test",
        "timezone": "UTC",
        "default_currency": "USD",
    }


def location_payload(slug: str = "fabricated-location") -> dict[str, object]:
    return {
        "name": "Fabricated Location",
        "slug": slug,
        "location_type": "physical",
        "timezone": "UTC",
        "address_line_1": "1 Example Way",
        "city": "Example",
        "region": "CA",
        "postal_code": "00000",
        "country_code": "US",
    }


def test_location_routes_are_unregistered_by_default() -> None:
    with TestClient(
        create_app(Settings(environment=EnvironmentName.TEST)), raise_server_exceptions=False
    ) as client:
        response = client.get(
            "/internal/organizations/00000000-0000-4000-8000-000000000001/locations"
        )
    assert response.status_code == 404


@pytest.mark.integration
def test_scoped_create_list_get_transition_and_cross_scope_not_found(
    internal_client: TestClient,
) -> None:
    first_org = internal_client.post(
        "/internal/organizations", json=organization_payload("api-location-one")
    ).json()["data"]
    second_org = internal_client.post(
        "/internal/organizations", json=organization_payload("api-location-two")
    ).json()["data"]
    for action, version in [("start-onboarding", 1), ("activate", 2)]:
        assert (
            internal_client.post(
                f"/internal/organizations/{first_org['id']}/{action}",
                json={"expected_version": version},
            ).status_code
            == 200
        )
    created = internal_client.post(
        f"/internal/organizations/{first_org['id']}/locations", json=location_payload()
    )
    assert created.status_code == 201
    location_id = created.json()["data"]["id"]
    assert (
        internal_client.get(
            f"/internal/organizations/{first_org['id']}/locations/{location_id}"
        ).status_code
        == 200
    )
    listed = internal_client.get(
        f"/internal/organizations/{first_org['id']}/locations", params={"limit": 1}
    )
    assert listed.status_code == 200 and listed.json()["data"][0]["id"] == location_id
    hidden = internal_client.get(
        f"/internal/organizations/{second_org['id']}/locations/{location_id}"
    )
    missing = internal_client.get(
        f"/internal/organizations/{second_org['id']}/locations/00000000-0000-4000-8000-000000000099"
    )
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["error"] == missing.json()["error"]
    activated = internal_client.post(
        f"/internal/organizations/{first_org['id']}/locations/{location_id}/activate",
        json={"expected_version": 1},
    )
    assert activated.status_code == 200 and activated.json()["data"]["version"] == 2
