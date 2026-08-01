from apps.api.app.config import EnvironmentName
from apps.api.app.main import app


def test_api_application_is_importable() -> None:
    assert app.title == "LILOs Platform API"
    assert app.version == "0.1.0"
    assert all(getattr(route, "path", None) != "/" for route in app.routes)
    assert app.state.settings.environment is EnvironmentName.LOCAL
    assert {"/health/live", "/health/ready"}.issubset(app.openapi()["paths"])
