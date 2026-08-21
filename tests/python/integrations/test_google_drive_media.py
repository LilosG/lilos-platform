"""Tests for signed Google Drive provider-media URLs."""

from datetime import timedelta
from uuid import uuid4

from cryptography.fernet import Fernet
from pydantic import HttpUrl

from apps.api.app.config import Settings
from apps.api.app.integrations.google_drive_media import DriveImage, GoogleDriveMediaService


def test_drive_proxy_url_round_trips_signed_file_identity() -> None:
    settings = Settings(
        secret_encryption_key=Fernet.generate_key().decode(),
        github_app_installation_redirect_uri=HttpUrl(
            "https://lilos-api.onrender.com/api/v1/integrations/github/callback"
        ),
    )
    image = DriveImage(
        file_id="drive-file-123",
        name="project-photo.jpg",
        mime_type="image/jpeg",
        path="Wheyland Electric/Project Photos/project-photo.jpg",
        modified_time=None,
    )
    service = GoogleDriveMediaService()

    url = service.public_proxy_url(
        settings,
        organization_id=uuid4(),
        image=image,
        lifetime=timedelta(minutes=5),
    )

    assert url is not None
    token = url.rsplit("/", 1)[1]
    payload = service.verify_proxy_token(settings, token)
    assert payload["file_id"] == "drive-file-123"
    assert payload["mime_type"] == "image/jpeg"
