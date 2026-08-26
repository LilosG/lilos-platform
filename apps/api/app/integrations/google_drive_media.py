"""Read-only Google Drive image discovery and signed provider-media proxy URLs.

The service account is used only to read files that have already been shared
with it. A short-lived signed URL lets Google Business Profile fetch a selected
image without making the underlying Drive file public.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import jwt

from apps.api.app.config import Settings

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DRIVE_FILES_ENDPOINT = "https://www.googleapis.com/drive/v3/files"


@dataclass(frozen=True, slots=True)
class DriveImage:
    file_id: str
    name: str
    mime_type: str
    path: str
    modified_time: str | None


@dataclass(slots=True)
class GoogleDriveMediaService:
    timeout_seconds: float = 30.0

    async def discover_images(
        self,
        settings: Settings,
        organization_name: str,
        *,
        limit: int = 25,
    ) -> list[DriveImage]:
        """Return images only from a Drive folder tree matching the organization.

        The account can see multiple client folders, so there is deliberately no
        global-image fallback. If no folder path meaningfully matches the client
        name, no image is returned rather than risking cross-client leakage.
        """
        credentials = self._credentials(settings)
        if credentials is None:
            return []
        access_token = await self._access_token(credentials)
        files = await self._list_visible_files(access_token)
        folders = {
            str(item.get("id")): item
            for item in files
            if item.get("mimeType") == "application/vnd.google-apps.folder"
        }
        org_terms = self._terms(organization_name)
        if not org_terms:
            return []

        candidates: list[tuple[int, DriveImage]] = []
        for item in files:
            mime_type = str(item.get("mimeType") or "")
            if not mime_type.startswith("image/"):
                continue
            file_id = str(item.get("id") or "")
            name = str(item.get("name") or "")
            if not file_id or not name:
                continue
            path = self._path_for(item, folders)
            path_terms = self._terms(path)
            overlap = len(org_terms & path_terms)
            # Require meaningful tenant/folder identity overlap. One token is
            # enough for distinctive business names; generic one-character
            # tokens are removed by _terms().
            if overlap == 0:
                continue
            score = overlap * 100 + len(org_terms & self._terms(name)) * 20
            candidates.append(
                (
                    score,
                    DriveImage(
                        file_id=file_id,
                        name=name,
                        mime_type=mime_type,
                        path=path,
                        modified_time=(
                            str(item.get("modifiedTime")) if item.get("modifiedTime") else None
                        ),
                    ),
                )
            )

        candidates.sort(
            key=lambda row: (row[0], row[1].modified_time or "", row[1].name.casefold()),
            reverse=True,
        )
        return [image for _, image in candidates[: max(1, min(limit, 100))]]

    async def fetch_image(self, settings: Settings, token: str) -> tuple[bytes, str]:
        payload = self.verify_proxy_token(settings, token)
        credentials = self._credentials(settings)
        if credentials is None:
            raise ValueError("Google Drive service account is not configured")
        access_token = await self._access_token(credentials)
        file_id = str(payload["file_id"])
        mime_type = str(payload.get("mime_type") or "application/octet-stream")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{DRIVE_FILES_ENDPOINT}/{file_id}",
                params={"alt": "media"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        response.raise_for_status()
        return response.content, response.headers.get("content-type", mime_type)

    def public_proxy_url(
        self,
        settings: Settings,
        *,
        organization_id: UUID,
        image: DriveImage,
        lifetime: timedelta = timedelta(hours=48),
    ) -> str | None:
        origin = self._api_origin(settings)
        signing_key = settings.secret_encryption_key
        if not origin or not signing_key:
            return None
        now = datetime.now(UTC)
        payload = {
            "purpose": "google_drive_provider_media",
            "organization_id": str(organization_id),
            "file_id": image.file_id,
            "mime_type": image.mime_type,
            "iat": int(now.timestamp()),
            "exp": int((now + lifetime).timestamp()),
        }
        token = jwt.encode(payload, signing_key, algorithm="HS256")
        return f"{origin}/api/v1/provider-media/google-drive/{token}"

    def verify_proxy_token(self, settings: Settings, token: str) -> dict[str, Any]:
        signing_key = settings.secret_encryption_key
        if not signing_key:
            raise ValueError("provider-media signing key is not configured")
        payload = jwt.decode(token, signing_key, algorithms=["HS256"])
        if payload.get("purpose") != "google_drive_provider_media":
            raise ValueError("invalid provider-media token purpose")
        if not payload.get("file_id"):
            raise ValueError("provider-media token is missing file id")
        return dict(payload)

    @staticmethod
    def _api_origin(settings: Settings) -> str | None:
        """Return the public API origin that actually mounts provider-media.

        The provider-media route lives on the API service. Google OAuth's
        redirect URI is therefore the canonical production source for that
        origin. A GitHub installation redirect is retained only as a legacy
        fallback; preferring it could point media URLs at a frontend host and
        make Google silently drop an otherwise valid Local Post image.
        """
        for candidate in (
            settings.google_oauth_redirect_uri,
            settings.github_app_installation_redirect_uri,
        ):
            if candidate is None:
                continue
            parsed = urlsplit(str(candidate))
            if parsed.scheme == "https" and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return None

    @staticmethod
    def _credentials(settings: Settings) -> dict[str, Any] | None:
        raw = settings.google_drive_service_account_json
        if not raw:
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Google Drive service-account JSON must be an object")
        for key in ("client_email", "private_key", "token_uri"):
            if not payload.get(key):
                raise ValueError(f"Google Drive service-account JSON is missing {key}")
        return payload

    async def _access_token(self, credentials: dict[str, Any]) -> str:
        now = datetime.now(UTC)
        assertion = jwt.encode(
            {
                "iss": str(credentials["client_email"]),
                "scope": DRIVE_SCOPE,
                "aud": str(credentials["token_uri"]),
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=55)).timestamp()),
            },
            str(credentials["private_key"]),
            algorithm="RS256",
        )
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                str(credentials["token_uri"]),
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            raise RuntimeError("Google Drive token exchange returned no access token")
        return str(token)

    async def _list_visible_files(self, access_token: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page_token: str | None = None
        for _ in range(20):
            params: dict[str, str | int] = {
                "q": "trashed = false",
                "pageSize": 1000,
                "fields": (
                    "nextPageToken,files(id,name,mimeType,parents,modifiedTime,description,size)"
                ),
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
                "corpora": "allDrives",
            }
            if page_token:
                params["pageToken"] = page_token
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    DRIVE_FILES_ENDPOINT,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Google Drive files response was invalid")
            raw_files = payload.get("files") or []
            if not isinstance(raw_files, list):
                raise RuntimeError("Google Drive files response was invalid")
            results.extend(item for item in raw_files if isinstance(item, dict))
            raw_next = payload.get("nextPageToken")
            page_token = str(raw_next) if raw_next else None
            if not page_token:
                return results
        raise RuntimeError("Google Drive file discovery exceeded pagination limit")

    @classmethod
    def _path_for(cls, item: dict[str, Any], folders: dict[str, dict[str, Any]]) -> str:
        names = [str(item.get("name") or "")]
        parents = item.get("parents") or []
        parent_id = str(parents[0]) if isinstance(parents, list) and parents else ""
        seen: set[str] = set()
        while parent_id and parent_id not in seen and len(names) < 12:
            seen.add(parent_id)
            folder = folders.get(parent_id)
            if folder is None:
                break
            names.append(str(folder.get("name") or ""))
            grandparents = folder.get("parents") or []
            parent_id = (
                str(grandparents[0]) if isinstance(grandparents, list) and grandparents else ""
            )
        return "/".join(reversed([name for name in names if name]))

    @staticmethod
    def _terms(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", value.casefold())
            if len(token) >= 3 and token not in {"the", "and", "inc", "llc", "company", "images"}
        }
