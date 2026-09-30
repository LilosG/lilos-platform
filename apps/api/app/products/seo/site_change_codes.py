"""Typed outcome codes for a governed site change.

A site change runs through the shared publication state machine, which records
failures as `content_publications.safe_error_code`. This closes the set of codes
an operator can be shown for an SEO change so the API and the UI switch on a
code, never on prose -- and so the handler and the serializer cannot drift apart.
"""

from __future__ import annotations

from enum import StrEnum


class SiteChangeCode(StrEnum):
    SITE_MAPPING_REQUIRED = "SITE_MAPPING_REQUIRED"
    SITE_CHANGE_FINGERPRINT_MISMATCH = "SITE_CHANGE_FINGERPRINT_MISMATCH"
    CHANGE_SET_INVALID = "CHANGE_SET_INVALID"
    CHECKS_UNAVAILABLE = "CHECKS_UNAVAILABLE"
    CONTENT_CHECKS_FAILED = "CONTENT_CHECKS_FAILED"
    CONTENT_DEPLOYMENT_FAILED = "CONTENT_DEPLOYMENT_FAILED"
    SITE_CHANGE_VERIFICATION_FAILED = "SITE_CHANGE_VERIFICATION_FAILED"
    GITHUB_CONNECTION_REQUIRED = "GITHUB_CONNECTION_REQUIRED"
    GITHUB_CREDENTIAL_REQUIRED = "GITHUB_CREDENTIAL_REQUIRED"
    PUBLISHING_TARGET_NOT_CONFIGURED = "PUBLISHING_TARGET_NOT_CONFIGURED"
    PROVIDER_WRITES_DISABLED = "PROVIDER_WRITES_DISABLED"
    CONTENT_PR_CLOSED = "CONTENT_PR_CLOSED"
    CONTENT_PR_HEAD_CHANGED = "CONTENT_PR_HEAD_CHANGED"


def blocked_code(safe_error_code: str | None) -> str | None:
    """The typed code for a stopped site change, or None when it is not a known block."""
    if safe_error_code is None:
        return None
    try:
        return SiteChangeCode(safe_error_code).value
    except ValueError:
        return None
