"""Content briefs target either an attributed existing page or a new page."""

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from apps.api.app.products.content.enums import ContentTargetKind
from apps.api.app.products.content.errors import (
    ContentNewPageTargetInvalidError,
    ContentSEOTargetMismatchError,
    ContentSEOTargetUnresolvedError,
)
from apps.api.app.products.content.service import ContentService

PAGE_URL = "https://example.invalid/real-page"


def _service(page_url: str | None) -> ContentService:
    service = ContentService()

    async def seo_target(*_args: object) -> tuple[str, Any] | None:
        page = SimpleNamespace(normalized_url=page_url) if page_url else None
        return f"seo-opportunity:{uuid4()}", page

    setattr(service, "_seo_target_for_item", seo_target)  # noqa: B010
    return service


async def _validate(service: ContentService, kind: ContentTargetKind, target: str | None) -> None:
    await service._validate_seo_target_reference(
        cast(Any, None), uuid4(), cast(Any, None), target, target_kind=kind
    )


@pytest.mark.anyio
@pytest.mark.parametrize("target", ["/brunch-guide", "/services/water-heater-repair"])
async def test_new_page_needs_no_attributed_page(target: str) -> None:
    await _validate(_service(None), ContentTargetKind.NEW_PAGE, target)


@pytest.mark.anyio
@pytest.mark.parametrize("target", [None, "", "brunch-guide", "//evil.example", "/"])
async def test_new_page_target_must_be_a_site_path(target: str | None) -> None:
    with pytest.raises(ContentNewPageTargetInvalidError):
        await _validate(_service(None), ContentTargetKind.NEW_PAGE, target)


@pytest.mark.anyio
async def test_existing_page_without_attribution_is_unresolved() -> None:
    with pytest.raises(ContentSEOTargetUnresolvedError):
        await _validate(_service(None), ContentTargetKind.EXISTING_PAGE, "/anything")


@pytest.mark.anyio
async def test_existing_page_with_attribution_must_match_the_page() -> None:
    await _validate(_service(PAGE_URL), ContentTargetKind.EXISTING_PAGE, PAGE_URL)
    with pytest.raises(ContentSEOTargetMismatchError):
        await _validate(_service(PAGE_URL), ContentTargetKind.EXISTING_PAGE, "/other")
