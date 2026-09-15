from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from apps.api.app.products.content.operator_service import ContentOperatorService


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
