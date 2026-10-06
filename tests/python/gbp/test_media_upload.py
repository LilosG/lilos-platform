"""Photo validation against Google's limits, the Storage client, and the special-hours payload."""

from datetime import date, time
from http import HTTPStatus

import httpx
import pytest

from apps.api.app.config import Settings
from apps.api.app.products.gbp.media_upload import (
    MediaDimensionsTooSmallError,
    MediaTooLargeError,
    MediaTooSmallError,
    MediaTypeUnsupportedError,
    validate_image,
)
from apps.api.app.products.gbp.operations import special_hour_periods
from apps.api.app.storage.objects import (
    StorageNotConfiguredError,
    SupabaseObjectStorage,
    object_storage,
)

from .media_images import flat, noise, oversized


def test_a_valid_jpeg_and_png_pass_with_their_facts() -> None:
    jpeg = validate_image(noise(300, 260))
    assert (jpeg.content_type, jpeg.extension, jpeg.width, jpeg.height) == (
        "image/jpeg",
        "jpg",
        300,
        260,
    )
    png = validate_image(noise(256, 256, "PNG"))
    assert (png.content_type, png.extension) == ("image/png", "png")


@pytest.mark.parametrize(
    ("data", "error"),
    [
        (b"not an image at all" * 1000, MediaTypeUnsupportedError),
        (noise(300, 300, "GIF"), MediaTypeUnsupportedError),
        (noise(300, 300, "BMP"), MediaTypeUnsupportedError),
        (b"\xff\xd8\xff\xe0" + b"\x00" * 20000, MediaTypeUnsupportedError),
        (flat(400, 400), MediaTooSmallError),
        (oversized(), MediaTooLargeError),
        (noise(200, 300), MediaDimensionsTooSmallError),
        (noise(300, 249), MediaDimensionsTooSmallError),
    ],
)
def test_each_limit_has_its_own_typed_error(data: bytes, error: type[Exception]) -> None:
    with pytest.raises(error):
        validate_image(data)


def test_the_type_is_read_from_the_bytes_not_from_a_name() -> None:
    # A PNG is accepted whatever it is called; there is no filename in the contract at all.
    assert validate_image(noise(300, 300, "PNG")).extension == "png"


def test_error_codes_are_the_published_ones() -> None:
    assert MediaTypeUnsupportedError.code == "MEDIA_TYPE_UNSUPPORTED"
    assert MediaTooSmallError.code == "MEDIA_TOO_SMALL"
    assert MediaTooLargeError.code == "MEDIA_TOO_LARGE"
    assert MediaDimensionsTooSmallError.code == "MEDIA_DIMENSIONS_TOO_SMALL"
    assert StorageNotConfiguredError.code == "STORAGE_NOT_CONFIGURED"
    assert StorageNotConfiguredError.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_storage_needs_both_settings() -> None:
    with pytest.raises(StorageNotConfiguredError):
        object_storage(Settings())
    with pytest.raises(StorageNotConfiguredError):
        object_storage(Settings(supabase_url="https://abc.supabase.co"))  # type: ignore[arg-type]
    configured = object_storage(
        Settings(
            supabase_url="https://abc.supabase.co",  # type: ignore[arg-type]
            supabase_service_role_key="s" * 40,  # type: ignore[arg-type]
        )
    )
    assert isinstance(configured, SupabaseObjectStorage)


@pytest.mark.anyio
async def test_the_storage_client_writes_privately_and_signs_for_fifteen_minutes() -> None:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.startswith("/storage/v1/object/sign/"):
            return httpx.Response(200, json={"signedURL": "/object/sign/gbp-media/o/a.jpg?token=t"})
        return httpx.Response(200, json={"Key": "gbp-media/o/a.jpg"})

    storage = SupabaseObjectStorage(
        "https://abc.supabase.co/",
        "service-key",
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    await storage.put("gbp-media", "org/loc/a b.jpg", b"bytes", "image/jpeg")
    url = await storage.signed_url("gbp-media", "org/loc/a.jpg", 900)
    put, sign = seen
    assert put.url.raw_path == b"/storage/v1/object/gbp-media/org/loc/a%20b.jpg"
    assert put.headers["authorization"] == "Bearer service-key"
    assert put.headers["x-upsert"] == "false"
    assert sign.content == b'{"expiresIn":900}'
    assert url == "https://abc.supabase.co/storage/v1/object/sign/gbp-media/o/a.jpg?token=t"


@pytest.mark.anyio
async def test_ensure_bucket_is_dry_by_default_and_never_makes_a_public_bucket() -> None:
    calls: list[tuple[str, str, bytes]] = []
    exists = {"value": False}

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.content))
        if request.method == "GET":
            return (
                httpx.Response(200, json={"public": False})
                if exists["value"]
                else httpx.Response(404)
            )
        return httpx.Response(200, json={"name": "gbp-media"})

    storage = SupabaseObjectStorage(
        "https://abc.supabase.co",
        "service-key",
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    assert await storage.ensure_bucket("gbp-media", apply=False) == "missing"
    assert [call[0] for call in calls] == ["GET"]
    assert await storage.ensure_bucket("gbp-media", apply=True) == "created"
    assert b'"public":false' in calls[-1][2]
    exists["value"] = True
    assert await storage.ensure_bucket("gbp-media", apply=True) == "private"


def test_closed_all_day_maps_to_googles_closed_true() -> None:
    assert special_hour_periods(date(2026, 12, 25), [], closed=True) == [
        {"startDate": {"year": 2026, "month": 12, "day": 25}, "closed": True}
    ]


def test_open_hours_map_to_one_entry_per_interval() -> None:
    entries = special_hour_periods(
        date(2026, 12, 24), [(time(9), time(12, 30)), (time(14), time(18))], closed=False
    )
    assert entries == [
        {
            "startDate": {"year": 2026, "month": 12, "day": 24},
            "openTime": {"hours": 9, "minutes": 0},
            "closeTime": {"hours": 12, "minutes": 30},
            "closed": False,
        },
        {
            "startDate": {"year": 2026, "month": 12, "day": 24},
            "openTime": {"hours": 14, "minutes": 0},
            "closeTime": {"hours": 18, "minutes": 0},
            "closed": False,
        },
    ]
