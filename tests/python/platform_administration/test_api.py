"""Production-mounted platform-administration route authorization and flow tests."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
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
            await AdministrationCatalogSeeder().seed(
                session, correlation_id="platform-admin-admin-catalog"
            )

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
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/provision-website",
            None,
        ),
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/start-offboarding",
            {"expected_version": 1},
        ),
        (
            "POST",
            f"/api/v1/platform/organizations/{organization_id}/archive",
            {"expected_version": 1},
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

    product_catalog = client.get("/api/v1/platform/products", headers=HEADERS)
    assert product_catalog.status_code == 200, product_catalog.text
    product_rows = product_catalog.json()["data"]
    assert product_rows
    assert {"id", "key", "name"}.issubset(product_rows[0])

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

    location_profile_created = client.post(
        f"/api/v1/platform/organizations/{organization_id}/locations/{location['id']}/profile",
        headers=HEADERS,
        json={"local_description": "Primary client location"},
    )
    assert location_profile_created.status_code == 201, location_profile_created.text
    location_profile = location_profile_created.json()["data"]
    assert location_profile["location_id"] == location["id"]
    assert location_profile["version"] == 1

    location_profile_read = client.get(
        f"/api/v1/platform/organizations/{organization_id}/locations/{location['id']}/profile",
        headers=HEADERS,
    )
    assert location_profile_read.status_code == 200, location_profile_read.text
    assert location_profile_read.json()["data"]["local_description"] == ("Primary client location")

    location_profile_updated = client.put(
        f"/api/v1/platform/organizations/{organization_id}/locations/{location['id']}/profile",
        headers=HEADERS,
        json={
            "local_description": "Confirmed primary client location",
            "expected_version": 1,
        },
    )
    assert location_profile_updated.status_code == 200, location_profile_updated.text
    assert location_profile_updated.json()["data"]["version"] == 2

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


@pytest.mark.integration
def test_platform_admin_creates_and_lists_product_entitlement(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    """A platform administrator can enable a product via the API, not a manual script."""
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"], assurance=AssuranceLevel.AAL2)

    org = _create_organization(client, slug="entitlement-test-org")
    organization_id = org["id"]

    # Create a GBP entitlement through the application API.
    create_response = client.post(
        f"/api/v1/platform/organizations/{organization_id}/product-entitlements",
        headers=HEADERS,
        json={
            "product_key": "gbp",
            "source": "platform_admin_onboarding",
            "reason": "Enable GBP during client onboarding",
        },
    )
    assert create_response.status_code == 201, create_response.text
    entitlement = dict(create_response.json()["data"])
    assert entitlement["status"] == "setup_required"
    assert entitlement["source"] == "platform_admin_onboarding"

    # Listing shows the created entitlement.
    list_response = client.get(
        f"/api/v1/platform/organizations/{organization_id}/product-entitlements",
        headers=HEADERS,
    )
    assert list_response.status_code == 200, list_response.text
    items = list(list_response.json()["data"])
    assert len(items) == 1
    assert items[0]["id"] == entitlement["id"]

    # Creating the same entitlement again returns a conflict, not a duplicate.
    duplicate_response = client.post(
        f"/api/v1/platform/organizations/{organization_id}/product-entitlements",
        headers=HEADERS,
        json={
            "product_key": "gbp",
            "source": "platform_admin_onboarding",
            "reason": "Duplicate attempt",
        },
    )
    assert duplicate_response.status_code == 409, duplicate_response.text
    assert duplicate_response.json()["error"]["code"] == "ENTITLEMENT_CONFLICT"


@pytest.mark.integration
def test_non_admin_cannot_create_product_entitlement(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["non_admin_subject"], assurance=AssuranceLevel.AAL2)
    organization_id = uuid4()

    response = client.post(
        f"/api/v1/platform/organizations/{organization_id}/product-entitlements",
        headers=HEADERS,
        json={
            "product_key": "gbp",
            "source": "test",
            "reason": "Should be denied",
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "AUTHORIZATION_DENIED"


@pytest.mark.integration
def test_platform_administrator_provisions_the_website_for_an_existing_client(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    """The manual path for clients activated before activation provisioned websites.

    Those clients hold a configured primary domain and no SEO website, so the
    crawler and every CTA destination have nothing to use, and no action in the
    product created one.
    """
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"])

    organization = _create_organization(client, slug=f"provision-{uuid4().hex[:10]}")
    organization_id = organization["id"]

    domain_response = client.post(
        f"/api/v1/platform/organizations/{organization_id}/domains",
        headers=HEADERS,
        json={"domain": "provision-target.test", "is_primary": True},
    )
    assert domain_response.status_code == 201, domain_response.text

    first = client.post(
        f"/api/v1/platform/organizations/{organization_id}/provision-website",
        headers=HEADERS,
    )
    assert first.status_code == 200, first.text
    created = first.json()["data"]
    assert created["website_created"] is True
    assert created["crawl_enqueued"] is True
    assert created["canonical_origin"] == "https://provision-target.test"
    assert created["website_id"] is not None
    assert created["crawl_run_id"] is not None

    # Pressing it twice must not cost the client a second website or crawl.
    second = client.post(
        f"/api/v1/platform/organizations/{organization_id}/provision-website",
        headers=HEADERS,
    )
    assert second.status_code == 200, second.text
    repeated = second.json()["data"]
    assert repeated["website_id"] == created["website_id"]
    assert repeated["website_created"] is False
    assert repeated["crawl_enqueued"] is False
    assert repeated["skipped_reason"] == "CRAWL_ALREADY_STARTED"


@pytest.mark.integration
def test_provisioning_without_a_primary_domain_says_so_instead_of_guessing(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"])

    organization = _create_organization(client, slug=f"nodomain-{uuid4().hex[:10]}")
    response = client.post(
        f"/api/v1/platform/organizations/{organization['id']}/provision-website",
        headers=HEADERS,
    )
    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "NO_PRIMARY_DOMAIN"
    # The message has to name the fix, not just the refusal.
    assert "mark it primary" in error["message"]


@pytest.mark.integration
def test_a_second_client_with_the_same_name_is_refused_and_names_the_escape_hatch(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    """Only the slug was unique, so "Cococabana" and "cococabana" both saved.

    The result was a permanent duplicate in every switcher and client list,
    with nothing to indicate which one held the real work.
    """
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"])

    first = client.post(
        "/api/v1/platform/organizations",
        headers=HEADERS,
        json={
            "name": "cococabana",
            "slug": f"cococabana-{uuid4().hex[:8]}",
            "organization_type": "test",
            "timezone": "UTC",
            "default_currency": "USD",
        },
    )
    assert first.status_code == 201, first.text

    # Different capitalisation, different slug: previously accepted in full.
    duplicate = client.post(
        "/api/v1/platform/organizations",
        headers=HEADERS,
        json={
            "name": "Cococabana",
            "slug": f"cococabana-{uuid4().hex[:8]}",
            "organization_type": "test",
            "timezone": "UTC",
            "default_currency": "USD",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    error = duplicate.json()["error"]
    assert error["code"] == "ORGANIZATION_NAME_CONFLICT"
    assert "allow_duplicate_name" in error["message"]


@pytest.mark.integration
def test_two_genuinely_same_named_clients_remain_possible_on_purpose(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    """The guard must not make a real business situation impossible."""
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"])
    name = f"Twin Client {uuid4().hex[:6]}"

    for index in range(2):
        body: dict[str, object] = {
            "name": name,
            "slug": f"twin-{uuid4().hex[:10]}",
            "organization_type": "test",
            "timezone": "UTC",
            "default_currency": "USD",
        }
        if index == 1:
            body["allow_duplicate_name"] = True
        response = client.post("/api/v1/platform/organizations", headers=HEADERS, json=body)
        assert response.status_code == 201, response.text


@pytest.mark.integration
def test_a_client_created_by_mistake_can_be_retired(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    """Retirement existed in the lifecycle engine and was never exposed.

    Prospect leads to offboarding and offboarding leads to archived, but
    neither route was mounted, so a client created by mistake was permanent.
    """
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"])

    organization = _create_organization(client, slug=f"retire-{uuid4().hex[:10]}")
    organization_id = organization["id"]
    assert organization["status"] == "prospect"

    offboarding = client.post(
        f"/api/v1/platform/organizations/{organization_id}/start-offboarding",
        headers=HEADERS,
        json={"expected_version": organization["version"]},
    )
    assert offboarding.status_code == 200, offboarding.text
    assert offboarding.json()["data"]["status"] == "offboarding"

    archived = client.post(
        f"/api/v1/platform/organizations/{organization_id}/archive",
        headers=HEADERS,
        json={"expected_version": offboarding.json()["data"]["version"]},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["data"]["status"] == "archived"


@pytest.mark.integration
def test_archiving_is_refused_without_offboarding_first(
    platform_administration_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    """Two steps, on purpose: archived is terminal in the transition map."""
    client, verifier, ids = platform_administration_client
    verifier.result = claims(ids["admin_subject"])

    organization = _create_organization(client, slug=f"direct-{uuid4().hex[:10]}")
    response = client.post(
        f"/api/v1/platform/organizations/{organization['id']}/archive",
        headers=HEADERS,
        json={"expected_version": organization["version"]},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "ORGANIZATION_TRANSITION_CONFLICT"
