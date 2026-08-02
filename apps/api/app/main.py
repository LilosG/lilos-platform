"""FastAPI application entrypoint for the LILOs modular monolith."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.app.config import Settings, get_settings
from apps.api.app.database.runtime import DatabaseRuntime, create_database_runtime
from apps.api.app.errors import register_exception_handlers
from apps.api.app.logging_config import configure_logging
from apps.api.app.middleware import CorrelationIdMiddleware
from apps.api.app.routes.health import router as health_router
from apps.api.app.routes.internal_industries import router as internal_industries_router
from apps.api.app.routes.internal_location_groups import router as internal_location_groups_router
from apps.api.app.routes.internal_locations import router as internal_locations_router
from apps.api.app.routes.internal_organizations import router as internal_organizations_router
from apps.api.app.routes.internal_profiles import router as internal_profiles_router


def create_app(
    settings: Settings | None = None,
    database_runtime: DatabaseRuntime | None = None,
) -> FastAPI:
    """Create the API runtime without product routes or eager database connections."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    resolved_database = database_runtime or create_database_runtime(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await resolved_database.dispose()

    application = FastAPI(
        title=resolved_settings.api_title,
        description="LILOs modular-monolith API runtime.",
        version=resolved_settings.api_version,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(application)
    application.include_router(health_router)
    if resolved_settings.internal_admin_routes_enabled:
        application.include_router(internal_industries_router)
        application.include_router(internal_organizations_router)
        application.include_router(internal_locations_router)
        application.include_router(internal_profiles_router)
        application.include_router(internal_location_groups_router)
    return application


app = create_app()
