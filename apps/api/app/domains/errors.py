"""Stable organization-domain errors."""

from apps.api.app.errors import ConflictError, NotFoundError


class OrganizationDomainNotFoundError(NotFoundError):
    code = "ORGANIZATION_DOMAIN_NOT_FOUND"
    public_message = "The requested domain was not found."


class OrganizationDomainConflictError(ConflictError):
    code = "ORGANIZATION_DOMAIN_CONFLICT"
    public_message = "This domain is already registered to the organization."


class OrganizationDomainVersionConflictError(ConflictError):
    code = "ORGANIZATION_DOMAIN_VERSION_CONFLICT"
    public_message = "The domain changed after it was loaded."


class OrganizationDomainStateConflictError(ConflictError):
    code = "ORGANIZATION_DOMAIN_STATE_CONFLICT"
    public_message = "The domain state does not permit that operation."


class OrganizationDomainPrimaryConflictError(ConflictError):
    code = "ORGANIZATION_DOMAIN_PRIMARY_CONFLICT"
    public_message = "The organization already has an active primary domain."
