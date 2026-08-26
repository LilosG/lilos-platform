"""Tests for signed Google Drive provider-media URLs."""

from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from pydantic import HttpUrl

from apps.api.app.config import Settings
from apps.api.app.integrations.google_drive_media import (
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

    async def fake_fetch_image(settings: Settings, token: str) -> tuple[bytes, str]:
        assert token == "signed-token"
        return content, "image/png"

    monkeypatch.setattr(provider_media.service, "fetch_image", fake_fetch_image)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="https://lilos-api.onrender.com",
    ) as client:
        response = await client.head("/api/v1/provider-media/google-drive/signed-token")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["content-length"] == str(len(content))
    assert response.content == b""
