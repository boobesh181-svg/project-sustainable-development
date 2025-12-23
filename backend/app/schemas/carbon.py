"""Pydantic schemas for carbon credit lifecycle."""

from uuid import UUID
from datetime import datetime
from enum import Enum as PyEnum
from pydantic import BaseModel, ConfigDict


class LifecycleStatus(str, PyEnum):
    ISSUED = "issued"
    VERIFIED = "verified"
    APPROVED = "approved"
    RETIRED = "retired"


class CarbonCreditCreate(BaseModel):
    project_id: UUID | None = None
    co2e_amount_tonnes: float
    methodology_version: str
    emission_factor_version: str
    issuer_id: UUID
    verifier_id: UUID
    approver_id: UUID


class CarbonCreditOut(BaseModel):
    id: UUID
    serial_number: int
    project_id: UUID | None
    status: LifecycleStatus
    co2e_amount_tonnes: float
    methodology_version: str
    emission_factor_version: str
    issued_at: datetime
    verified_at: datetime | None
    approved_at: datetime | None
    retired_at: datetime | None
    retirement_reason: str | None
    
    model_config = ConfigDict(from_attributes=True)


class CarbonCreditRetirement(BaseModel):
    retirement_reason: str
    retirement_note: str | None = None
