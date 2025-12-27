from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Base schemas
class BaseMRVSchema(BaseModel):
    """Base schema for MRV models"""
    
    model_config = ConfigDict(
        from_attributes=True,
    )


# Sample schemas
class MRVSampleCreate(BaseMRVSchema):
    """Schema for creating MRV samples"""
    sample_id: Optional[str] = Field(None, description="Optional custom sample ID, auto-generated if not provided")
    project_id: str = Field(..., description="Project UUID")
    collected_by: str = Field(..., description="Who collected the sample")
    geotag_lat: float = Field(..., description="Latitude coordinate")
    geotag_lon: float = Field(..., description="Longitude coordinate")
    sample_type: str = Field(..., description="Type of sample (e.g., 'concrete', 'steel', 'soil')")
    notes: Optional[str] = Field(None, description="Optional notes about the sample")
    
    @field_validator('geotag_lat')
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v
    
    @field_validator('geotag_lon')
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v


class MRVSampleUpdate(BaseMRVSchema):
    """Schema for updating MRV samples"""
    status: Optional[str] = Field(None, description="Sample status")
    notes: Optional[str] = Field(None, description="Optional notes about the sample")
    chain_of_custody: Optional[Dict[str, Any]] = Field(None, description="Chain of custody data")


class MRVSampleResponse(BaseMRVSchema):
    """Schema for MRV sample responses"""
    sample_id: str
    project_id: str
    collected_by: str
    collected_at: datetime
    geotag_lat: float
    geotag_lon: float
    sample_type: str
    chain_of_custody: Dict[str, Any]
    notes: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


# Test schemas
class MRVTestCreate(BaseMRVSchema):
    """Schema for creating MRV tests"""
    sample_id: str = Field(..., description="Sample ID")
    lab_id: str = Field(..., description="Laboratory UUID")
    parameter: str = Field(..., description="Parameter being tested")
    value: str = Field(..., description="Test result value")
    unit: str = Field(..., description="Unit of measurement")
    method: str = Field(..., description="Testing method used")
    lab_report_id: Optional[str] = Field(None, description="Laboratory report ID")
    passed: bool = Field(..., description="Whether test passed criteria")
    notes: Optional[str] = Field(None, description="Optional notes about the test")


class MRVTestUpdate(BaseMRVSchema):
    """Schema for updating MRV tests"""
    value: Optional[str] = Field(None, description="Test result value")
    passed: Optional[bool] = Field(None, description="Whether test passed criteria")
    notes: Optional[str] = Field(None, description="Optional notes about the test")


class MRVTestResponse(BaseMRVSchema):
    """Schema for MRV test responses"""
    id: str
    sample_id: str
    lab_id: str
    parameter: str
    value: str
    unit: str
    method: str
    certificate_file: Optional[str]
    lab_report_id: Optional[str]
    passed: bool
    notes: Optional[str]
    tested_at: datetime
    created_at: datetime


# Lab schemas
class LabCreate(BaseMRVSchema):
    """Schema for creating labs"""
    name: str = Field(..., description="Laboratory name")
    address: str = Field(..., description="Laboratory address")
    accreditation: Optional[str] = Field(None, description="Accreditation information")
    contact: Optional[str] = Field(None, description="Contact information")


class LabUpdate(BaseMRVSchema):
    """Schema for updating labs"""
    name: Optional[str] = Field(None, description="Laboratory name")
    address: Optional[str] = Field(None, description="Laboratory address")
    accreditation: Optional[str] = Field(None, description="Accreditation information")
    contact: Optional[str] = Field(None, description="Contact information")


class LabResponse(BaseMRVSchema):
    """Schema for lab responses"""
    lab_id: str
    name: str
    address: str
    accreditation: Optional[str]
    contact: Optional[str]
    created_at: datetime


# Chain step schemas
class ChainStepCreate(BaseMRVSchema):
    """Schema for creating chain of custody steps"""
    sample_id: str = Field(..., description="Sample ID")
    actor: str = Field(..., description="Person/organization performing the action")
    action: str = Field(..., description="Action performed")
    evidence_file: Optional[str] = Field(None, description="Path to evidence file")


class ChainStepResponse(BaseMRVSchema):
    """Schema for chain of custody step responses"""
    id: str
    sample_id: str
    actor: str
    action: str
    timestamp: datetime
    evidence_file: Optional[str]


# Event log schemas
class MRVEventLogCreate(BaseMRVSchema):
    """Schema for creating MRV event logs"""
    ref_type: str = Field(..., description="Reference type ('sample', 'test', 'lab')")
    ref_id: str = Field(..., description="Reference ID")
    event: str = Field(..., description="Event description")
    actor: str = Field(..., description="Person/organization performing the event")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional event details")


class MRVEventLogResponse(BaseMRVSchema):
    """Schema for MRV event log responses"""
    id: str
    ref_type: str
    ref_id: str
    event: str
    actor: str
    ts: datetime
    details: Dict[str, Any]


# Upload and utility schemas
class MRVUploadResponse(BaseMRVSchema):
    """Schema for file upload responses"""
    file_path: str = Field(..., description="Path to uploaded file")
    file_name: str = Field(..., description="Original file name")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="File content type")


class MRVStatsResponse(BaseMRVSchema):
    """Schema for MRV statistics"""
    total_samples: int
    samples_by_status: Dict[str, int]
    total_tests: int
    tests_by_parameter: Dict[str, int]
    pass_rate: float
    avg_processing_time_days: float
    active_labs: int


# Combined response schemas
class MRVSampleDetailResponse(BaseMRVSchema):
    """Schema for detailed sample response including tests and chain steps"""
    sample: MRVSampleResponse
    tests: list[MRVTestResponse]
    chain_steps: list[ChainStepResponse]
