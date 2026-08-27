"""Assemble the file that is committed to a client's Astro repository.

A revision carries its body and its frontmatter separately. The publish handler
previously committed ``revision.body`` alone, so the frontmatter never reached the
file. For an Astro content collection that is fatal rather than cosmetic: the
collection parses YAML frontmatter and validates it against the Zod schema in
``src/content/config.ts``, so a file without it fails ``astro build`` and takes
the client's Vercel deployment down with it. Even outside a collection, a page
with no title or description has no usable metadata.

This module is the single place a published file is assembled. It emits a YAML
frontmatter block followed by the body, and refuses input it cannot represent
faithfully rather than writing something that looks plausible and breaks a build.

Deliberately hand-rolled rather than pulled from a YAML library: the output must
be deterministic for content hashing and diff review, the accepted value shapes
are a small closed set, and a general emitter would happily produce constructs
(anchors, implicit typing, multi-document markers) that an Astro schema then
rejects.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

FRONTMATTER_DELIMITER = "---"

# Values YAML would otherwise coerce: an unquoted `yes`, `no`, `on`, `off`, `null`
# or `~` becomes a boolean or null, and a bare `1.0` becomes a number. Astro's Zod
# schemas expect strings, so every string is quoted.
_ALWAYS_QUOTE = True


class ContentFileFormatError(ValueError):
    """The revision cannot be represented as a publishable file."""

    def __init__(self, safe_code: str, message: str) -> None:
        super().__init__(message)
        self.safe_code = safe_code


def _quote(value: str) -> str:
    """Double-quote a YAML scalar, escaping what the spec requires."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, datetime):
        return _quote(value.isoformat())
    if isinstance(value, date):
        return _quote(value.isoformat())
    if isinstance(value, str):
        return _quote(value) if _ALWAYS_QUOTE else value
    raise ContentFileFormatError(
        "CONTENT_FRONTMATTER_UNSUPPORTED_VALUE",
        f"frontmatter values of type {type(value).__name__} cannot be published",
    )


def _emit(key: str, value: Any, indent: int = 0) -> list[str]:
    pad = "  " * indent
    if value is None:
        return [f"{pad}{key}: null"]
    if isinstance(value, Mapping):
        if not value:
            return [f"{pad}{key}: {{}}"]
        lines = [f"{pad}{key}:"]
        for child_key, child in value.items():
            lines.extend(_emit(str(child_key), child, indent + 1))
        return lines
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if not value:
            return [f"{pad}{key}: []"]
        lines = [f"{pad}{key}:"]
        for entry in value:
            if isinstance(entry, Mapping):
                if not entry:
                    lines.append(f"{pad}  - {{}}")
                    continue
                first = True
                for child_key, child in entry.items():
                    rendered = _emit(str(child_key), child, indent + 2)
                    if first:
                        # Hyphen shares the line with the mapping's first key.
                        rendered[0] = f"{pad}  - {rendered[0].lstrip()}"
                        first = False
                    lines.extend(rendered)
            elif isinstance(entry, Sequence) and not isinstance(entry, (str, bytes)):
                raise ContentFileFormatError(
                    "CONTENT_FRONTMATTER_UNSUPPORTED_VALUE",
                    "nested sequences cannot be published",
                )
            else:
                lines.append(f"{pad}  - {_scalar(entry)}")
        return lines
    return [f"{pad}{key}: {_scalar(value)}"]


def render_frontmatter(frontmatter: Mapping[str, Any]) -> str:
    """Render a YAML frontmatter block, keys in insertion order."""
    lines: list[str] = []
    for key in frontmatter:
        name = str(key)
        if not name or any(character in name for character in ":#\n"):
            raise ContentFileFormatError(
                "CONTENT_FRONTMATTER_INVALID_KEY",
                "frontmatter keys must be non-empty and free of ':', '#' and newlines",
            )
        lines.extend(_emit(name, frontmatter[key]))
    return "\n".join(lines)


def build_content_file(body: str, frontmatter: Mapping[str, Any]) -> str:
    """Return the exact bytes to commit for a content revision.

    Raises rather than guessing when the result would not build:
    - empty frontmatter, because an Astro collection schema cannot validate it
    - a body that already opens with a frontmatter delimiter, which would produce
      two blocks and make the second one page content
    """
    if not frontmatter:
        raise ContentFileFormatError(
            "CONTENT_FRONTMATTER_MISSING",
            "publishable content requires frontmatter for the Astro collection schema",
        )
    normalized_body = body.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    if normalized_body.lstrip().startswith(FRONTMATTER_DELIMITER):
        raise ContentFileFormatError(
            "CONTENT_BODY_HAS_FRONTMATTER",
            "the revision body already contains a frontmatter block",
        )
    rendered = render_frontmatter(frontmatter)
    trailing = "" if normalized_body.endswith("\n") else "\n"
    return (
        f"{FRONTMATTER_DELIMITER}\n"
        f"{rendered}\n"
        f"{FRONTMATTER_DELIMITER}\n\n"
        f"{normalized_body}{trailing}"
    )
