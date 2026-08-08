from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsPropertySelect(BaseModel):
    """Operator selects a discovered GA4 property to map."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    external_property_id: str = Field(min_length=1, max_length=500)
    property_number: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=300)


class AnalyticsSyncRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    days: int = Field(default=28, ge=7, le=365)


class AnalyticsDiscoverRequest(BaseModel):
    """Optional website id to drive canonical-domain recommendation."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    website_id: UUID | None = None
