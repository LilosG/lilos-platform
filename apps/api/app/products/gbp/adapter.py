"""Narrow Google Business Profile adapter and deterministic contract."""

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

BUSINESS_MANAGE_SCOPE = "https://www.googleapis.com/auth/business.manage"
ACCOUNT_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"
SUPPORTED_READ_MASK = (
    "name,title,storefrontAddress,regularHours,profile,phoneNumbers,categories,websiteUri,openInfo"
)
SUPPORTED_WRITE_FIELDS = frozenset({"profile.description", "regularHours"})


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

    async def list_accounts(self, access_token: str) -> list[dict[str, Any]]:
        return list(
            (await self._request("GET", f"{ACCOUNT_BASE}/accounts", access_token)).get(
                "accounts", []
            )
        )

    async def list_locations(self, access_token: str, account_name: str) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            f"{INFO_BASE}/{account_name}/locations",
            access_token,
            params={"readMask": SUPPORTED_READ_MASK, "pageSize": 100},
        )
        return list(payload.get("locations", []))

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
