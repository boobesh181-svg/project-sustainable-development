"""Pydantic schemas for emission factors with immutability enforcement."""

from uuid import UUID
from datetime import datetime
from enum import Enum as PyEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmissionFactorSourceType(str, PyEnum):
    IPCC = "IPCC"
    NATIONAL = "National"
    EPD = "EPD"


class EmissionFactorCreate(BaseModel):
    material_code: str = Field(..., json_schema_extra={"example": "CEMENT_OPC"}, min_length=1, max_length=100)
    material_name: str = Field(..., min_length=1, max_length=255)
    version: int = Field(..., ge=1)
    co2e_per_unit: float = Field(..., gt=0, description="kg CO₂e per unit")
    unit: str = Field(default="kg", max_length=50)
    # ISO-grade governance metadata
    source_type: EmissionFactorSourceType = Field(default=EmissionFactorSourceType.NATIONAL)
    jurisdiction: str = Field(default="GLOBAL", min_length=1, max_length=64)
    methodology_reference: str = Field(default="unspecified", min_length=1, max_length=255)
    valid_from: datetime
    valid_to: datetime | None = None
    # Deprecated: server derives actor identity from JWT; retained for backward compatibility.
    created_by: str | None = Field(None, min_length=1)

    @field_validator("valid_to")
    @classmethod
    def _valid_to_after_from(cls, v: datetime | None, info):
        valid_from = info.data.get("valid_from")
        if v is not None and valid_from is not None and v < valid_from:
            raise ValueError("valid_to must be >= valid_from")
        return v


class EmissionFactorOut(BaseModel):
    id: UUID
    material_code: str
    material_name: str
    version: int
    co2e_per_unit: float
    unit: str
    source_type: EmissionFactorSourceType
    jurisdiction: str
    methodology_reference: str
    valid_from: datetime
    valid_to: datetime | None
    is_active: bool
    factor_hash: str
    created_at: datetime
    created_by: str
    created_by_user_id: UUID | None = None
    
    model_config = ConfigDict(from_attributes=True)


class EmissionFactorActivate(BaseModel):
    """Request to activate (lock) an emission factor."""
    pass

