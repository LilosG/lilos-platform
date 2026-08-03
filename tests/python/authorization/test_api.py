"""Protected authorization-test route and non-disclosure tests."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.errors import TokenVerificationError
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.main import create_app
from apps.api.app.middleware import CORRELATION_ID_HEADER
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


class FakeVerifier:
    def __init__(self, claims: VerifiedProviderClaims) -> None:
        self.result: VerifiedProviderClaims | Exception = claims

    async def verify(self, token: str) -> VerifiedProviderClaims:
        del token
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def claims(subject: UUID, assurance: AssuranceLevel) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=subject,
        session_id=uuid4(),
        assurance_level=assurance,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        algorithm="ES256",
        key_id="authorization-test-key",
    )


@pytest.fixture
def authorized_client(
    postgresql_test_url: str,
    authorization_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, FakeVerifier, dict[str, UUID]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, UUID]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with authorization_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="api-catalog")
            organization = Organization(
                name="Authorization Organization",
                slug="authorization-organization",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            other_organization = Organization(
                name="Other Organization",
                slug="authorization-other",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            unassigned = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            session.add_all([organization, other_organization, profile, unassigned])
            await session.flush()
            location = Location(
                organization_id=organization.id,
                name="Authorized Location",
                slug="authorized-location",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=False,
                version=1,
            )
            other_location = Location(
                organization_id=other_organization.id,
                name="Other Location",
                slug="other-auth-location",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=False,
                version=1,
            )
            session.add_all([location, other_location])
            await session.flush()
            membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(
                    user_profile_id=profile.id, membership_type=MembershipType.SUPPORT
                ),
                correlation_id="api-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="api-owner",
            )
            identifiers = {
                "organization": organization.id,
                "location": location.id,
                "other_location": other_location.id,
                "unassigned_subject": unassigned.auth_user_id,
                "assigned_subject": profile.auth_user_id,
            }
            return claims(profile.auth_user_id, AssuranceLevel.AAL2), identifiers

    verified, identifiers = asyncio.run(populate())
    verifier = FakeVerifier(verified)
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "database_url": postgresql_test_url,
            "internal_admin_routes_enabled": True,
        }
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, verifier, identifiers


def path(ids: dict[str, UUID], suffix: str) -> str:
    return f"/internal/organizations/{ids['organization']}/authorization-test/{suffix}"


@pytest.mark.integration
def test_all_five_fixed_policies_and_aal_contract(
    authorized_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = authorized_client
    headers = {
        "Authorization": "Bearer fabricated.signed.token",
        CORRELATION_ID_HEADER: "authorization-route-check",
    }
    cases = [
        ("GET", path(ids, "organization-read")),
        ("GET", path(ids, f"location-read/{ids['location']}")),
        ("POST", path(ids, "organization-update")),
        ("POST", path(ids, f"location-update/{ids['location']}")),
        ("POST", path(ids, "aal2")),
    ]
    for method, target in cases:
        response = client.request(method, target, headers=headers)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers[CORRELATION_ID_HEADER] == "authorization-route-check"
        assert response.json()["data"] == {"authorized": True}
        assert "role" not in response.text and "deny" not in response.text

    verifier.result = claims(ids["assigned_subject"], AssuranceLevel.AAL1)
    aal2_denied = client.post(path(ids, "aal2"), headers=headers)
    assert aal2_denied.status_code == 403
    assert aal2_denied.json()["error"]["code"] == "AUTHORIZATION_DENIED"
    assert aal2_denied.headers["Cache-Control"] == "no-store"
    # A frontend-supplied assurance hint cannot change the fixed server policy.
    still_denied = client.post(path(ids, "aal2") + "?minimum_assurance_level=aal1", headers=headers)
    assert still_denied.status_code == 403


@pytest.mark.integration
def test_authentication_separation_generic_denial_and_cross_tenant_not_found(
    authorized_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = authorized_client
    target = path(ids, "organization-read")
    missing = client.get(target)
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    verifier.result = TokenVerificationError()
    invalid = client.get(target, headers={"Authorization": "Bearer secret-token-value"})
    assert invalid.status_code == 401 and "secret-token-value" not in invalid.text

    verifier.result = claims(ids["unassigned_subject"], AssuranceLevel.AAL2)
    no_membership = client.get(target, headers={"Authorization": "Bearer fabricated.token"})
    assert no_membership.status_code == 403
    assert no_membership.json()["error"]["code"] == "AUTHORIZATION_DENIED"
    assert "membership" not in no_membership.text.lower()

    verifier.result = claims(ids["assigned_subject"], AssuranceLevel.AAL2)
    cross_tenant = client.get(
        path(ids, f"location-read/{ids['other_location']}"),
        headers={"Authorization": "Bearer fabricated.token"},
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "LOCATION_NOT_FOUND"
    assert "organization" not in cross_tenant.text.lower()
    assert client.get("/internal/authorization-test/check").status_code == 404


def test_authorization_test_routes_are_guarded_by_environment() -> None:
    with TestClient(create_app(Settings(environment=EnvironmentName.TEST))) as client:
        assert (
            client.get(
                f"/internal/organizations/{uuid4()}/authorization-test/organization-read"
            ).status_code
            == 404
        )
    for environment in (
        EnvironmentName.DEVELOPMENT,
        EnvironmentName.STAGING,
        EnvironmentName.PRODUCTION,
    ):
        with pytest.raises(ValueError, match="local or test"):
            Settings(environment=environment, internal_admin_routes_enabled=True)
