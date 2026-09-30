"""Post-deploy read-back: does production serve what was approved?"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeItem, SiteChangeSet
from apps.api.app.products.seo.verification import (
    LivePage,
    fetch_live_page,
    verify_live_site_change,
)

PAGE_ID = uuid4()


def change_set(*fields: SiteChangeField) -> SiteChangeSet:
    proposed = {
        SiteChangeField.SEO_TITLE: "Best Brunch in San Diego | Coco Maya",
        SiteChangeField.META_DESCRIPTION: "Daily brunch with a patio & craft cocktails.",
        SiteChangeField.SCHEMA: '{"@type": "Restaurant"}',
    }
    return SiteChangeSet(
        items=[
            SiteChangeItem(
                page_id=PAGE_ID,
                field=field,
                current_value="old value",
                proposed_value=proposed[field],
                rationale="test",
            )
            for field in fields
        ]
    )


def page(title: str, description: str, status: int = 200) -> LivePage:
    html = (
        f"<html><head><title>{title}</title>"
        f'<meta name="description" content="{description}"></head><body><h1>Hi</h1></body></html>'
    )
    return LivePage(url="https://coco.example.invalid/brunch", http_status=status, html=html)


def test_live_verification_confirms_changed_values() -> None:
    proof = verify_live_site_change(
        change_set(SiteChangeField.SEO_TITLE, SiteChangeField.META_DESCRIPTION),
        # HTML-escaped ampersand and stray whitespace are the same text to a visitor.
        {
            PAGE_ID: page(
                "Best Brunch in San Diego |  Coco Maya",
                "Daily brunch with a patio &amp; craft cocktails.",
            )
        },
    )

    assert proof["result"] == "verified"
    checks = proof["checks"]
    assert isinstance(checks, list)
    assert [check["state"] for check in checks] == ["verified", "verified"]


def test_live_verification_mismatch_reports_observed_value() -> None:
    proof = verify_live_site_change(
        change_set(SiteChangeField.SEO_TITLE, SiteChangeField.META_DESCRIPTION),
        {PAGE_ID: page("The Old Title", "Daily brunch with a patio & craft cocktails.")},
    )

    assert proof["result"] == "failed"
    checks = proof["checks"]
    assert isinstance(checks, list)
    title = checks[0]
    assert title["state"] == "mismatch"
    assert title["expected"] == "Best Brunch in San Diego | Coco Maya"
    assert title["observed"] == "The Old Title"
    assert checks[1]["state"] == "verified"


def test_unreadable_page_is_unavailable_not_verified_or_failed() -> None:
    down = LivePage(
        url="https://coco.example.invalid/brunch", http_status=None, html=None, error="ConnectError"
    )
    proof = verify_live_site_change(change_set(SiteChangeField.SEO_TITLE), {PAGE_ID: down})
    assert proof["result"] == "unavailable"

    missing = page("x", "y", status=404)
    assert (
        verify_live_site_change(change_set(SiteChangeField.SEO_TITLE), {PAGE_ID: missing})["result"]
        == "unavailable"
    )
    assert (
        verify_live_site_change(change_set(SiteChangeField.SEO_TITLE), {})["result"]
        == "unavailable"
    )


def test_a_mismatch_outranks_an_unreadable_page() -> None:
    other = uuid4()
    cs = SiteChangeSet(
        items=[
            *change_set(SiteChangeField.SEO_TITLE).items,
            SiteChangeItem(
                page_id=other,
                field=SiteChangeField.SEO_TITLE,
                current_value="a",
                proposed_value="b",
                rationale="t",
            ),
        ]
    )
    proof = verify_live_site_change(cs, {PAGE_ID: page("Wrong", "d")})
    assert proof["result"] == "failed"


def test_fields_the_read_back_cannot_prove_are_never_reported_verified() -> None:
    proof = verify_live_site_change(
        change_set(SiteChangeField.SEO_TITLE, SiteChangeField.SCHEMA),
        {PAGE_ID: page("Best Brunch in San Diego | Coco Maya", "d")},
    )

    checks = proof["checks"]
    assert isinstance(checks, list)
    assert [check["state"] for check in checks] == ["verified", "not_checked"]
    assert proof["result"] == "verified"
    assert proof["limitations"] == ["schema is applied but cannot be read back from the live page."]


@pytest.mark.anyio
async def test_fetch_live_page_busts_cdn_cache_and_reports_errors() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/down":
            raise httpx.ConnectError("boom")
        return httpx.Response(200, text="<title>ok</title>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        ok = await fetch_live_page(
            "https://x.example.invalid/brunch", cache_buster="abc", client=client
        )
        down = await fetch_live_page(
            "https://x.example.invalid/down", cache_buster="abc", client=client
        )

    assert ok.http_status == 200 and ok.html == "<title>ok</title>"
    assert seen[0].url.params["lilos_verify"] == "abc"
    assert down.http_status is None and down.html is None and down.error == "ConnectError"
