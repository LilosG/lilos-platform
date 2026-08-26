"""Contract tests for governed GBP Local Post delivery and provider verification."""

import pytest

from apps.api.app.products.gbp.post_publication_contract import (
    GBPPostDeliveryRequirements,
    GBPPostPublicationContractError,
    build_provider_post_body,
    verify_provider_post,
)


def _governed() -> GBPPostDeliveryRequirements:
    return GBPPostDeliveryRequirements.from_document(
        {"version": 1, "cta_required": True, "media_required": True}
    )


def test_governed_contract_requires_cta_before_provider_dispatch() -> None:
    with pytest.raises(GBPPostPublicationContractError) as exc_info:
        build_provider_post_body(
            post_type="STANDARD",
            content="Panel upgrade planning for Carlsbad homeowners.",
            call_to_action=None,
            event_or_offer=None,
            requirements=_governed(),
            media_url="https://api.example.invalid/provider-media/image-token",
        )

    assert exc_info.value.safe_code == "POST_CTA_REQUIRED_MISSING"


def test_governed_contract_requires_media_before_provider_dispatch() -> None:
    with pytest.raises(GBPPostPublicationContractError) as exc_info:
        build_provider_post_body(
            post_type="STANDARD",
            content="Panel upgrade planning for Carlsbad homeowners.",
            call_to_action={"actionType": "LEARN_MORE", "url": "https://example.com/panels/"},
            event_or_offer=None,
            requirements=_governed(),
            media_url=None,
        )

    assert exc_info.value.safe_code == "POST_MEDIA_REQUIRED_MISSING"


def test_governed_contract_builds_exact_media_and_cta_payload() -> None:
    body = build_provider_post_body(
        post_type="standard",
        content="Panel upgrade planning for Carlsbad homeowners.",
        call_to_action={"actionType": "learn_more", "url": "https://example.com/panels/"},
        event_or_offer=None,
        requirements=_governed(),
        media_url="https://api.example.invalid/provider-media/image-token",
    )

    assert body == {
        "languageCode": "en-US",
        "postType": "STANDARD",
        "text": "Panel upgrade planning for Carlsbad homeowners.",
        "callToAction": {
            "actionType": "LEARN_MORE",
            "url": "https://example.com/panels/",
        },
        "media": [
            {
                "mediaFormat": "PHOTO",
                "sourceUrl": "https://api.example.invalid/provider-media/image-token",
            }
        ],
    }


def test_live_provider_post_verifies_only_when_governed_payload_matches() -> None:
    mismatch = verify_provider_post(
        {
            "state": "LIVE",
            "topicType": "STANDARD",
            "summary": "Panel upgrade planning for Carlsbad homeowners.",
            "callToAction": {
                "actionType": "LEARN_MORE",
                "url": "https://example.com/panels",
            },
            "media": [{"mediaFormat": "PHOTO", "googleUrl": "https://google.example/photo"}],
        },
        post_type="STANDARD",
        content="Panel upgrade planning for Carlsbad homeowners.",
        call_to_action={"actionType": "LEARN_MORE", "url": "https://example.com/panels/"},
        requirements=_governed(),
    )

    assert mismatch is None


def test_live_provider_post_missing_media_is_not_verified() -> None:
    mismatch = verify_provider_post(
        {
            "state": "LIVE",
            "topicType": "STANDARD",
            "summary": "Panel upgrade planning for Carlsbad homeowners.",
            "callToAction": {
                "actionType": "LEARN_MORE",
                "url": "https://example.com/panels/",
            },
            "media": [],
        },
        post_type="STANDARD",
        content="Panel upgrade planning for Carlsbad homeowners.",
        call_to_action={"actionType": "LEARN_MORE", "url": "https://example.com/panels/"},
        requirements=_governed(),
    )

    assert mismatch == "POST_MEDIA_MISSING"


def test_live_provider_post_wrong_cta_is_not_verified() -> None:
    mismatch = verify_provider_post(
        {
            "state": "LIVE",
            "topicType": "STANDARD",
            "summary": "Panel upgrade planning for Carlsbad homeowners.",
            "callToAction": {
                "actionType": "LEARN_MORE",
                "url": "https://example.net/wrong-page/",
            },
            "media": [{"mediaFormat": "PHOTO"}],
        },
        post_type="STANDARD",
        content="Panel upgrade planning for Carlsbad homeowners.",
        call_to_action={"actionType": "LEARN_MORE", "url": "https://example.com/panels/"},
        requirements=_governed(),
    )

    assert mismatch == "POST_CTA_MISMATCH"


def test_live_provider_post_wrong_content_is_not_verified() -> None:
    mismatch = verify_provider_post(
        {
            "state": "LIVE",
            "topicType": "STANDARD",
            "summary": "Different provider content.",
            "callToAction": {
                "actionType": "LEARN_MORE",
                "url": "https://example.com/panels/",
            },
            "media": [{"mediaFormat": "PHOTO"}],
        },
        post_type="STANDARD",
        content="Panel upgrade planning for Carlsbad homeowners.",
        call_to_action={"actionType": "LEARN_MORE", "url": "https://example.com/panels/"},
        requirements=_governed(),
    )

    assert mismatch == "POST_CONTENT_MISMATCH"


def test_legacy_revision_keeps_pre_contract_verification_semantics() -> None:
    requirements = GBPPostDeliveryRequirements.from_document({})

    assert requirements.governed is False
    assert (
        verify_provider_post(
            {"state": "LIVE"},
            post_type="STANDARD",
            content="Historical post",
            call_to_action=None,
            requirements=requirements,
        )
        is None
    )


def test_unknown_contract_version_fails_closed() -> None:
    with pytest.raises(GBPPostPublicationContractError) as exc_info:
        GBPPostDeliveryRequirements.from_document(
            {"version": 2, "cta_required": True, "media_required": True}
        )

    assert exc_info.value.safe_code == "POST_DELIVERY_CONTRACT_UNSUPPORTED"
