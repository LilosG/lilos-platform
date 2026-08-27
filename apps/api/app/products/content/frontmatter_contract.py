"""Map canonical content fields onto one client's Astro collection schema.

Every client Astro blog collection declares `title` and `description`. Beyond
that they diverge in ways that a shared field set cannot express, verified against
the live repositories:

- the publish date is `date` (wheylandelectric), `pubDate` (carlsbadfixit), or a
  required `publishDate` typed `z.date()` (tamarackrestoration) or `z.string()`
  (kelari-party-rentals)
- `category` is a required enum for tamarackrestoration and kelari-party-rentals
- `serviceAreas` and `services` are enum-constrained for carlsbadfixit, so an
  arbitrary string fails validation
- sage-therapy-center names FAQ keys `q`/`a` rather than `question`/`answer`

Emitting a key the schema does not declare, or a value outside an enum, fails
`astro build` and breaks that client's deployment on merge. So generation produces
canonical fields and this module renames and validates them per target. A target
with no recorded contract falls back to the universal floor, which is the only
assumption safe for every client.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from apps.api.app.products.content.file_format import UNIVERSAL_REQUIRED_FRONTMATTER

# Canonical names produced by content generation, independent of any client.
CANONICAL_TITLE = "title"
CANONICAL_DESCRIPTION = "description"
CANONICAL_PUBLISH_DATE = "publish_date"
CANONICAL_FAQS = "faqs"
CANONICAL_TAGS = "tags"
CANONICAL_SERVICES = "related_services"
CANONICAL_SERVICE_AREAS = "service_areas"
CANONICAL_CATEGORY = "category"
CANONICAL_IMAGE = "image"
CANONICAL_IMAGE_ALT = "image_alt"


class FrontmatterContractError(ValueError):
    """Generated frontmatter cannot satisfy this target's collection schema."""

    def __init__(self, safe_code: str, message: str) -> None:
        super().__init__(message)
        self.safe_code = safe_code


@dataclass(frozen=True, slots=True)
class FrontmatterContract:
    """One target's field names, required fields and allowed enum values."""

    # canonical name -> the key this client's schema declares
    field_names: Mapping[str, str] = field(default_factory=dict)
    required: tuple[str, ...] = UNIVERSAL_REQUIRED_FRONTMATTER
    # "date" emits an unquoted ISO date for z.coerce.date()/z.date();
    # "string" emits a quoted ISO string for z.string().
    date_format: str = "date"
    faq_question_key: str = "question"
    faq_answer_key: str = "answer"
    # target field name -> allowed values. A value outside the set is dropped
    # rather than published, because z.enum rejects it at build time.
    enums: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    defaults: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_document(cls, document: object) -> FrontmatterContract:
        """Build a contract from the target's stored JSON, tolerating an empty one."""
        if not isinstance(document, Mapping) or not document:
            return cls()
        raw_names = document.get("field_names")
        field_names = (
            {str(k): str(v) for k, v in raw_names.items()} if isinstance(raw_names, Mapping) else {}
        )
        raw_required = document.get("required")
        required = (
            tuple(str(item) for item in raw_required)
            if isinstance(raw_required, Sequence) and not isinstance(raw_required, str)
            else UNIVERSAL_REQUIRED_FRONTMATTER
        )
        raw_enums = document.get("enums")
        enums: dict[str, tuple[str, ...]] = {}
        if isinstance(raw_enums, Mapping):
            for key, values in raw_enums.items():
                if isinstance(values, Sequence) and not isinstance(values, str):
                    enums[str(key)] = tuple(str(value) for value in values)
        date_format = str(document.get("date_format") or "date")
        if date_format not in {"date", "string"}:
            raise FrontmatterContractError(
                "CONTENT_CONTRACT_INVALID",
                "date_format must be 'date' or 'string'",
            )
        raw_defaults = document.get("defaults")
        return cls(
            field_names=field_names,
            required=required,
            date_format=date_format,
            faq_question_key=str(document.get("faq_question_key") or "question"),
            faq_answer_key=str(document.get("faq_answer_key") or "answer"),
            enums=enums,
            defaults=dict(raw_defaults) if isinstance(raw_defaults, Mapping) else {},
        )

    def target_key(self, canonical: str) -> str:
        return self.field_names.get(canonical, canonical)

    def _allowed(self, target_key: str, value: str) -> bool:
        permitted = self.enums.get(target_key)
        return permitted is None or value in permitted

    def render(self, canonical: Mapping[str, Any]) -> dict[str, Any]:
        """Rename canonical fields to this client's keys, dropping what cannot build.

        Values outside a declared enum are omitted rather than emitted: a page
        missing an optional tag still builds, while one carrying an undeclared enum
        member does not. Required fields are checked after mapping, so a dropped
        required value surfaces as a clear error instead of an invalid file.
        """
        rendered: dict[str, Any] = {}

        def put(canonical_name: str, value: Any) -> None:
            if value is None:
                return
            key = self.target_key(canonical_name)
            if isinstance(value, str):
                if not value.strip() or not self._allowed(key, value):
                    return
                rendered[key] = value
                return
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                kept = [
                    str(entry)
                    for entry in value
                    if isinstance(entry, str) and entry.strip() and self._allowed(key, entry)
                ]
                if kept:
                    rendered[key] = kept
                return
            rendered[key] = value

        put(CANONICAL_TITLE, canonical.get(CANONICAL_TITLE))
        put(CANONICAL_DESCRIPTION, canonical.get(CANONICAL_DESCRIPTION))

        publish_date = canonical.get(CANONICAL_PUBLISH_DATE)
        if publish_date is not None:
            key = self.target_key(CANONICAL_PUBLISH_DATE)
            if isinstance(publish_date, (date, datetime)):
                iso = (
                    publish_date.date().isoformat()
                    if isinstance(publish_date, datetime)
                    else publish_date.isoformat()
                )
            else:
                iso = str(publish_date)
            # z.string() must receive a quoted string; z.date()/z.coerce.date()
            # accept either, so a plain string is safe for both.
            rendered[key] = iso

        faqs = canonical.get(CANONICAL_FAQS)
        if isinstance(faqs, Sequence) and not isinstance(faqs, (str, bytes)):
            entries: list[dict[str, str]] = []
            for entry in faqs:
                if not isinstance(entry, Mapping):
                    continue
                question = str(entry.get("question") or "").strip()
                answer = str(entry.get("answer") or "").strip()
                if question and answer:
                    entries.append({self.faq_question_key: question, self.faq_answer_key: answer})
            if entries:
                rendered[self.target_key(CANONICAL_FAQS)] = entries

        for name in (
            CANONICAL_TAGS,
            CANONICAL_SERVICES,
            CANONICAL_SERVICE_AREAS,
            CANONICAL_CATEGORY,
            CANONICAL_IMAGE,
            CANONICAL_IMAGE_ALT,
        ):
            put(name, canonical.get(name))

        for key, value in self.defaults.items():
            rendered.setdefault(str(key), value)
        return rendered

    def missing_required(self, rendered: Mapping[str, Any]) -> tuple[str, ...]:
        """Required target keys that are absent or blank after mapping."""
        missing: list[str] = []
        for key in self.required:
            value = rendered.get(key)
            if (
                value is None
                or (isinstance(value, str) and not value.strip())
                or isinstance(value, Sequence)
                and not isinstance(value, (str, bytes))
                and not value
            ):
                missing.append(key)
        return tuple(missing)
