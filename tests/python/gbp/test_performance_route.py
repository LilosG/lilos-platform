"""GET /command-center/gbp/performance: availability states, comparison, terms and isolation."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from authorization.fixtures import add_effective_product_entitlement
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.main import create_app
from apps.api.app.products.gbp.adapter import KeywordImpressionPoint
from apps.api.app.products.gbp.performance_enums import GBPPerformanceMetric
from gbp.test_performance_sync import FakeGoogle, run_sync, seed_client, service

HEADERS = {"Authorization": "Bearer fabricated.token"}
TODAY = datetime.now(UTC).date()


class FakeVerifier:
    def __init__(self, claims: VerifiedProviderClaims) -> None:
        self.claims = claims

    async def verify(self, token: str) -> VerifiedProviderClaims:
        del token
        return self.claims


def _claims(subject: UUID) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=subject,
        session_id=uuid4(),
        assurance_level=AssuranceLevel.AAL2,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        algorithm="ES256",
        key_id="gbp-performance-test-key",
    )


@pytest.fixture
def performance_client(
    postgresql_test_url: str, gbp_session_factory: async_sessionmaker[AsyncSession]
) -> Generator[tuple[TestClient, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        org, gbp_id, platform_id = await seed_client(gbp_session_factory, "Alpha")
        other_org, other_gbp_id, _ = await seed_client(gbp_session_factory, "Bravo")
        google = FakeGoogle()
        google.value_for = lambda metric, day: 3
        previous_month = (date(TODAY.year, TODAY.month, 1) - timedelta(days=1)).replace(day=1)
        google.keywords = {
            previous_month: [
                KeywordImpressionPoint("pizza", 40, None),
                KeywordImpressionPoint("rare", None, 15),
            ]
        }
        await run_sync(gbp_session_factory, service(google), org, gbp_id, now=datetime.now(UTC))
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with gbp_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="gbp-performance-catalog")
            profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            session.add(profile)
            await session.flush()
            await add_effective_product_entitlement(
                session, org, "gbp", correlation_id="gbp-performance-entitlement"
            )
            membership = await access.create_membership(
                session,
                org,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="gbp-performance-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                org,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="gbp-performance-owner",
            )
        ids = {
            "organization": org,
            "other_organization": other_org,
            "location": platform_id,
            "other_gbp": other_gbp_id,
        }
        return _claims(profile.auth_user_id), ids

    claims, ids = asyncio.run(populate())
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    with TestClient(
        create_app(settings, authentication_verifier=FakeVerifier(claims)),
        raise_server_exceptions=False,
    ) as client:
        yield client, ids


def _url(org: UUID) -> str:
    return f"/api/v1/organizations/{org}/command-center/gbp/performance"


@pytest.mark.integration
def test_performance_totals_comparison_availability_and_terms(
    performance_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = performance_client

    response = client.get(_url(ids["organization"]), headers=HEADERS)

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    body: dict[str, Any] = response.json()
    assert body["period"] == "28d" and body["location_id"] is None
    assert body["locations"] == [
        {"id": str(ids["location"]), "name": "Main", "mapped": True},
    ]
    assert body["current_range"]["days"] == body["previous_range"]["days"] == 28
    metrics = {item["metric"]: item for item in body["metrics"]}
    assert set(metrics) == {metric.value for metric in GBPPerformanceMetric}
    impressions = metrics["BUSINESS_IMPRESSIONS_MOBILE_SEARCH"]
    assert impressions["current"] == {
        "availability": "available",
        "value": 28 * 3,
        "days_covered": 28,
        "days_expected": 28,
    }
    assert impressions["previous"]["availability"] == "available"
    assert impressions["change"] == 0
    # The fake returns two of the eleven metrics; every other one is "no data", never 0.
    assert metrics["BUSINESS_BOOKINGS"]["current"]["value"] is None
    assert metrics["BUSINESS_BOOKINGS"]["current"]["availability"] == "no_data"
    # Profile views sums the four impression metrics; only one exists here, so it is partial.
    assert body["profile_views"]["current"]["availability"] == "partial"
    assert body["source"]["last_status"] == "succeeded"
    terms = body["search_terms"]
    assert terms["availability"] == "available"
    assert [
        (t["keyword"], t["value"], t["below_threshold"], t["is_exact"]) for t in terms["terms"]
    ] == [
        ("pizza", 40, None, True),
        ("rare", None, 15, False),
    ]


@pytest.mark.integration
def test_the_month_period_needs_a_month_and_a_location_filter_narrows(
    performance_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = performance_client
    org = ids["organization"]

    missing = client.get(_url(org), params={"period": "month"}, headers=HEADERS)
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "GBP_PERFORMANCE_MONTH_REQUIRED"
    bad = client.get(_url(org), params={"period": "month", "month": "2026-13"}, headers=HEADERS)
    assert bad.status_code == 422

    previous_month = (date(TODAY.year, TODAY.month, 1) - timedelta(days=1)).strftime("%Y-%m")
    month = client.get(
        _url(org),
        params={"period": "month", "month": previous_month, "location_id": str(ids["location"])},
        headers=HEADERS,
    )
    assert month.status_code == 200, month.text
    assert month.json()["month"] == f"{previous_month}-01"
    assert month.json()["search_terms"]["month"] == f"{previous_month}-01"
    assert month.json()["location_id"] == str(ids["location"])


@pytest.mark.integration
def test_another_tenants_locations_and_organizations_are_not_readable(
    performance_client: tuple[TestClient, dict[str, UUID]],
) -> None:
    client, ids = performance_client

    foreign_org = client.get(_url(ids["other_organization"]), headers=HEADERS)
    foreign_location = client.get(
        _url(ids["organization"]), params={"location_id": str(uuid4())}, headers=HEADERS
    )

    assert foreign_org.status_code in (403, 404)
    assert foreign_location.status_code == 404
    assert foreign_location.json()["error"]["code"] == "GBP_LOCATION_NOT_FOUND"
