from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MethodologyVersionCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=128)
    description: str | None = Field(None, max_length=255)


class MethodologyVersionOut(BaseModel):
    id: UUID
    code: str
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportingContextCreate(BaseModel):
    reporting_entity_id: UUID
    consolidation_method: str = Field(
        ..., pattern="^(EQUITY|FINANCIAL_CONTROL|OPERATIONAL_CONTROL)$"
    )
    reporting_purpose: str = Field(
        ..., pattern="^(ESG|PROCUREMENT|TAX|DISCLOSURE)$"
    )
    methodology_version_id: UUID
    valid_from: datetime
    valid_to: datetime | None = None


class ReportingContextOut(BaseModel):
    id: UUID
    reporting_entity_id: UUID
    consolidation_method: str
    reporting_purpose: str
    methodology_version_id: UUID
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganizationRelationshipCreate(BaseModel):
    project_id: UUID
    organization_id: UUID
    role_type: str = Field(
        ..., pattern="^(DEVELOPER|CONTRACTOR|SUPPLIER|OPERATOR)$"
    )
    ownership_percentage: Decimal | None = Field(None, ge=0, le=100)
    financial_control: bool = False
    operational_control: bool = False
    valid_from: datetime
    valid_to: datetime | None = None


class OrganizationRelationshipOut(BaseModel):
    id: UUID
    project_id: UUID
    organization_id: UUID
    role_type: str
    ownership_percentage: Decimal | None
    financial_control: bool
    operational_control: bool
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportGenerateRequest(BaseModel):
    project_id: UUID
    reporting_context_id: UUID


class ReportViewOut(BaseModel):
    id: UUID
    project_id: UUID
    reporting_context_id: UUID
    generated_at: datetime
    total_emissions: Decimal
    calculation_hash: str

    model_config = ConfigDict(from_attributes=True)


class ReportViewExportOut(BaseModel):
    report_view: ReportViewOut
    reporting_context: ReportingContextOut
    methodology_version: MethodologyVersionOut
    reporting_entity: OrganizationOut

    boundary_method: str
    reporting_purpose: str
    calculation_timestamp: datetime
    total_emissions: Decimal
    calculation_hash: str
