"""Typed structured change proposals for governed site edits.

A SEO recommendation used to be free prose (`proposed_action: str`) with no
machine-checkable claim about what would actually change on the client's
site. `SiteChangeSet` makes the proposal a closed, exact claim -- which
page, which field, its current value (read from the live repo, never
guessed), and the proposed replacement -- so that what a human approves is
provably what the site-change executor (B4) applies, byte for byte. The
approval flow records `SiteChangeSet.fingerprint()`; execution re-derives it
from the change set it is about to apply and refuses on any mismatch.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Deterministic validation bounds. These are the same constraints a search
# engine or the client's own CMS would enforce; Hermes drafts a value but
# never gets to skip them (see B4a: `create_site_change_item`).
MAX_SEO_TITLE_LENGTH = 60
MAX_META_DESCRIPTION_LENGTH = 160


class SiteChangeField(StrEnum):
    """The closed set of page fields a governed site change may target."""

    SEO_TITLE = "seo_title"
    META_DESCRIPTION = "meta_description"
    H1 = "h1"
    BODY_SECTION = "body_section"
    SCHEMA = "schema"
    INTERNAL_LINK = "internal_link"


_FIELD_MAX_LENGTH: dict[SiteChangeField, int | None] = {
    SiteChangeField.SEO_TITLE: MAX_SEO_TITLE_LENGTH,
    SiteChangeField.META_DESCRIPTION: MAX_META_DESCRIPTION_LENGTH,
    SiteChangeField.H1: None,
    SiteChangeField.BODY_SECTION: None,
    SiteChangeField.SCHEMA: None,
    SiteChangeField.INTERNAL_LINK: None,
}


class SiteChangeItem(BaseModel):
    """One exact field-level edit to one page.

    `current_value` must be read from the live repo file through
    `site_map_resolver` before this is constructed -- it is evidence, not a
    claim Hermes gets to assert. `proposed_value` is validated deterministically
    here so an over-length or no-op edit can never reach approval.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    page_id: UUID
    field: SiteChangeField
    current_value: str = Field(max_length=10_000)
    proposed_value: str = Field(min_length=1, max_length=10_000)
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_proposed_value(self) -> SiteChangeItem:
        if self.proposed_value == self.current_value:
            raise ValueError(
                f"proposed_value for {self.field.value} must differ from current_value"
            )
        max_length = _FIELD_MAX_LENGTH[self.field]
        if max_length is not None and len(self.proposed_value) > max_length:
            raise ValueError(
                f"proposed_value for {self.field.value} exceeds {max_length} characters "
                f"({len(self.proposed_value)})"
            )
        return self


class SiteChangeSet(BaseModel):
    """An ordered, exact set of edits. What is approved is exactly what executes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[SiteChangeItem] = Field(min_length=1, max_length=20)

    def fingerprint(self) -> str:
        """Stable digest recorded at approval and re-derived at execution.

        Execution refuses to apply a change set whose fingerprint does not
        match the one recorded when a human approved it -- see
        `seo_recommendation_revisions.change_set_fingerprint`.
        """
        payload = json.dumps(
            [item.model_dump(mode="json") for item in self.items],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()
