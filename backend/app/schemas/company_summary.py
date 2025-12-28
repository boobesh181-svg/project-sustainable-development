from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmissionsByMaterial(BaseModel):
    material_code: str
    material_name: str | None = None
    emissions_tco2e: float = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class EmissionsBySupplier(BaseModel):
    supplier_name: str
    emissions_tco2e: float = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class EmissionsByProject(BaseModel):
    project_id: UUID
    project_name: str
    emissions_tco2e: float = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class ReportStatusShare(BaseModel):
    status: str
    count: int = Field(ge=0)
    pct: float = Field(ge=0, le=100)

    model_config = ConfigDict(from_attributes=True)


class EmissionFactorSource(BaseModel):
    material_code: str
    material_name: str
    version: int
    unit: str
    co2e_per_unit: float
    factor_hash: str
    valid_from: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyMRVSummary(BaseModel):
    total_emissions_tco2e: float = Field(ge=0)

    emissions_by_material: list[EmissionsByMaterial]
    emissions_by_supplier: list[EmissionsBySupplier]
    emissions_by_project: list[EmissionsByProject]

    pct_verified: float = Field(ge=0, le=100)
    pct_approved: float = Field(ge=0, le=100)
    pct_locked: float = Field(ge=0, le=100)

    reporting_period_start: datetime | None
    reporting_period_end: datetime | None

    methodology_version: str
    emission_factor_sources_used: list[EmissionFactorSource]
    reports_by_status: list[ReportStatusShare]

    model_config = ConfigDict(from_attributes=True)
