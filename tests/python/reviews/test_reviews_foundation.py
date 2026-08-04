from uuid import uuid4

import pytest

from apps.api.app.ai.gateway import AIGateway, AIGatewayRequest, DeterministicAIProvider
from apps.api.app.products.reviews.errors import UnsafeDraftError
from apps.api.app.products.reviews.service import classify, review_hash, validate_draft


def test_review_ingestion_hash_and_classification_are_deterministic() -> None:
    assert review_hash(1, None, "Injured and need a refund") == review_hash(
        1, None, "Injured and need a refund"
    )
    result = classify("An employee assaulted me and I need a refund", 1)
    assert result["restricted"] is True and {"employee_misconduct", "refund"} <= set(
        result["risks"]
    )


def test_rating_and_sentiment_are_separate() -> None:
    assert classify("Everything was fine", 1)["sentiment"] == "unknown"


def test_unsafe_liability_draft_fails() -> None:
    with pytest.raises(UnsafeDraftError):
        validate_draft("We admit liability and guarantee compensation")


@pytest.mark.anyio
async def test_ai_gateway_requires_grounding_and_preserves_review() -> None:
    gateway = AIGateway(DeterministicAIProvider())
    with pytest.raises(ValueError):
        await gateway.execute(
            AIGatewayRequest(
                uuid4(),
                None,
                "reviews.response_generation",
                {"manual_fallback": "Thanks"},
                (),
                (),
                1000,
                1000,
            )
        )
    result = await gateway.execute(
        AIGatewayRequest(
            uuid4(),
            None,
            "reviews.response_generation",
            {"manual_fallback": "Thank you."},
            (uuid4(),),
            (uuid4(),),
            1000,
            1000,
        )
    )
    assert result["requires_human_review"] is True
