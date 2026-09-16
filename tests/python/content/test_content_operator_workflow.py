from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from apps.api.app.products.content.frontmatter_contract import FrontmatterContract
from apps.api.app.products.content.operator_service import ContentOperatorService


LEGACY_BODY = (
    "# Happy Hour\n\n"
    "Enjoy rooftop happy hour in Little Italy with cocktails and shareable plates."
)


def _item(**overrides: object) -> Any:
    values: dict[str, object] = {
        "id": uuid4(),
        "location_id": None,
        "content_type": "blog",
        "title": "Happy Hour in Little Italy",
        "slug": "happy-hour-little-italy",
        "status": "reviewing",
        "published_at": None,
    }
    values.update(overrides)
    return cast(Any, SimpleNamespace(**values))


def _revision(status: str = "approved") -> Any:
    return cast(
        Any,
        SimpleNamespace(status=status, revision_number=4),
    )


def _publication(status: str) -> Any:
    return cast(Any, SimpleNamespace(status=status))


def test_approved_revision_overrides_stale_reviewing_item_state() -> None:
    summary = ContentOperatorService._summary(_item(), _revision(), None)

    assert summary["stage"] == "ready_to_publish"
    assert summary["next_action"] == {
        "key": "publish",
        "label": "Publish to website",
    }


def test_publication_truth_overrides_revision_state() -> None:
    summary = ContentOperatorService._summary(
        _item(),
        _revision(),
        _publication("checks_running"),
    )

    assert summary["stage"] == "publishing"
    assert cast(dict[str, str], summary["next_action"])["key"] == "wait"


def test_verified_publication_is_the_only_success_terminal_state() -> None:
    summary = ContentOperatorService._summary(
        _item(status="publishing"),
        _revision("published"),
        _publication("verified"),
    )

    assert summary["stage"] == "published"
    assert cast(dict[str, str], summary["next_action"])["key"] == "view"


def test_failed_publication_surfaces_operator_attention() -> None:
    summary = ContentOperatorService._summary(
        _item(status="publishing"),
        _revision(),
        _publication("reconciliation_required"),
    )

    assert summary["stage"] == "needs_attention"
    assert cast(dict[str, str], summary["next_action"])["key"] == "review_publication"


def test_exhausted_publication_job_never_displays_as_publishing_forever() -> None:
    summary = ContentOperatorService._summary(
        _item(status="publishing"),
        _revision(),
        _publication("deployment_pending"),
        "dead_lettered",
    )
    assert summary["stage"] == "needs_attention"
    assert summary["publication_job_status"] == "dead_lettered"


def test_legacy_approved_revision_gets_all_deterministic_publish_metadata() -> None:
    revision = cast(
        Any,
        SimpleNamespace(
            frontmatter={
                "title": "Happy Hour in Little Italy, San Diego | Coco Maya",
            },
            body=LEGACY_BODY,
            created_at=datetime(2026, 9, 16, 17, 45, tzinfo=UTC),
        ),
    )
    contract = FrontmatterContract.from_document(
        {
            "field_names": {
                "publish_date": "date",
                "image_alt": "imageAlt",
                "seo_title": "seoTitle",
            },
            "required": ["title", "seoTitle", "description", "date", "image", "imageAlt"],
            "file_extensions": [".mdx"],
        }
    )

    canonical = ContentOperatorService._canonical_for_publish(
        revision,
        {
            "image": "/images/hh-chefs-wim-pizza.webp",
            "image_alt": "happy hour at Coco Maya in Little Italy",
        },
    )
    rendered = contract.render(canonical)

    assert contract.missing_required(rendered) == ()
    assert rendered["seoTitle"] == "Happy Hour in Little Italy, San Diego | Coco Maya"
    assert rendered["description"] == (
        "Enjoy rooftop happy hour in Little Italy with cocktails and shareable plates."
    )
    assert rendered["date"] == "2026-09-16"
    assert rendered["image"] == "/images/hh-chefs-wim-pizza.webp"
    assert rendered["imageAlt"] == "happy hour at Coco Maya in Little Italy"


def test_legacy_coco_maya_requirements_only_request_operator_image_fields() -> None:
    revision = cast(
        Any,
        SimpleNamespace(
            frontmatter={
                "title": "Happy Hour in Little Italy, San Diego | Coco Maya",
            },
            body=LEGACY_BODY,
            created_at=datetime(2026, 9, 16, 17, 45, tzinfo=UTC),
        ),
    )
    target = cast(
        Any,
        SimpleNamespace(
            id=uuid4(),
            frontmatter_contract={
                "field_names": {
                    "publish_date": "date",
                    "image_alt": "imageAlt",
                    "seo_title": "seoTitle",
                },
                "required": [
                    "title",
                    "seoTitle",
                    "description",
                    "date",
                    "image",
                    "imageAlt",
                ],
                "file_extensions": [".mdx"],
            },
        ),
    )

    requirements = ContentOperatorService._requirements(target, revision)

    assert requirements["missing"] == ["image", "imageAlt"]
    assert requirements["requires_image"] is True
    assert requirements["requires_image_alt"] is True
