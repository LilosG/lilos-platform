"""Internal location-group route contracts, scoping, and safety."""

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
    location_group_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[TestClient]:
    del location_group_session_factory
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
            "name": "Fabricated Group Organization",
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
            "name": "Fabricated Group Location",
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


def test_location_group_routes_are_unregistered_by_default() -> None:
    with TestClient(
        create_app(Settings(environment=EnvironmentName.TEST)),
        raise_server_exceptions=False,
    ) as client:
        assert (
            client.get(
                "/internal/organizations/00000000-0000-4000-8000-000000000001/location-groups"
            ).status_code
            == 404
        )


@pytest.mark.parametrize("environment", [EnvironmentName.LOCAL, EnvironmentName.TEST])
def test_location_group_routes_register_only_with_explicit_safe_enablement(
    environment: EnvironmentName,
) -> None:
    app = create_app(Settings(environment=environment, internal_admin_routes_enabled=True))
    paths = app.openapi()["paths"]
    assert "/internal/organizations/{organization_id}/location-groups" in paths


@pytest.mark.parametrize(
    "environment",
    [EnvironmentName.DEVELOPMENT, EnvironmentName.STAGING, EnvironmentName.PRODUCTION],
)
def test_unsafe_location_group_route_enablement_is_rejected(
    environment: EnvironmentName,
) -> None:
    with pytest.raises(ValidationError):
        Settings(environment=environment, internal_admin_routes_enabled=True)


@pytest.mark.integration
def test_group_routes_create_list_get_replace_archive_and_errors(
    internal_client: TestClient,
) -> None:
    organization_id = create_organization(internal_client, "group-api-org")
    base = f"/internal/organizations/{organization_id}/location-groups"
    correlation_id = "location-group-api"
    created = internal_client.post(
        base,
        json={"name": "North Region", "key": "NORTH-REGION", "description": " North "},
        headers={CORRELATION_ID_HEADER: correlation_id},
    )
    assert created.status_code == 201
    assert created.headers[CORRELATION_ID_HEADER] == correlation_id
    assert created.json()["data"]["key"] == "north-region"
    assert created.json()["data"]["version"] == 1
    group_id = created.json()["data"]["id"]
    assert internal_client.get(f"{base}/{group_id}").status_code == 200
    assert internal_client.get(base).json()["data"][0]["id"] == group_id
    duplicate = internal_client.post(base, json={"name": "Duplicate", "key": "north-region"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "LOCATION_GROUP_KEY_CONFLICT"
    replaced = internal_client.put(
        f"{base}/{group_id}",
        json={"name": "North Operations", "description": "", "expected_version": 1},
    )
    assert replaced.status_code == 200
    assert replaced.json()["data"]["description"] is None
    assert replaced.json()["data"]["version"] == 2
    stale = internal_client.put(
        f"{base}/{group_id}",
        json={"name": "Stale", "expected_version": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "LOCATION_GROUP_VERSION_CONFLICT"
    archived = internal_client.post(f"{base}/{group_id}/archive", json={"expected_version": 2})
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"
    denied = internal_client.put(
        f"{base}/{group_id}",
        json={"name": "Cannot Change", "expected_version": 3},
    )
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "LOCATION_GROUP_STATE_CONFLICT"


@pytest.mark.integration
def test_membership_routes_are_scoped_and_do_not_leak_ownership(
    internal_client: TestClient,
) -> None:
    first_org = create_organization(internal_client, "group-scope-one")
    second_org = create_organization(internal_client, "group-scope-two")
    location_id = create_location(internal_client, first_org, "group-location-one")
    group = internal_client.post(
        f"/internal/organizations/{first_org}/location-groups",
        json={"name": "Scoped Group", "key": "scoped-group"},
    )
    assert group.status_code == 201
    group_id = group.json()["data"]["id"]
    membership_path = (
        f"/internal/organizations/{first_org}/location-groups/{group_id}/locations/{location_id}"
    )
    added = internal_client.post(membership_path)
    assert added.status_code == 201
    duplicate = internal_client.post(membership_path)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "LOCATION_GROUP_MEMBERSHIP_CONFLICT"
    listed = internal_client.get(
        f"/internal/organizations/{first_org}/location-groups/{group_id}/locations"
    )
    assert listed.status_code == 200
    assert listed.json()["data"][0]["location_id"] == location_id
    cross = internal_client.get(f"/internal/organizations/{second_org}/location-groups/{group_id}")
    missing = internal_client.get(
        f"/internal/organizations/{second_org}/location-groups/00000000-0000-4000-8000-000000000099"
    )
    assert cross.status_code == missing.status_code == 404
    assert cross.json()["error"] == missing.json()["error"]
    removed = internal_client.delete(membership_path)
    assert removed.status_code == 200
    missing_membership = internal_client.delete(membership_path)
    assert missing_membership.status_code == 404
    assert missing_membership.json()["error"]["code"] == "LOCATION_GROUP_MEMBERSHIP_NOT_FOUND"
