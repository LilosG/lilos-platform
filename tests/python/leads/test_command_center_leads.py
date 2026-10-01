"""Canonical persisted Leads projections, outcome truth and scope negatives."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.products.leads.models import LeadSource, LeadSubmission
from leads import test_leads_api as canonical

HEADERS = canonical.HEADERS
run_db = canonical.run_db
canonical_leads_client = canonical.leads_client


def test_workspace_intake_detail_and_recorded_outcome(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    org = str(ids["organization"])
    canonical = f"/api/v1/organizations/{org}/leads"
    projection = f"/api/v1/organizations/{org}/command-center/leads"
    initial = client.get(projection, headers=HEADERS)
    assert initial.status_code == 200, initial.text
    assert initial.headers["cache-control"] == "private, no-store"
    assert initial.json()["inventory_count"] == 0
    assert initial.json()["recorded_conversions"] == 0
    assert initial.json()["sources"][0]["last_intake_at"] is None
    command = {
        "source_id": str(ids["source"]),
        "location_id": str(ids["location"]),
        "external_submission_id": "phase5-submission",
        "received_at": (datetime.now(UTC) - timedelta(days=3)).isoformat(),
        "first_name": "Synthetic",
        "email": "lead@example.test",
        "message": "Canonical inquiry",
    }
    created = client.post(canonical + "/intake", headers=HEADERS, json=command)
    assert created.status_code == 201, created.text
    lead = created.json()["data"]["lead_id"]
    replay = client.post(canonical + "/intake", headers=HEADERS, json=command)
    assert replay.json()["data"]["lead_id"] == lead
    assert replay.json()["data"]["created"] is False
    workspace = client.get(projection, headers=HEADERS).json()
    assert workspace["inventory_count"] == 1
    assert workspace["items"][0]["source_id"] == str(ids["source"])
    assert "first_name" not in workspace["items"][0]
    assert workspace["sources"][0]["quality"] == "partial"
    # Intake receipt time is ingestion evidence, distinct from upstream received_at.
    assert workspace["sources"][0]["intake_recency"] == "recent"
    assert workspace["sources"][0]["provider"] is None
    detail = client.get(projection + f"/{lead}", headers=HEADERS)
    assert detail.status_code == 200, detail.text
    data = detail.json()
    assert data["lead"]["outcome"] == "unknown"
    assert data["lead"]["message"] == command["message"]
    assert len(data["submissions"]) == 1
    assert data["source"]["sync_state"] == "unavailable_no_canonical_sync_record"
    assert data["lead"]["attribution"] == "source_identity_only_no_campaign_or_landing_page"
    assert data["downstream_outcomes"] == "unavailable_no_booking_sales_jobs_or_revenue_source"
    assert data["history"] and data["assignees"]

    async def stale_provider_evidence(session: AsyncSession) -> None:
        provider = Provider(
            key="phase5_test_provider",
            name="Synthetic provider",
            status="active",
            capabilities=[],
            manifest_version=1,
        )
        session.add(provider)
        await session.flush()
        connection = IntegrationConnection(
            organization_id=ids["organization"],
            provider_id=provider.id,
            status="degraded",
            granted_capabilities=[],
            version=1,
        )
        session.add(connection)
        await session.flush()
        source = await session.get(LeadSource, ids["source"])
        assert source is not None
        source.integration_connection_id = connection.id
        submission = await session.scalar(
            select(LeadSubmission).where(
                LeadSubmission.organization_id == ids["organization"],
                LeadSubmission.lead_id == UUID(lead),
            )
        )
        assert submission is not None
        submission.received_at = datetime.now(UTC) - timedelta(days=3)
        await session.commit()

    run_db(postgresql_test_url, stale_provider_evidence)
    sourced = client.get(projection, headers=HEADERS).json()["sources"][0]
    assert sourced["provider"] == "phase5_test_provider"
    assert sourced["connection_status"] == "degraded"
    assert sourced["intake_recency"] == "stale"
    converted = client.post(canonical + f"/{lead}/convert", headers=HEADERS, json={})
    assert converted.status_code == 200, converted.text
    data = client.get(projection + f"/{lead}", headers=HEADERS).json()
    assert data["lead"]["outcome"] == "recorded_conversion"
    assert data["lead"]["converted_value_cents"] is None
    archived = client.post(
        canonical + f"/{lead}/status", headers=HEADERS, json={"to_status": "archived"}
    )
    assert archived.status_code == 200
    data = client.get(projection, headers=HEADERS).json()
    assert data["recorded_conversions"] == 1
    assert data["items"][0]["outcome"] == "recorded_conversion"
    assert not client.get(projection + f"/{lead}", headers=HEADERS).json()["capabilities"][
        "can_record_outcome"
    ]
    assert (
        client.get(projection + f"/{lead}?location_id={uuid4()}", headers=HEADERS).status_code
        == 404
    )
    assert client.get(projection + f"/{uuid4()}", headers=HEADERS).status_code == 404


def test_unavailable_without_source_and_scope_rejection(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    org = ids["organization"]
    projection = f"/api/v1/organizations/{org}/command-center/leads"

    async def remove_source(session: AsyncSession) -> None:
        await session.execute(delete(LeadSource).where(LeadSource.organization_id == org))
        await session.commit()

    run_db(postgresql_test_url, remove_source)
    response = client.get(projection, headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["inventory_count"] is None
    assert response.json()["recorded_conversions"] is None
    assert response.json()["quality"] == "unavailable"
    assert client.get(projection).status_code == 401
    assert client.get(projection + f"?location_id={uuid4()}", headers=HEADERS).status_code == 404
    assert client.get(projection + "?offset=-1", headers=HEADERS).status_code == 422
    foreign = client.get(
        f"/api/v1/organizations/{ids['other_organization']}/command-center/leads", headers=HEADERS
    )
    assert foreign.status_code == 403
