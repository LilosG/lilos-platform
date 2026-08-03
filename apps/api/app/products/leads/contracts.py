from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LeadIntake(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_id: UUID
    external_submission_id: str = Field(min_length=1, max_length=500)
    location_id: UUID | None = None
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    service_id: UUID | None = None
    message: str | None = Field(default=None, max_length=10000)
    received_at: datetime


class ConsentRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    channel: Literal["email", "sms", "phone"]
    consent_type: Literal[
        "transactional_email",
        "transactional_sms",
        "marketing_email",
        "marketing_sms",
        "phone_call",
        "automated_call",
    ]
    status: Literal["granted", "denied", "unknown", "not_required", "withdrawn", "expired"]
    source: str = Field(min_length=1, max_length=64)
    disclosure_version: str = Field(min_length=1, max_length=64)
    evidence_reference: str = Field(min_length=1, max_length=500)
    captured_at: datetime


class CommunicationCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    channel: Literal["email", "sms"]
    consent_type: Literal[
        "transactional_email", "transactional_sms", "marketing_email", "marketing_sms"
    ]
    message_reference: str = Field(min_length=1, max_length=500)
    workflow_run_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)
