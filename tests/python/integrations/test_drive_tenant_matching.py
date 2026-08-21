"""Drive image selection must fail closed across client folders."""

from apps.api.app.integrations.google_drive_media import GoogleDriveMediaService


def test_drive_terms_ignore_generic_folder_words() -> None:
    assert GoogleDriveMediaService._terms("Wheyland Electric Images") == {
        "wheyland",
        "electric",
    }
