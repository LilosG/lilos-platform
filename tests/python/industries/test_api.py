"""Temporary internal industry and assignment API tests."""

from collections.abc import Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.main import create_app


@pytest.fixture
def internal_client(
    postgresql_test_url: str,
    industry_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[TestClient]:
    del industry_session_factory
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "database_url": postgresql_test_url,
            "internal_admin_routes_enabled": True,
        }
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def test_industry_routes_are_unregistered_by_default() -> None:
    with TestClient(
        create_app(Settings(environment=EnvironmentName.TEST)), raise_server_exceptions=False
    ) as client:
        assert client.get("/internal/industries").status_code == 404


@pytest.mark.integration
def test_create_list_lifecycle_and_organization_assignment(internal_client: TestClient) -> None:
    created = internal_client.post(
        "/internal/industries",
        json={
            "key": "  FABRICATED_API_INDUSTRY  ",
            "name": "Fabricated API Industry",
            "default_configuration": {"feature": {"enabled": True}},
        },
    )
    assert created.status_code == 201
    industry = created.json()["data"]
    assert industry["key"] == "fabricated_api_industry"
    listed = internal_client.get("/internal/industries", params={"limit": 1})
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == industry["id"]
    deprecated = internal_client.post(
        f"/internal/industries/{industry['id']}/deprecate",
        json={"expected_version": 1},
    )
    assert deprecated.status_code == 200
    rejected_organization = internal_client.post(
        "/internal/organizations",
        json={
            "name": "Fabricated Rejected Organization",
            "slug": "fabricated-rejected-org",
            "organization_type": "client",
            "timezone": "UTC",
            "default_currency": "USD",
            "industry_id": industry["id"],
        },
    )
    assert rejected_organization.status_code == 409
    assert rejected_organization.json()["error"]["code"] == "INDUSTRY_ASSIGNMENT_CONFLICT"
    reactivated = internal_client.post(
        f"/internal/industries/{industry['id']}/reactivate",
        json={"expected_version": 2},
    )
    assert reactivated.status_code == 200
    organization = internal_client.post(
        "/internal/organizations",
        json={
            "name": "Fabricated API Organization",
            "slug": "fabricated-api-industry-org",
            "organization_type": "client",
            "timezone": "UTC",
            "default_currency": "USD",
            "industry_id": industry["id"],
        },
    )
    assert organization.status_code == 201
    org = organization.json()["data"]
    assert org["industry_id"] == industry["id"]
    second = internal_client.post(
        "/internal/industries",
        json={"key": "second_api_industry", "name": "Second API Industry"},
    ).json()["data"]
    assigned = internal_client.post(
        f"/internal/organizations/{org['id']}/industry",
        json={"industry_id": second["id"], "expected_version": 1},
    )
    assert assigned.status_code == 200
    assert assigned.json()["data"]["industry_id"] == second["id"]
    assert assigned.json()["data"]["version"] == 2
