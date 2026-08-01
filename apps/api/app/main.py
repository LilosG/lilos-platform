"""FastAPI application entrypoint for the LILOs modular monolith."""

from fastapi import FastAPI

from apps.api.app.config import Settings, get_settings
from apps.api.app.errors import register_exception_handlers
from apps.api.app.logging_config import configure_logging
from apps.api.app.middleware import CorrelationIdMiddleware
from apps.api.app.routes.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API runtime without product routes or external dependencies."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    application = FastAPI(
        title=resolved_settings.api_title,
        description="LILOs modular-monolith API runtime.",
        version=resolved_settings.api_version,
    )
    application.state.settings = resolved_settings
    application.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(application)
    application.include_router(health_router)
    return application


app = create_app()
