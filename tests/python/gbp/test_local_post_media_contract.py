"""Focused contract coverage for GBP Local Post media and CTA payloads."""

from typing import Any

import pytest

from apps.api.app.products.gbp.adapter import GoogleBusinessProfileAdapter


class _StubAdapter(GoogleBusinessProfileAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.request_json: dict[str, Any] | None = None

    async def _request(
        self,
        method: str,
        url: str,
        access_token: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        del method, url, access_token
        self.request_json = kwargs.get("json")
        return {
            "name": "accounts/1/locations/2/localPosts/3",
            "state": "PROCESSING",
        }


@pytest.mark.anyio
async def test_local_post_preserves_media_and_cta_for_google() -> None:
    adapter = _StubAdapter()
    source_url = "https://lilos-api.onrender.com/api/v1/provider-media/google-drive/signed-token"
    target_url = "https://wheylandelectric.com/electrical-panel-upgrades/"

    await adapter.create_local_post(
        "token",
        "accounts/1/locations/2",
        {
            "postType": "STANDARD",
            "text": "Electrical panel upgrade planning for Carlsbad homeowners.",
            "media": [{"mediaFormat": "PHOTO", "sourceUrl": source_url}],
            "callToAction": {"actionType": "LEARN_MORE", "url": target_url},
        },
    )

    assert adapter.request_json == {
        "topicType": "STANDARD",
        "summary": "Electrical panel upgrade planning for Carlsbad homeowners.",
        "media": [{"mediaFormat": "PHOTO", "sourceUrl": source_url}],
        "callToAction": {"actionType": "LEARN_MORE", "url": target_url},
    }
