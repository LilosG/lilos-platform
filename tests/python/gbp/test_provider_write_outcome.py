"""Classification of failed provider writes.

The safety property under test is asymmetric: mistakenly calling a failure
"not applied" risks a duplicate post on a live profile, while mistakenly calling
it ambiguous only costs operator attention. Unknown failures must therefore stay
ambiguous.
"""

import httpx
import pytest

from apps.api.app.products.gbp.provider_write_outcome import (
    classify_provider_write_failure,
)


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://mybusiness.googleapis.com/v4/localPosts")
    response = httpx.Response(status_code=status, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 409, 412, 422])
def test_provider_rejection_did_not_apply_the_write(status: int) -> None:
    """A rejected request created nothing, so it must not wait for a human."""
    outcome = classify_provider_write_failure(_status_error(status))

    assert outcome.applied == "not_applied"
    assert outcome.requires_reconciliation is False
    assert outcome.job_result == "permanent_failure"
    assert outcome.safe_error_code == f"PROVIDER_REJECTED_{status}"


@pytest.mark.parametrize("status", [408, 429])
def test_throttling_did_not_apply_the_write_and_is_retryable(status: int) -> None:
    outcome = classify_provider_write_failure(_status_error(status))

    assert outcome.applied == "not_applied"
    assert outcome.requires_reconciliation is False
    assert outcome.job_result == "retryable_failure"


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_errors_stay_ambiguous(status: int) -> None:
    """Google may have applied the write before failing to report it."""
    outcome = classify_provider_write_failure(_status_error(status))

    assert outcome.applied == "unknown"
    assert outcome.requires_reconciliation is True
    assert outcome.job_result == "ambiguous"
    assert outcome.safe_error_code == "PROVIDER_WRITE_AMBIGUOUS"


def test_connect_failures_did_not_apply_the_write() -> None:
    """The request body never reached the provider."""
    outcome = classify_provider_write_failure(httpx.ConnectError("no route"))

    assert outcome.applied == "not_applied"
    assert outcome.job_result == "retryable_failure"
    assert outcome.safe_error_code == "PROVIDER_UNREACHABLE"


def test_read_timeout_stays_ambiguous() -> None:
    """A read timeout happens after the request went out, unlike a connect timeout."""
    outcome = classify_provider_write_failure(httpx.ReadTimeout("timed out"))

    assert outcome.applied == "unknown"
    assert outcome.requires_reconciliation is True


def test_unparseable_success_body_stays_ambiguous() -> None:
    """The adapter raises ValueError after a 2xx, so the write probably landed."""
    outcome = classify_provider_write_failure(ValueError("invalid provider response"))

    assert outcome.applied == "unknown"
    assert outcome.requires_reconciliation is True


def test_unknown_failure_defaults_to_ambiguous() -> None:
    """The default must never assume a write was safely not applied."""
    outcome = classify_provider_write_failure(RuntimeError("something new"))

    assert outcome.applied == "unknown"
    assert outcome.requires_reconciliation is True
    assert outcome.job_result == "ambiguous"
