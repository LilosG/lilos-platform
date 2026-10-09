"""Website publishing setup: state, repository listing and idempotent target linking."""

import asyncio
from uuid import UUID, uuid4

import pytest
from authorization.fixtures import add_effective_product_entitlement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.products.content.github_app_service import (
    GITHUB_INSTALLATION_PREFIX,
    DiscoveredRepository,
)
from apps.api.app.products.content.models import PublishingTarget
from apps.api.app.products.content.target_contract_catalog import CONTRACTS

from .test_seo_api import HEADERS, FakeVerifier, claims, seo_client

__all__ = ["seo_client"]

VERIFIED = "LilosG/cococabana"
UNVERIFIED = "LilosG/not-checked-yet"
REPOSITORIES = [
    DiscoveredRepository(VERIFIED, "cococabana", "main", True),
    DiscoveredRepository(UNVERIFIED, "not-checked-yet", "trunk", False),
]
Fixture = tuple[TestClient, dict[str, UUID]]


@pytest.fixture(autouse=True)
def entitled(seo_client: Fixture, seo_session_factory: async_sessionmaker[AsyncSession]) -> None:
    _, ids = seo_client

    async def run() -> None:
        async with seo_session_factory.begin() as session:
            for product in ["gbp", "content"]:
                await add_effective_product_entitlement(
                    session, ids["organization"], product, correlation_id="publishing"
                )

    asyncio.run(run())


def setup_github(
    factory: async_sessionmaker[AsyncSession], org: UUID, status: str = "connected"
) -> UUID:
    async def run() -> UUID:
        async with factory.begin() as session:
            provider = Provider(key="github", name="GitHub", status="active", capabilities=[])
            session.add(provider)
            await session.flush()
            connection = IntegrationConnection(
                organization_id=org,
                provider_id=provider.id,
                external_account_reference=f"{GITHUB_INSTALLATION_PREFIX}4242",
                status=status,
            )
            session.add(connection)
            await session.flush()
            return connection.id

    return asyncio.run(run())


def fake_repositories(
    monkeypatch: pytest.MonkeyPatch, repositories: list[DiscoveredRepository] | Exception
) -> list[str]:
    calls: list[str] = []

    async def listing(_self: object, _settings: object, installation_id: str) -> list[object]:
        calls.append(installation_id)
        if isinstance(repositories, Exception):
            raise repositories
        return list(repositories)

    monkeypatch.setattr(
        "apps.api.app.products.content.github_app_service.GitHubAppService."
        "list_installation_repositories",
        listing,
    )
    return calls


def targets(factory: async_sessionmaker[AsyncSession], org: UUID) -> list[PublishingTarget]:
    async def run() -> list[PublishingTarget]:
        async with factory() as session:
            return list(
                await session.scalars(
                    select(PublishingTarget).where(PublishingTarget.organization_id == org)
                )
            )

    return asyncio.run(run())


def add_target(
    factory: async_sessionmaker[AsyncSession],
    org: UUID,
    connection: UUID,
    contract: dict[str, object],
) -> None:
    async def run() -> None:
        async with factory.begin() as session:
            session.add(
                PublishingTarget(
                    organization_id=org,
                    connection_id=connection,
                    key="primary-site",
                    target_type="github_astro",
                    repository_id="LilosG/existing",
                    base_branch="main",
                    allowed_path_prefix="src/content/blog",
                    frontmatter_contract=contract,
                    allowed_site_change_prefixes=[],
                    status="active",
                    version=1,
                )
            )

    asyncio.run(run())


def url(ids: dict[str, UUID], tail: str = "") -> str:
    return (
        f"/api/v1/organizations/{ids['organization']}/command-center/integrations/publishing{tail}"
    )


def view(client: TestClient, ids: dict[str, UUID]) -> dict[str, object]:
    base = f"/api/v1/organizations/{ids['organization']}/command-center/integrations"
    response = client.get(base, headers=HEADERS)
    assert response.status_code == 200, response.text
    publishing: dict[str, object] = response.json()["publishing"]
    return publishing


def test_publishing_state_for_each_setup(
    seo_client: Fixture, seo_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    assert view(client, ids) == {
        "state": "github_not_connected",
        "repository": None,
        "branch": None,
        "can_manage": True,
    }
    connection = setup_github(seo_session_factory, org)
    assert view(client, ids)["state"] == "not_linked"
    add_target(seo_session_factory, org, connection, {})
    unverified = view(client, ids)
    assert unverified["state"] == "format_unverified"
    assert unverified["repository"] == "LilosG/existing"
    assert unverified["branch"] == "main"

    async def verify() -> None:
        async with seo_session_factory.begin() as session:
            row = await session.scalar(select(PublishingTarget))
            assert row is not None
            row.frontmatter_contract = {"required": ["title"]}

    asyncio.run(verify())
    assert view(client, ids)["state"] == "linked"


def test_publishing_state_reports_a_disconnected_github(
    seo_client: Fixture, seo_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    client, ids = seo_client
    setup_github(seo_session_factory, ids["organization"], status="reconnect_required")
    assert view(client, ids)["state"] == "github_not_connected"


def test_repositories_mark_verified_suggested_and_scope_to_the_installation(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    setup_github(seo_session_factory, ids["organization"])
    calls = fake_repositories(monkeypatch, REPOSITORIES)
    # The org slug is "seo-test-org": no name matches, so nothing is suggested.
    response = client.get(url(ids, "/repositories"), headers=HEADERS)
    assert response.status_code == 200, response.text
    assert calls == ["4242"]
    rows = {row["repository_id"]: row for row in response.json()["repositories"]}
    assert set(rows) == {VERIFIED, UNVERIFIED}
    assert rows[VERIFIED]["format_verified"] is True
    assert rows[UNVERIFIED]["format_verified"] is False
    assert rows[VERIFIED]["default_branch"] == "main"
    assert rows[VERIFIED]["private"] is True
    assert not any(row["suggested"] for row in rows.values())
    assert VERIFIED in CONTRACTS


def test_the_only_accessible_repository_is_suggested(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    setup_github(seo_session_factory, ids["organization"])
    fake_repositories(monkeypatch, [REPOSITORIES[0]])
    rows = client.get(url(ids, "/repositories"), headers=HEADERS).json()["repositories"]
    assert [row["suggested"] for row in rows] == [True]


def test_repository_listing_failure_is_a_typed_error_not_an_empty_list(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    missing = client.get(url(ids, "/repositories"), headers=HEADERS)
    assert missing.status_code == 409
    assert missing.json()["error"]["code"] == "PUBLISHING_GITHUB_NOT_CONNECTED"
    setup_github(seo_session_factory, ids["organization"])
    fake_repositories(monkeypatch, RuntimeError("github down"))
    failed = client.get(url(ids, "/repositories"), headers=HEADERS)
    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "PUBLISHING_REPOSITORIES_UNAVAILABLE"
    assert failed.json()["error"]["retryable"] is True
    assert "github down" not in failed.text


def link(client: TestClient, ids: dict[str, UUID], repository: str, key: str = "key-00000001"):  # noqa: ANN201
    return client.post(
        url(ids, "/target"),
        headers={**HEADERS, "Idempotency-Key": key},
        json={"repository_id": repository},
    )


def test_link_creates_the_target_with_the_catalog_contract_and_audits_it(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    connection = setup_github(seo_session_factory, org)
    fake_repositories(monkeypatch, REPOSITORIES)
    response = link(client, ids, VERIFIED)
    assert response.status_code == 201, response.text
    assert response.json() == {"repository": VERIFIED, "branch": "main", "replayed": False}
    (target,) = targets(seo_session_factory, org)
    assert target.connection_id == connection
    assert target.key == "primary-site"
    assert target.repository_id == VERIFIED
    assert target.base_branch == "main"
    assert target.allowed_path_prefix == "src/content/blog"
    assert target.status == "active"
    assert target.frontmatter_contract
    assert target.frontmatter_contract["required"] == CONTRACTS[VERIFIED]["required"]
    assert view(client, ids)["state"] == "linked"

    async def audited() -> int:
        async with seo_session_factory() as session:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.organization_id == org,
                        AuditEvent.event_type == "content.target.configured",
                        AuditEvent.resource_id == target.id,
                    )
                )
                or 0
            )

    assert asyncio.run(audited()) == 1


def test_replaying_the_same_key_returns_the_same_target_and_creates_nothing(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    setup_github(seo_session_factory, org)
    fake_repositories(monkeypatch, REPOSITORIES)
    first = link(client, ids, VERIFIED)
    assert first.status_code == 201, first.text
    again = link(client, ids, VERIFIED)
    assert again.status_code == 200, again.text
    assert again.json() == {"repository": VERIFIED, "branch": "main", "replayed": True}
    assert len(targets(seo_session_factory, org)) == 1
    other = link(client, ids, UNVERIFIED)
    assert other.status_code == 409
    assert other.json()["error"]["code"] == "PUBLISHING_IDEMPOTENCY_CONFLICT"
    assert len(targets(seo_session_factory, org)) == 1


def test_a_repository_outside_the_installation_is_rejected(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    setup_github(seo_session_factory, org)
    fake_repositories(monkeypatch, [REPOSITORIES[1]])
    # In the contract catalog, but not reachable by this client's installation.
    response = link(client, ids, VERIFIED)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PUBLISHING_REPOSITORY_NOT_ACCESSIBLE"
    assert targets(seo_session_factory, org) == []


def test_an_unverified_repository_is_refused_and_creates_nothing(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    setup_github(seo_session_factory, org)
    fake_repositories(monkeypatch, REPOSITORIES)
    response = link(client, ids, UNVERIFIED)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PUBLISHING_FORMAT_UNVERIFIED"
    assert targets(seo_session_factory, org) == []


def test_an_existing_active_target_is_never_replaced(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    connection = setup_github(seo_session_factory, org)
    add_target(seo_session_factory, org, connection, {"required": ["title"]})
    fake_repositories(monkeypatch, REPOSITORIES)
    response = link(client, ids, VERIFIED)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PUBLISHING_TARGET_EXISTS"
    assert [row.repository_id for row in targets(seo_session_factory, org)] == ["LilosG/existing"]


def test_idempotency_key_and_body_are_required(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    setup_github(seo_session_factory, ids["organization"])
    fake_repositories(monkeypatch, REPOSITORIES)
    body = {"repository_id": VERIFIED}
    assert client.post(url(ids, "/target"), headers=HEADERS, json=body).status_code == 422
    keyed = {**HEADERS, "Idempotency-Key": "key-00000002"}
    extra = {"repository_id": VERIFIED, "base_branch": "evil"}
    assert client.post(url(ids, "/target"), headers=keyed, json=extra).status_code == 422


def test_users_without_manage_targets_or_aal2_are_denied(
    seo_client: Fixture,
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ids = seo_client
    org = ids["organization"]
    setup_github(seo_session_factory, org)
    fake_repositories(monkeypatch, REPOSITORIES)
    verifier = client.app.state.authentication_verifier  # type: ignore[attr-defined]
    assert isinstance(verifier, FakeVerifier)

    async def manager() -> UUID:
        access = AccessControlService()
        async with seo_session_factory.begin() as session:
            profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            session.add(profile)
            await session.flush()
            membership = await access.create_membership(
                session,
                org,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="publishing-manager",
            )
            role = await access.catalog.get_role_by_key(session, "organization_manager")
            assert role is not None
            await access.add_assignment(
                session,
                org,
                membership.id,
                RoleAssignmentCreate(role_id=role.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="publishing-manager-role",
            )
            return profile.auth_user_id

    subject = asyncio.run(manager())
    verifier.result = claims(subject)
    assert client.get(url(ids, "/repositories"), headers=HEADERS).status_code == 403
    assert link(client, ids, VERIFIED).status_code == 403
    # The manager may see where publishing stands, but not change it.
    assert view(client, ids)["can_manage"] is False
    assert targets(seo_session_factory, org) == []

    # The owner on a session that has not stepped up is refused the same way.
    verifier.result = claims(ids["assigned_subject"], AssuranceLevel.AAL1)
    assert client.get(url(ids, "/repositories"), headers=HEADERS).status_code == 403
    assert link(client, ids, VERIFIED).status_code == 403
    assert targets(seo_session_factory, org) == []


def test_another_organization_cannot_reach_this_clients_publishing(
    seo_client: Fixture,
) -> None:
    client, ids = seo_client
    foreign = f"/api/v1/organizations/{ids['other_organization']}/command-center/integrations"
    assert client.get(foreign + "/publishing/repositories", headers=HEADERS).status_code in {
        403,
        404,
    }
    assert client.get(url(ids, "/repositories")).status_code == 401
