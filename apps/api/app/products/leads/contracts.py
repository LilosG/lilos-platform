from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONSENT_TYPES_BY_CHANNEL = {
    "email": frozenset({"transactional_email", "marketing_email"}),
    "sms": frozenset({"transactional_sms", "marketing_sms"}),
    "phone": frozenset({"phone_call", "automated_call"}),
}


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

    @model_validator(mode="after")
    def consent_type_matches_channel(self) -> Self:
        if self.consent_type not in CONSENT_TYPES_BY_CHANNEL[self.channel]:
            raise ValueError("consent_type is not valid for the selected channel")
        return self


class CommunicationCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    channel: Literal["email", "sms"]
    consent_type: Literal[
        "transactional_email", "transactional_sms", "marketing_email", "marketing_sms"
    ]
    message_reference: str = Field(min_length=1, max_length=500)
    workflow_run_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def consent_type_matches_channel(self) -> Self:
        if self.consent_type not in CONSENT_TYPES_BY_CHANNEL[self.channel]:
            raise ValueError("consent_type is not valid for the selected channel")
        return self


class LeadAssignment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    assigned_to_user_id: UUID


class LeadStatusTransition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    to_status: Literal[
        "new",
        "validating",
        "unassigned",
        "assigned",
        "acknowledged",
        "contact_attempted",
        "contacted",
        "qualifying",
        "qualified",
        "appointment_requested",
        "appointment_scheduled",
        "nurture",
        "unresponsive",
        "archived",
    ]
    safe_reason: str | None = Field(default=None, max_length=500)


class LeadConversion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    converted_value_cents: int | None = Field(default=None, ge=0)


class LeadLoss(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    to_status: Literal["lost", "disqualified", "spam", "cancelled"]
    loss_reason: str = Field(min_length=1, max_length=500)


class LeadNoteCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    body: str = Field(min_length=1, max_length=5000)


class LeadTaskCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None
    assigned_to_user_id: UUID | None = None
