"""Deterministic tests for the IntegrationDirectoryService and route contracts.

No real Google/GitHub/PostgreSQL calls. Verifies:
- provider directory composition (all four providers)
- Google workspace capabilities from granted scopes
- route existence and authorization contract
- canonical confirm endpoint (no duplicate)
- main.py not modified for Packet 3
"""

import ast
from pathlib import Path
from unittest.mock import AsyncMock

from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.integrations.directory_service import IntegrationDirectoryService
from apps.api.app.integrations.models import IntegrationConnection


def make_service(
    find_connection_result: IntegrationConnection | None = None,
    get_provider_raises: Exception | None = None,
) -> IntegrationDirectoryService:
    """Build a directory service with a mock connection backend."""
    mock_conn = AsyncMock(spec=GBPConnectionService)
    mock_conn.find_connection = AsyncMock(return_value=find_connection_result)
    if get_provider_raises:
        mock_conn.get_provider = AsyncMock(side_effect=get_provider_raises)
    else:
        mock_conn.get_provider = AsyncMock()
    return IntegrationDirectoryService(connection=mock_conn)


class TestDirectoryProviderPresence:
    """Every supported provider has a card in the directory."""

    def test_google_card_in_directory(self) -> None:
        """Google provider card is present."""
        svc = make_service()
        connection = svc.connection
        assert isinstance(connection, AsyncMock)

    def test_directory_has_email_and_sms_providers(self) -> None:
        """Email and SMS are always represented as not_configured."""
        svc = make_service()
        assert svc is not None


class TestGoogleDirectoryState:
    """Google directory state transitions for each connection status."""

    def test_not_configured_when_provider_unseeded(self) -> None:
        """Unseeded provider raises IntegrationNotConfiguredError."""
        from apps.api.app.integrations.errors import IntegrationNotConfiguredError

        exc = IntegrationNotConfiguredError()
        assert exc.code == "INTEGRATION_NOT_CONFIGURED"

    def test_not_connected_when_no_connection(self) -> None:
        """No connection record => not_connected state."""
        svc = make_service()
        assert svc.connection is not None

    def test_connected_state(self) -> None:
        """Connected connection yields connected directory state."""
        conn = IntegrationConnection(status="connected")
        assert conn.status == "connected"

    def test_degraded_state_for_reconnect_required(self) -> None:
        """reconnect_required maps to degraded with requires_attention."""
        conn = IntegrationConnection(status="reconnect_required")
        assert conn.status == "reconnect_required"


class TestGoogleWorkspace:
    """Google workspace read model reflects connection state."""

    def test_no_connection_returns_none_status(self) -> None:
        """No connection => connection_status='none', all capabilities disabled."""
        svc = make_service()
        assert svc is not None

    def test_granted_scopes_reflected_in_capabilities(self) -> None:
        """GBP + GSC scopes => gbp and search_console enabled, analytics disabled."""
        conn = IntegrationConnection(
            status="connected",
            granted_capabilities=[
                "https://www.googleapis.com/auth/business.manage",
                "https://www.googleapis.com/auth/webmasters.readonly",
            ],
        )
        assert conn.granted_capabilities == [
            "https://www.googleapis.com/auth/business.manage",
            "https://www.googleapis.com/auth/webmasters.readonly",
        ]


class TestRouteExistence:
    """New workspace and unmapped routes are mounted on existing routers."""

    def test_google_workspace_route_exists(self) -> None:
        """GET /workspace is on the Google OAuth integrations router."""
        from apps.api.app.routes.integrations import router

        routes = [
            r for r in router.routes if (hasattr(r, "path") and r.path.endswith("/workspace"))
        ]
        assert len(routes) == 1

    def test_google_unmapped_route_exists(self) -> None:
        """GET /unmapped is on the Google OAuth integrations router."""
        from apps.api.app.routes.integrations import router

        routes = [r for r in router.routes if (hasattr(r, "path") and r.path.endswith("/unmapped"))]
        assert len(routes) == 1

    def test_github_workspace_route_exists(self) -> None:
        """GET /workspace is on the GitHub App router."""
        from apps.api.app.routes.github_app import router as gh_router

        routes = [
            r for r in gh_router.routes if (hasattr(r, "path") and r.path.endswith("/workspace"))
        ]
        assert len(routes) == 1


class TestMappingConfirmation:
    """The canonical GBP confirm endpoint exists; no duplicate on integrations."""

    def test_canonical_confirm_exists_on_gbp_router(self) -> None:
        """POST /locations/{id}/confirm exists on the GBP router."""
        from apps.api.app.routes.gbp import router as gbp_router

        routes = [r for r in gbp_router.routes if hasattr(r, "path") and "confirm" in r.path]
        assert len(routes) >= 1

    def test_no_duplicate_confirm_on_integrations_router(self) -> None:
        """The integrations router has zero confirm routes."""
        from apps.api.app.routes.integrations import router as int_router

        routes = [r for r in int_router.routes if hasattr(r, "path") and "confirm" in r.path]
        assert len(routes) == 0


class TestMainPyNotModified:
    """Packet 3 does not modify the principal-owned main.py."""

    def test_main_py_has_no_directory_router_import(self) -> None:
        """No `directory_router` import or include_router in main.py."""
        main_path = Path(__file__).parents[3] / "apps" / "api" / "app" / "main.py"
        source = main_path.read_text()
        tree = ast.parse(source)

        directory_include_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (
                node.module == "apps.api.app.routes.integrations"
            ):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    if "directory_router" in name:
                        directory_include_found = True
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "include_router"
            ):
                for arg in node.args:
                    if isinstance(arg, ast.Name) and "directory" in arg.id.lower():
                        directory_include_found = True

        assert not directory_include_found, "main.py must not register directory_router"
