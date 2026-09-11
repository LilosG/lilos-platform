from apps.api.app.products.gbp.post_strategy import (
    GOOGLE_REVIEW_SOURCE,
    SERVICE_KNOWLEDGE_SOURCE,
    GBPPostDiversityGateway,
    StrategicGBPPostGenerationService,
)


def test_automated_source_starts_with_business_topic() -> None:
    assert (
        StrategicGBPPostGenerationService.select_automated_source_type([], review_available=True)
        == SERVICE_KNOWLEDGE_SOURCE
    )


def test_automated_source_never_runs_reviews_back_to_back() -> None:
    assert (
        StrategicGBPPostGenerationService.select_automated_source_type(
            [GOOGLE_REVIEW_SOURCE, SERVICE_KNOWLEDGE_SOURCE],
            review_available=True,
        )
        == SERVICE_KNOWLEDGE_SOURCE
    )


def test_automated_source_uses_review_when_recent_mix_is_service_heavy() -> None:
    assert (
        StrategicGBPPostGenerationService.select_automated_source_type(
            [
                SERVICE_KNOWLEDGE_SOURCE,
                SERVICE_KNOWLEDGE_SOURCE,
                GOOGLE_REVIEW_SOURCE,
            ],
            review_available=True,
        )
        == GOOGLE_REVIEW_SOURCE
    )


def test_automated_source_keeps_review_share_at_or_below_half() -> None:
    assert (
        StrategicGBPPostGenerationService.select_automated_source_type(
            [
                SERVICE_KNOWLEDGE_SOURCE,
                GOOGLE_REVIEW_SOURCE,
                GOOGLE_REVIEW_SOURCE,
                SERVICE_KNOWLEDGE_SOURCE,
            ],
            review_available=True,
        )
        == SERVICE_KNOWLEDGE_SOURCE
    )


def test_automated_source_uses_business_topic_when_no_review_is_available() -> None:
    assert (
        StrategicGBPPostGenerationService.select_automated_source_type(
            [SERVICE_KNOWLEDGE_SOURCE],
            review_available=False,
        )
        == SERVICE_KNOWLEDGE_SOURCE
    )


def test_legacy_execution_provenance_is_classified() -> None:
    assert (
        StrategicGBPPostGenerationService.infer_source_type({"source_review_id": "review-id"})
        == GOOGLE_REVIEW_SOURCE
    )
    assert (
        StrategicGBPPostGenerationService.infer_source_type({"source_service_topic": "Brunch"})
        == SERVICE_KNOWLEDGE_SOURCE
    )
    assert StrategicGBPPostGenerationService.infer_source_type({}) is None


def test_review_strategy_forbids_repetitive_guest_story_openers() -> None:
    instructions = GBPPostDiversityGateway.strategy_instructions(GOOGLE_REVIEW_SOURCE)

    assert "supporting evidence" in instructions
    assert "Do not begin with 'one guest'" in instructions
    assert "opening construction" in instructions


def test_business_topic_strategy_forbids_fabricated_testimonials() -> None:
    instructions = GBPPostDiversityGateway.strategy_instructions(SERVICE_KNOWLEDGE_SOURCE)

    assert "selected business topic" in instructions
    assert "Do not manufacture testimonial language" in instructions
