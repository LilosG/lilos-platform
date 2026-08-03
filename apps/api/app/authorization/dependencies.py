"""Reusable fixed-policy authorization dependencies for protected routes."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision, AuthorizationRequest
from apps.api.app.authorization.enums import AuthorizationReason
from apps.api.app.authorization.errors import AuthorizationDeniedError
from apps.api.app.authorization.service import AuthorizationService
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.locations.errors import LocationNotFoundError

service = AuthorizationService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
AuthorizationDependency = Callable[..., Coroutine[Any, Any, AuthorizationDecision]]


def require_authorization(
    permission_key: str,
    resource_scope: ScopeType,
    minimum_assurance_level: AssuranceLevel = AssuranceLevel.AAL1,
) -> AuthorizationDependency:
    """Bind an immutable server-side route policy to the current principal."""

    async def evaluate_policy(
        request: Request,
        principal: Authenticated,
        session: DatabaseSession,
        organization_id: UUID,
        location_id: UUID | None,
    ) -> AuthorizationDecision:
        policy_request = AuthorizationRequest(
            platform_user_id=principal.platform_user_id,
            organization_id=organization_id,
            permission_key=permission_key,
            resource_scope=resource_scope,
            location_id=location_id,
            minimum_assurance_level=minimum_assurance_level,
        )
        decision = await service.evaluate(
            session,
            principal,
            policy_request,
            correlation_id=request_correlation_id(request),
        )
        if decision.reason_code is AuthorizationReason.LOCATION_NOT_FOUND:
            raise LocationNotFoundError
        if not decision.allowed:
            raise AuthorizationDeniedError
        return decision

    if resource_scope is ScopeType.ORGANIZATION:

        async def organization_dependency(
            request: Request,
            organization_id: UUID,
            principal: Authenticated,
            session: DatabaseSession,
        ) -> AuthorizationDecision:
            return await evaluate_policy(request, principal, session, organization_id, None)

        return organization_dependency

    async def location_dependency(
        request: Request,
        organization_id: UUID,
        location_id: UUID,
        principal: Authenticated,
        session: DatabaseSession,
    ) -> AuthorizationDecision:
        return await evaluate_policy(request, principal, session, organization_id, location_id)

    return location_dependency
