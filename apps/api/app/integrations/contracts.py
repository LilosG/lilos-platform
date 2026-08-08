"""Typed request contracts for Google OAuth integration routes."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class GoogleConnectRequest(Contract):
    """Begin (or re-consent) a Google connection for the given products.

    Defaults to ``gbp`` only to preserve the existing GBP-page behavior; the
    Integrations page requests the union of products it needs so a single
    Google authorization covers Business Profile, Search Console, and
    Analytics. Re-consent reuses the existing connection row.
    """

    products: list[Literal["gbp", "search_console", "analytics"]] = Field(
        default=["gbp"], min_length=1, max_length=3
    )


class MappingCreate(Contract):
    """Bind a discovered Google Business Profile location to a platform resource."""

    connection_id: UUID
    external_resource_id: Annotated[str, Field(min_length=1, max_length=500)]
    platform_resource_id: UUID | None = None
