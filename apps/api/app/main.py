"""FastAPI application entrypoint for the LILOs modular monolith."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.authentication.verifier import TokenVerifier
from apps.api.app.config import Settings, get_settings
from apps.api.app.database.runtime import DatabaseRuntime, create_database_runtime
from apps.api.app.errors import register_exception_handlers
from apps.api.app.logging_config import configure_logging
from apps.api.app.middleware import CorrelationIdMiddleware
from apps.api.app.routes.administration import router as administration_router
from apps.api.app.routes.api_v1 import router as api_v1_router
from apps.api.app.routes.client_onboarding import router as client_onboarding_router
from apps.api.app.routes.content import router as content_router
from apps.api.app.routes.gbp import organization_router as gbp_organization_router
from apps.api.app.routes.gbp import router as gbp_router
from apps.api.app.routes.gbp_operations import router as gbp_operations_router
from apps.api.app.routes.github_app import callback_router as github_app_callback_router
from apps.api.app.routes.github_app import router as github_app_router
from apps.api.app.routes.health import router as health_router
from apps.api.app.routes.insights import router as insights_router
from apps.api.app.routes.integrations import callback_router as integrations_callback_router
from apps.api.app.routes.integrations import router as integrations_router
from apps.api.app.routes.internal_access_control import router as internal_access_control_router
from apps.api.app.routes.internal_authentication import router as internal_authentication_router
from apps.api.app.routes.internal_business_identity import (
    router as internal_business_identity_router,
)
from apps.api.app.routes.internal_industries import router as internal_industries_router
from apps.api.app.routes.internal_location_groups import router as internal_location_groups_router
from apps.api.app.routes.internal_locations import router as internal_locations_router
from apps.api.app.routes.internal_organizations import router as internal_organizations_router
from apps.api.app.routes.internal_profiles import router as internal_profiles_router
from apps.api.app.routes.internal_user_profiles import router as internal_user_profiles_router
from apps.api.app.routes.leads import router as leads_router
from apps.api.app.routes.platform_administration import router as platform_administration_router
from apps.api.app.routes.reviews import router as reviews_router
from apps.api.app.routes.seo import router as seo_router
from apps.api.app.routes.workflows import router as workflows_router


def create_app(
    settings: Settings | None = None,
    database_runtime: DatabaseRuntime | None = None,
    authentication_verifier: TokenVerifier | None = None,
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
    application.state.authentication_verifier = authentication_verifier
    origins = resolved_settings.allowed_web_origins()
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    application.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(api_v1_router)
    application.include_router(administration_router)
    application.include_router(gbp_router)
    application.include_router(gbp_operations_router)
    application.include_router(gbp_organization_router)
    application.include_router(reviews_router)
    application.include_router(workflows_router)
    application.include_router(leads_router)
    application.include_router(content_router)
    application.include_router(seo_router)
    application.include_router(insights_router)
    application.include_router(platform_administration_router)
    application.include_router(client_onboarding_router)
    application.include_router(integrations_router)
    application.include_router(integrations_callback_router)
    application.include_router(github_app_router)
    application.include_router(github_app_callback_router)
    if resolved_settings.internal_admin_routes_enabled:
        application.include_router(internal_industries_router)
        application.include_router(internal_organizations_router)
        application.include_router(internal_locations_router)
        application.include_router(internal_profiles_router)
        application.include_router(internal_location_groups_router)
        application.include_router(internal_business_identity_router)
        application.include_router(internal_authentication_router)
        application.include_router(internal_user_profiles_router)
        application.include_router(internal_access_control_router)
    return application


app = create_app()
