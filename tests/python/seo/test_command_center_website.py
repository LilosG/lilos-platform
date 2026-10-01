"""Phase 4 website inventory/evidence/scope; real canonical crawl, disposable PostgreSQL."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from .test_seo_api import HEADERS, execute_crawl_directly, seo_client

__all__ = ["seo_client"]


def test_website_inventory_evidence_scope_and_missing_paths(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = seo_client
    base = f"/api/v1/organizations/{ids['organization']}"
    path = base + "/command-center/website-content"
    empty = client.get(path, headers=HEADERS)
    assert empty.status_code == 200, empty.text
    assert empty.headers["cache-control"] == "private, no-store"
    assert empty.json()["website_id"] is None
    assert empty.json()["pages"] == []
    assert empty.json()["content_availability"] == "permission_required"
    assert empty.json()["conversions"] == "unavailable_no_canonical_path_source"
    site = client.post(
        base + "/seo/websites",
        headers=HEADERS,
        json={
            "key": "phase4",
            "name": "Phase 4",
            "canonical_origin": "https://example.test",
            "location_id": str(ids["location"]),
        },
    ).json()["data"]
    crawl = client.post(
        base + f"/seo/websites/{site['id']}/check",
        headers=HEADERS,
        json={"idempotency_key": "phase4-website-check"},
    )
    assert crawl.status_code == 202
    execute_crawl_directly(
        seo_session_factory, ids["organization"], UUID(crawl.json()["data"]["id"])
    )
    view = client.get(path + f"?website_id={site['id']}", headers=HEADERS)
    assert view.status_code == 200, view.text
    data = view.json()
    assert data["crawls"][0]["status"] == "success"
    assert data["pages"] and data["pages"][0]["observed_at"]
    assert all(p["website_id"] == site["id"] for p in data["pages"])
    assert all(o["website_id"] == site["id"] for o in data["opportunities"])
    page = data["pages"][0]
    detail_path = path + f"/websites/{site['id']}/pages/{page['id']}"
    detail = client.get(detail_path, headers=HEADERS)
    assert detail.status_code == 200, detail.text
    assert detail.json()["mapping"]["state"] == "unavailable"
    assert detail.json()["evidence"]["ga4_organic_landing"]["availability"] == "unavailable"
    for endpoint in [path, detail_path]:
        assert client.get(endpoint).status_code == 401
        foreign = client.get(
            endpoint.replace(str(ids["organization"]), str(ids["other_organization"])),
            headers=HEADERS,
        )
        assert foreign.status_code in {403, 404}
        assert site["id"] not in foreign.text
    assert client.get(path + f"?website_id={uuid4()}", headers=HEADERS).status_code == 404
    assert client.get(path + "?offset=-1", headers=HEADERS).status_code == 422
    assert (
        client.get(detail_path.replace(site["id"], str(uuid4())), headers=HEADERS).status_code
        == 404
    )
