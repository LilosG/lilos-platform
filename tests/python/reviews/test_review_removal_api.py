"""A review Google no longer lists: routes refuse replies, and the workspace reads it as history."""

from uuid import UUID

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from apps.api.app.products.reviews.models import Review

from .test_reviews_api import (
    HEADERS,
    _approved_fact,
    _fetch_review_and_revision,
    _ingest,
    reviews_client,  # noqa: F401  (fixture)
    run_db,
)

CODE = "REVIEW_NO_LONGER_ON_PROVIDER"


def _remove(postgresql_test_url: str, review_id: UUID) -> None:
    async def work(session: AsyncSession) -> None:
        async with session.begin():
            await session.execute(
                update(Review).where(Review.id == review_id).values(status="removed")
            )

    run_db(postgresql_test_url, work)


@pytest.mark.integration
def test_every_reply_route_refuses_a_removed_review_with_a_typed_conflict(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],  # noqa: F811
) -> None:
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]
    _ingest(postgresql_test_url, ids, body="Lovely evening", rating=5, external_id="gone-1")
    review, revision = _fetch_review_and_revision(postgresql_test_url, org, location)
    base = f"/api/v1/organizations/{org}/locations/{location}/reviews/{review}/responses"
    fact = _approved_fact(client, org)

    def draft(text: str) -> str:
        created = client.post(
            base,
            headers=HEADERS,
            json={
                "review_revision_id": str(revision),
                "response_text": text,
                "generated_by_type": "user",
                "approved_fact_revision_ids": [fact],
            },
        )
        assert created.status_code == 201
        return str(created.json()["data"]["id"])

    # Work in flight before Google dropped the review: one awaiting approval, one approved.
    awaiting = draft("Thank you for visiting us.")
    approved = draft("We appreciated your kind words.")
    assert client.post(f"{base}/{approved}/approve", headers=HEADERS).status_code == 200
    _remove(postgresql_test_url, review)

    attempts = {
        "draft": client.post(
            base,
            headers=HEADERS,
            json={
                "review_revision_id": str(revision),
                "response_text": "A new reply.",
                "generated_by_type": "user",
                "approved_fact_revision_ids": [fact],
            },
        ),
        "regenerate": client.post(
            f"{base}/ai-draft",
            headers=HEADERS,
            json={
                "review_revision_id": str(revision),
                "approved_fact_revision_ids": [fact],
                "idempotency_key": "removed-regenerate-key",
            },
        ),
        "approve": client.post(f"{base}/{awaiting}/approve", headers=HEADERS),
        "publish": client.post(
            f"{base}/{approved}/publish",
            headers=HEADERS,
            json={"idempotency_key": "removed-publish-key"},
        ),
    }
    for name, response in attempts.items():
        assert response.status_code == 409, name
        assert response.json()["error"]["code"] == CODE, name


@pytest.mark.integration
def test_the_workspace_counts_removed_reviews_apart_and_offers_no_action_on_one(
    postgresql_test_url: str,
    reviews_client: tuple[TestClient, dict[str, UUID]],  # noqa: F811
) -> None:
    client, ids = reviews_client
    org, location = ids["organization"], ids["location"]
    for index, rating in enumerate((5, 5, 1)):
        _ingest(
            postgresql_test_url,
            ids,
            body=f"Visit number {index}",
            rating=rating,
            external_id=f"count-{index}",
        )
    path = f"/api/v1/organizations/{org}/command-center/reviews"
    params = {"location_id": str(location)}
    before = client.get(path, headers=HEADERS, params=params).json()
    assert (before["inventory_count"], before["removed_count"]) == (3, 0)
    assert before["average_rating"] == pytest.approx(11 / 3)

    gone = next(item for item in before["items"] if item["rating"] == 1.0)
    _remove(postgresql_test_url, UUID(gone["id"]))

    after = client.get(path, headers=HEADERS, params=params).json()
    assert (after["inventory_count"], after["removed_count"]) == (2, 1)
    assert after["awaiting_response_count"] == 2
    assert after["average_rating"] == 5.0
    assert [item["status"] for item in after["items"]] == ["classified", "classified"]

    only_removed = client.get(path, headers=HEADERS, params={**params, "status": "removed"}).json()
    assert [item["id"] for item in only_removed["items"]] == [gone["id"]]
    assert only_removed["items"][0]["status"] == "removed"

    detail = client.get(f"{path}/locations/{location}/{gone['id']}", headers=HEADERS).json()
    assert detail["review"]["status"] == "removed"
    assert (detail["can_draft"], detail["can_ai_draft"]) == (False, False)
