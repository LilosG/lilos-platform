"""Portfolio overview: real persisted evidence, explicit availability, tenant scope."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from apps.api.app.execution.models import WorkflowRun
from apps.api.app.platform_admin.models import PlatformAdministrator
from leads import test_leads_api as canonical

HEADERS = canonical.HEADERS
run_db = canonical.run_db
canonical_leads_client = canonical.leads_client
PORTFOLIO = "/api/v1/command-center/portfolio"


def test_portfolio_reports_real_counts_and_never_invents_zero(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    org = str(ids["organization"])

    empty = client.get(PORTFOLIO, headers=HEADERS)
    assert empty.status_code == 200, empty.text
    assert "no-store" in empty.headers["cache-control"]
    body = empty.json()
    # Only the caller's organization; the other tenant is never listed.
    assert [row["organization_id"] for row in body["clients"]] == [org]
    assert str(ids["other_organization"]) not in empty.text
    row = body["clients"][0]
    assert row["leads"]["availability"] == "available"
    assert row["leads"]["current"] == 0
    # No rank-scan data exists anywhere: shown as not tracked, never as a number.
    assert row["local_visibility"] == {
        "current": None,
        "previous": None,
        "percent_delta": None,
        "source": "rank_scan",
        "availability": "not_tracked",
        "freshness_at": None,
    }
    assert body["totals"]["local_visibility"]["availability"] == "not_tracked"
    # Products this organization is not entitled to read are labeled, not zeroed.
    assert row["search_clicks"]["current"] is None
    assert row["search_clicks"]["availability"] in {"not_permitted", "not_connected"}
    assert row["organic_sessions"]["current"] is None
    assert row["health"] == "not_configured"
    assert "GOOGLE_NOT_CONNECTED" in row["health_reasons"]

    command = {
        "source_id": str(ids["source"]),
        "location_id": str(ids["location"]),
        "external_submission_id": "portfolio-submission",
        "received_at": (datetime.now(UTC) - timedelta(days=3)).isoformat(),
        "first_name": "Synthetic",
        "email": "portfolio@example.test",
        "message": "Portfolio inquiry",
    }
    created = client.post(
        f"/api/v1/organizations/{org}/leads/intake", headers=HEADERS, json=command
    )
    assert created.status_code == 201, created.text
    older = dict(
        command,
        external_submission_id="portfolio-older",
        email="older@example.test",
        received_at=(datetime.now(UTC) - timedelta(days=40)).isoformat(),
    )
    assert (
        client.post(f"/api/v1/organizations/{org}/leads/intake", headers=HEADERS, json=older)
    ).status_code == 201

    async def fail_run(session: AsyncSession) -> None:
        run = await session.get(WorkflowRun, ids["workflow_run"])
        assert run is not None
        run.status = "failed"
        run.failure_code = "SYNTHETIC_FAILURE"
        await session.commit()

    run_db(postgresql_test_url, fail_run)

    second = client.get(PORTFOLIO + "?days=28", headers=HEADERS)
    assert second.status_code == 200, second.text
    data = second.json()
    leads = data["clients"][0]["leads"]
    assert leads["current"] == 1
    assert leads["previous"] == 1
    assert leads["percent_delta"] == 0.0
    assert data["totals"]["website_leads"]["current"] == 1
    assert data["clients"][0]["health"] == "not_configured"
    assert "WORKFLOW_ATTENTION" in data["clients"][0]["health_reasons"]
    failed = [item for item in data["attention"] if item["code"] == "WORKFLOW_FAILED"]
    assert failed and failed[0]["organization_id"] == org
    assert failed[0]["reference"] == "leads.send_communication:SYNTHETIC_FAILURE"
    assert data["client_count"] == 1
    assert data["location_count"] == 1


def test_portfolio_rejects_invalid_period_and_requires_authentication(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, _ = canonical_leads_client
    assert client.get(PORTFOLIO + "?days=30", headers=HEADERS).status_code == 422
    assert client.get(PORTFOLIO).status_code == 401


CLIENTS = "/api/v1/command-center/clients"


def test_client_overview_is_tenant_scoped_and_labels_missing_data(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = canonical_leads_client
    org, other = str(ids["organization"]), str(ids["other_organization"])

    listed = client.get(CLIENTS, headers=HEADERS)
    assert listed.status_code == 200, listed.text
    assert [(row["organization_id"], row["access"]) for row in listed.json()["data"]] == [
        (org, "member")
    ]
    assert listed.json()["platform_administrator"] is False
    assert other not in listed.text

    own = client.get(f"{CLIENTS}/{org}/overview?days=28", headers=HEADERS)
    assert own.status_code == 200, own.text
    assert "no-store" in own.headers["cache-control"]
    body = own.json()
    row = body["client"]
    assert body["access"] == "member"
    assert row["organization_id"] == org
    assert row["local_visibility"]["availability"] == "not_tracked"
    assert row["average_local_rank"]["availability"] == "not_tracked"
    assert row["average_local_rank"]["current"] is None
    assert {system["key"] for system in body["systems"]} == {
        "google",
        "analytics",
        "search_console",
        "automations",
    }
    # The fixture organization has no Insights entitlement: labeled, not zeroed.
    assert body["insights"]["availability"] == "not_permitted"
    assert body["insights"]["workflow_runs"] == {}
    assert body["insights"]["seo_opportunities_blocked"] is None

    # Another tenant and an unknown id are indistinguishable: no disclosure.
    assert client.get(f"{CLIENTS}/{other}/overview", headers=HEADERS).status_code == 404
    assert client.get(f"{CLIENTS}/{uuid4()}/overview", headers=HEADERS).status_code == 404
    assert client.get(f"{CLIENTS}/{org}/overview?days=30", headers=HEADERS).status_code == 422
    assert client.get(f"{CLIENTS}/{org}/overview").status_code == 401


def test_platform_administrator_sees_every_active_client(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    org, other = str(ids["organization"]), str(ids["other_organization"])

    async def grant(session: AsyncSession) -> None:
        session.add(PlatformAdministrator(user_profile_id=ids["profile"]))
        await session.commit()

    run_db(postgresql_test_url, grant)

    elevated = client.get(CLIENTS, headers=HEADERS).json()
    assert elevated["platform_administrator"] is True
    access = {row["organization_id"]: row["access"] for row in elevated["data"]}
    assert access == {org: "member", other: "platform_administrator"}
    portfolio = client.get(PORTFOLIO, headers=HEADERS).json()
    assert {row["organization_id"] for row in portfolio["clients"]} == {org, other}
    overview = client.get(f"{CLIENTS}/{other}/overview", headers=HEADERS)
    assert overview.status_code == 200, overview.text
    assert overview.json()["access"] == "platform_administrator"
