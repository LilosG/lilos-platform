"""The report routes: permissions, tenant isolation, the whole generate-to-sent journey."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from reports.routes_support import BASE, call
from reports.support import Factory

pytestmark = pytest.mark.integration
SEPT = "2026-09/previous"
SEPT_BODY = {"start_month": "2026-09-01", "end_month": "2026-09-01"}
MONTH_ROUTES = [
    ("get", "/{period}/{revision}", None),
    ("put", "/{period}/{revision}/narrative", {"what_changed": "a", "next_work": "b"}),
    ("post", "/{period}/{revision}/draft-narrative", None),
    ("post", "/{period}/{revision}/approve", None),
    ("post", "/{period}/{revision}/mark-sent", {"sent_on": "2026-10-03"}),
]


def url(org: UUID, tail: str = "") -> str:
    return f"{BASE}/{org}/command-center/reports{tail}"


@pytest.fixture(autouse=True)
def pin_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """The route handlers read the real clock; the stored data is for September 2026."""
    import apps.api.app.reports.service as service_module
    import apps.api.app.routes.command_center_reports as routes_module

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return (
                datetime(2026, 10, 5, 16, 0, tzinfo=UTC).astimezone(tz)
                if tz
                else datetime(2026, 10, 5, 16, 0)
            )

    monkeypatch.setattr(service_module, "datetime", Clock)
    monkeypatch.setattr(routes_module, "datetime", Clock)


def generate(client: TestClient, org: UUID, role: str = "manager") -> Any:
    return call(client, "post", url(org, "/generate"), role, SEPT_BODY)


def test_reads_need_insights_read_and_writes_need_manage_or_publish(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    org = ids["org"]

    # A viewer reads but cannot write.
    assert call(client, "get", url(org), "viewer").status_code == 200
    assert generate(client, org, "viewer").status_code == 403
    # A manager generates and edits the narrative, but cannot approve or record a send.
    made = generate(client, org, "manager")
    assert made.status_code == 200, made.text
    assert made.json()["created"] is True
    edit = call(
        client,
        "put",
        url(org, f"/{SEPT}/1/narrative"),
        "manager",
        {"what_changed": "Views grew.", "next_work": "Keep posting."},
    )
    assert edit.status_code == 200 and edit.json()["narrative"]["origin"] == "manual"
    for role in ("viewer", "manager"):
        assert call(client, "post", url(org, f"/{SEPT}/1/approve"), role).status_code == 403
        assert (
            call(
                client, "post", url(org, f"/{SEPT}/1/mark-sent"), role, {"sent_on": "2026-10-03"}
            ).status_code
            == 403
        )
    for method, tail, body in MONTH_ROUTES[1:3]:
        assert (
            call(
                client, method, url(org, tail.format(period=SEPT, revision=1)), "viewer", body
            ).status_code
            == 403
        )
    # The viewer sees the stored report exactly as saved, with what they may do.
    detail = call(client, "get", url(org, f"/{SEPT}/1"), "viewer").json()
    assert detail["permissions"] == {"can_generate": False, "can_publish": False}
    assert call(client, "get", url(org, f"/{SEPT}/1"), "owner").json()["permissions"] == {
        "can_generate": True,
        "can_publish": True,
    }
    # Unauthenticated callers get nothing.
    assert call(client, "get", url(org), None).status_code == 401


def test_another_tenants_user_can_read_and_change_nothing(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    org = ids["org"]
    assert generate(client, org, "owner").status_code == 200

    assert call(client, "get", url(org), "other").status_code in (403, 404)
    assert call(client, "post", url(org, "/generate"), "other", SEPT_BODY).status_code in (403, 404)
    for method, tail, body in MONTH_ROUTES:
        response = call(
            client, method, url(org, tail.format(period=SEPT, revision=1)), "other", body
        )
        assert response.status_code in (403, 404), (method, tail, response.status_code)
    # Their own client has no such revision.
    own = ids["other"]
    assert call(client, "get", url(own, f"/{SEPT}/1"), "other").status_code == 404

    # The portfolio lists only clients the caller can read.
    mine = call(client, "get", "/api/v1/command-center/reports", "other").json()
    assert [row["organization_id"] for row in mine["clients"]] == [str(own)]
    assert mine["clients"][0]["status"] is None and mine["counts"]["not_generated"] == 1
    theirs = call(client, "get", "/api/v1/command-center/reports", "owner").json()
    assert [row["organization_id"] for row in theirs["clients"]] == [str(org)]


def test_generate_edit_approve_and_mark_sent_end_to_end(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, factory = reports_app
    org = ids["org"]

    first = generate(client, org, "owner").json()["report"]
    assert first["period"] == SEPT_BODY and first["comparison"]["basis"] == "previous_period"
    assert (first["revision"], first["status"]) == (1, "draft")
    assert first["readiness"] == "ready" and first["is_current"] is True
    assert first["snapshot"]["local_rank"] == {"state": "not_tracked", "value": None}
    assert first["narrative"] == {"what_changed": "", "next_work": "", "origin": "none"}
    # Identical data: the same revision comes back.
    again = generate(client, org, "owner").json()
    assert again["created"] is False and again["report"]["revision"] == 1

    assert call(client, "post", url(org, f"/{SEPT}/1/approve"), "owner").json()["error"][
        "code"
    ] == ("REPORT_NARRATIVE_EMPTY")
    call(
        client,
        "put",
        url(org, f"/{SEPT}/1/narrative"),
        "owner",
        {"what_changed": "Views grew.", "next_work": "Keep posting."},
    )

    approved = call(client, "post", url(org, f"/{SEPT}/1/approve"), "owner")
    assert approved.status_code == 200 and approved.json()["status"] == "ready"
    assert approved.json()["approved_at"] is not None
    # An approved revision cannot be edited or regenerated unchanged.
    locked = call(
        client,
        "put",
        url(org, f"/{SEPT}/1/narrative"),
        "owner",
        {"what_changed": "x", "next_work": "y"},
    )
    assert (locked.status_code, locked.json()["error"]["code"]) == (409, "REPORT_NOT_EDITABLE")
    assert generate(client, org, "owner").json()["error"]["code"] == "REPORT_ALREADY_APPROVED"

    early = call(
        client, "post", url(org, f"/{SEPT}/1/mark-sent"), "owner", {"sent_on": "2026-09-20"}
    )
    assert (early.status_code, early.json()["error"]["code"]) == (400, "REPORT_SENT_DATE_INVALID")
    sent = call(
        client, "post", url(org, f"/{SEPT}/1/mark-sent"), "owner", {"sent_on": "2026-10-03"}
    )
    assert sent.status_code == 200 and sent.json()["status"] == "sent"
    assert sent.json()["delivery"]["sent_on"] == "2026-10-03"
    replay = call(
        client, "post", url(org, f"/{SEPT}/1/mark-sent"), "owner", {"sent_on": "2026-10-04"}
    )
    assert replay.status_code == 200 and replay.json()["delivery"]["sent_on"] == "2026-10-03"

    listing = call(client, "get", url(org), "viewer").json()
    assert listing["current_month"] == "2026-09-01"
    assert (
        listing["current"]["status"] == "sent"
        and listing["current"]["delivery"]["sent_on"] == "2026-10-03"
    )
    assert [(r["period"], r["revision"], r["status"]) for r in listing["history"]] == [
        (SEPT_BODY, 1, "sent")
    ]
    assert listing["upcoming"] is None  # no schedule exists for this client yet

    board = call(client, "get", "/api/v1/command-center/reports", "owner").json()
    assert board["month"] == "2026-09-01"
    assert board["counts"] == {
        "ready": 0,
        "needs_attention": 0,
        "missing_data": 0,
        "sent": 1,
        "not_generated": 0,
    }
    assert board["clients"][0]["sent_on"] == "2026-10-03"


def test_months_that_have_not_ended_and_months_without_data_are_refused(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    org = ids["org"]

    def post(body: dict[str, Any]) -> Any:
        return call(client, "post", url(org, "/generate"), "owner", body)

    running = post({"start_month": "2026-10-01", "end_month": "2026-10-01"})
    assert (running.status_code, running.json()["error"]["code"]) == (400, "REPORT_MONTH_NOT_ENDED")
    assert call(client, "get", url(org, "/2026-13/previous/1"), "owner").status_code == 400
    assert call(client, "get", url(org, f"/{SEPT}/9"), "owner").status_code == 404

    # A month nothing was synced for is stored as missing data and cannot be approved.
    july = post({"start_month": "2026-07-01", "end_month": "2026-07-01"})
    assert july.status_code == 200 and july.json()["report"]["readiness"] == "missing_data"
    call(
        client,
        "put",
        url(org, "/2026-07/previous/1/narrative"),
        "owner",
        {"what_changed": "a", "next_work": "b"},
    )
    refused = call(client, "post", url(org, "/2026-07/previous/1/approve"), "owner")
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "REPORT_DATA_MISSING")


def test_period_and_comparison_errors_are_typed_codes(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    org = ids["org"]

    def code(body: dict[str, Any]) -> tuple[int, str]:
        response = call(client, "post", url(org, "/generate"), "owner", body)
        return response.status_code, response.json()["error"]["code"]

    sept = {"start_month": "2026-09-01", "end_month": "2026-09-01"}
    assert code({"start_month": "2026-09-15", "end_month": "2026-09-15"}) == (
        400,
        "REPORT_MONTH_NOT_FIRST",
    )
    assert code({"start_month": "2026-09-01", "end_month": "2026-08-01"}) == (
        400,
        "REPORT_PERIOD_ORDER",
    )
    assert code({"start_month": "2025-08-01", "end_month": "2026-09-01"}) == (
        400,
        "REPORT_PERIOD_TOO_LONG",
    )
    assert code({**sept, "comparison": {"basis": "custom_baseline"}}) == (
        400,
        "REPORT_BASELINE_REQUIRED",
    )
    assert code(
        {**sept, "comparison": {"basis": "previous_period", "baseline_start": "2026-01-01"}}
    ) == (
        400,
        "REPORT_BASELINE_UNEXPECTED",
    )
    overlapping = {
        "basis": "custom_baseline",
        "baseline_start": "2026-08-01",
        "baseline_end": "2026-09-01",
    }
    assert code({**sept, "comparison": overlapping}) == (400, "REPORT_BASELINE_OVERLAPS")
    too_long = {
        "basis": "custom_baseline",
        "baseline_start": "2024-01-01",
        "baseline_end": "2025-06-01",
    }
    assert code({**sept, "comparison": too_long}) == (400, "REPORT_PERIOD_TOO_LONG")
    for bad in (
        "/2026-9/previous/1",
        "/2026-09_/previous/1",
        "/2026-09_2026-10_2026-11/previous/1",
    ):
        response = call(client, "get", url(org, bad), "owner")
        assert (response.status_code, response.json()["error"]["code"]) == (
            400,
            "REPORT_PERIOD_INVALID",
        )
    response = call(client, "get", url(org, "/2026-09/sometimes/1"), "owner")
    assert (response.status_code, response.json()["error"]["code"]) == (
        400,
        "REPORT_COMPARISON_INVALID",
    )


def test_a_range_against_each_comparison_is_stored_and_numbered_apart(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    client, ids, _ = reports_app
    org = ids["org"]
    window = {"start_month": "2026-08-01", "end_month": "2026-09-01"}

    def post(comparison: dict[str, Any] | None) -> Any:
        body = {**window, **({"comparison": comparison} if comparison else {})}
        return call(client, "post", url(org, "/generate"), "owner", body)

    previous = post(None)
    year_ago = post({"basis": "same_period_last_year"})
    baseline = post(
        {"basis": "custom_baseline", "baseline_start": "2026-01-01", "baseline_end": "2026-03-01"}
    )
    for response in (previous, year_ago, baseline):
        assert response.status_code == 200, response.text
        assert response.json()["report"]["revision"] == 1  # numbered per comparison
    report = baseline.json()["report"]
    assert report["snapshot"]["comparison"]["compared_as"] == "monthly_average"
    assert report["comparison"]["baseline_start"] == "2026-01-01"
    assert previous.json()["report"]["snapshot"]["comparison"]["year_ago"] is not None
    assert year_ago.json()["report"]["snapshot"]["comparison"]["year_ago"] is None

    fetched = call(client, "get", url(org, "/2026-08_2026-09/vs-2026-01_2026-03/1"), "owner")
    assert fetched.status_code == 200 and fetched.json()["comparison"]["basis"] == "custom_baseline"
    assert call(client, "get", url(org, "/2026-08_2026-09/year-ago/1"), "owner").status_code == 200
    # The board lists only single months against the month before.
    board = call(client, "get", "/api/v1/command-center/reports", "owner").json()
    assert board["clients"][0]["status"] is None


def test_reads_never_recompute_a_stored_report(
    reports_app: tuple[TestClient, dict[str, UUID], Factory],
) -> None:
    import asyncio

    from sqlalchemy import text

    client, ids, factory = reports_app
    org = ids["org"]
    stored = generate(client, org, "owner").json()["report"]["snapshot"]

    async def change() -> None:
        async with factory.begin() as session:
            await session.execute(text("update gbp_performance_daily_metrics set value = 99"))

    asyncio.run(change())
    later = call(client, "get", url(org, f"/{SEPT}/1"), "owner").json()["snapshot"]

    assert later == stored  # what was measured then, never the live numbers
    assert date.fromisoformat(later["period"]["start_month"]) == date(2026, 9, 1)
