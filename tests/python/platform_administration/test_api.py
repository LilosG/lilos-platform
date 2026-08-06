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


def _create_organization(
    client: TestClient, *, slug: str, industry_id: UUID | None = None
) -> dict[str, object]:
    body = {
        "name": "Platform Admin Test Org",
        "slug": slug,
        "organization_type": "test",
        "timezone": "UTC",
        "default_currency": "USD",
    }
    if industry_id is not None:
        body["industry_id"] = str(industry_id)
    response = client.post("/api/v1/platform/organizations", headers=HEADERS, json=body)
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

    organization = _create_organization(
        client, slug="platform-admin-flow-org", industry_id=ids["active_industry"]
    )
    organization_id = organization["id"]
    assert organization["status"] == "prospect"

    onboarding = client.post(
        f"/api/v1/platform/organizations/{organization_id}/start-onboarding",
        headers=HEADERS,
        json={"expected_version": 1},
    )
    assert onboarding.status_code == 200, onboarding.text
    assert onboarding.json()["data"]["status"] == "onboarding"

    # Activation must fail closed while onboarding is incomplete: no profile,
    # no location, no domain, no industry, and no active member yet.
    premature_activation = client.post(
        f"/api/v1/platform/organizations/{organization_id}/activate",
        headers=HEADERS,
        json={"expected_version": 2},
    )
    assert premature_activation.status_code == 409, premature_activation.text
    premature_body = premature_activation.json()
    assert premature_body["error"]["code"] == "ONBOARDING_INCOMPLETE"
    assert premature_body["error"]["details"], premature_body

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
            "is_primary": True,
        },
    )
    assert location_response.status_code == 201, location_response.text
    location = location_response.json()["data"]
    assert location["status"] == "setup_required"
    assert location["is_primary"] is True

    list_locations = client.get(
        f"/api/v1/platform/organizations/{organization_id}/locations", headers=HEADERS
    )
    assert list_locations.status_code == 200
    assert any(item["id"] == location["id"] for item in list_locations.json()["data"]["items"])

    # A location may remain "setup_required" while the organization is still
    # onboarding — activating a location requires an already-active parent
    # organization, so that transition happens after organization activation
    # below, not here.

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

    # Organization profile and domain setup happen through the platform-admin
    # routes too: the standard RBAC-protected `/api/v1/organizations/...`
    # equivalents require an already-ACTIVE organization (by design — see
    # `AuthorizationService._evaluate`'s `ORGANIZATION_NOT_EFFECTIVE` gate),
    # so they are unreachable before activation. This mirrors the existing
    # dual-entry-point pattern already used for locations.
    profile_created = client.post(
        f"/api/v1/platform/organizations/{organization_id}/profile",
        headers=HEADERS,
        json={},
    )
    assert profile_created.status_code == 201, profile_created.text

    domain_created = client.post(
        f"/api/v1/platform/organizations/{organization_id}/domains",
        headers=HEADERS,
        json={"domain": "example-client.com", "is_primary": True},
    )
    assert domain_created.status_code == 201, domain_created.text

    activated = client.post(
        f"/api/v1/platform/organizations/{organization_id}/activate",
        headers=HEADERS,
        json={"expected_version": 2},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["data"]["status"] == "active"

    location_activated = client.post(
        f"/api/v1/platform/organizations/{organization_id}/locations/{location['id']}/activate",
        headers=HEADERS,
        json={"expected_version": 1},
    )
    assert location_activated.status_code == 200, location_activated.text
    assert location_activated.json()["data"]["status"] == "active"


@pytest.mark.integration
def test_platform_administrator_assigns_industry_before_activation(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"])

    organization = _create_organization(client, slug="platform-admin-industry-org")
    organization_id = organization["id"]
    assert organization["industry_id"] is None

    assigned = client.post(
        f"/api/v1/platform/organizations/{organization_id}/industry",
        headers=HEADERS,
        json={"industry_id": str(ids["active_industry"]), "expected_version": 1},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["data"]["industry_id"] == str(ids["active_industry"])

    get_org = client.get(f"/api/v1/platform/organizations/{organization_id}", headers=HEADERS)
    assert get_org.json()["data"]["industry_id"] == str(ids["active_industry"])


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


@pytest.mark.integration
def test_platform_administrator_aal1_session_denied_gated_route(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    """A real active grant is not enough at AAL1 -- the exact bug being fixed."""
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"], assurance=AssuranceLevel.AAL1)

    response = client.get("/api/v1/platform/organizations", headers=HEADERS)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "AUTHORIZATION_DENIED"


@pytest.mark.integration
def test_platform_administrator_aal2_session_allowed_gated_route(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"], assurance=AssuranceLevel.AAL2)

    response = client.get("/api/v1/platform/organizations", headers=HEADERS)
    assert response.status_code == 200, response.text


@pytest.mark.integration
def test_self_status_distinguishes_not_admin_needs_step_up_and_active(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client

    # Signed in, holds a grant, but session is only AAL1: needs step-up.
    verifier.result = claims(ids["admin_subject"], assurance=AssuranceLevel.AAL1)
    needs_step_up = client.get("/api/v1/me/platform-administrator", headers=HEADERS)
    assert needs_step_up.status_code == 200, needs_step_up.text
    data = needs_step_up.json()["data"]
    assert set(data.keys()) == {
        "is_platform_administrator",
        "meets_required_assurance",
        "required_assurance_level",
    }
    assert data == {
        "is_platform_administrator": True,
        "meets_required_assurance": False,
        "required_assurance_level": "aal2",
    }

    # Same account, now AAL2: fully authorized.
    verifier.result = claims(ids["admin_subject"], assurance=AssuranceLevel.AAL2)
    active = client.get("/api/v1/me/platform-administrator", headers=HEADERS)
    assert active.status_code == 200, active.text
    assert active.json()["data"] == {
        "is_platform_administrator": True,
        "meets_required_assurance": True,
        "required_assurance_level": "aal2",
    }

    # Signed in, no grant at all, even at AAL2: not a platform administrator.
    verifier.result = claims(ids["non_admin_subject"], assurance=AssuranceLevel.AAL2)
    not_admin = client.get("/api/v1/me/platform-administrator", headers=HEADERS)
    assert not_admin.status_code == 200, not_admin.text
    assert not_admin.json()["data"] == {
        "is_platform_administrator": False,
        "meets_required_assurance": True,
        "required_assurance_level": "aal2",
    }

    # A revoked grant reads identically to never having had one.
    verifier.result = claims(ids["revoked_admin_subject"], assurance=AssuranceLevel.AAL2)
    revoked = client.get("/api/v1/me/platform-administrator", headers=HEADERS)
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["is_platform_administrator"] is False


@pytest.mark.integration
def test_self_status_response_carries_no_secret_or_token(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"], assurance=AssuranceLevel.AAL1)

    response = client.get("/api/v1/me/platform-administrator", headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.text.lower()
    for forbidden in ("token", "secret", "totp", "authorization", "bearer"):
        assert forbidden not in body

    assert response.headers["cache-control"] == "no-store"


@pytest.mark.integration
def test_self_status_requires_authentication(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, _verifier, _ids = platform_administration_client

    response = client.get("/api/v1/me/platform-administrator")
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
