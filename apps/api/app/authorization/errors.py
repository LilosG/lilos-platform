"""Non-disclosing authorization failure contract."""

from apps.api.app.authorization.enums import AuthorizationReason
from apps.api.app.errors import AuthorizationError

# What a member can be told, and what to do about it.
#
# The authorization service already computes exactly why a request was refused,
# audits it, and then the reason was thrown away: every denial reached the
# operator as "You do not have permission to view this". Six causes with six
# different fixes — an unactivated client, a product that was never enabled, a
# role missing the permission, a suspended membership, a missing step-up — all
# read identically, so the only way to act on one was to guess.
_MEMBER_DISCLOSURE: dict[AuthorizationReason, tuple[str, str]] = {
    AuthorizationReason.ORGANIZATION_NOT_EFFECTIVE: (
        "ORGANIZATION_NOT_ACTIVE",
        "This client is not active yet. Finish onboarding activation before "
        "connecting providers or running product work.",
    ),
    AuthorizationReason.MEMBERSHIP_INACTIVE: (
        "MEMBERSHIP_INACTIVE",
        "Your membership in this organization is not active. An administrator has to reinstate it.",
    ),
    AuthorizationReason.INSUFFICIENT_ASSURANCE: (
        "STEP_UP_REQUIRED",
        "This action requires stronger authentication. Sign in again with "
        "multi-factor authentication.",
    ),
    AuthorizationReason.PERMISSION_NOT_GRANTED: (
        "PERMISSION_NOT_GRANTED",
        "Your role in this organization does not grant this action.",
    ),
    AuthorizationReason.EXPLICIT_DENY: (
        "PERMISSION_EXPLICITLY_DENIED",
        "This action is explicitly denied for your role in this organization.",
    ),
    AuthorizationReason.PRODUCT_ENTITLEMENT_NOT_EFFECTIVE: (
        "PRODUCT_NOT_ENABLED",
        "The product this action belongs to is not enabled for this client. "
        "Enable it in Administration, then try again.",
    ),
    AuthorizationReason.CATALOG_INCONSISTENCY: (
        "AUTHORIZATION_CATALOG_INCONSISTENT",
        "This action cannot be authorized because the permission catalog is "
        "inconsistent. This is a platform configuration fault, not your access.",
    ),
}


class AuthorizationDeniedError(AuthorizationError):
    code = "AUTHORIZATION_DENIED"
    public_message = "Authorization is required for this action."
    response_headers = {"Cache-Control": "no-store"}

    def __init__(
        self,
        *,
        reason: AuthorizationReason | None = None,
        member: bool = False,
    ) -> None:
        """Build a denial that explains itself to a member and stays silent otherwise.

        Disclosure is gated on membership because a reason can reveal whether an
        organization exists and what state it is in. A member already knows both;
        a stranger probing organization ids learns nothing beyond the refusal.
        """
        super().__init__(self.public_message)
        if reason is None or not member:
            return
        disclosure = _MEMBER_DISCLOSURE.get(reason)
        if disclosure is None:
            return
        code, message = disclosure
        # Instance attributes shadow the class contract, which is what the shared
        # api_exception_handler serialises.
        self.code = code
        self.public_message = message
