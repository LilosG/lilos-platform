"""Supabase Storage client for private buckets.

Objects are written with the service-role key and read back only through short-lived signed
URLs. Nothing here makes a bucket or an object public.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import Protocol
from urllib.parse import quote

import httpx

from apps.api.app.config import Settings
from apps.api.app.errors import ApiError
from apps.api.app.schemas import ErrorCategory

GBP_MEDIA_BUCKET = "gbp-media"
SIGNED_URL_SECONDS = 15 * 60
LIST_PAGE_SIZE = 100
DELETE_BATCH_SIZE = 100


class StorageNotConfiguredError(ApiError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "STORAGE_NOT_CONFIGURED"
    category = ErrorCategory.SYSTEM
    public_message = "Photo storage is not configured."


class StorageRequestError(ApiError):
    status_code = HTTPStatus.BAD_GATEWAY
    code = "STORAGE_REQUEST_FAILED"
    category = ErrorCategory.SYSTEM
    retryable = True
    public_message = "Photo storage did not accept the request."


class ObjectStorage(Protocol):
    async def put(self, bucket: str, path: str, data: bytes, content_type: str) -> None: ...
    async def delete(self, bucket: str, path: str) -> None: ...
    async def delete_prefix(self, bucket: str, prefix: str) -> int: ...
    async def signed_url(
        self, bucket: str, path: str, expires_in: int = SIGNED_URL_SECONDS
    ) -> str: ...


def _quoted(path: str) -> str:
    return quote(path, safe="/")


@dataclass(slots=True)
class SupabaseObjectStorage:
    base_url: str
    service_key: str
    timeout_seconds: float = 20.0
    client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient

    @property
    def _root(self) -> str:
        return f"{self.base_url.rstrip('/')}/storage/v1"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.service_key}", "apikey": self.service_key}

    async def _send(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        json: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            async with self.client_factory() as client:
                return await client.request(
                    method,
                    url,
                    content=content,
                    json=json,
                    headers={**self._headers, **(headers or {})},
                    timeout=self.timeout_seconds,
                )
        except httpx.HTTPError as error:
            raise StorageRequestError from error

    async def put(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        response = await self._send(
            "POST",
            f"{self._root}/object/{bucket}/{_quoted(path)}",
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "false"},
        )
        if response.status_code >= 400:
            raise StorageRequestError

    async def delete(self, bucket: str, path: str) -> None:
        response = await self._send("DELETE", f"{self._root}/object/{bucket}/{_quoted(path)}")
        if response.status_code >= 400 and response.status_code != HTTPStatus.NOT_FOUND:
            raise StorageRequestError

    async def _list(self, bucket: str, prefix: str) -> list[dict[str, object]]:
        """List one folder level under ``prefix``; a missing prefix is simply empty."""
        entries: list[dict[str, object]] = []
        offset = 0
        while True:
            response = await self._send(
                "POST",
                f"{self._root}/object/list/{bucket}",
                json={
                    "prefix": prefix,
                    "limit": LIST_PAGE_SIZE,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )
            if response.status_code == HTTPStatus.NOT_FOUND:
                return entries
            if response.status_code >= 400:
                raise StorageRequestError
            page = response.json()
            if not isinstance(page, list):
                raise StorageRequestError
            entries.extend(item for item in page if isinstance(item, dict))
            if len(page) < LIST_PAGE_SIZE:
                return entries
            offset += LIST_PAGE_SIZE

    async def delete_prefix(self, bucket: str, prefix: str) -> int:
        """Delete every object under ``prefix`` (a folder path) and return how many went.

        Supabase lists one folder level at a time; an entry without an id is a folder and is
        descended into. An absent bucket, prefix or object counts as already deleted.
        """
        deleted = 0
        pending = [prefix.strip("/")]
        while pending:
            folder = pending.pop()
            files: list[str] = []
            for entry in await self._list(bucket, folder):
                name = entry.get("name")
                if not isinstance(name, str) or not name:
                    continue
                path = f"{folder}/{name}" if folder else name
                if entry.get("id") is None:
                    pending.append(path)
                else:
                    files.append(path)
            for start in range(0, len(files), DELETE_BATCH_SIZE):
                chunk = files[start : start + DELETE_BATCH_SIZE]
                response = await self._send(
                    "DELETE", f"{self._root}/object/{bucket}", json={"prefixes": chunk}
                )
                if response.status_code >= 400 and response.status_code != HTTPStatus.NOT_FOUND:
                    raise StorageRequestError
                deleted += len(chunk)
        return deleted

    async def signed_url(self, bucket: str, path: str, expires_in: int = SIGNED_URL_SECONDS) -> str:
        response = await self._send(
            "POST",
            f"{self._root}/object/sign/{bucket}/{_quoted(path)}",
            json={"expiresIn": expires_in},
        )
        if response.status_code >= 400:
            raise StorageRequestError
        signed = response.json().get("signedURL")
        if not isinstance(signed, str) or not signed.startswith("/"):
            raise StorageRequestError
        return f"{self._root}{signed}"

    async def ensure_bucket(self, bucket: str, *, apply: bool) -> str:
        """Report, and with ``apply`` create, one private bucket. Returns what was found or done."""
        found = await self._send("GET", f"{self._root}/bucket/{bucket}")
        if found.status_code == HTTPStatus.OK:
            return "private" if not found.json().get("public") else "public"
        if not apply:
            return "missing"
        created = await self._send(
            "POST",
            f"{self._root}/bucket",
            json={"id": bucket, "name": bucket, "public": False},
        )
        if created.status_code >= 400:
            raise StorageRequestError
        return "created"


def object_storage(settings: Settings) -> ObjectStorage:
    if settings.supabase_url is None or settings.supabase_service_role_key is None:
        raise StorageNotConfiguredError
    return SupabaseObjectStorage(
        base_url=str(settings.supabase_url),
        service_key=settings.supabase_service_role_key.get_secret_value(),
    )
