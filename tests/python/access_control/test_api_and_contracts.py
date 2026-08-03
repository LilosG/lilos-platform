"""Guard, transport, normalization, and scope-contract tests."""

import logging
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.app.access_control.contracts import InvitationCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipStatus, MembershipType, ScopeType
from apps.api.app.access_control.policy import permission_fixture_allows
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.main import create_app
from apps.api.app.organizations.enums import OrganizationStatus


@pytest.fixture(autouse=True)
def restore_application_logger() -> Iterator[None]:
    """Keep create_app logging configuration from leaking into unrelated suites."""
    logger = logging.getLogger("lilos")
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield
    logger.handlers = handlers
    logger.setLevel(level)
    logger.propagate = propagate


def test_access_routes_are_unregistered_by_default() -> None:
    with TestClient(create_app(Settings(environment=EnvironmentName.TEST))) as client:
        assert client.get("/internal/roles").status_code == 404


def test_access_routes_register_only_under_existing_safe_guard() -> None:
    settings = Settings(environment=EnvironmentName.TEST, internal_admin_routes_enabled=True)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        assert (
            client.post(f"/internal/organizations/{uuid4()}/memberships", json={}).status_code
            != 404
        )
        assert (
            client.post(f"/internal/organizations/{uuid4()}/bootstrap-owner", json={}).status_code
            != 404
        )
    for environment in (
        EnvironmentName.DEVELOPMENT,
        EnvironmentName.STAGING,
        EnvironmentName.PRODUCTION,
    ):
        with pytest.raises(ValueError):
            Settings(environment=environment, internal_admin_routes_enabled=True)


def test_invitation_email_normalization_and_scope_validation() -> None:
    command = InvitationCreate(
        user_profile_id=uuid4(),
        email="  Fabricated@Example.Invalid  ",
        membership_type=MembershipType.CLIENT,
        invited_by_user_profile_id=uuid4(),
    )
    assert command.email == "fabricated@example.invalid"
    RoleAssignmentCreate(role_id=uuid4(), scope_type=ScopeType.ORGANIZATION)
    RoleAssignmentCreate(role_id=uuid4(), scope_type=ScopeType.LOCATION, location_id=uuid4())
    with pytest.raises(ValidationError):
        RoleAssignmentCreate(
            role_id=uuid4(), scope_type=ScopeType.ORGANIZATION, location_id=uuid4()
        )


def test_deny_precedence_and_independent_parent_states() -> None:
    location_id = uuid4()
    assert permission_fixture_allows(
        organization_status=OrganizationStatus.ACTIVE,
        user_status=UserStatus.ACTIVE,
        membership_status=MembershipStatus.ACTIVE,
        location_id=location_id,
        allow_scopes=[(ScopeType.LOCATION, location_id)],
        deny_scopes=[],
    )
    assert not permission_fixture_allows(
        organization_status=OrganizationStatus.ACTIVE,
        user_status=UserStatus.ACTIVE,
        membership_status=MembershipStatus.ACTIVE,
        location_id=location_id,
        allow_scopes=[(ScopeType.LOCATION, location_id)],
        deny_scopes=[(ScopeType.ORGANIZATION, None)],
    )
    assert not permission_fixture_allows(
        organization_status=OrganizationStatus.ACTIVE,
        user_status=UserStatus.DEACTIVATED,
        membership_status=MembershipStatus.ACTIVE,
        location_id=location_id,
        allow_scopes=[(ScopeType.ORGANIZATION, None)],
        deny_scopes=[],
    )
    assert not permission_fixture_allows(
        organization_status=OrganizationStatus.PAUSED,
        user_status=UserStatus.ACTIVE,
        membership_status=MembershipStatus.ACTIVE,
        location_id=location_id,
        allow_scopes=[(ScopeType.ORGANIZATION, None)],
        deny_scopes=[],
    )
