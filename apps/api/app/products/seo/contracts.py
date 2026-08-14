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
    model_config = ConfigDict(frozen=True, extra="forbid")
    external_property_id: str = Field(min_length=1, max_length=1000)
    property_type: Literal["domain", "url_prefix"]


class SearchConsoleSyncRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    days: int = Field(default=28, ge=7, le=365)


class CrawlRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    workflow_run_id: UUID
    seed_paths: list[str] = Field(default_factory=lambda: ["/"], max_length=50)
    max_pages: int = Field(default=50, ge=1, le=500)
    max_depth: int = Field(default=3, ge=1, le=10)
    crawl_delay_seconds: float = Field(default=1.0, ge=0.1, le=10.0)
    request_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    total_timeout_seconds: float = Field(default=600.0, ge=30.0, le=3600.0)
    max_redirects: int = Field(default=5, ge=0, le=10)
    concurrency: int = Field(default=4, ge=1, le=10)
    retry_limit: int = Field(default=2, ge=0, le=5)
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