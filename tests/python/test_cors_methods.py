"""CORS must permit every HTTP method the router actually serves.

A method missing from ``allow_methods`` fails the browser preflight, so the real
request is never sent. Nothing reaches application code, no server-side log is
written, and the UI simply appears inert. That is exactly how schedule pause,
resume, cadence and cancel came to do nothing: PATCH was absent from the list
while ``PATCH /workflows/schedules/{schedule_id}`` was live.

This test compares the allowlist against the registered routes so adding a route
with a new method cannot reintroduce the failure.
"""

from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.config import Settings
from apps.api.app.main import create_app

# Handled by the browser and the middleware itself; never listed explicitly.
_IMPLICIT_METHODS = frozenset({"HEAD", "OPTIONS"})


def _app_with_cors() -> FastAPI:
    settings = Settings(web_origins="https://lilos-platform-web.vercel.app")
    return create_app(settings=settings)


def _configured_allow_methods(app: FastAPI) -> set[str]:
    for middleware in app.user_middleware:
        if getattr(middleware.cls, "__name__", "") == CORSMiddleware.__name__:
            options = getattr(middleware, "kwargs", None) or getattr(middleware, "options", {})
            return {str(method).upper() for method in options["allow_methods"]}
    raise AssertionError("CORSMiddleware is not configured")


def _walk_routes(routes: list[Any], depth: int = 0) -> Iterator[Any]:
    """Yield every route, descending into included routers.

    This FastAPI version represents an included router as a wrapper in
    ``app.routes`` rather than flattening its routes, so a shallow scan of
    ``app.routes`` sees only the docs endpoints and would make this test pass
    while the whole product API went unchecked.
    """
    for route in routes:
        yield route
        inner = getattr(route, "original_router", None)
        if inner is not None and depth < 6:
            yield from _walk_routes(list(getattr(inner, "routes", [])), depth + 1)


def _routed_methods(app: Any) -> set[str]:
    methods: set[str] = set()
    for route in _walk_routes(list(app.routes)):
        for method in getattr(route, "methods", None) or ():
            methods.add(str(method).upper())
    return methods - _IMPLICIT_METHODS


def test_cors_allows_every_method_the_router_serves() -> None:
    app = _app_with_cors()

    routed = _routed_methods(app)
    allowed = _configured_allow_methods(app)

    # Self-check: a traversal that silently finds nothing would pass vacuously.
    assert "PATCH" in routed, "route discovery failed to find the known PATCH routes"
    assert len(routed) >= 4, f"suspiciously few methods discovered: {sorted(routed)}"
    missing = routed - allowed
    assert not missing, (
        "these methods are served by a route but rejected at CORS preflight, so the "
        f"browser never sends the request: {sorted(missing)}"
    )


def test_patch_is_allowed() -> None:
    """Guards the specific regression: schedule administration is PATCH-only."""
    assert "PATCH" in _configured_allow_methods(_app_with_cors())


def test_preflight_for_schedule_update_is_accepted() -> None:
    """End-to-end preflight check against the live middleware."""
    from starlette.testclient import TestClient

    origin = "https://lilos-platform-web.vercel.app"
    with TestClient(_app_with_cors()) as client:
        response = client.options(
            "/api/v1/organizations/00000000-0000-0000-0000-000000000000"
            "/workflows/schedules/00000000-0000-0000-0000-000000000001",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200, response.text
    assert "PATCH" in response.headers["access-control-allow-methods"]
