"""Classify a failed provider write as definitely-not-applied or genuinely ambiguous.

A state-changing provider call that raises tells us nothing by itself about whether
the remote resource was created. Treating every failure as ambiguous is safe but
expensive: an ambiguous publication enters ``reconciliation_required`` and waits for
a human, so a plainly rejected request (malformed body, expired token, rate limit)
consumed operator attention it never needed.

Some failures do carry proof. A connection that was never established, or a provider
response that rejects the request outright, cannot have created anything. Those can
fail or retry on their own. Anything else — a timeout after the bytes went out, a 5xx,
an unparseable success body, an exception shape we do not recognise — stays ambiguous
and reconciles, because the write may have landed.

The default is deliberately ambiguous. An unrecognised failure is never assumed safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

# Provider rejected the request on its own terms. No resource was created.
_REJECTED_STATUSES = frozenset({400, 401, 403, 404, 405, 409, 412, 422})
# Provider refused to process it. Not applied, and worth trying again later.
_THROTTLED_STATUSES = frozenset({408, 429})


@dataclass(frozen=True, slots=True)
class ProviderWriteOutcome:
    """How a failed provider write should be recorded."""

    applied: Literal["not_applied", "unknown"]
    safe_error_code: str
    # Mirrors JobOutcome.result so callers can pass it straight through.
    job_result: Literal["permanent_failure", "retryable_failure", "ambiguous"]

    @property
    def requires_reconciliation(self) -> bool:
        return self.applied == "unknown"


_AMBIGUOUS = ProviderWriteOutcome(
    applied="unknown",
    safe_error_code="PROVIDER_WRITE_AMBIGUOUS",
    job_result="ambiguous",
)


def classify_provider_write_failure(error: BaseException) -> ProviderWriteOutcome:
    """Return how to record ``error`` raised by a state-changing provider call."""
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status in _REJECTED_STATUSES:
            return ProviderWriteOutcome(
                applied="not_applied",
                safe_error_code=f"PROVIDER_REJECTED_{status}",
                job_result="permanent_failure",
            )
        if status in _THROTTLED_STATUSES:
            return ProviderWriteOutcome(
                applied="not_applied",
                safe_error_code=f"PROVIDER_THROTTLED_{status}",
                job_result="retryable_failure",
            )
        # 5xx and anything unmapped: the provider may have applied the write
        # before failing to report it.
        return _AMBIGUOUS

    # Connect-phase failures happen before the request body is delivered, so the
    # provider never saw it. Read/write/pool timeouts are NOT in this set: those
    # occur after the request went out and are genuinely ambiguous.
    if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout, httpx.UnsupportedProtocol)):
        return ProviderWriteOutcome(
            applied="not_applied",
            safe_error_code="PROVIDER_UNREACHABLE",
            job_result="retryable_failure",
        )

    return _AMBIGUOUS
