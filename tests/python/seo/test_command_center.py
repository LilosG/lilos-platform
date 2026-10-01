"""Projection acceptance against canonical services and tenant-authorized API."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from .test_seo_api import HEADERS, execute_crawl_directly, seo_client

# Re-export fixture for pytest collection, without adding another seed engine.
__all__ = ["seo_client"]


def test_reference_projection_and_foreign_scope_denial(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    base = f"/api/v1/organizations/{org}"
    website = client.post(
        base + "/seo/websites",
        headers=HEADERS,
        json={
            "location_id": str(ids["location"]),
            "key": "projection",
            "name": "Projection",
            "canonical_origin": "https://example.test",
        },
    ).json()["data"]
    crawl = client.post(
        base + f"/seo/websites/{website['id']}/crawl",
        headers=HEADERS,
        json={
            "workflow_run_id": str(ids["workflow_run"]),
            "seed_paths": ["/", "/broken"],
            "max_pages": 2,
            "max_depth": 1,
            "idempotency_key": "phase1-projection-crawl",
        },
    )
    assert crawl.status_code == 202, crawl.text
    execute_crawl_directly(seo_session_factory, org, UUID(crawl.json()["data"]["id"]))
    projection = client.get(base + "/command-center/opportunities", headers=HEADERS)
    assert projection.status_code == 200, projection.text
    rows = projection.json()["data"]
    assert rows
    row = rows[0]
    assert row["id"] == f"seo_opportunity:{row['source_id']}"
    assert row["organization_id"] == str(org)
    assert row["classification"] == "Issue"
    assert row["evidence"]
    detail = client.get(base + f"/command-center/opportunities/{row['source_id']}", headers=HEADERS)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["source_id"] == row["source_id"]
    assert detail.json()["data"]["evidence_context"]["quality"] == "issues_detected"
    assert detail.json()["page_url"].endswith("/broken")
    assert isinstance(detail.json()["can_approve"], bool)
    assert client.get(base + "/command-center/attention", headers=HEADERS).status_code == 200
    foreign = f"/api/v1/organizations/{ids['other_organization']}/command-center"
    for path in ["/opportunities", "/attention", f"/opportunities/{row['source_id']}"]:
        response = client.get(foreign + path, headers=HEADERS)
        assert response.status_code in {403, 404}
        assert row["source_id"] not in response.text
    assert client.get(base + "/command-center/opportunities").status_code == 401
    assert (
        client.get(base + "/command-center/opportunities?limit=101", headers=HEADERS).status_code
        == 422
    )
