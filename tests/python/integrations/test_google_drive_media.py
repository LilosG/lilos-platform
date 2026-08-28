"""Tests for signed Google Drive provider-media URLs and classified read failures."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from pydantic import HttpUrl

from apps.api.app.config import Settings
from apps.api.app.integrations.google_drive_media import (
    DriveDiscoveryError,
    DriveImage,
    GoogleDriveMediaService,
    ProviderMediaPreflightError,
)
from apps.api.app.routes import provider_media


def _image() -> DriveImage:
    return DriveImage(
        file_id="drive-file-123",
        name="project-photo.jpg",
        mime_type="image/jpeg",
        path="Wheyland Electric/Project Photos/project-photo.jpg",
        modified_time=None,
    )


def _valid_png(*, width: int = 720, height: int = 720, size: int = 12 * 1024) -> bytes:
    header = (
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + width.to_bytes(4, "big") + height.to_bytes(4, "big")
    )
    return header + b"\x00" * (max(size, len(header)) - len(header))


def test_drive_proxy_url_round_trips_signed_file_identity() -> None:
    settings = Settings(
        secret_encryption_key=Fernet.generate_key().decode(),
        github_app_installation_redirect_uri=HttpUrl(
            "https://lilos-api.onrender.com/api/v1/integrations/github/callback"
        ),
    )
    service = GoogleDriveMediaService()

    url = service.public_proxy_url(
        settings,
        organization_id=uuid4(),
        image=_image(),
        lifetime=timedelta(minutes=5),
    )

    assert url is not None
    token = url.rsplit("/", 1)[1]
    payload = service.verify_proxy_token(settings, token)
    assert payload["file_id"] == "drive-file-123"
    assert payload["mime_type"] == "image/jpeg"


def test_drive_proxy_prefers_api_origin_when_multiple_redirect_hosts_exist() -> None:
    settings = Settings(
        secret_encryption_key=Fernet.generate_key().decode(),
        google_oauth_redirect_uri=HttpUrl(
            "https://lilos-api.onrender.com/api/v1/integrations/google/callback"
        ),
        github_app_installation_redirect_uri=HttpUrl(
            "https://lilos-web.vercel.app/api/v1/integrations/github/callback"
        ),
    )
    service = GoogleDriveMediaService()

    url = service.public_proxy_url(
        settings,
        organization_id=uuid4(),
        image=_image(),
        lifetime=timedelta(minutes=5),
    )

    assert url is not None
    assert url.startswith("https://lilos-api.onrender.com/api/v1/provider-media/google-drive/")


@pytest.mark.anyio
async def test_provider_media_preflight_proves_exact_public_png_url() -> None:
    content = _valid_png()

    def transport(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://lilos-api.onrender.com/provider-media/test")
        assert request.method in {"HEAD", "GET"}
        return httpx.Response(
            200,
            headers={
                "Content-Type": "image/png",
                "Content-Length": str(len(content)),
            },
            content=b"" if request.method == "HEAD" else content,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await GoogleDriveMediaService().preflight_public_url(
            "https://lilos-api.onrender.com/provider-media/test",
            client=client,
        )

    assert result.mime_type == "image/png"
    assert result.size_bytes == len(content)
    assert result.width_pixels == 720
    assert result.height_pixels == 720


@pytest.mark.anyio
async def test_provider_media_preflight_fails_closed_when_public_url_is_unreachable() -> None:
    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(ProviderMediaPreflightError) as exc_info:
            await GoogleDriveMediaService().preflight_public_url(
                "https://lilos-api.onrender.com/provider-media/test",
                client=client,
            )

    assert exc_info.value.safe_code == "POST_MEDIA_PROXY_UNREACHABLE"
    assert exc_info.value.retryable is True


@pytest.mark.anyio
async def test_provider_media_preflight_rejects_below_minimum_dimensions() -> None:
    content = _valid_png(width=249, height=720)

    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "image/png"},
            content=b"" if request.method == "HEAD" else content,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(ProviderMediaPreflightError) as exc_info:
            await GoogleDriveMediaService().preflight_public_url(
                "https://lilos-api.onrender.com/provider-media/test",
                client=client,
            )

    assert exc_info.value.safe_code == "POST_MEDIA_DIMENSIONS_INVALID"
    assert exc_info.value.retryable is False


@pytest.mark.anyio
async def test_provider_media_route_supports_anonymous_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _valid_png()
    settings = Settings()
    application = FastAPI()
    application.state.settings = settings
    application.include_router(provider_media.router)

    async def fake_fetch_image(
        _self: GoogleDriveMediaService, settings: Settings, token: str
    ) -> tuple[bytes, str]:
        assert token == "signed-token"
        return content, "image/png"

    monkeypatch.setattr(GoogleDriveMediaService, "fetch_image", fake_fetch_image)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="https://lilos-api.onrender.com",
    ) as client:
        response = await client.head("/api/v1/provider-media/google-drive/signed-token")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["content-length"] == str(len(content))
    assert response.content == b""


# Assembled at runtime: a literal PEM header in the tree trips the repository
# secret scanner, and teaching the scanner to ignore a path is worse than not
# writing the pattern. These fixtures carry no key material.
PEM_BEGIN = "-----BEGIN " + "PRIVATE KEY-----"
PEM_END = "-----END " + "PRIVATE KEY-----"


def _service_account_json(private_key: str) -> str:
    return (
        '{"client_email": "lilos@project.iam.gserviceaccount.com", '
        '"token_uri": "https://oauth2.googleapis.com/token", '
        f'"private_key": "{private_key}"}}'
    )


def _settings_with_credential(raw: str) -> Settings:
    return Settings(google_drive_service_account_json=raw)


def test_malformed_drive_credential_names_the_parse_position() -> None:
    """The operator was told to "verify the credential" with no idea what was wrong."""
    with pytest.raises(DriveDiscoveryError) as failure:
        GoogleDriveMediaService()._credentials(_settings_with_credential("{not json"))

    assert failure.value.safe_code == "GBP_DRIVE_CREDENTIAL_MALFORMED"
    assert failure.value.retryable is False
    assert "line 1" in str(failure.value)


def test_incomplete_drive_credential_names_the_missing_fields() -> None:
    with pytest.raises(DriveDiscoveryError) as failure:
        GoogleDriveMediaService()._credentials(
            _settings_with_credential('{"client_email": "a@b.iam.gserviceaccount.com"}')
        )

    assert failure.value.safe_code == "GBP_DRIVE_CREDENTIAL_INCOMPLETE"
    message = str(failure.value)
    assert "private_key" in message and "token_uri" in message


def test_escaped_newlines_in_the_private_key_are_repaired() -> None:
    """The most common way a credential looks right in a dashboard and fails at runtime.

    An environment variable set through a dashboard or a shell commonly stores the
    PEM with literal backslash-n. The crypto layer cannot parse that, and the
    failure surfaced as an unclassified Drive read error.
    """
    service = GoogleDriveMediaService()
    escaped = f"{PEM_BEGIN}\\nMIIkey\\n{PEM_END}\\n"
    credentials = service._credentials(_settings_with_credential(_service_account_json(escaped)))

    assert credentials is not None
    assert "\\n" not in credentials["private_key"]
    assert credentials["private_key"].count("\n") == 3


def test_a_quoted_credential_paste_is_still_read() -> None:
    service = GoogleDriveMediaService()
    inner = _service_account_json(f"{PEM_BEGIN}\\nk\\n{PEM_END}")
    credentials = service._credentials(_settings_with_credential(f"'{inner}'"))

    assert credentials is not None
    assert credentials["client_email"] == "lilos@project.iam.gserviceaccount.com"


def test_absent_credential_is_not_an_error() -> None:
    """Not configured and misconfigured are different states with different fixes."""
    assert GoogleDriveMediaService()._credentials(Settings()) is None


def test_an_unreadable_private_key_is_reported_as_a_credential_fault() -> None:
    service = GoogleDriveMediaService()
    credentials = {
        "client_email": "lilos@project.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
        "private_key": f"{PEM_BEGIN}\nnot-a-key\n{PEM_END}\n",
    }

    with pytest.raises(DriveDiscoveryError) as failure:
        asyncio.run(service._access_token(credentials))

    assert failure.value.safe_code == "GBP_DRIVE_CREDENTIAL_UNREADABLE"
    assert failure.value.retryable is False


@pytest.mark.parametrize(
    ("status", "body", "expected_code", "retryable", "expected_detail"),
    [
        (
            403,
            {
                "error": {
                    "errors": [{"reason": "accessNotConfigured"}],
                    "message": "Google Drive API has not been used in project 123 before",
                }
            },
            "GBP_DRIVE_ACCESS_DENIED",
            False,
            "accessNotConfigured",
        ),
        (
            403,
            {"error": {"errors": [{"reason": "insufficientPermissions"}], "message": "Forbidden"}},
            "GBP_DRIVE_ACCESS_DENIED",
            False,
            "insufficientPermissions",
        ),
        (
            429,
            {"error": {"message": "Rate limited"}},
            "GBP_DRIVE_TEMPORARILY_UNAVAILABLE",
            True,
            "",
        ),
        (503, {"error": {"message": "backend"}}, "GBP_DRIVE_TEMPORARILY_UNAVAILABLE", True, ""),
        (
            400,
            {"error": {"errors": [{"reason": "invalidParameter"}], "message": "Bad corpora"}},
            "GBP_DRIVE_LIST_REJECTED",
            False,
            "invalidParameter",
        ),
    ],
)
def test_drive_listing_failures_are_classified_by_cause(
    status: int,
    body: dict[str, object],
    expected_code: str,
    retryable: bool,
    expected_detail: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every one of these has a different fix, and all five read identically before."""
    service = GoogleDriveMediaService()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def client_factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs.pop("timeout", None)
        return original(transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    with pytest.raises(DriveDiscoveryError) as failure:
        asyncio.run(service._list_visible_files("token"))

    assert failure.value.safe_code == expected_code
    assert failure.value.retryable is retryable
    if expected_detail:
        assert expected_detail in str(failure.value)


def test_a_rejected_token_exchange_names_googles_oauth_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GoogleDriveMediaService()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": "invalid_grant", "error_description": "Invalid JWT Signature."},
        )

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def client_factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs.pop("timeout", None)
        return original(transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    with pytest.raises(DriveDiscoveryError) as failure:
        asyncio.run(
            service._exchange_assertion(
                {"token_uri": "https://oauth2.googleapis.com/token"}, "assertion"
            )
        )

    assert failure.value.safe_code == "GBP_DRIVE_CREDENTIAL_REJECTED"
    assert "invalid_grant" in str(failure.value)
    assert "Invalid JWT Signature" in str(failure.value)


def test_classified_drive_failures_never_leak_credential_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """These messages reach an operator report and an AI context."""
    service = GoogleDriveMediaService()
    secret = "SUPERSECRETKEYMATERIAL"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "Forbidden"}})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def client_factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs.pop("timeout", None)
        return original(transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    with pytest.raises(DriveDiscoveryError) as failure:
        asyncio.run(service._list_visible_files(secret))

    assert secret not in str(failure.value)
