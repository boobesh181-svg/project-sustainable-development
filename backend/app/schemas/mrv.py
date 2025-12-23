"""Pydantic schemas for MRV reports and calculations."""

from uuid import UUID
from datetime import datetime
from enum import Enum as PyEnum
from pydantic import BaseModel, ConfigDict


class MRVStatus(str, PyEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class MRVReportCreate(BaseModel):
    project_id: UUID
    parameter: str
    value: str
    emission_factor_id: UUID | None = None


class MRVReportOut(BaseModel):
    id: UUID
    project_id: UUID
    parameter: str
    value: str
    status: MRVStatus
    ts: datetime
    emission_factor_version_snapshot: str | None
    emission_factor_hash_snapshot: str | None
    emission_factor_value_snapshot: float | None
    
    model_config = ConfigDict(from_attributes=True)


class MRVCalculationResult(BaseModel):
    report_id: str
    co2e: float
    co2e_unit: str
    factor_version: str
    factor_hash: str
    factor_value: float
    input_value: float
