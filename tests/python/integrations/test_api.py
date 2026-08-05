"""Production-mounted Google OAuth connection route tests. No real Google calls."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.models import ProductEntitlement
from apps.api.app.administration.repository import AdministrationCatalogRepository
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.main import create_app
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
        key_id="integrations-test-key",
    )


HEADERS = {"Authorization": "Bearer fabricated.token"}


@pytest.fixture
def integrations_client(
    postgresql_test_url: str,
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, FakeVerifier, dict[str, object]], None, None]:
    async def populate() -> tuple[VerifiedProviderClaims, dict[str, object]]:
        access, seeder = AccessControlService(), AccessCatalogSeeder()
        async with integrations_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="integrations-api-catalog")
            await AdministrationCatalogSeeder().seed(
                session, correlation_id="integrations-api-admin"
            )
            await ProviderCatalogSeeder().run(session)

            organization = Organization(
                name="Integrations Test Org",
                slug="integrations-test-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            no_entitlement_organization = Organization(
                name="Integrations No Entitlement Org",
                slug="integrations-no-entitlement-org",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            non_member_profile = UserProfile(
                auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1
            )
            session.add_all(
                [organization, no_entitlement_organization, profile, non_member_profile]
            )
            await session.flush()

            membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="integrations-api-member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="integrations-api-owner",
            )
            no_entitlement_membership = await access.create_membership(
                session,
                no_entitlement_organization.id,
                MembershipCreate(
                    user_profile_id=non_member_profile.id, membership_type=MembershipType.CLIENT
                ),
                correlation_id="integrations-api-member-2",
            )
            await access.add_assignment(
                session,
                no_entitlement_organization.id,
                no_entitlement_membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="integrations-api-owner-2",
            )

            product = await AdministrationCatalogRepository().get_product_by_key(session, "gbp")
            assert product is not None
            session.add(
                ProductEntitlement(
                    organization_id=organization.id,
                    product_id=product.id,
                    status="active",
                    source="test",
                    reason="integrations test fixture",
                    version=1,
                )
            )
            await session.flush()

            identifiers: dict[str, object] = {
                "member_subject": profile.auth_user_id,
                "non_member_subject": non_member_profile.auth_user_id,
                "organization_id": organization.id,
                "no_entitlement_organization_id": no_entitlement_organization.id,
            }
            return claims(profile.auth_user_id), identifiers

    verified, identifiers = asyncio.run(populate())
    verifier = FakeVerifier(verified)
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "database_url": postgresql_test_url,
            "google_oauth_client_id": "test-client-id",
            "google_oauth_client_secret": "test-client-secret",
            "google_oauth_redirect_uri": "https://api.example.invalid/api/v1/integrations/google/callback",
            "secret_encryption_key": Fernet.generate_key().decode("utf-8"),
            "web_origins": "https://app.example.invalid",
        }
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, verifier, identifiers


@pytest.mark.integration
def test_non_member_cannot_connect_or_read_status(
    integrations_client: tuple[TestClient, FakeVerifier, dict[str, object]],
) -> None:
    client, verifier, ids = integrations_client
    verifier.result = claims(ids["non_member_subject"])  # type: ignore[arg-type]
    organization_id = ids["organization_id"]

    connect = client.post(
        f"/api/v1/organizations/{organization_id}/integrations/google/connect", headers=HEADERS
    )
    assert connect.status_code == 403
    assert connect.json()["error"]["code"] == "AUTHORIZATION_DENIED"
    assert connect.headers["cache-control"] == "no-store"

    status_response = client.get(
        f"/api/v1/organizations/{organization_id}/integrations/google/status", headers=HEADERS
    )
    assert status_response.status_code == 403


@pytest.mark.integration
def test_connect_without_effective_entitlement_is_blocked(
    integrations_client: tuple[TestClient, FakeVerifier, dict[str, object]],
) -> None:
    client, verifier, ids = integrations_client
    verifier.result = claims(ids["non_member_subject"])  # type: ignore[arg-type]
    organization_id = ids["no_entitlement_organization_id"]

    response = client.post(
        f"/api/v1/organizations/{organization_id}/integrations/google/connect", headers=HEADERS
    )
    assert response.status_code == 409, response.text


@pytest.mark.integration
def test_connect_status_disconnect_full_flow(
    integrations_client: tuple[TestClient, FakeVerifier, dict[str, object]],
) -> None:
    client, verifier, ids = integrations_client
    verifier.result = claims(ids["member_subject"])  # type: ignore[arg-type]
    organization_id = ids["organization_id"]

    initial_status = client.get(
        f"/api/v1/organizations/{organization_id}/integrations/google/status", headers=HEADERS
    )
    assert initial_status.status_code == 200
    assert initial_status.json()["data"] is None

    connect = client.post(
        f"/api/v1/organizations/{organization_id}/integrations/google/connect", headers=HEADERS
    )
    assert connect.status_code == 200, connect.text
    authorization_url = connect.json()["data"]["authorization_url"]
    assert authorization_url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert connect.headers["cache-control"] == "no-store"

    pending_status = client.get(
        f"/api/v1/organizations/{organization_id}/integrations/google/status", headers=HEADERS
    )
    assert pending_status.status_code == 200
    assert pending_status.json()["data"]["status"] == "pending"

    disconnect = client.post(
        f"/api/v1/organizations/{organization_id}/integrations/google/disconnect", headers=HEADERS
    )
    assert disconnect.status_code == 200, disconnect.text
    assert disconnect.json()["data"]["status"] == "disconnected"


@pytest.mark.integration
def test_callback_with_invalid_state_redirects_with_failure_reason(
    integrations_client: tuple[TestClient, FakeVerifier, dict[str, object]],
) -> None:
    client, _verifier, _ids = integrations_client
    response = client.get(
        "/api/v1/integrations/google/callback",
        params={"state": "not-a-real-state", "code": "irrelevant"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://app.example.invalid/gbp?")
    assert "connected=0" in location
    assert "reason=invalid_state" in location


@pytest.mark.integration
def test_callback_with_provider_denial_redirects_with_failure_reason(
    integrations_client: tuple[TestClient, FakeVerifier, dict[str, object]],
) -> None:
    client, verifier, ids = integrations_client
    verifier.result = claims(ids["member_subject"])  # type: ignore[arg-type]
    organization_id = ids["organization_id"]
    connect = client.post(
        f"/api/v1/organizations/{organization_id}/integrations/google/connect", headers=HEADERS
    )
    authorization_url = connect.json()["data"]["authorization_url"]
    state = httpx.URL(authorization_url).params["state"]

    response = client.get(
        "/api/v1/integrations/google/callback",
        params={"state": state, "error": "access_denied"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert "connected=0" in location
    assert "reason=access_denied" in location
