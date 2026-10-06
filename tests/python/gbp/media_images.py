"""Synthetic images for upload tests."""

import os
import random
from io import BytesIO

from PIL import Image


def noise(width: int, height: int, fmt: str = "JPEG", *, seed: int = 1) -> bytes:
    """Incompressible pixels, so the file is large enough to pass the minimum-size check."""
    random.seed(seed)
    data = bytes(random.getrandbits(8) for _ in range(width * height * 3))
    buffer = BytesIO()
    Image.frombytes("RGB", (width, height), data).save(buffer, fmt)
    return buffer.getvalue()


def flat(width: int, height: int, fmt: str = "JPEG") -> bytes:
    """One colour: compresses to a few hundred bytes."""
    buffer = BytesIO()
    Image.new("RGB", (width, height), (200, 40, 40)).save(buffer, fmt)
    return buffer.getvalue()


def oversized() -> bytes:
    """Just over 5 MB; the size is checked before the bytes are decoded."""
    return os.urandom(5 * 1024 * 1024 + 1)
