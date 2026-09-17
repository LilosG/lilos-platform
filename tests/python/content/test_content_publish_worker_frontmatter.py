from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from apps.api.app.products.content.frontmatter_contract import FrontmatterContract
from apps.api.app.products.content.publish_handler import _canonical_frontmatter


def test_worker_reconstructs_legacy_coco_maya_publish_metadata() -> None:
    revision = cast(
        Any,
        SimpleNamespace(
            frontmatter={"title": "Happy Hour in Little Italy, San Diego | Coco Maya"},
            body=(
                "# Happy Hour\n\nEnjoy rooftop happy hour in Little Italy with cocktails "
                "and shareable plates."
            ),
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

    canonical = _canonical_frontmatter(
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
