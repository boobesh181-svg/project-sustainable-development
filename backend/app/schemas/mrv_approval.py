"""Pydantic schemas for MRV approval workflow (immutable-after-approval)."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class MRVReportCreate(BaseModel):
    """Create a new MRV report (DRAFT state)."""
    project_id: UUID
    reporting_period: str = Field(..., min_length=1, max_length=50, description="e.g., '2025-Q1'")
    sample_desc: str = Field(..., min_length=1)
    parameter: str = Field(..., min_length=1, max_length=255)
    value: str = Field(..., min_length=1, max_length=255)
    total_co2e: float = Field(..., gt=0, description="Total CO2 equivalent in tonnes")
    created_by: str = Field(..., min_length=1, max_length=100)
    emission_factor_id: UUID | None = None
    certificate_path: str | None = None


class MRVReportAdvance(BaseModel):
    """Advance MRV report to next workflow state."""
    next_status: str = Field(
        ...,
        description="Target status: SUBMITTED, VERIFIED, APPROVED, or LOCKED"
    )
    actor: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User advancing the workflow (verifier/approver)"
    )


class MRVReportOut(BaseModel):
    """MRV report response (full details)."""
    id: UUID
    project_id: UUID
    reporting_period: str
    sample_desc: str
    parameter: str
    value: str
    total_co2e: float
    status: str
    created_by: str
    verified_by: str | None
    approved_by: str | None
    created_at: datetime
    updated_at: datetime
    emission_factor_id: UUID | None
    certificate_path: str | None
    emission_factor_version_snapshot: str | None
    emission_factor_hash_snapshot: str | None
    emission_factor_value_snapshot: float | None
    
    model_config = ConfigDict(from_attributes=True)


class MRVReportSummary(BaseModel):
    """MRV report summary (list view)."""
    id: UUID
    project_id: UUID
    reporting_period: str
    total_co2e: float
    status: str
    created_by: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
