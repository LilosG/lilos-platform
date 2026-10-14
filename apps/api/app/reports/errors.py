"""Safe, typed errors of the monthly client report."""

from http import HTTPStatus

from apps.api.app.errors import ApiError, AuthorizationError, ConflictError, NotFoundError
from apps.api.app.schemas import ErrorCategory


class ReportMonthNotEndedError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_MONTH_NOT_ENDED"
    category = ErrorCategory.VALIDATION
    public_message = "A report covers a calendar month that has ended."


class ReportNotFoundError(NotFoundError):
    code = "REPORT_NOT_FOUND"
    public_message = "The requested report was not found."


class ReportScopeNotReadableError(AuthorizationError):
    code = "REPORT_SCOPE_NOT_READABLE"
    public_message = "A report covers every active location, and you cannot read all of them."


class ReportAlreadyApprovedError(ConflictError):
    code = "REPORT_ALREADY_APPROVED"
    public_message = "This report is already approved and its data has not changed."


class ReportNotEditableError(ConflictError):
    code = "REPORT_NOT_EDITABLE"
    public_message = "An approved report cannot be edited."


class ReportRevisionSupersededError(ConflictError):
    code = "REPORT_REVISION_SUPERSEDED"
    public_message = "A newer revision of this report exists."


class ReportDataMissingError(ConflictError):
    code = "REPORT_DATA_MISSING"
    public_message = "This report is missing the Business Profile data it needs."


class ReportNarrativeEmptyError(ConflictError):
    code = "REPORT_NARRATIVE_EMPTY"
    public_message = "Write both narrative sections before approving the report."


class ReportNotApprovedError(ConflictError):
    code = "REPORT_NOT_APPROVED"
    public_message = "Approve the report before recording it as sent."


class ReportSentDateInvalidError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_SENT_DATE_INVALID"
    category = ErrorCategory.VALIDATION
    public_message = "The sent date must be after the report's month and not in the future."
