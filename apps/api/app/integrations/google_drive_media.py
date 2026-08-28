"""Read-only Google Drive image discovery and signed provider-media proxy URLs.

The service account is used only to read files that have already been shared
with it. A short-lived signed URL lets Google Business Profile fetch a selected
image without making the underlying Drive file public.
"""

from __future__ import annotations

import json
import re
from base64 import b64decode
from binascii import Error as BinasciiError
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import jwt

from apps.api.app.config import Settings

_BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]+={0,2}")
_SMART_QUOTES = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"})

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DRIVE_FILES_ENDPOINT = "https://www.googleapis.com/drive/v3/files"
GBP_PHOTO_MIME_TYPES = frozenset({"image/jpeg", "image/png"})
GBP_PHOTO_MIN_BYTES = 10 * 1024
GBP_PHOTO_MAX_BYTES = 5 * 1024 * 1024
GBP_PHOTO_MIN_DIMENSION = 250


class DriveDiscoveryError(RuntimeError):
    """Safe, classified Drive read failure.

    Every failure in this path — a malformed credential, a rejected JWT, a Drive
    API that is not enabled, a folder never shared with the service account —
    used to reach the operator as one sentence: "verify the configured Drive
    credential and folder access". Those have completely different fixes, and the
    operator was left to guess which one applied. The cause is only knowable
    here, where the exception still has its context, so it is classified here.

    The message carries the provider's status and reason, never the credential.
    """

    def __init__(self, safe_code: str, message: str, *, retryable: bool) -> None:
        self.safe_code = safe_code
        self.retryable = retryable
        super().__init__(message)


class ProviderMediaPreflightError(RuntimeError):
    """Safe provider-media failure detected before any Google post write."""

    def __init__(self, safe_code: str, message: str, *, retryable: bool) -> None:
        self.safe_code = safe_code
        self.retryable = retryable
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ProviderMediaPreflight:
    mime_type: str
    size_bytes: int
    width_pixels: int
    height_pixels: int


def _credential_shape(raw: str) -> str:
    """Describe a credential value without revealing any of it.

    The parse position alone is not actionable: line 1 column 14 is the same
    report whether the value is base64, a file path, or JSON whose private key
    was pasted with literal newlines. These counts name the mangling, and none of
    them is key material — only lengths, character classes and counts.
    """
    stripped = raw.strip()
    if not stripped:
        return "The value is empty."
    leading = stripped[0]
    kind = (
        "starts with '{' so it looks like JSON"
        if leading == "{"
        else "starts with a PEM header, so it looks like a bare private key rather "
        "than the key file"
        if stripped.startswith("-----BEGIN")
        else "looks like a filesystem path rather than the key contents"
        if leading == "/"
        else f"starts with {leading!r}"
    )
    return (
        f"The value is {len(stripped)} characters, {kind}, and contains "
        f"{stripped.count(chr(10))} real newlines, {stripped.count(chr(9))} tabs and "
        f"{stripped.count(chr(92) + 'n')} escaped newline sequences."
    )


def _escape_control_characters_in_strings(candidate: str) -> str:
    """Escape raw control characters that appear inside JSON string literals.

    A service-account key file holds its PEM as a single line with \\n escapes.
    Editors, shells and dashboard fields routinely convert those into real
    newlines, which is invalid JSON — a control character inside a string — and is
    the most common reason a key that looks right fails to parse. Only characters
    inside string literals are touched, so JSON structure is never altered.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    replacements = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    for character in candidate:
        if escaped:
            out.append(character)
            escaped = False
            continue
        if character == "\\":
            out.append(character)
            escaped = in_string
            continue
        if character == '"':
            in_string = not in_string
            out.append(character)
            continue
        if in_string and character in replacements:
            out.append(replacements[character])
            continue
        out.append(character)
    return "".join(out)


def _decode_service_account(raw: str) -> tuple[object | None, str]:
    """Read a service-account key that survived an environment variable.

    Returns the parsed payload, or None plus a safe description of why not.
    Three tolerated encodings, in order of directness: the key file as-is, the
    same file base64-encoded (which is how an operator avoids newline mangling
    entirely), and JSON whose string literals contain raw control characters.
    Anything still unparseable is reported with the parser's own reason.
    """
    candidate = raw.strip()
    # A dashboard or shell paste often arrives wrapped in quotes.
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in "\"'":
        candidate = candidate[1:-1]

    first_error: json.JSONDecodeError | None = None
    try:
        return json.loads(candidate), ""
    except json.JSONDecodeError as exc:
        first_error = exc

    # Base64, tolerating whitespace introduced by line wrapping.
    compact = "".join(candidate.split())
    if compact and len(compact) % 4 == 0 and _BASE64_PATTERN.fullmatch(compact):
        try:
            decoded = b64decode(compact, validate=True).decode("utf-8")
        except (BinasciiError, UnicodeDecodeError):
            decoded = ""
        if decoded:
            with suppress(json.JSONDecodeError):
                return json.loads(decoded), ""

    with suppress(json.JSONDecodeError):
        return json.loads(_escape_control_characters_in_strings(candidate)), ""

    # Curly quotes: a value pasted through a rich-text field or a chat client on
    # macOS arrives with typographic quotes that JSON cannot read.
    straightened = candidate.translate(_SMART_QUOTES)
    if straightened != candidate:
        with suppress(json.JSONDecodeError):
            return json.loads(straightened), ""
        with suppress(json.JSONDecodeError):
            return json.loads(_escape_control_characters_in_strings(straightened)), ""

    reason = (
        f"The parser reported: {first_error.msg} at line {first_error.lineno}, "
        f"column {first_error.colno}."
    )
    return None, f"{reason} {_credential_shape(raw)}"


def _safe_oauth_reason(response: httpx.Response) -> str:
    """Google's OAuth error code, which is the actionable part and is not secret."""
    try:
        payload = response.json()
    except ValueError:
        return "unparseable response"
    if not isinstance(payload, dict):
        return "unexpected response"
    code = str(payload.get("error") or "unspecified")
    description = str(payload.get("error_description") or "").strip()
    return f"{code} - {description}"[:200] if description else code[:200]


def _safe_drive_reason(response: httpx.Response) -> str:
    """Google Drive's error status/reason, e.g. accessNotConfigured or forbidden."""
    try:
        payload = response.json()
    except ValueError:
        return "unparseable response"
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return "unexpected response"
    reasons = [
        str(item.get("reason"))
        for item in (error.get("errors") or [])
        if isinstance(item, dict) and item.get("reason")
    ]
    message = str(error.get("message") or "").strip()
    parts = [part for part in (", ".join(reasons), message) if part]
    return " - ".join(parts)[:200] or "unspecified"


@dataclass(frozen=True, slots=True)
class DriveDiscovery:
    """Images found for one client, plus why the count is what it is.

    GBP_DRIVE_NO_ELIGIBLE_IMAGE covered two situations with completely different
    fixes: the service account can see nothing in Drive at all (the folder was
    never shared with it), or it can see plenty but no folder path identifies this
    client (the folder is named something the tenant match cannot recognise).
    These counts separate them.

    Deliberately no folder or file names: this description reaches an agent run
    scoped to one organization, and naming another client's folders there would be
    a cross-tenant leak.
    """

    images: list[DriveImage]
    visible_files: int
    visible_images: int
    service_account_email: str
    match_terms: tuple[str, ...]

    def explain(self) -> str:
        if self.visible_files == 0:
            return (
                "The Drive service account can see no files at all. Share the "
                f"client's image folder with {self.service_account_email} "
                "(Viewer is enough)."
            )
        if self.visible_images == 0:
            return (
                f"The service account can see {self.visible_files} Drive items but no "
                "images among them. Confirm the shared folder contains JPEG or PNG "
                "files rather than only documents or shortcuts."
            )
        return (
            f"The service account can see {self.visible_files} Drive items including "
            f"{self.visible_images} images, but none sit under a folder path naming "
            f"this client. A folder in the path has to contain one of: "
            f"{', '.join(self.match_terms)}. Rename the client folder to include the "
            "business name, or share the correctly named folder with "
            f"{self.service_account_email}."
        )


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
        """Images for one client. See discover() for the self-explaining version."""
        return (await self.discover(settings, organization_name, limit=limit)).images

    async def discover(
        self,
        settings: Settings,
        organization_name: str,
        *,
        limit: int = 25,
    ) -> DriveDiscovery:
        """Return images only from a Drive folder tree matching the organization.

        The account can see multiple client folders, so there is deliberately no
        global-image fallback. If no folder path meaningfully matches the client
        name, no image is returned rather than risking cross-client leakage.

        The counts travel with the result so an empty outcome can explain itself:
        nothing shared, nothing image-shaped, or nothing named for this client.
        """
        credentials = self._credentials(settings)
        if credentials is None:
            return DriveDiscovery([], 0, 0, "not configured", ())
        account_email = str(credentials.get("client_email") or "unknown")
        access_token = await self._access_token(credentials)
        files = await self._list_visible_files(access_token)
        folders = {
            str(item.get("id")): item
            for item in files
            if item.get("mimeType") == "application/vnd.google-apps.folder"
        }
        visible_images = sum(
            1 for item in files if str(item.get("mimeType") or "").startswith("image/")
        )
        org_terms = self._terms(organization_name)
        if not org_terms:
            return DriveDiscovery([], len(files), visible_images, account_email, ())

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
        return DriveDiscovery(
            images=[image for _, image in candidates[: max(1, min(limit, 100))]],
            visible_files=len(files),
            visible_images=visible_images,
            service_account_email=account_email,
            match_terms=tuple(sorted(org_terms)),
        )

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

    async def preflight_public_url(
        self,
        url: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> ProviderMediaPreflight:
        """Prove the exact Local Post source URL is anonymously fetchable and eligible.

        Google Local Posts ingest media from ``sourceUrl`` server-to-server. The
        worker therefore validates both HEAD and GET semantics over the public
        HTTPS URL immediately before dispatch, then enforces Google's documented
        JPG/PNG, size, and minimum-dimension requirements on the returned bytes.
        """
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ProviderMediaPreflightError(
                "POST_MEDIA_URL_NOT_HTTPS",
                "The provider-media source URL is not a public HTTPS URL.",
                retryable=False,
            )

        owns_client = client is None
        http_client = client or httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=False,
        )
        try:
            try:
                head = await http_client.head(
                    url,
                    headers={"Accept": "image/jpeg,image/png"},
                )
                if head.status_code != 200:
                    raise ProviderMediaPreflightError(
                        "POST_MEDIA_PROXY_UNREACHABLE",
                        "The provider-media source URL did not accept an anonymous HEAD request.",
                        retryable=True,
                    )
                response = await http_client.get(
                    url,
                    headers={"Accept": "image/jpeg,image/png"},
                )
            except ProviderMediaPreflightError:
                raise
            except httpx.HTTPError as exc:
                raise ProviderMediaPreflightError(
                    "POST_MEDIA_PROXY_UNREACHABLE",
                    "The provider-media source URL could not be fetched anonymously.",
                    retryable=True,
                ) from exc

            if response.status_code != 200:
                raise ProviderMediaPreflightError(
                    "POST_MEDIA_PROXY_UNREACHABLE",
                    "The provider-media source URL did not return HTTP 200.",
                    retryable=True,
                )
            mime_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if mime_type not in GBP_PHOTO_MIME_TYPES:
                raise ProviderMediaPreflightError(
                    "POST_MEDIA_FORMAT_UNSUPPORTED",
                    "The selected GBP post image is not a JPG or PNG image.",
                    retryable=False,
                )
            size_bytes = len(response.content)
            if not GBP_PHOTO_MIN_BYTES <= size_bytes <= GBP_PHOTO_MAX_BYTES:
                raise ProviderMediaPreflightError(
                    "POST_MEDIA_SIZE_INVALID",
                    "The selected GBP post image is outside Google's supported file-size range.",
                    retryable=False,
                )
            dimensions = self._image_dimensions(response.content, mime_type)
            if dimensions is None:
                raise ProviderMediaPreflightError(
                    "POST_MEDIA_DIMENSIONS_UNREADABLE",
                    "The selected GBP post image dimensions could not be validated.",
                    retryable=False,
                )
            width_pixels, height_pixels = dimensions
            if width_pixels < GBP_PHOTO_MIN_DIMENSION or height_pixels < GBP_PHOTO_MIN_DIMENSION:
                raise ProviderMediaPreflightError(
                    "POST_MEDIA_DIMENSIONS_INVALID",
                    "The selected GBP post image is below Google's minimum resolution.",
                    retryable=False,
                )
            return ProviderMediaPreflight(
                mime_type=mime_type,
                size_bytes=size_bytes,
                width_pixels=width_pixels,
                height_pixels=height_pixels,
            )
        finally:
            if owns_client:
                await http_client.aclose()

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
        payload, failure = _decode_service_account(raw)
        if payload is None:
            raise DriveDiscoveryError(
                "GBP_DRIVE_CREDENTIAL_MALFORMED",
                "The Google Drive service-account credential could not be read. "
                f"{failure} Paste the key file exactly as downloaded, or paste it "
                "base64-encoded if the dashboard mangles newlines.",
                retryable=False,
            )
        if not isinstance(payload, dict):
            raise DriveDiscoveryError(
                "GBP_DRIVE_CREDENTIAL_MALFORMED",
                "The Google Drive service-account credential must be a JSON object.",
                retryable=False,
            )
        missing = [
            key for key in ("client_email", "private_key", "token_uri") if not payload.get(key)
        ]
        if missing:
            raise DriveDiscoveryError(
                "GBP_DRIVE_CREDENTIAL_INCOMPLETE",
                f"The Google Drive service-account credential is missing {', '.join(missing)}.",
                retryable=False,
            )
        # An environment variable set through a dashboard or shell commonly stores
        # the PEM with literal backslash-n rather than real newlines, which the
        # crypto layer cannot parse. Repairing it here cannot make an otherwise
        # invalid key valid, and it removes the single most common cause of a
        # credential that looks correct in the dashboard and fails at runtime.
        private_key = str(payload["private_key"])
        if "\\n" in private_key and "\n" not in private_key:
            payload = {**payload, "private_key": private_key.replace("\\n", "\n")}
        return payload

    async def _access_token(self, credentials: dict[str, Any]) -> str:
        now = datetime.now(UTC)
        try:
            assertion = self._signed_assertion(credentials, now)
        except DriveDiscoveryError:
            raise
        except Exception as exc:
            raise DriveDiscoveryError(
                "GBP_DRIVE_CREDENTIAL_UNREADABLE",
                "The Drive service-account private key could not be read for signing. "
                "It is usually stored with escaped rather than real newlines, or is "
                "truncated.",
                retryable=False,
            ) from exc
        return await self._exchange_assertion(credentials, assertion)

    @staticmethod
    def _signed_assertion(credentials: dict[str, Any], now: datetime) -> str:
        return jwt.encode(
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

    async def _exchange_assertion(self, credentials: dict[str, Any], assertion: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    str(credentials["token_uri"]),
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": assertion,
                    },
                )
        except httpx.RequestError as exc:
            raise DriveDiscoveryError(
                "GBP_DRIVE_UNREACHABLE",
                "Google could not be reached to exchange the Drive credential.",
                retryable=True,
            ) from exc
        if response.status_code >= 400:
            # Google returns the actionable part as error/error_description:
            # "invalid_grant" means the key or clock is wrong, whereas
            # "invalid_scope" means the scope was never granted. Both are safe.
            raise DriveDiscoveryError(
                "GBP_DRIVE_CREDENTIAL_REJECTED",
                "Google rejected the Drive service-account credential "
                f"({response.status_code}: {_safe_oauth_reason(response)}). Check that the "
                "service account exists, its key is current, and the Drive API is enabled "
                "for the project.",
                retryable=False,
            )
        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            raise DriveDiscoveryError(
                "GBP_DRIVE_CREDENTIAL_REJECTED",
                "Google returned no access token for the Drive service-account credential.",
                retryable=False,
            )
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
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.get(
                        DRIVE_FILES_ENDPOINT,
                        params=params,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
            except httpx.RequestError as exc:
                raise DriveDiscoveryError(
                    "GBP_DRIVE_UNREACHABLE",
                    "Google Drive could not be reached to list client media.",
                    retryable=True,
                ) from exc
            if response.status_code in (401, 403):
                # accessNotConfigured means the Drive API is not enabled on the
                # project; forbidden or insufficientPermissions means the folder was
                # never shared with the service account. Different fixes entirely.
                raise DriveDiscoveryError(
                    "GBP_DRIVE_ACCESS_DENIED",
                    "Google Drive denied the service account "
                    f"({response.status_code}: {_safe_drive_reason(response)}). Confirm the "
                    "Drive API is enabled for the project and the client image folder is "
                    "shared with the service-account address.",
                    retryable=False,
                )
            if response.status_code == 429 or response.status_code >= 500:
                raise DriveDiscoveryError(
                    "GBP_DRIVE_TEMPORARILY_UNAVAILABLE",
                    f"Google Drive is temporarily unavailable ({response.status_code}).",
                    retryable=True,
                )
            if response.status_code >= 400:
                raise DriveDiscoveryError(
                    "GBP_DRIVE_LIST_REJECTED",
                    "Google Drive rejected the media listing request "
                    f"({response.status_code}: {_safe_drive_reason(response)}).",
                    retryable=False,
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise DriveDiscoveryError(
                    "GBP_DRIVE_LIST_REJECTED",
                    "Google Drive returned an unexpected media listing response.",
                    retryable=True,
                )
            raw_files = payload.get("files") or []
            if not isinstance(raw_files, list):
                raise DriveDiscoveryError(
                    "GBP_DRIVE_LIST_REJECTED",
                    "Google Drive returned an unexpected media listing response.",
                    retryable=True,
                )
            results.extend(item for item in raw_files if isinstance(item, dict))
            raw_next = payload.get("nextPageToken")
            page_token = str(raw_next) if raw_next else None
            if not page_token:
                return results
        raise RuntimeError("Google Drive file discovery exceeded pagination limit")

    @staticmethod
    def _image_dimensions(content: bytes, mime_type: str) -> tuple[int, int] | None:
        if mime_type == "image/png":
            if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n":
                return None
            width = int.from_bytes(content[16:20], "big")
            height = int.from_bytes(content[20:24], "big")
            return (width, height) if width > 0 and height > 0 else None

        if mime_type != "image/jpeg" or len(content) < 4 or content[:2] != b"\xff\xd8":
            return None
        sof_markers = {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }
        standalone_markers = {0x01, 0xD8, 0xD9, *range(0xD0, 0xD8)}
        index = 2
        while index + 3 < len(content):
            if content[index] != 0xFF:
                index += 1
                continue
            while index < len(content) and content[index] == 0xFF:
                index += 1
            if index >= len(content):
                return None
            marker = content[index]
            index += 1
            if marker in standalone_markers:
                continue
            if index + 2 > len(content):
                return None
            segment_length = int.from_bytes(content[index : index + 2], "big")
            if segment_length < 2 or index + segment_length > len(content):
                return None
            if marker in sof_markers:
                if segment_length < 7:
                    return None
                height = int.from_bytes(content[index + 3 : index + 5], "big")
                width = int.from_bytes(content[index + 5 : index + 7], "big")
                return (width, height) if width > 0 and height > 0 else None
            index += segment_length
        return None

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
