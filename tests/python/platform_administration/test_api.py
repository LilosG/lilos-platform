"""Production-mounted platform-administration route authorization and flow tests."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.models import Industry
from apps.api.app.main import create_app
from apps.api.app.platform_admin.models import PlatformAdministrator


class FakeVerifier:
    def __init__(self, claims: VerifiedProviderClaims) -> None:
        self.result: VerifiedProviderClaims | Exception = claims

    async def verify(self, token: str) -> VerifiedProviderClaims:
        del token
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def claims(
    subject: UUID, assurance: AssuranceLevel = AssuranceLevel.AAL2
) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=subject,
        session_id=uuid4(),
        assurance_level=assurance,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        algorithm="ES256",
        key_id="platform-admin-test-key",
    )


HEADERS = {"Authorization": "Bearer fabricated.token"}


@pytest.fixture
def platform_administration_client(
    postgresql_test_url: str,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, FakeVerifier, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        seeder = AccessCatalogSeeder()
        async with platform_administration_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="platform-admin-catalog")

            admin_profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            revoked_admin_profile = UserProfile(
                auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1
            )
            non_admin_profile = UserProfile(
                auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1
            )
            session.add_all([admin_profile, revoked_admin_profile, non_admin_profile])
            await session.flush()

            active_grant = PlatformAdministrator(user_profile_id=admin_profile.id)
            revoked_grant = PlatformAdministrator(
                user_profile_id=revoked_admin_profile.id,
                revoked_at=datetime.now(UTC),
            )
            session.add_all([active_grant, revoked_grant])

            active_industry = Industry(
                key="general_local_business",
                name="General Local Business",
                status=IndustryStatus.ACTIVE,
                version=1,
            )
            deprecated_industry = Industry(
                key="legacy_industry",
                name="Legacy Industry",
                status=IndustryStatus.DEPRECATED,
                version=1,
            )
            session.add_all([active_industry, deprecated_industry])
            await session.flush()

            identifiers = {
                "admin_subject": admin_profile.auth_user_id,
                "revoked_admin_subject": revoked_admin_profile.auth_user_id,
                "non_admin_subject": non_admin_profile.auth_user_id,
                "non_admin_profile": non_admin_profile.id,
                "active_industry": active_industry.id,
                "deprecated_industry": deprecated_industry.id,
            }
            return claims(admin_profile.auth_user_id), identifiers

    verified, identifiers = asyncio.run(populate())
    verifier = FakeVerifier(verified)
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, verifier, identifiers


def _create_organization(client: TestClient, *, slug: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/platform/organizations",
        headers=HEADERS,
        json={
            "name": "Platform Admin Test Org",
            "slug": slug,
            "organization_type": "test",
            "timezone": "UTC",
            "default_currency": "USD",
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json()["data"])


@pytest.mark.integration
def test_non_platform_administrator_gets_403_on_every_mutating_route(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["non_admin_subject"])
    organization_id = uuid4()
    location_id = uuid4()

    valid_organization_body = {
        "name": "Denied Org",
        "slug": "denied-org",
        "organization_type": "test",
        "timezone": "UTC",
        "default_currency": "USD",
    }
    valid_location_body = {
        "name": "Denied Location",
        "slug": "denied-location",
        "location_type": "physical",
        "timezone": "UTC",
        "address_line_1": "1 Example Way",
        "city": "Example",
        "region": "CA",
        "postal_code": "00000",
        "country_code": "US",
    }
    requests = [
        ("POST", "/api/v1/platform/organizations", valid_organization_body),
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/start-onboarding",
            {"expected_version": 1},
        ),
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/activate",
            {"expected_version": 1},
        ),
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/pause",
            {"expected_version": 1},
        ),
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/resume",
            {"expected_version": 1},
        ),
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/locations",
            valid_location_body,
        ),
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/locations/{location_id}/activate",
            {"expected_version": 1},
        ),
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/owner",
            {"auth_user_id": str(uuid4())},
        ),
    ]
    for method, path, body in requests:
        response = client.request(method, path, headers=HEADERS, json=body)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["error"]["code"] == "AUTHORIZATION_DENIED"
        assert response.headers["cache-control"] == "no-store"

    # Read routes are also gated by the router-level dependency.
    read_response = client.get("/api/v1/platform/organizations", headers=HEADERS)
    assert read_response.status_code == 403
    industries_response = client.get("/api/v1/platform/industries", headers=HEADERS)
    assert industries_response.status_code == 403


@pytest.mark.integration
def test_revoked_platform_administrator_gets_403(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["revoked_admin_subject"])
    response = client.post(
        "/api/v1/platform/organizations",
        headers=HEADERS,
        json={
            "name": "Should Not Exist",
            "slug": "should-not-exist",
            "organization_type": "test",
            "timezone": "UTC",
            "default_currency": "USD",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTHORIZATION_DENIED"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.integration
def test_platform_administrator_creates_organization_and_location_and_bootstraps_owner(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"])

    organization = _create_organization(client, slug="platform-admin-flow-org")
    organization_id = organization["id"]
    assert organization["status"] == "prospect"

    onboarding = client.post(
        f"/api/v1/platform/organizations/{organization_id}/start-onboarding",
        headers=HEADERS,
        json={"expected_version": 1},
    )
    assert onboarding.status_code == 200, onboarding.text
    assert onboarding.json()["data"]["status"] == "onboarding"

    activated = client.post(
        f"/api/v1/platform/organizations/{organization_id}/activate",
        headers=HEADERS,
        json={"expected_version": 2},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["data"]["status"] == "active"

    get_org = client.get(f"/api/v1/platform/organizations/{organization_id}", headers=HEADERS)
    assert get_org.status_code == 200
    assert get_org.json()["data"]["id"] == organization_id

    list_orgs = client.get("/api/v1/platform/organizations", headers=HEADERS)
    assert list_orgs.status_code == 200
    assert any(item["id"] == organization_id for item in list_orgs.json()["data"]["items"])

    location_response = client.post(
        f"/api/v1/platform/organizations/{organization_id}/locations",
        headers=HEADERS,
        json={
            "name": "Main Site",
            "slug": "main-site",
            "location_type": "physical",
            "timezone": "UTC",
            "address_line_1": "1 Example Way",
            "city": "Example",
            "region": "CA",
            "postal_code": "00000",
            "country_code": "US",
        },
    )
    assert location_response.status_code == 201, location_response.text
    location = location_response.json()["data"]
    assert location["status"] == "setup_required"

    list_locations = client.get(
        f"/api/v1/platform/organizations/{organization_id}/locations", headers=HEADERS
    )
    assert list_locations.status_code == 200
    assert any(item["id"] == location["id"] for item in list_locations.json()["data"]["items"])

    location_activated = client.post(
        f"/api/v1/platform/organizations/{organization_id}/locations/{location['id']}/activate",
        headers=HEADERS,
        json={"expected_version": 1},
    )
    assert location_activated.status_code == 200, location_activated.text
    assert location_activated.json()["data"]["status"] == "active"

    owner_auth_user_id = str(uuid4())
    first_bootstrap = client.post(
        f"/api/v1/platform/organizations/{organization_id}/owner",
        headers=HEADERS,
        json={"auth_user_id": owner_auth_user_id, "email": "owner@example.invalid"},
    )
    assert first_bootstrap.status_code == 200, first_bootstrap.text
    first_data = first_bootstrap.json()["data"]
    assert first_data["user_profile_created"] is True
    assert first_data["membership_created"] is True
    assert first_data["owner_role_assignment_created"] is True

    second_bootstrap = client.post(
        f"/api/v1/platform/organizations/{organization_id}/owner",
        headers=HEADERS,
        json={"auth_user_id": owner_auth_user_id, "email": "owner@example.invalid"},
    )
    assert second_bootstrap.status_code == 200, second_bootstrap.text
    second_data = second_bootstrap.json()["data"]
    assert second_data["user_profile_created"] is False
    assert second_data["membership_created"] is False
    assert second_data["owner_role_assignment_created"] is False
    assert second_data["user_profile_id"] == first_data["user_profile_id"]
    assert second_data["membership_id"] == first_data["membership_id"]


@pytest.mark.integration
def test_platform_administrator_lists_only_active_industries(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"])

    response = client.get("/api/v1/platform/industries", headers=HEADERS)
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    keys = {item["key"] for item in items}
    assert "general_local_business" in keys
    assert "legacy_industry" not in keys
