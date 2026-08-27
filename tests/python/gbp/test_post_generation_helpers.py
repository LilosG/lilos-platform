"""Focused deterministic tests for GBP AI post generation helpers."""

from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.dialects import postgresql

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
