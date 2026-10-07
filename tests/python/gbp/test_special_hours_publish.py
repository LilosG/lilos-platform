"""Approved special hours are written to Google exactly as approved, as one full list."""

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from starlette.testclient import TestClient

from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution import handlers as handler_mod
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.products.gbp.operations_models import GBPSpecialHoursPublication
from apps.api.app.products.gbp.special_hours_publish import (
    entry_key,
    merge_special_hours,
    same_special_hours,
)

from .test_gbp_operations_api import HEADERS, gbp_operations_client, run_db

__all__ = ["gbp_operations_client"]

TODAY = datetime.now(UTC).date()
FIRST = TODAY + timedelta(days=30)
SECOND = TODAY + timedelta(days=31)
UNMANAGED = TODAY + timedelta(days=45)
YESTERDAY = TODAY - timedelta(days=1)


def entry(
    day: date, opens: tuple[int, int] = (9, 0), closes: tuple[int, int] = (17, 0)
) -> dict[str, Any]:
    return {
        "startDate": {"year": day.year, "month": day.month, "day": day.day},
        "openTime": {"hours": opens[0], "minutes": opens[1]},
        "closeTime": {"hours": closes[0], "minutes": closes[1]},
        "closed": False,
    }


def google_form(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What Google returns: zero minutes and a false `closed` are omitted."""
    result = []
    for item in entries:
        copy = {k: v for k, v in item.items() if k not in {"closed", "openTime", "closeTime"}}
        if item.get("closed"):
            copy["closed"] = True
        else:
            for name in ("openTime", "closeTime"):
                copy[name] = {k: v for k, v in item[name].items() if v}
        result.append(copy)
    return result


class FakeGoogle:
    """Google replaces the whole specialHours list on patch and reports it in its own form."""

    def __init__(self, special: list[dict[str, Any]] | None = None) -> None:
        self.special = list(special or [])
        self.patches: list[list[dict[str, Any]]] = []
        self.masks: list[list[str]] = []
        self.patch_error: Exception | None = None
        self.ignore_patch = False

    async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
        return {"name": location_name, "specialHours": {"specialHourPeriods": self.special}}

    async def patch_location(
        self,
        access_token: str,
        location_name: str,
        fields: dict[str, Any],
        update_mask: list[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        sent = fields["specialHours"]["specialHourPeriods"]
        self.patches.append(sent)
        self.masks.append(update_mask)
        if self.patch_error is not None:
            raise self.patch_error
        if not self.ignore_patch:
            self.special = google_form(sent)
        return {"name": location_name}


async def fake_token(session: Any, organization_id: UUID) -> tuple[str, object]:
    return "token", object()


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> FakeGoogle:
    fake = FakeGoogle()
    monkeypatch.setattr(handler_mod, "_adapter_factory", lambda: fake)
    monkeypatch.setattr(handler_mod, "_token_resolver", fake_token)
    monkeypatch.setattr(handler_mod, "_google_writes_enabled", lambda: True)
    return fake


class Console:
    """The approval journey through the real API, plus the worker running the queued publish."""

    def __init__(self, client: TestClient, ids: dict[str, UUID], url: str) -> None:
        self.client, self.ids, self.url = client, ids, url
        self.base = (
            f"/api/v1/organizations/{ids['organization']}/locations/{ids['location']}"
            "/gbp/operations"
        )

    def propose(self, day: date, *, closed: bool = False) -> str:
        body: dict[str, Any] = {"service_date": day.isoformat(), "closed": closed, "source": "t"}
        if not closed:
            body["periods"] = [{"opens": "09:00:00", "closes": "17:00:00"}]
        response = self.client.post(
            f"{self.base}/locations/{self.ids['gbp_location']}/special-hours",
            headers=HEADERS,
            json=body,
        )
        assert response.status_code == 201, response.text
        return str(response.json()["data"]["id"])

    def decide(self, item: str, approve: bool = True) -> Any:
        return self.client.post(
            f"{self.base}/special-hours/{item}/decision",
            headers=HEADERS,
            json={"approve": approve},
        )

    def retry(self, item: str, key: str = "retry-key-0001") -> Any:
        return self.client.post(
            f"{self.base}/special-hours/{item}/retry",
            headers=HEADERS,
            json={"idempotency_key": key},
        )

    def listing(self) -> dict[str, dict[str, Any]]:
        rows = self.client.get(
            f"{self.base}/locations/{self.ids['gbp_location']}/special-hours", headers=HEADERS
        ).json()["data"]
        return {row["id"]: row for row in rows}

    def work[T](self, work: Callable[[Any], Awaitable[T]]) -> T:
        return run_db(self.url, work)

    def publications(self) -> list[GBPSpecialHoursPublication]:
        async def read(session: Any) -> list[GBPSpecialHoursPublication]:
            return list(
                await session.scalars(
                    select(GBPSpecialHoursPublication).order_by(
                        GBPSpecialHoursPublication.created_at
                    )
                )
            )

        return self.work(read)

    def run_worker(self, organization: UUID | None = None) -> JobOutcome:
        """Execute the newest queued publication, as the worker would."""
        publication = self.publications()[-1]

        async def execute(session: Any) -> JobOutcome:
            return await handler_mod._handle_gbp_publish_special_hours(
                session,
                organization_id=organization or self.ids["organization"],
                location_id=self.ids["location"],
                input_document={"publication_id": str(publication.id)},
                correlation_id="special-hours-test",
                workflow_run_id=publication.workflow_run_id,
            )

        return self.work(execute)


@pytest.fixture
def console(
    gbp_operations_client: tuple[TestClient, dict[str, UUID]], postgresql_test_url: str
) -> Console:
    client, ids = gbp_operations_client
    return Console(client, ids, postgresql_test_url)


def sent_dates(patch: list[dict[str, Any]]) -> set[date]:
    return {date(*(entry_key(item) or ((0, 1, 1),))[0]) for item in patch}


def test_google_form_is_compared_in_canonical_form() -> None:
    sent = [entry(FIRST, (9, 0), (17, 0))]
    assert same_special_hours(sent, google_form(sent), TODAY)
    assert not same_special_hours(sent, google_form([entry(FIRST, (9, 0), (18, 0))]), TODAY)
    closed = [{"startDate": entry(FIRST)["startDate"], "closed": True}]
    assert same_special_hours(closed, google_form(closed), TODAY)
    assert not same_special_hours(closed, [], TODAY)
    # Dates that have passed never decide whether Google matches.
    assert same_special_hours(sent, [*google_form(sent), entry(YESTERDAY)], TODAY)


def test_merge_keeps_unmanaged_future_dates_and_drops_past_ones() -> None:
    google = [entry(YESTERDAY), entry(UNMANAGED), entry(FIRST, (10, 0), (11, 0))]
    merged = merge_special_hours(google, [entry(FIRST), entry(SECOND)], TODAY)
    assert {item["startDate"]["day"] for item in merged} == {
        UNMANAGED.day,
        FIRST.day,
        SECOND.day,
    }
    # The approved hours win over what Google had for the same date.
    first = [item for item in merged if item["startDate"]["day"] == FIRST.day]
    assert first == [entry(FIRST)]


@pytest.mark.integration
def test_a_second_approval_keeps_the_first_date(console: Console, google: FakeGoogle) -> None:
    first = console.propose(FIRST)
    assert console.decide(first).json()["data"]["status"] == "approved"
    assert console.run_worker().result == "succeeded"
    assert sent_dates(google.patches[-1]) == {FIRST}
    assert google.masks == [["specialHours"]]

    second = console.propose(SECOND, closed=True)
    console.decide(second)
    assert console.run_worker().result == "succeeded"

    # Google replaces the whole list, so the second write must carry both dates.
    assert sent_dates(google.patches[-1]) == {FIRST, SECOND}
    assert sent_dates(google_form(google.special)) == {FIRST, SECOND}
    states = {row["id"]: row["status"] for row in console.listing().values()}
    assert states == {first: "published", second: "published"}
    assert all(row["verified_at"] for row in console.listing().values())


@pytest.mark.integration
def test_every_approved_date_is_sent_even_when_google_no_longer_holds_it(
    console: Console, google: FakeGoogle
) -> None:
    console.decide(console.propose(FIRST))
    console.run_worker()
    google.special = []  # the date was removed on Google since
    console.decide(console.propose(SECOND))
    assert console.run_worker().result == "succeeded"
    assert sent_dates(google.patches[-1]) == {FIRST, SECOND}


@pytest.mark.integration
def test_future_dates_google_already_holds_survive_and_past_ones_are_dropped(
    console: Console, google: FakeGoogle
) -> None:
    google.special = google_form([entry(YESTERDAY), entry(UNMANAGED)])
    console.decide(console.propose(FIRST))
    assert console.run_worker().result == "succeeded"
    assert sent_dates(google.patches[-1]) == {FIRST, UNMANAGED}


@pytest.mark.integration
def test_the_newest_approved_revision_of_a_date_is_the_one_sent(
    console: Console, google: FakeGoogle
) -> None:
    older = console.propose(FIRST)
    console.decide(older)
    console.run_worker()
    newer = console.propose(FIRST, closed=True)
    console.decide(newer)
    assert console.run_worker().result == "succeeded"
    assert google.patches[-1] == [
        {"startDate": entry(FIRST)["startDate"], "closed": True},
    ]
    states = {row["id"]: row["status"] for row in console.listing().values()}
    assert states == {older: "superseded", newer: "published"}
    # A later rejected revision never takes an approved date off Google.
    console.decide(console.propose(FIRST), approve=False)
    assert {r["status"] for r in console.listing().values()} == {
        "superseded",
        "published",
        "rejected",
    }


@pytest.mark.integration
def test_rejecting_queues_nothing_and_a_decision_is_applied_once(
    console: Console, google: FakeGoogle
) -> None:
    rejected = console.propose(FIRST)
    assert console.decide(rejected, approve=False).json()["data"]["status"] == "rejected"
    assert console.publications() == []
    assert console.decide(rejected, approve=False).status_code == 200
    assert console.decide(rejected, approve=True).status_code == 409

    approved = console.propose(SECOND)
    console.decide(approved)
    console.decide(approved)
    assert len(console.publications()) == 1

    async def runs(session: Any) -> int:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(WorkflowRun)
                .join(WorkflowVersion, WorkflowVersion.id == WorkflowRun.workflow_version_id)
                .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
                .where(WorkflowDefinition.key == "gbp.publish_special_hours")
            )
        )

    assert console.work(runs) == 1
    assert google.patches == []


@pytest.mark.integration
def test_google_rejecting_the_write_fails_only_the_waiting_date(
    console: Console, google: FakeGoogle
) -> None:
    live = console.propose(FIRST)
    console.decide(live)
    console.run_worker()
    waiting = console.propose(SECOND)
    console.decide(waiting)
    google.patch_error = httpx.HTTPStatusError(
        "bad", request=httpx.Request("PATCH", "https://x"), response=httpx.Response(400)
    )
    outcome = console.run_worker()
    assert (outcome.result, outcome.safe_error) == ("permanent_failure", "PROVIDER_REJECTED_400")
    rows = console.listing()
    assert rows[live]["status"] == "published"
    assert (rows[waiting]["status"], rows[waiting]["safe_error_code"]) == (
        "failed",
        "PROVIDER_REJECTED_400",
    )
    assert sent_dates(google_form(google.special)) == {FIRST}


@pytest.mark.integration
def test_an_unconfirmed_write_needs_attention_and_a_retry_confirms_it(
    console: Console, google: FakeGoogle
) -> None:
    live = console.propose(FIRST)
    console.decide(live)
    console.run_worker()
    waiting = console.propose(SECOND)
    console.decide(waiting)
    google.patch_error = httpx.ReadTimeout("slow")
    assert console.run_worker().safe_error == "PROVIDER_WRITE_AMBIGUOUS"
    rows = console.listing()
    assert {rows[live]["status"], rows[waiting]["status"]} == {"reconciliation_required"}

    assert console.retry(live).status_code == 200
    assert console.listing()[live]["status"] == "approved"
    google.patch_error = None
    assert console.run_worker().result == "succeeded"
    assert {row["status"] for row in console.listing().values()} == {"published"}
    assert sent_dates(google.patches[-1]) == {FIRST, SECOND}


@pytest.mark.integration
def test_retry_is_idempotent_and_only_for_dates_that_need_it(
    console: Console, google: FakeGoogle
) -> None:
    item = console.propose(FIRST)
    console.decide(item)
    console.run_worker()
    assert console.retry(item).status_code == 409  # already live

    google.patch_error = httpx.ReadTimeout("slow")
    second = console.propose(SECOND)
    console.decide(second)
    console.run_worker()
    queued = len(console.publications())
    assert console.retry(second, "same-key-0001").status_code == 200
    assert console.retry(second, "same-key-0001").status_code == 200
    assert len(console.publications()) == queued + 1


@pytest.mark.integration
def test_a_write_google_does_not_reflect_is_not_called_published(
    console: Console, google: FakeGoogle
) -> None:
    google.ignore_patch = True
    item = console.propose(FIRST)
    console.decide(item)
    outcome = console.run_worker()
    assert outcome.safe_error == "VERIFICATION_CONTENT_MISMATCH"
    row = console.listing()[item]
    assert (row["status"], row["safe_error_code"]) == (
        "reconciliation_required",
        "VERIFICATION_CONTENT_MISMATCH",
    )
    assert row["verified_at"] is None


@pytest.mark.integration
def test_the_provider_write_switch_stops_the_write(
    console: Console, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(handler_mod, "_google_writes_enabled", lambda: False)
    item = console.propose(FIRST)
    console.decide(item)
    outcome = console.run_worker()
    assert outcome.safe_error == "PROVIDER_WRITES_DISABLED"
    assert google.patches == []
    assert console.listing()[item]["safe_error_code"] == "PROVIDER_WRITES_DISABLED"


@pytest.mark.integration
def test_a_date_that_passed_before_it_was_sent_is_not_sent(
    console: Console, google: FakeGoogle
) -> None:
    item = console.propose(YESTERDAY)
    console.decide(item)
    outcome = console.run_worker()
    assert outcome.safe_error == "NOTHING_TO_PUBLISH"
    assert google.patches == []
    row = console.listing()[item]
    assert (row["status"], row["safe_error_code"]) == ("failed", "SERVICE_DATE_PASSED")


@pytest.mark.integration
def test_special_hours_are_scoped_to_their_tenant_and_location(
    console: Console, google: FakeGoogle
) -> None:
    item = console.propose(FIRST)
    sibling = (
        f"/api/v1/organizations/{console.ids['organization']}/locations/"
        f"{console.ids['sibling_location']}/gbp/operations"
    )
    for path in ("decision", "retry"):
        body = {"approve": True} if path == "decision" else {"idempotency_key": "scope-key-0001"}
        response = console.client.post(
            f"{sibling}/special-hours/{item}/{path}", headers=HEADERS, json=body
        )
        assert response.status_code == 404
    console.decide(item)
    other_tenant = console.run_worker(organization=console.ids["other_organization"])
    assert other_tenant.safe_error == "PUBLICATION_NOT_FOUND"
    assert google.patches == []
    assert console.listing()[item]["status"] == "approved"


@pytest.mark.integration
def test_every_write_leaves_an_audit_event(console: Console, google: FakeGoogle) -> None:
    console.decide(console.propose(FIRST))
    console.run_worker()

    async def events(session: Any) -> set[str]:
        return set(
            await session.scalars(
                select(AuditEvent.event_type).where(
                    AuditEvent.organization_id == console.ids["organization"]
                )
            )
        )

    assert {
        "gbp.special_hours.proposed",
        "gbp.special_hours.decided",
        "gbp.special_hours.publication_reserved",
        "gbp.special_hours.publication_verified",
    } <= console.work(events)


@pytest.mark.integration
def test_the_publication_records_exactly_what_was_sent(
    console: Console, google: FakeGoogle
) -> None:
    console.decide(console.propose(FIRST))
    console.run_worker()
    publication = console.publications()[-1]
    assert publication.status == "verified"
    assert publication.sent_periods == google.patches[-1]
