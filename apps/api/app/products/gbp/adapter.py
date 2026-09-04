"""Narrow Google Business Profile adapter and deterministic contract."""

from dataclasses import dataclass
from typing import Any, Protocol, cast

import httpx

BUSINESS_MANAGE_SCOPE = "https://www.googleapis.com/auth/business.manage"
ACCOUNT_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"
MYBUSINESS_BASE = "https://mybusiness.googleapis.com/v4"
SUPPORTED_READ_MASK = ",".join(
    [
        "name",
        "title",
        "storefrontAddress",
        "serviceArea",
        "regularHours",
        "specialHours",
        "moreHours",
        "profile",
        "phoneNumbers",
        "categories",
        "websiteUri",
        "openInfo",
        "labels",
        "serviceItems",
    ]
)
SUPPORTED_WRITE_FIELDS = frozenset({"profile.description", "regularHours"})

ACCOUNT_PAGE_SIZE = 20
LOCATION_PAGE_SIZE = 100
REVIEW_PAGE_SIZE = 50
LOCAL_POST_PAGE_SIZE = 100
MAX_PROVIDER_PAGES = 1_000

SUPPORTED_POST_TYPES = frozenset({"STANDARD", "OFFER", "EVENT"})
SUPPORTED_CTA_TYPES = frozenset({"BOOK", "ORDER", "SHOP", "LEARN_MORE", "SIGN_UP", "CALL", "MENU"})
SUPPORTED_MEDIA_FORMATS = frozenset({"PHOTO", "VIDEO"})


class GBPAdapter(Protocol):
    async def list_accounts(self, access_token: str) -> list[dict[str, Any]]: ...
    async def list_locations(
        self, access_token: str, account_name: str
    ) -> list[dict[str, Any]]: ...
    async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]: ...
    async def patch_location(
        self,
        access_token: str,
        location_name: str,
        fields: dict[str, Any],
        update_mask: list[str],
        idempotency_key: str,
    ) -> dict[str, Any]: ...
    async def update_review_reply(
        self, access_token: str, review_name: str, comment: str
    ) -> dict[str, Any]: ...
    async def get_review(self, access_token: str, review_name: str) -> dict[str, Any]: ...
    async def list_reviews(self, access_token: str, location_name: str) -> list[dict[str, Any]]: ...
    async def create_local_post(
        self, access_token: str, location_name: str, post_body: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def get_local_post(self, access_token: str, post_name: str) -> dict[str, Any]: ...
    async def list_local_posts(
        self, access_token: str, location_name: str
    ) -> list[dict[str, Any]]: ...
    async def create_media(
        self, access_token: str, location_name: str, media_item: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def get_media(self, access_token: str, media_name: str) -> dict[str, Any]: ...
    async def delete_media(self, access_token: str, media_name: str) -> None: ...


@dataclass(slots=True)
class GoogleBusinessProfileAdapter:
    timeout_seconds: float = 20.0

    async def _request(self, method: str, url: str, token: str, **kwargs: Any) -> dict[str, Any]:
        extra_headers = kwargs.pop("headers", {})
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.request(
                method,
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "X-Goog-Api-Format-Version": "2",
                    **extra_headers,
                },
                **kwargs,
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("invalid provider response")
        return payload

    @staticmethod
    def _page_items(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
        raw_items = payload.get(key, [])
        if not isinstance(raw_items, list) or not all(isinstance(item, dict) for item in raw_items):
            raise ValueError(f"invalid provider {key} page")
        return cast(list[dict[str, Any]], raw_items)

    @staticmethod
    def _next_page_token(payload: dict[str, Any]) -> str | None:
        raw_token = payload.get("nextPageToken")
        if raw_token is None or raw_token == "":
            return None
        if not isinstance(raw_token, str) or not raw_token.strip():
            raise ValueError("invalid provider pagination token")
        return raw_token

    async def list_accounts(self, access_token: str) -> list[dict[str, Any]]:
        url = f"{ACCOUNT_BASE}/accounts"
        params: dict[str, int | str] = {"pageSize": ACCOUNT_PAGE_SIZE}
        accounts: list[dict[str, Any]] = []
        seen_tokens: set[str] = set()
        for _page_number in range(MAX_PROVIDER_PAGES):
            payload = await self._request("GET", url, access_token, params=params)
            accounts.extend(self._page_items(payload, "accounts"))
            token = self._next_page_token(payload)
            if token is None:
                return accounts
            if token in seen_tokens:
                raise ValueError("provider pagination token repeated")
            seen_tokens.add(token)
            params = {"pageSize": ACCOUNT_PAGE_SIZE, "pageToken": token}
        raise ValueError("provider account pagination exceeded safety limit")

    async def list_locations(self, access_token: str, account_name: str) -> list[dict[str, Any]]:
        url = f"{INFO_BASE}/{account_name}/locations"
        params: dict[str, int | str] = {
            "readMask": SUPPORTED_READ_MASK,
            "pageSize": LOCATION_PAGE_SIZE,
        }
        locations: list[dict[str, Any]] = []
        seen_tokens: set[str] = set()
        for _page_number in range(MAX_PROVIDER_PAGES):
            payload = await self._request("GET", url, access_token, params=params)
            locations.extend(self._page_items(payload, "locations"))
            token = self._next_page_token(payload)
            if token is None:
                return locations
            if token in seen_tokens:
                raise ValueError("provider pagination token repeated")
            seen_tokens.add(token)
            params = {
                "readMask": SUPPORTED_READ_MASK,
                "pageSize": LOCATION_PAGE_SIZE,
                "pageToken": token,
            }
        raise ValueError("provider location pagination exceeded safety limit")

    async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"{INFO_BASE}/{location_name}",
            access_token,
            params={"readMask": SUPPORTED_READ_MASK},
        )

    async def patch_location(
        self,
        access_token: str,
        location_name: str,
        fields: dict[str, Any],
        update_mask: list[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if not update_mask or not set(update_mask) <= SUPPORTED_WRITE_FIELDS:
            raise ValueError("unsupported GBP update field")
        return await self._request(
            "PATCH",
            f"{INFO_BASE}/{location_name}",
            access_token,
            params={"updateMask": ",".join(sorted(update_mask)), "validateOnly": "false"},
            json={"name": location_name, **fields},
            headers={"X-LILOS-Idempotency-Key": idempotency_key},
        )

    async def update_review_reply(
        self, access_token: str, review_name: str, comment: str
    ) -> dict[str, Any]:
        """PUT {review_name}/reply — create or update the owner reply to a review."""
        return await self._request(
            "PUT",
            f"{MYBUSINESS_BASE}/{review_name}/reply",
            access_token,
            json={"comment": comment},
        )

    async def get_review(self, access_token: str, review_name: str) -> dict[str, Any]:
        """GET a single review resource by name (for verification re-read)."""
        return await self._request(
            "GET",
            f"{MYBUSINESS_BASE}/{review_name}",
            access_token,
        )

    async def list_reviews(self, access_token: str, location_name: str) -> list[dict[str, Any]]:
        """List reviews for a location via the legacy My Business v4 API.

        ``location_name`` must be the v4 account-qualified parent
        ``accounts/{accountId}/locations/{locationId}``.  Returns the raw
        ``reviews`` array (each entry has ``name``, ``reviewId``,
        ``starRating``, ``comment``, ``createTime``, ``updateTime``, and any
        provider-owned ``reviewReply`` moderation data). The adapter preserves
        that reply object for the Reviews domain to normalize and reconcile.

        Google caps this endpoint at 50 reviews per page. Follow the provider's
        opaque ``nextPageToken`` until it is absent; that token is the
        authoritative pagination-completion signal. ``totalReviewCount`` is
        informational metadata and can lag the paginated collection, so it
        must not be used to reject an otherwise complete token walk. Repeated,
        malformed, and unbounded token sequences still fail closed.
        """
        url = f"{MYBUSINESS_BASE}/{location_name}/reviews"
        params: dict[str, int | str] = {"pageSize": REVIEW_PAGE_SIZE}
        reviews: list[dict[str, Any]] = []
        seen_tokens: set[str] = set()

        for _page_number in range(MAX_PROVIDER_PAGES):
            payload = await self._request("GET", url, access_token, params=params)
            reviews.extend(self._page_items(payload, "reviews"))

            token = self._next_page_token(payload)
            if token is None:
                return reviews
            if token in seen_tokens:
                raise ValueError("provider review pagination token repeated")
            seen_tokens.add(token)
            params = {"pageSize": REVIEW_PAGE_SIZE, "pageToken": token}

        raise ValueError("provider review pagination exceeded safety limit")

    @staticmethod
    def _local_post_provider_body(post_body: dict[str, Any]) -> dict[str, Any]:
        """Translate the LILOs Local Post contract to Google's v4 wire schema."""
        raw_post_type = post_body.get("topicType", post_body.get("postType"))
        post_type = str(raw_post_type or "").upper()
        if post_type not in SUPPORTED_POST_TYPES:
            raise ValueError(f"unsupported GBP post type: {raw_post_type}")

        raw_summary = post_body.get("summary", post_body.get("text"))
        if not isinstance(raw_summary, str) or not raw_summary.strip():
            raise ValueError("GBP Local Post summary is required")

        provider_body = {
            key: value
            for key, value in post_body.items()
            if key not in {"postType", "text", "topicType", "summary"}
        }
        provider_body["topicType"] = post_type
        provider_body["summary"] = raw_summary

        cta = provider_body.get("callToAction")
        if cta is not None:
            if not isinstance(cta, dict):
                raise ValueError("invalid GBP CTA payload")
            cta_type = cta.get("actionType")
            if cta_type not in SUPPORTED_CTA_TYPES:
                raise ValueError(f"unsupported GBP CTA action type: {cta_type}")

        return provider_body

    async def create_local_post(
        self, access_token: str, location_name: str, post_body: dict[str, Any]
    ) -> dict[str, Any]:
        """POST {location_name}/localPosts using Google's canonical LocalPost fields."""
        provider_body = self._local_post_provider_body(post_body)
        return await self._request(
            "POST",
            f"{MYBUSINESS_BASE}/{location_name}/localPosts",
            access_token,
            json=provider_body,
        )

    async def get_local_post(self, access_token: str, post_name: str) -> dict[str, Any]:
        """GET a single Local Post resource by name (for verification re-read)."""
        return await self._request(
            "GET",
            f"{MYBUSINESS_BASE}/{post_name}",
            access_token,
        )

    async def list_local_posts(self, access_token: str, location_name: str) -> list[dict[str, Any]]:
        """List Local Posts for a location (for reconciliation)."""
        url = f"{MYBUSINESS_BASE}/{location_name}/localPosts"
        params: dict[str, int | str] = {"pageSize": LOCAL_POST_PAGE_SIZE}
        posts: list[dict[str, Any]] = []
        seen_tokens: set[str] = set()
        for _page_number in range(MAX_PROVIDER_PAGES):
            payload = await self._request("GET", url, access_token, params=params)
            posts.extend(self._page_items(payload, "localPosts"))
            token = self._next_page_token(payload)
            if token is None:
                return posts
            if token in seen_tokens:
                raise ValueError("provider pagination token repeated")
            seen_tokens.add(token)
            params = {"pageSize": LOCAL_POST_PAGE_SIZE, "pageToken": token}
        raise ValueError("provider local post pagination exceeded safety limit")

    async def create_media(
        self, access_token: str, location_name: str, media_item: dict[str, Any]
    ) -> dict[str, Any]:
        """POST {location_name}/media — upload a photo or video to a location."""
        media_format = media_item.get("mediaFormat")
        if media_format not in SUPPORTED_MEDIA_FORMATS:
            raise ValueError(f"unsupported GBP media format: {media_format}")
        return await self._request(
            "POST",
            f"{MYBUSINESS_BASE}/{location_name}/media",
            access_token,
            json=media_item,
        )

    async def get_media(self, access_token: str, media_name: str) -> dict[str, Any]:
        """GET a single media resource by name (for verification re-read)."""
        return await self._request(
            "GET",
            f"{MYBUSINESS_BASE}/{media_name}",
            access_token,
        )

    async def delete_media(self, access_token: str, media_name: str) -> None:
        """DELETE a media resource by name."""
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.request(
                "DELETE",
                f"{MYBUSINESS_BASE}/{media_name}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "X-Goog-Api-Format-Version": "2",
                },
            )
        response.raise_for_status()
