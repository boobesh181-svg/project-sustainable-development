"""Pydantic schemas for emission factors with immutability enforcement."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmissionFactorCreate(BaseModel):
    material_code: str = Field(..., example="CEMENT_OPC", min_length=1, max_length=100)
    material_name: str = Field(..., min_length=1, max_length=255)
    version: int = Field(..., ge=1)
    co2e_per_unit: float = Field(..., gt=0, description="kg CO₂e per unit")
    unit: str = Field(default="kg", max_length=50)
    valid_from: datetime
    created_by: str = Field(..., min_length=1)


class EmissionFactorOut(BaseModel):
    id: UUID
    material_code: str
    material_name: str
    version: int
    co2e_per_unit: float
    unit: str
    valid_from: datetime
    valid_to: datetime | None
    is_active: bool
    factor_hash: str
    created_at: datetime
    created_by: str
    
    model_config = ConfigDict(from_attributes=True)


class EmissionFactorActivate(BaseModel):
    """Request to activate (lock) an emission factor."""
    pass

