"""Resolve a live client-page URL and field to the exact file text controlling
it, and apply a targeted, minimal-diff edit -- never a guess.

Three source types cover every pattern observed across client repos:

- ``keystatic_json``: a Keystatic singleton content file (JSON), e.g.
  ``LilosG/coco-maya``'s ``src/content/brunchPage.json`` ->
  ``singleton.seo.title``, or ``LilosG/louisiana-purchase``'s
  ``src/content/brunchPage/page.json`` -> top-level ``seo.title`` (no
  ``singleton`` wrapper). The locator's ``json_pointer`` is just the key path,
  so both shapes are the same source type.
- ``frontmatter``: MD/MDX frontmatter (blog posts), e.g. ``title``,
  ``seoTitle``, ``description``.
- ``astro_code``: a named binding's string literal in an ``.astro`` file's
  frontmatter block or in ``src/lib/seo.ts`` -- the pattern home-services
  client sites use, which have no Keystatic content layer at all.

Every editor here does a targeted, minimal string replacement of the exact
value already read from the file. It never reformats or regex-rewrites the
rest of the file, and it never guesses: if the current value cannot be
proven to be exactly one occurrence, or the field cannot be located and
parsed as expected, resolution raises `SEOSiteMappingRequiredError` for that
page -- other pages in the same change set are unaffected.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlsplit

import yaml

from apps.api.app.products.seo.change_set import SiteChangeField
from apps.api.app.products.seo.errors import SEOSiteMappingRequiredError

FRONTMATTER_DELIMITER = "---"


@dataclass(frozen=True, slots=True)
class KeystaticJsonLocator:
    """A string leaf inside a JSON content file, addressed by key path."""

    source_type = "keystatic_json"
    file_path: str
    json_pointer: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FrontmatterLocator:
    """A frontmatter key in an MD/MDX file."""

    source_type = "frontmatter"
    file_path: str
    key: str


@dataclass(frozen=True, slots=True)
class AstroCodeLocator:
    """A named binding's string literal in an `.astro` or `.ts` file.

    ``binding_name`` must resolve to exactly one `name: "value"` or
    `name = "value"` assignment in the file; more than one match is
    ambiguous and is refused, never guessed at.
    """

    source_type = "astro_code"
    file_path: str
    binding_name: str


SiteMapLocator = KeystaticJsonLocator | FrontmatterLocator | AstroCodeLocator


@dataclass(frozen=True, slots=True)
class SiteMapEntry:
    """The complete locator set for one live URL path."""

    url_path: str
    fields: dict[SiteChangeField, SiteMapLocator]


def _require_file(files: dict[str, str], file_path: str) -> str:
    content = files.get(file_path)
    if content is None:
        raise SEOSiteMappingRequiredError(f"Mapped file {file_path} was not found in the repo.")
    return content


def _resolve_json_pointer(document: object, pointer: tuple[str, ...], file_path: str) -> str:
    node = document
    for key in pointer:
        if not isinstance(node, dict) or key not in node:
            raise SEOSiteMappingRequiredError(
                f"{'.'.join(pointer)} does not resolve inside {file_path}."
            )
        node = node[key]
    if not isinstance(node, str):
        raise SEOSiteMappingRequiredError(
            f"{'.'.join(pointer)} in {file_path} is not a plain string value."
        )
    return node


def _parse_frontmatter(content: str, file_path: str) -> tuple[dict[str, object], str, str, str]:
    """Split MD/MDX frontmatter from its body.

    Returns (frontmatter_dict, raw_frontmatter_text, delimiter_prefix, body),
    where the caller can reconstruct the file as
    ``prefix + raw_frontmatter_text + suffix_delimiter + body``.
    """
    if not content.startswith(f"{FRONTMATTER_DELIMITER}\n"):
        raise SEOSiteMappingRequiredError(f"{file_path} has no leading frontmatter block.")
    closing = content.find(f"\n{FRONTMATTER_DELIMITER}", len(FRONTMATTER_DELIMITER) + 1)
    if closing == -1:
        raise SEOSiteMappingRequiredError(f"{file_path} frontmatter block is not closed.")
    raw = content[len(FRONTMATTER_DELIMITER) + 1 : closing]
    body = content[closing + 1 + len(FRONTMATTER_DELIMITER) :]
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SEOSiteMappingRequiredError(f"{file_path} frontmatter is not valid YAML.") from exc
    if not isinstance(parsed, dict):
        raise SEOSiteMappingRequiredError(f"{file_path} frontmatter is not a mapping.")
    return parsed, raw, f"{FRONTMATTER_DELIMITER}\n", body


def _astro_binding_pattern(binding_name: str) -> re.Pattern[str]:
    # Matches `name: "value"`, `name: 'value'`, or `name = "value"` -- the
    # two shapes seen in Astro frontmatter objects and plain TS exports.
    escaped = re.escape(binding_name)
    return re.compile(rf'{escaped}\s*[:=]\s*(["\'])((?:(?!\1).)*)\1')


def resolve_current_value(files: dict[str, str], locator: SiteMapLocator) -> str:
    """Read the live value a field controls, from the repo checkout in `files`."""
    if isinstance(locator, KeystaticJsonLocator):
        content = _require_file(files, locator.file_path)
        try:
            document = json.loads(content)
        except json.JSONDecodeError as exc:
            raise SEOSiteMappingRequiredError(f"{locator.file_path} is not valid JSON.") from exc
        return _resolve_json_pointer(document, locator.json_pointer, locator.file_path)

    if isinstance(locator, FrontmatterLocator):
        content = _require_file(files, locator.file_path)
        parsed, _raw, _prefix, _body = _parse_frontmatter(content, locator.file_path)
        value = parsed.get(locator.key)
        if not isinstance(value, str):
            raise SEOSiteMappingRequiredError(
                f"Frontmatter key {locator.key!r} in {locator.file_path} is not a plain string."
            )
        return value

    content = _require_file(files, locator.file_path)
    matches = list(_astro_binding_pattern(locator.binding_name).finditer(content))
    if len(matches) != 1:
        raise SEOSiteMappingRequiredError(
            f"Binding {locator.binding_name!r} in {locator.file_path} resolved to "
            f"{len(matches)} matches; it must resolve to exactly one."
        )
    return matches[0].group(2)


def apply_change(
    files: dict[str, str],
    locator: SiteMapLocator,
    current_value: str,
    proposed_value: str,
) -> dict[str, str]:
    """Return `files` with exactly one field's value replaced.

    Always re-derives and checks `current_value` against the live file
    before writing, so a stale approval (the file changed since the
    recommendation was made) is refused rather than silently overwriting
    unrelated drift.
    """
    live_value = resolve_current_value(files, locator)
    if live_value != current_value:
        raise SEOSiteMappingRequiredError(
            f"{locator.file_path} no longer matches the approved current value; "
            "re-run analysis before applying this change."
        )

    if isinstance(locator, KeystaticJsonLocator):
        content = files[locator.file_path]
        # ensure_ascii=False: the file stores literal UTF-8 (em dashes,
        # curly quotes, etc.); the default \uXXXX escaping would never match.
        needle = json.dumps(current_value, ensure_ascii=False)
        replacement = json.dumps(proposed_value, ensure_ascii=False)
        occurrences = content.count(needle)
        if occurrences != 1:
            raise SEOSiteMappingRequiredError(
                f"{needle} occurs {occurrences} times in {locator.file_path}; "
                "it must occur exactly once to edit safely."
            )
        updated = content.replace(needle, replacement, 1)
        return {**files, locator.file_path: updated}

    if isinstance(locator, FrontmatterLocator):
        content = files[locator.file_path]
        _parsed, raw, prefix, body = _parse_frontmatter(content, locator.file_path)
        # Match the exact "key: value" line as written, quoted or not, and
        # replace only its value -- preserving the file's own quote style
        # rather than reformatting through a YAML dumper.
        line_pattern = re.compile(
            rf'^({re.escape(locator.key)}:\s*)(["\']?){re.escape(current_value)}\2\s*$',
            re.MULTILINE,
        )
        matches = list(line_pattern.finditer(raw))
        if len(matches) != 1:
            raise SEOSiteMappingRequiredError(
                f"Frontmatter key {locator.key!r} value does not occur exactly once "
                f"in {locator.file_path}; it cannot be edited safely."
            )
        prefix_group, quote = matches[0].group(1), matches[0].group(2)
        updated_raw = (
            raw[: matches[0].start()]
            + f"{prefix_group}{quote}{proposed_value}{quote}"
            + raw[matches[0].end() :]
        )
        updated_content = f"{prefix}{updated_raw}\n{FRONTMATTER_DELIMITER}{body}"
        return {**files, locator.file_path: updated_content}

    content = files[locator.file_path]
    matches = list(_astro_binding_pattern(locator.binding_name).finditer(content))
    if len(matches) != 1:
        raise SEOSiteMappingRequiredError(
            f"Binding {locator.binding_name!r} in {locator.file_path} resolved to "
            f"{len(matches)} matches; it must resolve to exactly one."
        )
    match = matches[0]
    quote = match.group(1)
    escaped_proposed = proposed_value.replace("\\", "\\\\").replace(quote, f"\\{quote}")
    start, end = match.span(2)
    updated = f"{content[:start]}{escaped_proposed}{content[end:]}"
    return {**files, locator.file_path: updated}


# --------------------------------------------------------------------------
# Declarative page map
#
# A publishing target stores its page map under ``frontmatter_contract["page_map"]``:
#
#   {"/brunch": {"seo_title": {"source_type": "keystatic_json",
#                              "file_path": "src/content/brunchPage.json",
#                              "json_pointer": ["singleton", "seo", "title"]},
#                "meta_description": {...}},
#    "/blog/{slug}": {"seo_title": {"source_type": "frontmatter",
#                                   "file_path": "src/content/blog/{slug}.mdx",
#                                   "key": "seoTitle"}}}
#
# A key is an exact URL path, or a template whose ``{name}`` segments capture one
# path segment and are substituted into ``file_path``. Nothing here is inferred:
# a URL that matches no key, or more than one template, is refused for that page.
# --------------------------------------------------------------------------

_TEMPLATE_PART = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def normalize_url_path(url_or_path: str) -> str:
    """Reduce a live URL or path to its canonical path: no host, query, fragment or slash."""
    path = urlsplit(url_or_path).path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    return path if path == "/" else path.rstrip("/")


def _template_pattern(template: str) -> re.Pattern[str]:
    pieces: list[str] = []
    cursor = 0
    for match in _TEMPLATE_PART.finditer(template):
        pieces.append(re.escape(template[cursor : match.start()]))
        pieces.append(f"(?P<{match.group(1)}>[^/]+)")
        cursor = match.end()
    pieces.append(re.escape(template[cursor:]))
    return re.compile("^" + "".join(pieces) + "$")


def _fill(value: str, captures: Mapping[str, str]) -> str:
    return _TEMPLATE_PART.sub(lambda match: captures.get(match.group(1), match.group(0)), value)


def _path_is_allowed(file_path: str, allowed_prefixes: Sequence[str]) -> bool:
    candidate = PurePosixPath(file_path)
    if candidate.is_absolute() or ".." in candidate.parts or ".git" in candidate.parts:
        return False
    return any(
        candidate.parts[: len(PurePosixPath(prefix).parts)] == PurePosixPath(prefix).parts
        for prefix in allowed_prefixes
        if prefix.strip("/")
    )


def _locator_from_document(
    document: object,
    captures: Mapping[str, str],
    allowed_prefixes: Sequence[str],
    field_name: str,
) -> SiteMapLocator:
    if not isinstance(document, Mapping):
        raise SEOSiteMappingRequiredError(f"Page map entry for {field_name} is not an object.")
    raw_path = document.get("file_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise SEOSiteMappingRequiredError(f"Page map entry for {field_name} has no file_path.")
    file_path = _fill(raw_path, captures)
    if _TEMPLATE_PART.search(file_path) or not _path_is_allowed(file_path, allowed_prefixes):
        raise SEOSiteMappingRequiredError(
            f"{file_path} is outside this target's allowed site-change paths."
        )
    source_type = document.get("source_type")
    if source_type == "keystatic_json":
        pointer = document.get("json_pointer")
        if (
            not isinstance(pointer, Sequence)
            or isinstance(pointer, str)
            or not pointer
            or not all(isinstance(part, str) for part in pointer)
        ):
            raise SEOSiteMappingRequiredError(f"{field_name} has an invalid json_pointer.")
        return KeystaticJsonLocator(file_path=file_path, json_pointer=tuple(pointer))
    if source_type == "frontmatter":
        key = document.get("key")
        if not isinstance(key, str) or not key:
            raise SEOSiteMappingRequiredError(f"{field_name} has no frontmatter key.")
        return FrontmatterLocator(file_path=file_path, key=key)
    if source_type == "astro_code":
        binding = document.get("binding_name")
        if not isinstance(binding, str) or not binding:
            raise SEOSiteMappingRequiredError(f"{field_name} has no binding_name.")
        return AstroCodeLocator(file_path=file_path, binding_name=binding)
    raise SEOSiteMappingRequiredError(f"{field_name} has an unsupported source_type.")


def page_map_from_contract(contract: object) -> Mapping[str, object]:
    """The declarative page map stored on a publishing target, or empty."""
    if not isinstance(contract, Mapping):
        return {}
    page_map = contract.get("page_map")
    return page_map if isinstance(page_map, Mapping) else {}


def resolve_entry(
    page_map: Mapping[str, object],
    url_or_path: str,
    allowed_prefixes: Sequence[str],
) -> SiteMapEntry:
    """Resolve one live page to its exact per-field locators, or refuse that page.

    An exact key beats a template. Two templates matching the same path is
    ambiguous and refused; so is any mapped file outside the target's allowed
    site-change prefixes.
    """
    url_path = normalize_url_path(url_or_path)
    matched: tuple[str, Mapping[str, str]] | None = None
    if url_path in page_map:
        matched = (url_path, {})
    else:
        templates: list[tuple[str, Mapping[str, str]]] = []
        for key in page_map:
            if not _TEMPLATE_PART.search(key):
                continue
            found = _template_pattern(key).match(url_path)
            if found:
                templates.append((key, found.groupdict()))
        if len(templates) > 1:
            raise SEOSiteMappingRequiredError(
                f"{url_path} matches more than one page map template."
            )
        if templates:
            matched = templates[0]
    if matched is None:
        raise SEOSiteMappingRequiredError(f"{url_path} has no entry in this target's page map.")

    key, captures = matched
    raw_fields = page_map[key]
    if not isinstance(raw_fields, Mapping) or not raw_fields:
        raise SEOSiteMappingRequiredError(f"Page map entry {key} declares no fields.")
    fields: dict[SiteChangeField, SiteMapLocator] = {}
    for raw_field, document in raw_fields.items():
        try:
            field = SiteChangeField(str(raw_field))
        except ValueError as exc:
            raise SEOSiteMappingRequiredError(
                f"Page map entry {key} names unknown field {raw_field!r}."
            ) from exc
        fields[field] = _locator_from_document(document, captures, allowed_prefixes, str(raw_field))
    return SiteMapEntry(url_path=url_path, fields=fields)
