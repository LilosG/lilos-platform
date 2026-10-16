"""Safe, typed errors of the monthly client report."""

from http import HTTPStatus

from apps.api.app.errors import ApiError, AuthorizationError, ConflictError, NotFoundError
from apps.api.app.schemas import ErrorCategory


class ReportMonthNotEndedError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_MONTH_NOT_ENDED"
    category = ErrorCategory.VALIDATION
    public_message = "A report covers calendar months that have ended."


class ReportMonthNotFirstError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_MONTH_NOT_FIRST"
    category = ErrorCategory.VALIDATION
    public_message = "A report month is given as the first day of the month."


class ReportPeriodOrderError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_PERIOD_ORDER"
    category = ErrorCategory.VALIDATION
    public_message = "The last month cannot be before the first month."


class ReportPeriodTooLongError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_PERIOD_TOO_LONG"
    category = ErrorCategory.VALIDATION
    public_message = "A period covers 1 to 12 whole months."


class ReportPeriodInvalidError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_PERIOD_INVALID"
    category = ErrorCategory.VALIDATION
    public_message = "The period is not a month or a range of months."


class ReportComparisonInvalidError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_COMPARISON_INVALID"
    category = ErrorCategory.VALIDATION
    public_message = "The comparison is not one this report offers."


class ReportBaselineRequiredError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_BASELINE_REQUIRED"
    category = ErrorCategory.VALIDATION
    public_message = "A baseline comparison needs a first and a last baseline month."


class ReportBaselineUnexpectedError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_BASELINE_UNEXPECTED"
    category = ErrorCategory.VALIDATION
    public_message = "Baseline months are only given for a baseline comparison."


class ReportBaselineOverlapsError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "REPORT_BASELINE_OVERLAPS"
    category = ErrorCategory.VALIDATION
    public_message = "The baseline must end before the report period starts."


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
    public_message = "The sent date must be after the report's last month and not in the future."


class ReportCardFigureUnavailableError(ApiError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "REPORT_CARD_FIGURE_UNAVAILABLE"
    category = ErrorCategory.VALIDATION
    public_message = "A result card can only be about a figure this report has."
