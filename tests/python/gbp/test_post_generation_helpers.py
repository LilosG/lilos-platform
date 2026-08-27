"""Focused deterministic tests for GBP AI post generation helpers."""

from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.dialects import postgresql

from apps.api.app.products.content.service import GovernedFact
from apps.api.app.products.gbp.post_generation import TASK_KEY, GBPPostGenerationService
from apps.api.app.products.reviews.models import Review, ReviewRevision


def test_target_url_prefers_relevant_service_page() -> None:
    knowledge = {
        "website_knowledge": [
            {
                "url": "https://example.com/ev-charger-installation/",
                "title": "EV Charger Installation",
                "h1": "Home EV Charger Installation",
            },
            {"url": "https://example.com/", "title": "Home"},
        ]
    }

    target = GBPPostGenerationService._select_target_url(
        {"websiteUri": "https://example.com/"},
        knowledge,
        "Customer review praised the EV charger installation",
    )

    assert target == "https://example.com/ev-charger-installation/"


def test_target_url_requires_positive_review_relevance() -> None:
    knowledge = {
        "website_knowledge": [
            {
                "url": "https://example.com/panel-upgrades/",
                "title": "Electrical Panel Upgrades",
                "h1": "Panel Upgrades",
            }
        ]
    }

    target = GBPPostGenerationService._select_target_url(
        {"websiteUri": "https://example.com/"},
        knowledge,
        "Customer review praised recessed kitchen lighting installation",
    )

    assert target is None


def test_clean_draft_is_bounded_and_uses_fallback() -> None:
    assert GBPPostGenerationService._clean_draft("", "Fallback copy") == "Fallback copy"
    assert len(GBPPostGenerationService._clean_draft("x" * 1400, "fallback")) == 1200


def _compiled_unused_review_sql() -> str:
    """Render the unused-review selection statement as PostgreSQL."""
    organization_id = uuid4()
    location_id = uuid4()
    base = (
        select(Review, ReviewRevision)
        .join(
            ReviewRevision,
            and_(
                ReviewRevision.organization_id == Review.organization_id,
                ReviewRevision.review_id == Review.id,
                ReviewRevision.revision_number == Review.current_revision_number,
            ),
        )
        .where(
            Review.organization_id == organization_id,
            Review.location_id == location_id,
            Review.status != "removed",
        )
    )
    statement = GBPPostGenerationService._unused_eligible_review_statement(
        base, organization_id, location_id
    )
    return str(
        statement.compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    )


def test_unused_review_exclusion_is_scoped_to_the_generation_task() -> None:
    """Unrelated AI tasks at the same location must not mark a review as used.

    Regression: the exclusion previously scanned the most recent completed AIExecution
    rows for the location without filtering by task, so review-response, content, and
    SEO executions consumed the window and could make an already-used review eligible
    again -- producing a duplicate post on a live profile.
    """
    sql = _compiled_unused_review_sql()

    assert "ai_task_definitions" in sql
    assert f"= '{TASK_KEY}'" in sql
    assert "NOT (EXISTS" in sql
    assert "->> 'source_review_id'" in sql


def test_unused_review_exclusion_is_not_a_bounded_window() -> None:
    """Eligibility must be resolved in SQL, not by paging a capped candidate list.

    Regression: candidates were capped at the 100 newest reviews and the used-set at 250
    executions, so a location could report exhaustion while unused reviews remained.
    """
    sql = _compiled_unused_review_sql()

    # Exactly one LIMIT -- the single selected row. No inner window over the used-set.
    assert sql.count("LIMIT") == 1
    assert "LIMIT 1" in sql
    assert "ORDER BY reviews.review_created_at DESC" in sql
    # Empty-text revisions are filtered in SQL so LIMIT 1 cannot land on an unusable row.
    assert "btrim" in sql


def test_service_topics_are_ordered_deduplicated_and_bounded() -> None:
    """Ordered candidates let a location post when its top service has no page."""
    governed_facts: list[GovernedFact] = [
        {
            "fact_key": "primary_services",
            "value": ["Panel Upgrades", "EV Chargers"],
            "authority": "client",
            "revision_id": "r1",
        },
        {
            "fact_key": "services",
            "value": ["panel upgrades", "Lighting"],
            "authority": "client",
            "revision_id": "r2",
        },
    ]
    profile: dict[str, object] = {
        "serviceItems": [{"structuredName": "Generator Installation"}, "Lighting"]
    }

    topics = GBPPostGenerationService._service_topics(governed_facts, profile)

    assert topics[0] == "Panel Upgrades"
    assert "EV Chargers" in topics
    assert "Generator Installation" in topics
    # "panel upgrades" and the repeated "Lighting" must not appear twice.
    assert len(topics) == len({topic.casefold() for topic in topics})
    assert len(topics) <= 12


def test_service_topics_empty_when_no_approved_services() -> None:
    """No invented topic when nothing is approved -- the caller must fail closed."""
    assert GBPPostGenerationService._service_topics([], {}) == []


def test_service_fallback_copy_claims_nothing_beyond_the_service() -> None:
    """The manual path must not imply a customer spoke, or invent an offer."""
    copy = GBPPostGenerationService._service_fallback_copy("Amp Electric", "Panel Upgrades")

    assert "Amp Electric" in copy
    assert "Panel Upgrades" in copy
    assert len(copy) <= 1200
    lowered = copy.casefold()
    for invented in ("review", "customer said", "%", "free", "discount", "guarantee", "$"):
        assert invented not in lowered


def test_service_fallback_copy_handles_missing_topic() -> None:
    copy = GBPPostGenerationService._service_fallback_copy("Amp Electric", "   ")

    assert "our services" in copy
