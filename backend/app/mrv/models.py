from __future__ import annotations

from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum
from typing import Any, Dict

from sqlalchemy import (
    Boolean, DateTime, Enum as SAEnum, ForeignKey, 
    Index, JSON, Numeric, String, Text, Float
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MRVSampleStatus(str, PyEnum):
    COLLECTED = "collected"
    SUBMITTED = "submitted"
    IN_LAB = "in_lab"
    TESTED = "tested"
    APPROVED = "approved"
    REJECTED = "rejected"


class MRVSample(Base):
    """MRV Sample tracking model"""
    __tablename__ = "mrv_sample"
    
    sample_id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=lambda: str(uuid.uuid4())[:8]
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project.id"), nullable=False  # UUID as string for SQLite compatibility
    )
    collected_by: Mapped[str] = mapped_column(String(255), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    geotag_lat: Mapped[float] = mapped_column(Numeric(10, 8), nullable=False)
    geotag_lon: Mapped[float] = mapped_column(Numeric(11, 8), nullable=False)
    sample_type: Mapped[str] = mapped_column(String(100), nullable=False)
    chain_of_custody: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MRVSampleStatus] = mapped_column(
        SAEnum(MRVSampleStatus, name="mrv_sample_status"), 
        default=MRVSampleStatus.COLLECTED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    mrv_flags: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # Store last QA check summary
    
    # Relationships
    tests: Mapped[list[MRVTest]] = relationship("MRVTest", back_populates="sample", cascade="all, delete-orphan")
    chain_steps: Mapped[list[ChainStep]] = relationship("ChainStep", back_populates="sample", cascade="all, delete-orphan")
    project: Mapped["Project"] = relationship("Project", back_populates="mrv_samples")
    
    # Indexes
    __table_args__ = (
        Index('idx_mrv_sample_project_id', 'project_id'),
        Index('idx_mrv_sample_status', 'status'),
        Index('idx_mrv_sample_collected_at', 'collected_at'),
    )
    
    def __repr__(self) -> str:
        return f"<MRVSample(sample_id='{self.sample_id}', status='{self.status}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'sample_id': self.sample_id,
            'project_id': str(self.project_id),
            'collected_by': self.collected_by,
            'collected_at': self.collected_at.isoformat() if self.collected_at else None,
            'geotag_lat': float(self.geotag_lat) if self.geotag_lat else None,
            'geotag_lon': float(self.geotag_lon) if self.geotag_lon else None,
            'sample_type': self.sample_type,
            'chain_of_custody': self.chain_of_custody,
            'notes': self.notes,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class MRVTest(Base):
    """MRV Test results model"""
    __tablename__ = "mrv_test"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    sample_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("mrv_sample.sample_id"), nullable=False
    )
    lab_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("lab.lab_id"), nullable=False  # UUID as string for SQLite compatibility
    )
    parameter: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    method: Mapped[str] = mapped_column(String(255), nullable=False)
    certificate_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    certificate_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA256 hash for duplicate detection
    lab_report_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    co2_contribution_kg: Mapped[float] = mapped_column(Float, nullable=True)  # CO2 contribution in kg
    lca_method: Mapped[str] = mapped_column(String(100), nullable=True)  # LCA method used
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    sample: Mapped[MRVSample] = relationship("MRVSample", back_populates="tests")
    lab: Mapped["Lab"] = relationship("Lab", back_populates="mrv_tests")
    
    # Indexes
    __table_args__ = (
        Index('idx_mrv_test_sample_id', 'sample_id'),
        Index('idx_mrv_test_lab_id', 'lab_id'),
        Index('idx_mrv_test_parameter', 'parameter'),
    )
    
    def __repr__(self) -> str:
        return f"<MRVTest(id='{self.id}', parameter='{self.parameter}', passed={self.passed})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'sample_id': self.sample_id,
            'lab_id': str(self.lab_id),
            'parameter': self.parameter,
            'value': self.value,
            'unit': self.unit,
            'method': self.method,
            'certificate_file': self.certificate_file,
            'lab_report_id': self.lab_report_id,
            'passed': self.passed,
            'notes': self.notes,
            'tested_at': self.tested_at.isoformat() if self.tested_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Lab(Base):
    """Laboratory information model"""
    __tablename__ = "lab"
    
    lab_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    accreditation: Mapped[str] = mapped_column(String(100), nullable=True)
    contact: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    tests: Mapped[list[MRVTest]] = relationship("MRVTest", back_populates="lab")
    mrv_tests: Mapped[list[MRVTest]] = relationship("MRVTest", back_populates="lab")
    
    def __repr__(self) -> str:
        return f"<Lab(lab_id='{self.lab_id}', name='{self.name}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'lab_id': str(self.lab_id),
            'name': self.name,
            'address': self.address,
            'accreditation': self.accreditation,
            'contact': self.contact,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ChainStep(Base):
    """Chain of custody tracking model"""
    __tablename__ = "chain_step"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    sample_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("mrv_sample.sample_id"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    evidence_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    
    # Relationships
    sample: Mapped[MRVSample] = relationship("MRVSample", back_populates="chain_steps")
    
    # Indexes
    __table_args__ = (
        Index('idx_chain_step_sample_id', 'sample_id'),
        Index('idx_chain_step_timestamp', 'timestamp'),
    )
    
    def __repr__(self) -> str:
        return f"<ChainStep(id='{self.id}', sample_id='{self.sample_id}', action='{self.action}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'sample_id': self.sample_id,
            'actor': self.actor,
            'action': self.action,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'evidence_file': self.evidence_file,
        }


class MRVEventLog(Base):
    """MRV audit trail model"""
    __tablename__ = "mrv_event_log"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    ref_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'sample', 'test', 'lab'
    ref_id: Mapped[str] = mapped_column(String(50), nullable=False)
    event: Mapped[str] = mapped_column(String(255), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # Indexes
    __table_args__ = (
        Index('idx_mrv_event_log_ref', 'ref_type', 'ref_id'),
        Index('idx_mrv_event_log_ts', 'ts'),
        Index('idx_mrv_event_log_event', 'event'),
    )
    
    def __repr__(self) -> str:
        return f"<MRVEventLog(id='{self.id}', ref_type='{self.ref_type}', event='{self.event}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'ref_type': self.ref_type,
            'ref_id': self.ref_id,
            'event': self.event,
            'actor': self.actor,
            'ts': self.ts.isoformat() if self.ts else None,
            'details': self.details,
        }


class CarbonLedger(Base):
    """Carbon ledger for tracking project-level carbon accounting"""
    
    __tablename__ = "carbon_ledger"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project.id"), nullable=False
    )
    sample_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("mrv_sample.sample_id"), nullable=False
    )
    test_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mrv_test.id"), nullable=True
    )
    co2_kg: Mapped[float] = mapped_column(Float, nullable=False)  # CO2 in kg
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # Source of calculation
    material_type: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity_tonnes: Mapped[float] = mapped_column(Float, nullable=True)
    lca_method: Mapped[str] = mapped_column(String(100), nullable=True)
    calculation_details: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    project: Mapped["Project"] = relationship("Project")
    sample: Mapped[MRVSample] = relationship("MRVSample")
    test: Mapped[MRVTest] = relationship("MRVTest")
    
    # Indexes
    __table_args__ = (
        Index('idx_carbon_ledger_project_id', 'project_id'),
        Index('idx_carbon_ledger_sample_id', 'sample_id'),
        Index('idx_carbon_ledger_created_at', 'created_at'),
    )


class CarbonCreditIssuance(Base):
    """Carbon credit issuance tracking"""
    
    __tablename__ = "carbon_credit_issuance"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project.id"), nullable=False
    )
    credits_t: Mapped[float] = mapped_column(Float, nullable=False)  # Credits in tonnes CO2
    value_usd: Mapped[float] = mapped_column(Float, nullable=False)  # Value in USD
    credit_rate_usd_per_ton: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, issued, retired
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    retired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    calculation_details: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project")
    
    # Indexes
    __table_args__ = (
        Index('idx_carbon_credit_issuance_project_id', 'project_id'),
        Index('idx_carbon_credit_issuance_status', 'status'),
        Index('idx_carbon_credit_issuance_issued_at', 'issued_at'),
    )
