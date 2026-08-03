"""Stable shared-administration errors."""

from apps.api.app.errors import ConflictError, NotFoundError


class AdministrationNotFoundError(NotFoundError):
    code = "ADMINISTRATION_RESOURCE_NOT_FOUND"


class AdministrationConflictError(ConflictError):
    code = "ADMINISTRATION_CONFLICT"


class AdministrationVersionConflictError(ConflictError):
    code = "ADMINISTRATION_VERSION_CONFLICT"


class CatalogMismatchError(ConflictError):
    code = "ADMINISTRATION_CATALOG_MISMATCH"


class ReadinessBlockedError(ConflictError):
    code = "PRODUCT_NOT_READY"
