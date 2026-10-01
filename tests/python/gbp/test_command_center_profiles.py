"""Operational GBP details require canonical confirmed mapping and location authority."""

from typing import cast
from uuid import UUID

from fastapi import FastAPI
from starlette.testclient import TestClient

from apps.api.app.authentication.enums import AssuranceLevel

from .test_gbp_operations_api import HEADERS, claims, gbp_operations_client

__all__ = ["gbp_operations_client"]


def test_profile_projection_missing_snapshot_and_mapping_scope(
    gbp_operations_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = gbp_operations_client
    org, location, profile = ids["organization"], ids["location"], ids["gbp_location"]
    path = (
        f"/api/v1/organizations/{org}/command-center/local-search"
        f"/locations/{location}/profiles/{profile}"
    )
    assert client.get(path, headers=HEADERS).status_code == 404
    confirmed = client.post(
        f"/api/v1/organizations/{org}/locations/{location}/gbp-mapping/{profile}/confirm",
        headers=HEADERS,
        json={"location_id": str(location), "write_enabled": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    response = client.get(path, headers=HEADERS)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["organization_id"] == str(org)
    assert data["location_id"] == str(location)
    assert data["profile_id"] == str(profile)
    assert data["profile"] is None and data["observed_at"] is None
    assert data["health"] is None
    assert data["completeness"] is None
    assert data["completeness_code"] == "GBP_CAPABILITY_SNAPSHOT_NOT_FOUND"
    assert data["posts"] == [] and data["provider_posts"] == []
    assert data["can_propose"] and data["can_approve"]
    assert client.get(path).status_code == 401
    sibling = path.replace(str(location), str(ids["sibling_location"]))
    assert client.get(sibling, headers=HEADERS).status_code == 404
    foreign = path.replace(str(org), str(ids["other_organization"]))
    assert client.get(foreign, headers=HEADERS).status_code in {403, 404}
    cast(FastAPI, client.app).state.gbp_operations_test_verifier.result = claims(
        ids["assigned_subject"], AssuranceLevel.AAL1
    )
    read = client.get(path, headers=HEADERS)
    assert read.status_code == 200, read.text
    assert not read.json()["can_approve"]
    assert not read.json()["can_publish"]
