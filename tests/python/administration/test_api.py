"""Phase 4 route authentication, fixed-policy, and exposure tests."""

from fastapi.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.main import create_app


def test_phase4_routes_require_authentication_and_no_store() -> None:
    app = create_app(Settings(environment=EnvironmentName.TEST))
    with TestClient(app) as client:
        response = client.get("/api/v1/organizations/11111111-1111-4111-8111-111111111111/services")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.headers["cache-control"] == "no-store"


def test_phase4_has_no_generic_permission_schema_or_product_creation_endpoint() -> None:
    paths = create_app(Settings(environment=EnvironmentName.TEST)).openapi()["paths"]
    assert "/api/v1/organizations/{organization_id}/products" in paths
    assert not any(path.endswith("/permission-check") for path in paths)
    assert not any(
        path == "/api/v1/products" and "post" in methods for path, methods in paths.items()
    )
    assert not any(
        "schema-registry" in path and "post" in methods for path, methods in paths.items()
    )
