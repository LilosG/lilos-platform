"""Unit coverage for Google Business Profile adapter contracts."""

from typing import Any

import pytest

from apps.api.app.products.gbp.adapter import (
    MYBUSINESS_BASE,
    GoogleBusinessProfileAdapter,
)


class StubGoogleBusinessProfileAdapter(GoogleBusinessProfileAdapter):
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        super().__init__()
        self.pages = list(pages)
        self.calls: list[dict[str, Any]] = []

    async def _request(self, method: str, url: str, token: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"method": method, "url": url, "token": token, **kwargs})
        return self.pages.pop(0)


def _reviews(start: int, count: int) -> list[dict[str, str]]:
    return [{"reviewId": f"review-{index}"} for index in range(start, start + count)]


async def _list_collection(
    adapter: StubGoogleBusinessProfileAdapter, method: str
) -> list[dict[str, Any]]:
    if method == "list_accounts":
        return await adapter.list_accounts("token")
    if method == "list_locations":
        return await adapter.list_locations("token", "accounts/1")
    if method == "list_reviews":
        return await adapter.list_reviews("token", "accounts/1/locations/2")
    return await adapter.list_local_posts("token", "accounts/1/locations/2")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "key"),
    [
        ("list_accounts", "accounts"),
        ("list_locations", "locations"),
        ("list_reviews", "reviews"),
        ("list_local_posts", "localPosts"),
    ],
)
async def test_list_collections_return_empty_terminal_page(method: str, key: str) -> None:
    adapter = StubGoogleBusinessProfileAdapter([{key: []}])

    result = await _list_collection(adapter, method)

    assert result == []
    assert len(adapter.calls) == 1


@pytest.mark.anyio
async def test_list_accounts_retrieves_multiple_pages_at_provider_maximum() -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [
            {"accounts": _reviews(0, 20), "nextPageToken": "accounts-2"},
            {"accounts": _reviews(20, 1)},
        ]
    )

    result = await adapter.list_accounts("token")

    assert len(result) == 21
    assert adapter.calls[0]["params"] == {"pageSize": 20}
    assert adapter.calls[1]["params"] == {"pageSize": 20, "pageToken": "accounts-2"}


@pytest.mark.anyio
async def test_list_locations_retrieves_multiple_pages_at_provider_maximum() -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [
            {"locations": _reviews(0, 100), "nextPageToken": "locations-2"},
            {"locations": _reviews(100, 1)},
        ]
    )

    result = await adapter.list_locations("token", "accounts/1")

    assert len(result) == 101
    assert adapter.calls[0]["params"]["pageSize"] == 100
    assert adapter.calls[1]["params"]["pageToken"] == "locations-2"


@pytest.mark.anyio
async def test_list_local_posts_retrieves_multiple_pages_at_provider_maximum() -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [
            {"localPosts": _reviews(0, 100), "nextPageToken": "posts-2"},
            {"localPosts": _reviews(100, 1)},
        ]
    )

    result = await adapter.list_local_posts("token", "accounts/1/locations/2")

    assert len(result) == 101
    assert adapter.calls[0]["params"] == {"pageSize": 100}
    assert adapter.calls[1]["params"] == {"pageSize": 100, "pageToken": "posts-2"}


@pytest.mark.anyio
async def test_list_reviews_uses_provider_maximum_and_one_page_for_50_reviews() -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [{"reviews": _reviews(0, 50), "totalReviewCount": 50}]
    )

    result = await adapter.list_reviews("token", "accounts/1/locations/2")

    assert len(result) == 50
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["params"] == {"pageSize": 50}


@pytest.mark.anyio
async def test_list_reviews_preserves_provider_reply_moderation_payload() -> None:
    provider_reply = {
        "comment": "Thank you!",
        "updateTime": "2026-08-11T12:00:00Z",
        "reviewReplyState": "REJECTED",
        "policyViolation": "OFF_TOPIC",
    }
    adapter = StubGoogleBusinessProfileAdapter(
        [
            {
                "reviews": [{"reviewId": "review-1", "reviewReply": provider_reply}],
                "totalReviewCount": 1,
            }
        ]
    )

    result = await adapter.list_reviews("token", "accounts/1/locations/2")

    assert result == [{"reviewId": "review-1", "reviewReply": provider_reply}]


@pytest.mark.anyio
async def test_list_reviews_follows_token_and_returns_all_90_in_page_order() -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [
            {"reviews": _reviews(0, 50), "nextPageToken": "page-2", "totalReviewCount": 90},
            {"reviews": _reviews(50, 40), "totalReviewCount": 90},
        ]
    )

    result = await adapter.list_reviews("token", "accounts/1/locations/2")

    assert [review["reviewId"] for review in result] == [f"review-{i}" for i in range(90)]
    assert len(adapter.calls) == 2
    assert adapter.calls[0]["params"] == {"pageSize": 50}
    assert adapter.calls[1]["params"] == {"pageSize": 50, "pageToken": "page-2"}
    assert adapter.calls[1]["url"] == f"{MYBUSINESS_BASE}/accounts/1/locations/2/reviews"


@pytest.mark.anyio
@pytest.mark.parametrize("bad_token", [123, "   "])
async def test_list_reviews_rejects_malformed_token_without_looping(bad_token: object) -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [{"reviews": _reviews(0, 1), "nextPageToken": bad_token}]
    )

    with pytest.raises(ValueError, match="pagination token"):
        await adapter.list_reviews("token", "accounts/1/locations/2")

    assert len(adapter.calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method,key",
    [
        ("list_accounts", "accounts"),
        ("list_locations", "locations"),
        ("list_reviews", "reviews"),
        ("list_local_posts", "localPosts"),
    ],
)
async def test_all_list_collections_reject_malformed_tokens(method: str, key: str) -> None:
    adapter = StubGoogleBusinessProfileAdapter([{key: [], "nextPageToken": "  "}])

    with pytest.raises(ValueError, match="pagination token"):
        await _list_collection(adapter, method)

    assert len(adapter.calls) == 1


@pytest.mark.anyio
async def test_list_reviews_rejects_repeated_token_without_looping() -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [
            {"reviews": _reviews(0, 1), "nextPageToken": "same-token"},
            {"reviews": _reviews(1, 1), "nextPageToken": "same-token"},
        ]
    )

    with pytest.raises(ValueError, match="token repeated"):
        await adapter.list_reviews("token", "accounts/1/locations/2")

    assert len(adapter.calls) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method,key",
    [
        ("list_accounts", "accounts"),
        ("list_locations", "locations"),
        ("list_reviews", "reviews"),
        ("list_local_posts", "localPosts"),
    ],
)
async def test_all_list_collections_reject_repeated_tokens(method: str, key: str) -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [{key: [], "nextPageToken": "same-token"}, {key: [], "nextPageToken": "same-token"}]
    )

    with pytest.raises(ValueError, match="token repeated"):
        await _list_collection(adapter, method)

    assert len(adapter.calls) == 2


@pytest.mark.anyio
async def test_list_reviews_rejects_provider_total_mismatch_as_incomplete() -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [{"reviews": _reviews(0, 50), "totalReviewCount": 90}]
    )

    with pytest.raises(ValueError, match="incomplete"):
        await adapter.list_reviews("token", "accounts/1/locations/2")

    assert len(adapter.calls) == 1


@pytest.mark.anyio
async def test_create_local_post_translates_internal_fields_to_google_v4_contract() -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [{"name": "accounts/1/locations/2/localPosts/3", "state": "PROCESSING"}]
    )

    result = await adapter.create_local_post(
        "token",
        "accounts/1/locations/2",
        {
            "languageCode": "en-US",
            "postType": "STANDARD",
            "text": "A grounded post for a local electrician.",
        },
    )

    assert result["name"] == "accounts/1/locations/2/localPosts/3"
    assert adapter.calls[0]["url"] == f"{MYBUSINESS_BASE}/accounts/1/locations/2/localPosts"
    assert adapter.calls[0]["json"] == {
        "languageCode": "en-US",
        "topicType": "STANDARD",
        "summary": "A grounded post for a local electrician.",
    }
    assert "postType" not in adapter.calls[0]["json"]
    assert "text" not in adapter.calls[0]["json"]


@pytest.mark.anyio
async def test_create_local_post_preserves_canonical_google_fields() -> None:
    adapter = StubGoogleBusinessProfileAdapter(
        [{"name": "accounts/1/locations/2/localPosts/4", "state": "LIVE"}]
    )

    await adapter.create_local_post(
        "token",
        "accounts/1/locations/2",
        {
            "topicType": "STANDARD",
            "summary": "Canonical provider body.",
            "callToAction": {"actionType": "LEARN_MORE", "url": "https://example.com"},
        },
    )

    assert adapter.calls[0]["json"] == {
        "topicType": "STANDARD",
        "summary": "Canonical provider body.",
        "callToAction": {"actionType": "LEARN_MORE", "url": "https://example.com"},
    }


@pytest.mark.anyio
async def test_create_local_post_rejects_missing_summary_before_provider_call() -> None:
    adapter = StubGoogleBusinessProfileAdapter([])

    with pytest.raises(ValueError, match="summary is required"):
        await adapter.create_local_post(
            "token",
            "accounts/1/locations/2",
            {"postType": "STANDARD", "text": "   "},
        )

    assert adapter.calls == []
