"""Deterministic delivery and verification contract for governed GBP posts.

The approved GBP post revision remains the source of truth for copy, CTA, and
post type. ``publication_requirements`` records which parts of that approved
revision are mandatory for external delivery. Provider acceptance is not
verification: a post is verified only when Google re-reads the required
content, CTA, and media.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from apps.api.app.products.gbp.adapter import SUPPORTED_CTA_TYPES, SUPPORTED_POST_TYPES

CONTRACT_VERSION = 1


class GBPPostPublicationContractError(ValueError):
    """A deterministic, secret-free contract validation failure."""

    def __init__(self, safe_code: str, message: str) -> None:
        self.safe_code = safe_code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class GBPPostDeliveryRequirements:
    """Server-owned publication requirements persisted on an immutable revision."""

    version: int | None
    media_required: bool
    cta_required: bool

    @property
    def governed(self) -> bool:
        return self.version == CONTRACT_VERSION

    @classmethod
    def from_document(cls, document: object) -> GBPPostDeliveryRequirements:
        if not isinstance(document, dict) or not document:
            return cls(version=None, media_required=False, cta_required=False)
        raw_version = document.get("version")
        if raw_version != CONTRACT_VERSION:
            raise GBPPostPublicationContractError(
                "POST_DELIVERY_CONTRACT_UNSUPPORTED",
                "The approved GBP post uses an unsupported publication contract version.",
            )
        return cls(
            version=CONTRACT_VERSION,
            media_required=document.get("media_required") is True,
            cta_required=document.get("cta_required") is True,
        )


def build_provider_post_body(
    *,
    post_type: str,
    content: str,
    call_to_action: dict[str, object] | None,
    event_or_offer: dict[str, object] | None,
    requirements: GBPPostDeliveryRequirements,
    media_url: str | None,
) -> dict[str, Any]:
    """Build the internal adapter payload from the approved immutable revision."""
    normalized_type = post_type.upper()
    if normalized_type not in SUPPORTED_POST_TYPES:
        raise GBPPostPublicationContractError(
            "POST_TYPE_UNSUPPORTED",
            "The approved GBP post type is not supported by the provider adapter.",
        )
    if not content.strip():
        raise GBPPostPublicationContractError(
            "POST_CONTENT_MISSING",
            "The approved GBP post has no publishable content.",
        )

    body: dict[str, Any] = {
        "languageCode": "en-US",
        "postType": normalized_type,
        "text": content,
    }

    if requirements.cta_required and not call_to_action:
        raise GBPPostPublicationContractError(
            "POST_CTA_REQUIRED_MISSING",
            "The approved GBP post requires a client-owned call to action.",
        )
    if call_to_action:
        action_type = str(call_to_action.get("actionType") or "").upper()
        target_url = str(call_to_action.get("url") or "").strip()
        if action_type not in SUPPORTED_CTA_TYPES:
            raise GBPPostPublicationContractError(
                "POST_CTA_UNSUPPORTED",
                "The approved GBP call-to-action type is not supported.",
            )
        if action_type != "CALL" and not target_url:
            raise GBPPostPublicationContractError(
                "POST_CTA_URL_MISSING",
                "The approved GBP call to action requires a destination URL.",
            )
        body["callToAction"] = {**call_to_action, "actionType": action_type}

    if requirements.media_required and not media_url:
        raise GBPPostPublicationContractError(
            "POST_MEDIA_REQUIRED_MISSING",
            "The approved GBP post requires media but no provider-fetchable image is available.",
        )
    if media_url:
        body["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": media_url}]

    if event_or_offer:
        if normalized_type == "EVENT":
            body["event"] = event_or_offer
        elif normalized_type == "OFFER":
            body["offer"] = event_or_offer

    return body


def verify_provider_post(
    provider_post: dict[str, Any],
    *,
    post_type: str,
    content: str,
    call_to_action: dict[str, object] | None,
    requirements: GBPPostDeliveryRequirements,
) -> str | None:
    """Return a safe mismatch code, or ``None`` when provider truth matches approval."""
    if not requirements.governed:
        # Rows approved before the versioned contract existed retain their
        # historical LIVE-only acceptance behavior. New automated revisions
        # always carry version 1 and are fully verified below.
        return None

    provider_type = str(
        provider_post.get("topicType") or provider_post.get("postType") or ""
    ).upper()
    if provider_type != post_type.upper():
        return "POST_TYPE_MISMATCH"

    provider_summary = str(provider_post.get("summary") or provider_post.get("text") or "").strip()
    if provider_summary != content.strip():
        return "POST_CONTENT_MISMATCH"

    if requirements.cta_required:
        expected = call_to_action or {}
        actual = provider_post.get("callToAction")
        if not isinstance(actual, dict):
            return "POST_CTA_MISMATCH"
        expected_type = str(expected.get("actionType") or "").upper()
        actual_type = str(actual.get("actionType") or "").upper()
        if expected_type != actual_type:
            return "POST_CTA_MISMATCH"
        if expected_type != "CALL" and _normalized_url(
            str(expected.get("url") or "")
        ) != _normalized_url(str(actual.get("url") or "")):
            return "POST_CTA_MISMATCH"

    if requirements.media_required:
        media = provider_post.get("media")
        if not isinstance(media, list) or not any(
            isinstance(item, dict) and str(item.get("mediaFormat") or "").upper() == "PHOTO"
            for item in media
        ):
            return "POST_MEDIA_MISSING"

    return None


def _normalized_url(value: str) -> str:
    """Normalize only provider-irrelevant URL presentation differences."""
    value = value.strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return value
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))
