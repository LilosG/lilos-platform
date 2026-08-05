"""Fixed-policy dependency guarding cross-organization platform administration routes."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.authentication.contracts import AuthenticatedPrincipal
from apps.api.app.authentication.dependencies import get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authorization.errors import AuthorizationDeniedError
from apps.api.app.authorization.service import assurance_satisfies
from apps.api.app.database.session import get_database_session
from apps.api.app.platform_admin.models import PlatformAdministrator
from apps.api.app.platform_admin.repository import PlatformAdministratorRepository

DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
Authenticated = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]
PlatformAdministratorDependency = Callable[..., Coroutine[Any, Any, PlatformAdministrator]]

repository = PlatformAdministratorRepository()


def require_platform_administrator(
    minimum_assurance_level: AssuranceLevel = AssuranceLevel.AAL2,
) -> PlatformAdministratorDependency:
    """Bind an immutable cross-organization platform-administrator policy to the principal.

    Additive to ``require_authorization``: it never consults organization
    membership, role assignments, or the per-org RBAC catalog. It only checks
    that the authenticated principal is active, meets the required assurance
    level, and holds an active (non-revoked) ``PlatformAdministrator`` grant.
    Denial raises the same ``AuthorizationDeniedError`` (403, non-disclosing)
    the rest of the application uses for authorization failures.
    """

    async def evaluate(
        principal: Authenticated,
        session: DatabaseSession,
    ) -> PlatformAdministrator:
        if principal.user_status is not UserStatus.ACTIVE or not assurance_satisfies(
            principal.assurance_level, minimum_assurance_level
        ):
            raise AuthorizationDeniedError
        grant = await repository.get_active_by_user_profile_id(session, principal.platform_user_id)
        if grant is None:
            raise AuthorizationDeniedError
        return grant

    return evaluate
