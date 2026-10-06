"""Server-side checks for an uploaded Business Profile photo, against Google's published limits.

JPG or PNG, 10 KB to 5 MB, at least 250 x 250 px. The type is read from the bytes, never from
the filename or the client's Content-Type.
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from apps.api.app.errors import ApiError
from apps.api.app.schemas import ErrorCategory

MIN_BYTES = 10 * 1024
MAX_BYTES = 5 * 1024 * 1024
MIN_DIMENSION = 250
# Far above any real photo, far below a decompression bomb.
MAX_PIXELS = 100_000_000
_FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png")}


class MediaTypeUnsupportedError(ApiError):
    status_code = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    code = "MEDIA_TYPE_UNSUPPORTED"
    category = ErrorCategory.VALIDATION
    public_message = "Photos must be JPG or PNG images."


class MediaTooSmallError(ApiError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "MEDIA_TOO_SMALL"
    category = ErrorCategory.VALIDATION
    public_message = "Photos must be at least 10 KB."


class MediaTooLargeError(ApiError):
    status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    code = "MEDIA_TOO_LARGE"
    category = ErrorCategory.VALIDATION
    public_message = "Photos must be 5 MB or smaller."


class MediaDimensionsTooSmallError(ApiError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "MEDIA_DIMENSIONS_TOO_SMALL"
    category = ErrorCategory.VALIDATION
    public_message = "Photos must be at least 250 x 250 pixels."


@dataclass(frozen=True, slots=True)
class ImageFacts:
    content_type: str
    extension: str
    byte_size: int
    width: int
    height: int


def validate_image(data: bytes) -> ImageFacts:
    if len(data) > MAX_BYTES:
        raise MediaTooLargeError
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = image.format or ""
            width, height = image.size
            if width * height > MAX_PIXELS:
                raise MediaTypeUnsupportedError
            image.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as error:
        raise MediaTypeUnsupportedError from error
    if image_format not in _FORMATS:
        raise MediaTypeUnsupportedError
    if len(data) < MIN_BYTES:
        raise MediaTooSmallError
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise MediaDimensionsTooSmallError
    content_type, extension = _FORMATS[image_format]
    return ImageFacts(content_type, extension, len(data), width, height)
