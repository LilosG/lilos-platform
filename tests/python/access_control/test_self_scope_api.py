"""Self-scoped /me and /me/organizations isolation tests."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.contracts import MembershipCreate
from apps.api.app.access_control.enums import MembershipType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
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
    subject: UUID, assurance: AssuranceLevel = AssuranceLevel.AAL1
) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=subject,
        session_id=uuid4(),
        assurance_level=assurance,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        algorithm="ES256",
        key_id="self-scope-test-key",
    )


@pytest.fixture
def self_scope_client(
    postgresql_test_url: str,
    access_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[tuple[TestClient, FakeVerifier, dict[str, UUID]], None, None]:
    async def populate() -> dict[str, UUID]:
        access = AccessControlService()
        async with access_session_factory.begin() as session:
            organization_a = Organization(
                name="Self Scope Org A",
                slug="self-scope-org-a",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            organization_b = Organization(
                name="Self Scope Org B",
                slug="self-scope-org-b",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            user_a = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            user_b = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            session.add_all([organization_a, organization_b, user_a, user_b])
            await session.flush()
            membership_a = await access.create_membership(
                session,
                organization_a.id,
                MembershipCreate(user_profile_id=user_a.id, membership_type=MembershipType.CLIENT),
                correlation_id="self-scope-a",
            )
            await access.create_membership(
                session,
                organization_b.id,
                MembershipCreate(user_profile_id=user_b.id, membership_type=MembershipType.CLIENT),
                correlation_id="self-scope-b",
            )
            return {
                "user_a_subject": user_a.auth_user_id,
                "user_b_subject": user_b.auth_user_id,
                "organization_a": organization_a.id,
                "membership_a": membership_a.id,
            }

    identifiers = asyncio.run(populate())
    verifier = FakeVerifier(claims(identifiers["user_a_subject"]))
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    with TestClient(
        create_app(settings, authentication_verifier=verifier), raise_server_exceptions=False
    ) as client:
        yield client, verifier, identifiers


@pytest.mark.integration
def test_me_returns_only_the_verified_principal(
    self_scope_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = self_scope_client
    headers = {"Authorization": "Bearer fabricated.token"}
    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["data"]["auth_user_id"] == str(ids["user_a_subject"])

    missing = client.get("/api/v1/me")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.integration
def test_my_organizations_is_isolated_per_caller(
    self_scope_client: tuple[TestClient, FakeVerifier, dict[str, UUID]],
) -> None:
    client, verifier, ids = self_scope_client
    headers = {"Authorization": "Bearer fabricated.token"}

    response = client.get("/api/v1/me/organizations", headers=headers)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    rows = response.json()["data"]
    assert [row["organization_id"] for row in rows] == [str(ids["organization_a"])]
    assert rows[0]["membership_id"] == str(ids["membership_a"])

    verifier.result = claims(ids["user_b_subject"])
    other = client.get("/api/v1/me/organizations", headers=headers)
    assert other.status_code == 200
    other_rows = other.json()["data"]
    assert ids["organization_a"] not in {row["organization_id"] for row in other_rows}

    verifier.result = claims(uuid4())
    stranger = client.get("/api/v1/me/organizations", headers=headers)
    assert stranger.status_code == 401
    assert stranger.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
