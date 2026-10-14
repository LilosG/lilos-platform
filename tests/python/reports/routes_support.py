"""An app over a seeded database with one user per role, for the report route tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from authorization.fixtures import add_effective_product_entitlement
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
from reports.support import Factory, seed_complete_month, seed_org

BASE = "/api/v1/organizations"


class TokenVerifier:
    """Maps a bearer token to the claims of the user it names."""

    def __init__(self, claims: dict[str, VerifiedProviderClaims]) -> None:
        self.claims = claims

    async def verify(self, token: str) -> VerifiedProviderClaims:
        return self.claims[token]


def claims_for(subject: UUID) -> VerifiedProviderClaims:
    now = datetime.now(UTC)
    return VerifiedProviderClaims(
        auth_user_id=subject,
        session_id=uuid4(),
        assurance_level=AssuranceLevel.AAL2,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        algorithm="ES256",
        key_id="reports-test-key",
    )


def headers(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {role}"}


async def add_user(factory: Factory, organization_id: UUID, role: str) -> VerifiedProviderClaims:
    access = AccessControlService()
    async with factory.begin() as session:
        profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
        session.add(profile)
        await session.flush()
        membership = await access.create_membership(
            session,
            organization_id,
            MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
            correlation_id=f"member-{role}",
        )
        role_row = await access.catalog.get_role_by_key(session, role)
        assert role_row is not None
        await access.add_assignment(
            session,
            organization_id,
            membership.id,
            RoleAssignmentCreate(role_id=role_row.id, scope_type=ScopeType.ORGANIZATION),
            correlation_id=f"assign-{role}",
        )
    return claims_for(profile.auth_user_id)


async def populate(factory: Factory) -> tuple[dict[str, VerifiedProviderClaims], dict[str, UUID]]:
    org, gbp, location = await seed_org(factory, "Alpha")
    other, other_gbp, other_location = await seed_org(factory, "Bravo")
    await seed_complete_month(factory, org, gbp, location)
    async with factory.begin() as session:
        await AccessCatalogSeeder().seed(session, correlation_id="reports-catalog")
        for tenant in (org, other):
            for product in ("insights", "gbp"):
                await add_effective_product_entitlement(
                    session, tenant, product, correlation_id=f"entitle-{product}"
                )
    users = {
        "owner": await add_user(factory, org, "organization_owner"),
        "manager": await add_user(factory, org, "organization_manager"),
        "viewer": await add_user(factory, org, "organization_viewer"),
        "other": await add_user(factory, other, "organization_owner"),
    }
    return users, {"org": org, "other": other, "gbp": gbp, "location": location}


@pytest.fixture
def reports_app(
    postgresql_test_url: str, factory: Factory
) -> Generator[tuple[TestClient, dict[str, UUID], Factory], None, None]:
    import asyncio

    users, ids = asyncio.run(populate(factory))
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )
    app = create_app(settings, authentication_verifier=TokenVerifier(users))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, ids, factory


def call(client: TestClient, method: str, path: str, role: str | None, body: Any = None) -> Any:
    return client.request(method, path, headers=headers(role) if role else {}, json=body)


Call = Callable[..., Any]
