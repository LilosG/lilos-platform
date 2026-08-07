from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WebsiteCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    location_id: UUID | None = None
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=300)
    canonical_origin: str = Field(min_length=1, max_length=1000)


class SearchPropertyCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    connection_id: UUID
    external_property_id: str = Field(min_length=1, max_length=1000)
    property_type: Literal["domain", "url_prefix"]


class SearchPropertySelect(BaseModel):
    """Operator selects a discovered Search Console property to map."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    external_property_id: str = Field(min_length=1, max_length=1000)
    property_type: Literal["domain", "url_prefix"]


class SearchConsoleSyncRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    days: int = Field(default=28, ge=7, le=365)


class CrawlRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    workflow_run_id: UUID
    seed_paths: list[str] = Field(default_factory=lambda: ["/"], max_length=20)
    max_pages: int = Field(default=5, ge=1, le=20)
    idempotency_key: str = Field(min_length=8, max_length=128)


class RecommendationCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    proposed_action: str = Field(min_length=1, max_length=10000)
    evidence_references: list[str] = Field(default_factory=list, max_length=100)
    expected_result_hypothesis: str = Field(min_length=1, max_length=2000)
    risk: Literal["low", "medium", "high"]
    effort: Literal["low", "medium", "high"]


class RecommendationDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approve: bool


class ImplementationTaskCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    workflow_run_id: UUID
    target_type: str = Field(min_length=1, max_length=32)
    target_reference: str = Field(min_length=1, max_length=1000)


class ImplementationTaskVerify(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    verification_evidence: dict[str, object] = Field(default_factory=dict)


class OutcomeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    baseline_start: str
    baseline_end: str
    measurement_start: str
    measurement_end: str
    classification: Literal["improved", "unchanged", "regressed", "inconclusive"]
    metrics: dict[str, object] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list, max_length=20)
