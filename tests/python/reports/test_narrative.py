"""Hermes narrative drafts: grounded in the snapshot, number-checked, never breaking a report."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from apps.api.app.ai.gateway import AIGatewayRequest
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.reports.narrative import (
    AI_TASK_KEY,
    RETENTION_POLICY_KEY,
    NarrativeDrafter,
    numbers_in,
)
from apps.api.app.routes.command_center_reports import get_narrative_drafter
from reports.routes_support import BASE, call
from reports.support import Factory

pytestmark = pytest.mark.integration
SEPT = "2026-09/previous"
GOOD = {
    "what_changed": (
        "Your profile was viewed 720 times in September, up from 600 in August, a rise of 20%. "
        "Calls, website clicks and direction requests together came to 540."
    ),
    "next_work": "We will keep publishing posts and answering every review.",
}


class FakeGateway:
    """Stands in for the AI gateway: returns a scripted draft, or fails, and records requests."""

    def __init__(self, draft: dict[str, str] | Exception) -> None:
        self.draft = draft
        self.requests: list[AIGatewayRequest] = []

    async def execute(self, request: AIGatewayRequest) -> dict[str, Any]:
        self.requests.append(request)
        if isinstance(self.draft, Exception):
            raise self.draft
        return {
            "provider": "fake",
            "model": "fixture",
            "draft": json.dumps(self.draft),
            "narrative": self.draft,
            "requires_human_review": True,
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            "latency_ms": 5,
            "cost_microunits": 100,
        }


def url(org: UUID, tail: str = "") -> str:
    return f"{BASE}/{org}/command-center/reports{tail}"


def override(client: TestClient, gateway: object) -> None:
    app = cast(Any, client.app)
    drafter = NarrativeDrafter(cast(Any, gateway))
    app.dependency_overrides[get_narrative_drafter] = lambda: drafter


def use(client: TestClient, draft: dict[str, str] | Exception) -> FakeGateway:
    gateway = FakeGateway(draft)
    override(client, gateway)
    return gateway


def generate(client: TestClient, org: UUID) -> dict[str, Any]:
    body: dict[str, Any] = call(
        client,
        "post",
        url(org, "/generate"),
        "manager",
        {"start_month": "2026-09-01", "end_month": "2026-09-01"},
    ).json()
    report: dict[str, Any] = body["report"]
    return report


def draft(client: TestClient, org: UUID, role: str = "manager") -> Any:
    return call(client, "post", url(org, f"/{SEPT}/1/draft-narrative"), role)


def executions(factory: Factory) -> list[AIExecution]:
    import asyncio

    async def read() -> list[AIExecution]:
        async with factory() as session:
            return list(await session.scalars(select(AIExecution).order_by(AIExecution.created_at)))

    return asyncio.run(read())


def test_numbers_are_found_in_every_form_a_sentence_can_state_them() -> None:
    text = (
        "Views reached 1,204 (up 12.5%) from 1,000. Two reviews came in on September 3rd, "
        "and we posted 3 times.\n1. First point.\nAbout twenty calls."
    )
    found = numbers_in(text)

    assert Decimal("1204") in found and Decimal("12.5") in found and Decimal("1000") in found
    assert Decimal("2") in found and Decimal("3") in found and Decimal("20") in found
    # A date mention and a list marker are not figures.
    assert found.count(Decimal("3")) == 1 and Decimal("1") not in found


def test_a_draft_that_states_only_snapshot_numbers_is_kept_and_labeled(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, factory = reports_app
    org = ids["org"]
    report = generate(client, org)
    gateway = use(client, GOOD)

    result = draft(client, org).json()

    assert result["outcome"] == "drafted" and result["failure"] is None
    narrative = result["report"]["narrative"]
    assert narrative["what_changed"] == GOOD["what_changed"] and narrative["origin"] == "hermes"
    # The stored snapshot was the only evidence the model was given, and nothing else moved.
    (request,) = gateway.requests
    assert request.task_key == AI_TASK_KEY and request.location_id is None
    evidence = request.input_document["evidence"]
    assert (
        evidence["period"] == "September 2026" and evidence["profile_views"]["this_period"] == 720
    )
    assert request.approved_fact_revision_ids and request.input_references
    assert result["report"]["snapshot"] == report["snapshot"]
    # It is recorded like any model call, under a retention policy.
    (record,) = executions(factory)
    assert record.status == "completed" and record.provider_key == "fake"
    assert record.requires_human_review is True and record.safe_error_code is None

    import asyncio

    async def task_policy() -> str:
        async with factory() as session:
            task = await session.scalar(
                select(AITaskDefinition).where(AITaskDefinition.key == AI_TASK_KEY)
            )
            assert task is not None
            return task.retention_policy_key

    assert asyncio.run(task_policy()) == RETENTION_POLICY_KEY


@pytest.mark.parametrize(
    ("draft_text", "failure"),
    [
        ("Views grew by 4,321 this month.", "number_not_in_data"),
        ("Roughly eighty more people found you.", "number_not_in_data"),
        ("Views reached 720, written with help from Claude.", "authorship_mentioned"),
        ("This summary was produced by an AI assistant: 720 views.", "authorship_mentioned"),
        ("Views rose to 720 because of our new posts.", "causal_claim"),
    ],
)
def test_a_draft_that_fails_a_check_is_not_used_and_the_narrative_is_unchanged(
    reports_app: tuple[TestClient, dict[str, UUID], Factory], draft_text: str, failure: str
) -> None:
    client, ids, factory = reports_app
    org = ids["org"]
    generate(client, org)
    mine = {"what_changed": "My own words.", "next_work": "My own plan."}
    call(client, "put", url(org, f"/{SEPT}/1/narrative"), "manager", mine)
    before = call(client, "get", url(org, f"/{SEPT}/1"), "manager").json()
    use(client, {"what_changed": draft_text, "next_work": "We will keep going."})

    response = draft(client, org)

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "not_used" and body["failure"] == failure
    after = call(client, "get", url(org, f"/{SEPT}/1"), "manager").json()
    assert after["narrative"] == before["narrative"] == {**mine, "origin": "manual"}
    assert after["snapshot"] == before["snapshot"]
    (record,) = executions(factory)
    assert record.status == "validation_failed" and record.safe_error_code == failure.upper()


def test_a_failed_provider_leaves_the_report_usable_and_the_narrative_untouched(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, factory = reports_app
    org = ids["org"]
    generate(client, org)
    use(client, RuntimeError("provider exploded"))

    result = draft(client, org).json()

    assert result["outcome"] == "not_used" and result["failure"] == "draft_failed"
    assert result["report"]["narrative"]["origin"] == "none"
    (record,) = executions(factory)
    assert record.status == "provider_failed"
    # The person writes it by hand and the report is approved as usual.
    call(
        client,
        "put",
        url(org, f"/{SEPT}/1/narrative"),
        "owner",
        {"what_changed": "Written by hand.", "next_work": "Next steps."},
    )
    assert call(client, "post", url(org, f"/{SEPT}/1/approve"), "owner").status_code == 200


def test_malformed_and_empty_drafts_are_rejected_with_their_own_codes(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    org = ids["org"]
    generate(client, org)

    use(client, {"what_changed": "   ", "next_work": ""})
    assert draft(client, org).json()["failure"] == "draft_empty"

    class Broken:
        async def execute(self, request: AIGatewayRequest) -> dict[str, Any]:
            return {"draft": "not json at all"}

    override(client, Broken())
    assert draft(client, org).json()["failure"] == "draft_malformed"


def test_only_a_manager_may_draft_and_an_approved_report_is_never_drafted(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    org = ids["org"]
    generate(client, org)
    gateway = use(client, GOOD)

    assert draft(client, org, "viewer").status_code == 403
    assert gateway.requests == []

    assert draft(client, org, "owner").json()["outcome"] == "drafted"
    assert call(client, "post", url(org, f"/{SEPT}/1/approve"), "owner").status_code == 200
    gateway.requests.clear()
    locked = draft(client, org, "owner")
    assert (locked.status_code, locked.json()["error"]["code"]) == (409, "REPORT_NOT_EDITABLE")
    assert gateway.requests == []  # refused before any spend
