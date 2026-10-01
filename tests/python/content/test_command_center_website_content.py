"""Canonical Content details and publication state fidelity in the Phase 4 projection."""

import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.products.content.models import ContentPublication

from .test_content_api import HEADERS, content_client

__all__ = ["content_client"]


def test_content_projection_exact_revision_and_publication_states(
    content_client: tuple[TestClient, dict[str, UUID]],
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, ids = content_client
    base = f"/api/v1/organizations/{ids['organization']}"
    workspace = base + "/command-center/website-content"
    empty = client.get(workspace, headers=HEADERS)
    assert empty.status_code == 200, empty.text
    assert empty.json()["content_scope"] == "organization"
    assert empty.json()["page_availability"] == "permission_required"
    assert empty.json()["pages"] == []
    item = client.post(
        base + "/content",
        headers=HEADERS,
        json={
            "location_id": str(ids["location"]),
            "content_type": "blog",
            "title": "Phase 4 grounded content",
            "slug": "phase4-grounded",
        },
    ).json()["data"]
    path = workspace + f"/content/{item['id']}"
    detail = client.get(path, headers=HEADERS)
    assert detail.status_code == 200, detail.text
    assert detail.json()["facts"]
    assert detail.headers["cache-control"] == "private, no-store"
    brief = client.post(
        base + f"/content/{item['id']}/briefs",
        headers=HEADERS,
        json={
            "audience": "Synthetic visitors",
            "intent": "Answer a question",
            "target_reference": "/articles/",
            "approved_fact_revision_ids": [str(ids["approved_fact"])],
        },
    )
    assert brief.status_code == 201, brief.text
    draft = client.post(
        base + f"/content/{item['id']}/revisions/ai-draft",
        headers=HEADERS,
        json={
            "brief_id": brief.json()["data"]["id"],
            "idempotency_key": "phase4-ai-draft-workflow",
        },
    )
    assert draft.status_code == 202, draft.text
    queued = client.get(path, headers=HEADERS)
    assert queued.status_code == 200, queued.text
    assert queued.json()["draft_runs"][0]["id"] == draft.json()["data"]["workflow_run_id"]
    assert queued.json()["draft_runs"][0]["status"] == "queued"

    revision = client.post(
        base + f"/content/{item['id']}/revisions",
        headers=HEADERS,
        json={
            "body": "A grounded synthetic article.",
            "frontmatter": {"title": "Synthetic article"},
            "created_by_type": "user",
            "approved_fact_revision_ids": [str(ids["approved_fact"])],
        },
    )
    assert revision.status_code == 201, revision.text
    revision_id = revision.json()["data"]["id"]
    for stage in ["editorial", "client"]:
        decision = client.post(
            base + f"/content-operations/{item['id']}/revisions/{revision_id}/decision",
            headers=HEADERS,
            json={"stage": stage, "approve": True},
        )
        assert decision.status_code == 200, decision.text
    publication = client.post(
        base + f"/content-operations/{item['id']}/publish",
        headers=HEADERS,
        json={
            "idempotency_key": "phase4-content-publication",
            "publishing_target_id": str(ids["target"]),
        },
    )
    assert publication.status_code == 202, publication.text
    replay = client.post(
        base + f"/content-operations/{item['id']}/publish",
        headers=HEADERS,
        json={
            "idempotency_key": "phase4-content-publication",
            "publishing_target_id": str(ids["target"]),
        },
    )
    assert replay.json()["data"]["id"] == publication.json()["data"]["id"]
    for state in [
        "reserved",
        "pull_request_created",
        "checks_running",
        "checks_failed",
        "merged",
        "deployment_pending",
        "deployed",
        "verified",
        "failed",
        "reconciliation_required",
    ]:

        async def set_state(publication_state: str = state) -> None:
            async with content_session_factory.begin() as session:
                row = await session.scalar(
                    select(ContentPublication).where(
                        ContentPublication.id == UUID(publication.json()["data"]["id"])
                    )
                )
                assert row is not None
                row.status = publication_state

        asyncio.run(set_state())
        result = client.get(path, headers=HEADERS)
        assert result.status_code == 200, result.text
        projected = result.json()["publications"][0]
        assert projected["status"] == state
        assert projected["workflow_status"] == "queued"
        assert projected["verified_at"] is None
        assert projected["deployment_status"] is None
        assert projected["verification_evidence"] is None
        assert projected["can_recover"] == (
            state not in {"verified", "failed", "checks_failed", "rolled_back"}
        )
    assert client.get(path).status_code == 401
    assert client.get(
        path.replace(str(ids["organization"]), str(ids["other_organization"])), headers=HEADERS
    ).status_code in {403, 404}
