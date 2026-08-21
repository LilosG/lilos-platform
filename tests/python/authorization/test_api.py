"""Production-capable authorized route and non-disclosure tests."""

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
            invitee = UserProfile(
                auth_user_id=uuid4(),
                email="invited-user@example.invalid",
                status=UserStatus.ACTIVE,
                version=1,
            )
            session.add_all([organization, other_organization, profile, unassigned, invitee])
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
            assignment = await access.add_assignment(
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
                "membership": membership.id,
                "owner_role": owner.id,
                "owner_assignment": assignment.id,
                "invitee": invitee.id,
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


def organization_path(ids: dict[str, UUID], suffix: str = "") -> str:
    return f"/api/v1/organizations/{ids['organization']}{suffix}"


@pytest.mark.integration
def test_real_routes_apply_fixed_permissions_aal_and_no_store(
    authorized_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = authorized_client
    headers = {
        "Authorization": "Bearer fabricated.signed.token",
        CORRELATION_ID_HEADER: "authorization-route-check",
    }
    for target in (
        organization_path(ids),
        organization_path(ids, f"/locations/{ids['location']}"),
        organization_path(ids, "/business-identity"),
    ):
        response = client.get(target, headers=headers)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers[CORRELATION_ID_HEADER] == "authorization-route-check"

    verifier.result = claims(ids["assigned_subject"], AssuranceLevel.AAL1)
    privilege_path = organization_path(ids, f"/memberships/{ids['membership']}/role-assignments")
    denied = client.post(
        privilege_path,
        headers=headers,
        json={"role_id": str(ids["owner_role"]), "scope_type": "organization"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "AUTHORIZATION_DENIED"
    assert denied.headers["Cache-Control"] == "no-store"
    assert (
        client.post(
            privilege_path + "?minimum_assurance_level=aal1",
            headers=headers,
            json={"role_id": str(ids["owner_role"]), "scope_type": "organization"},
        ).status_code
        == 403
    )

    verifier.result = claims(ids["assigned_subject"], AssuranceLevel.AAL2)
    duplicate = client.post(
        privilege_path,
        headers=headers,
        json={"role_id": str(ids["owner_role"]), "scope_type": "organization"},
    )
    assert duplicate.status_code == 409

    final_owner = client.delete(
        organization_path(
            ids,
            f"/memberships/{ids['membership']}/role-assignments/{ids['owner_assignment']}",
        ),
        headers=headers,
    )
    assert final_owner.status_code == 409
    assert final_owner.json()["error"]["code"] == "LAST_ACTIVE_OWNER_CONFLICT"

    final_owner_membership = client.post(
        organization_path(ids, f"/memberships/{ids['membership']}/suspend"),
        headers=headers,
        json={"expected_version": 1},
    )
    assert final_owner_membership.status_code == 409
    assert final_owner_membership.json()["error"]["code"] == "LAST_ACTIVE_OWNER_CONFLICT"


@pytest.mark.integration
def test_guarded_invitation_issuance_requires_fixed_aal2_and_never_trusts_actor_input(
    authorized_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = authorized_client
    target = f"/internal/organizations/{ids['organization']}/invitations"
    payload = {
        "user_profile_id": str(ids["invitee"]),
        "email": "invited-user@example.invalid",
        "membership_type": "client",
    }
    headers = {"Authorization": "Bearer fabricated.token"}
    verifier.result = claims(ids["assigned_subject"], AssuranceLevel.AAL1)
    denied = client.post(target, headers=headers, json=payload)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "AUTHORIZATION_DENIED"

    verifier.result = claims(ids["assigned_subject"], AssuranceLevel.AAL2)
    issued = client.post(target, headers=headers, json=payload)
    assert issued.status_code == 201
    assert issued.headers["Cache-Control"] == "no-store"
    assert issued.headers["Pragma"] == "no-cache"
    assert len(issued.json()["data"]["invitation_token"]) >= 43
    assert "invited_by_user_profile_id" not in payload


@pytest.mark.integration
def test_authentication_separation_generic_denial_and_cross_tenant_not_found(
    authorized_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = authorized_client
    target = organization_path(ids)
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
        organization_path(ids, f"/locations/{ids['other_location']}"),
        headers={"Authorization": "Bearer fabricated.token"},
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "LOCATION_NOT_FOUND"
    assert "organization" not in cross_tenant.text.lower()


def test_proof_routes_are_removed_and_production_routes_are_always_mounted() -> None:
    verifier = FakeVerifier(claims(uuid4(), AssuranceLevel.AAL1))
    verifier.result = TokenVerificationError()
    with TestClient(
        create_app(Settings(environment=EnvironmentName.TEST), authentication_verifier=verifier)
    ) as client:
        assert client.get(f"/api/v1/organizations/{uuid4()}").status_code == 401
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


UNAUTHENTICATED_PRODUCTION_ROUTES = frozenset(
    {
        # The Google OAuth redirect carries no bearer token -- it is a full
        # browser navigation Google issues directly, not an API call this
        # platform's own frontend makes. Tenant identity is recovered entirely
        # from the already-validated, hashed, one-time `state` parameter; see
        # `test_google_oauth_callback_is_deliberately_unauthenticated_but_fails_closed`.
        ("get", "/api/v1/integrations/google/callback"),
        ("get", "/api/v1/integrations/github/callback"),
    }
)


MACHINE_AUTH_PRODUCTION_ROUTES = frozenset(
    {
        # Lead machine intake authenticates with source-scoped ingestion
        # credentials instead of the platform bearer-token verifier.
        ("post", "/api/v1/leads/intake"),
    }
)


def test_every_production_route_authenticates_before_request_processing() -> None:
    verifier = FakeVerifier(claims(uuid4(), AssuranceLevel.AAL1))
    verifier.result = TokenVerificationError()
    app = create_app(Settings(environment=EnvironmentName.TEST), authentication_verifier=verifier)
    routes = {
        path: operations
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/v1")
    }
    assert routes
    with TestClient(app) as client:
        for route_path, operations in routes.items():
            target = route_path
            for parameter in (
                "organization_id",
                "location_id",
                "group_id",
                "membership_id",
                "invitation_id",
                "assignment_id",
                "deny_id",
            ):
                target = target.replace("{" + parameter + "}", str(uuid4()))
            for method in operations:
                if (method, route_path) in UNAUTHENTICATED_PRODUCTION_ROUTES or (
                    method,
                    route_path,
                ) in MACHINE_AUTH_PRODUCTION_ROUTES:
                    continue
                response = client.request(method, target, json={})
                assert response.status_code == 401, (method, route_path, response.text)
                assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
                assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.integration
def test_google_oauth_callback_is_deliberately_unauthenticated_but_fails_closed(
    postgresql_test_url: str,
) -> None:
    """The callback is reachable without auth, but an invalid `state` is still rejected."""
    app = create_app(
        Settings.model_validate(
            {
                "environment": EnvironmentName.TEST,
                "database_url": postgresql_test_url,
                "web_origins": "https://app.example.invalid",
            }
        )
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/v1/integrations/google/callback",
            params={"state": "not-a-real-state"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "connected=0" in response.headers["location"]
        assert "reason=invalid_state" in response.headers["location"]
