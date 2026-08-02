"""Stable industry-domain API errors."""

from apps.api.app.errors import ConflictError, NotFoundError


class IndustryNotFoundError(NotFoundError):
    code = "INDUSTRY_NOT_FOUND"
    public_message = "The requested industry was not found."


class IndustryKeyConflictError(ConflictError):
    code = "INDUSTRY_KEY_CONFLICT"
    public_message = "The industry key is already in use."


class IndustryVersionConflictError(ConflictError):
    code = "INDUSTRY_VERSION_CONFLICT"
    public_message = "The industry changed after it was loaded."


class IndustryTransitionConflictError(ConflictError):
    code = "INDUSTRY_TRANSITION_CONFLICT"
    public_message = "The industry cannot perform that lifecycle transition."


class IndustryAssignmentConflictError(ConflictError):
    code = "INDUSTRY_ASSIGNMENT_CONFLICT"
    public_message = "The industry is not active and cannot be assigned."


class IndustrySeedConflictError(ConflictError):
    code = "INDUSTRY_SEED_CONFLICT"
    public_message = "An existing industry does not match the controlled seed record."
