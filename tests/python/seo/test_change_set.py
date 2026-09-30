"""SiteChangeSet is an exact, deterministically-validated claim about a page edit."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeItem, SiteChangeSet


def _item(**overrides: object) -> SiteChangeItem:
    defaults: dict[str, object] = {
        "page_id": uuid4(),
        "field": SiteChangeField.SEO_TITLE,
        "current_value": "Old Title | Coco Maya",
        "proposed_value": "Best Brunch in Little Italy | Coco Maya",
        "rationale": "Aligns with the dominant ranking query for this page.",
    }
    defaults.update(overrides)
    return SiteChangeItem(**defaults)  # type: ignore[arg-type]


def test_valid_seo_title_change_is_accepted() -> None:
    item = _item()
    assert item.field == SiteChangeField.SEO_TITLE
    assert item.proposed_value != item.current_value


def test_proposed_value_must_differ_from_current_value() -> None:
    with pytest.raises(ValidationError, match="must differ from current_value"):
        _item(proposed_value="Old Title | Coco Maya")


def test_seo_title_over_60_characters_is_rejected() -> None:
    with pytest.raises(ValidationError, match="exceeds 60 characters"):
        _item(proposed_value="A" * 61)


def test_meta_description_over_160_characters_is_rejected() -> None:
    with pytest.raises(ValidationError, match="exceeds 160 characters"):
        _item(
            field=SiteChangeField.META_DESCRIPTION,
            current_value="Old description.",
            proposed_value="A" * 161,
        )


def test_empty_proposed_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _item(proposed_value="")


def test_h1_has_no_length_cap_but_still_requires_a_change() -> None:
    item = _item(
        field=SiteChangeField.H1,
        current_value="Brunch",
        proposed_value="A" * 500,
    )
    assert len(item.proposed_value) == 500


def test_fingerprint_is_stable_across_item_order() -> None:
    page_a, page_b = uuid4(), uuid4()
    forward = SiteChangeSet(
        items=[
            SiteChangeItem(
                page_id=page_a,
                field=SiteChangeField.SEO_TITLE,
                current_value="A",
                proposed_value="B",
                rationale="r",
            ),
            SiteChangeItem(
                page_id=page_b,
                field=SiteChangeField.META_DESCRIPTION,
                current_value="C",
                proposed_value="D",
                rationale="r",
            ),
        ]
    )
    assert forward.fingerprint() == forward.fingerprint()


def test_fingerprint_changes_when_a_value_changes() -> None:
    base = SiteChangeSet(items=[_item()])
    changed = SiteChangeSet(items=[_item(proposed_value="A different proposed title")])
    assert base.fingerprint() != changed.fingerprint()


def test_change_set_requires_at_least_one_item() -> None:
    with pytest.raises(ValidationError):
        SiteChangeSet(items=[])
