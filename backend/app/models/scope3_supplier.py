from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text, UUID, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class AttestationStatus(str, PyEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class LiabilityType(str, PyEnum):
    FINANCIAL = "financial"
    LEGAL = "legal"
    REGULATORY = "regulatory"
    CONTRACTUAL = "contractual"


class SupplierProfile(Base, UUIDMixin, TimestampMixin):
    """Extended supplier profile for MRV system integration"""
    __tablename__ = "supplier_profiles"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, unique=True)
    supplier_code = Column(String(50), unique=True, nullable=False)
    
    # Supplier classification
    primary_material_categories = Column(Text, nullable=False)  # JSON array of material categories
    certification_status = Column(String(50), nullable=True)  # e.g., "ISO 14001", "FSC", etc.
    quality_rating = Column(String(10), nullable=True)  # e.g., "A", "B", "C"
    
    # Integration status
    digital_integration_level = Column(String(20), default="basic")  # basic, intermediate, advanced
    api_access_enabled = Column(Boolean, default=False)
    real_time_reporting = Column(Boolean, default=False)
    
    # Capacity and capabilities
    annual_production_capacity = Column(Text, nullable=True)  # JSON object by material category
    geographic_coverage = Column(Text, nullable=True)  # JSON array of countries/regions
    lead_time_days = Column(Integer, nullable=True)
    
    # Compliance and liability
    compliance_status = Column(String(20), default="pending")
    liability_insurance_required = Column(Boolean, default=True)
    insurance_coverage_amount = Column(String(50), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    onboarding_date = Column(DateTime(timezone=True), nullable=True)
    last_audit_date = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="supplier_profile")
    material_tokens = relationship("MaterialToken", back_populates="supplier")
    attestations = relationship("SupplierAttestation", back_populates="supplier")
    liability_records = relationship("SupplierLiabilityRecord", back_populates="supplier")
    
    def __repr__(self) -> str:
        return f"<SupplierProfile {self.supplier_code} ({self.compliance_status})>"


class MaterialToken(Base, UUIDMixin, TimestampMixin):
    """Unique material batch tokens for double counting prevention"""
    __tablename__ = "material_tokens"

    supplier_id = Column(UUID(as_uuid=True), ForeignKey("supplier_profiles.id"), nullable=False)
    token_number = Column(String(100), unique=True, nullable=False, index=True)
    
    # Material details
    material_category_id = Column(UUID(as_uuid=True), ForeignKey("material_categories.id"), nullable=False)
    material_subtype_id = Column(UUID(as_uuid=True), ForeignKey("material_subtypes.id"), nullable=True)
    
    # Batch information
    batch_number = Column(String(100), nullable=False)
    production_date = Column(DateTime(timezone=True), nullable=False)
    quantity_produced = Column(String(50), nullable=False)  # String to handle large numbers
    unit_of_measure = Column(String(20), nullable=False)
    
    # Quality and specifications
    quality_grade = Column(String(20), nullable=True)
    specification_reference = Column(String(100), nullable=True)
    test_results_url = Column(String(500), nullable=True)
    
    # Status and tracking
    status = Column(String(20), default="active")  # active, allocated, depleted, expired
    allocated_quantity = Column(String(50), default="0")
    remaining_quantity = Column(String(50), nullable=False)
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    
    # Digital signature
    supplier_signature = Column(String(100), nullable=True)  # Digital signature hash
    blockchain_hash = Column(String(100), nullable=True)  # Optional blockchain reference
    
    # Relationships
    supplier = relationship("SupplierProfile", back_populates="material_tokens")
    material_category = relationship("MaterialCategory")
    material_subtype = relationship("MaterialSubtype")
    allocations = relationship("TokenAllocation", back_populates="material_token")
    
    # Constraints
    __table_args__ = (
        Index('ix_material_token_batch', 'supplier_id', 'batch_number'),
        Index('ix_material_token_status', 'status', 'expiry_date'),
    )
    
    def __repr__(self) -> str:
        return f"<MaterialToken {self.token_number} ({self.status})>"


class TokenAllocation(Base, UUIDMixin, TimestampMixin):
    """Allocation of material tokens to specific projects"""
    __tablename__ = "token_allocations"

    material_token_id = Column(UUID(as_uuid=True), ForeignKey("material_tokens.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    activity_data_id = Column(UUID(as_uuid=True), ForeignKey("activity_data.id"), nullable=True)
    
    # Allocation details
    allocated_quantity = Column(String(50), nullable=False)
    allocation_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    allocated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Usage tracking
    used_quantity = Column(String(50), default="0")
    remaining_allocation = Column(String(50), nullable=False)
    last_used_date = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(20), default="allocated")  # allocated, partially_used, fully_used, cancelled
    
    # Relationships
    material_token = relationship("MaterialToken", back_populates="allocations")
    project = relationship("Project", back_populates="token_allocations")
    activity_data = relationship("ActivityData", back_populates="token_allocation")
    allocator = relationship("User", foreign_keys=[allocated_by])
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('material_token_id', 'project_id', name='uq_token_project'),
        Index('ix_allocation_project', 'project_id', 'allocation_date'),
        Index('ix_allocation_token', 'material_token_id', 'status'),
    )
    
    def __repr__(self) -> str:
        return f"<TokenAllocation {self.allocated_quantity} ({self.status})>"


class SupplierAttestation(Base, UUIDMixin, TimestampMixin):
    """Digital attestation for every submission"""
    __tablename__ = "supplier_attestations"

    activity_data_id = Column(UUID(as_uuid=True), ForeignKey("activity_data.id"), nullable=False, unique=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("supplier_profiles.id"), nullable=False)
    
    # Attestation details
    attestation_status = Column(Enum(AttestationStatus), default=AttestationStatus.DRAFT)
    attestation_date = Column(DateTime(timezone=True), nullable=False)
    attested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    attester_title = Column(String(100), nullable=False)
    
    # Legal declarations
    data_accuracy_statement = Column(Text, nullable=False)
    compliance_statement = Column(Text, nullable=False)
    liability_acceptance = Column(Boolean, nullable=False)
    legal_disclaimer = Column(Text, nullable=True)
    
    # Organizational details
    organization_legal_name = Column(String(200), nullable=False)
    organization_id_number = Column(String(50), nullable=False)  # Legal entity identifier
    jurisdiction = Column(String(100), nullable=False)
    
    # Contact information
    authorized_signatory_name = Column(String(100), nullable=False)
    authorized_signatory_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=True)
    
    # Digital signature
    signature_hash = Column(String(100), nullable=False)
    signature_timestamp = Column(DateTime(timezone=True), nullable=False)
    certificate_reference = Column(String(100), nullable=True)
    
    # Verification
    verification_status = Column(String(20), default="pending")  # pending, verified, rejected
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verification_date = Column(DateTime(timezone=True), nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # Relationships
    activity_data = relationship("ActivityData", back_populates="attestations")
    supplier = relationship("SupplierProfile", back_populates="attestations")
    attestor = relationship("User", foreign_keys=[attested_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    
    def __repr__(self) -> str:
        return f"<SupplierAttestation {self.attestation_status.value} ({self.supplier.supplier_code})>"


class SupplierLiabilityRecord(Base, UUIDMixin, TimestampMixin):
    """Liability tracking and management"""
    __tablename__ = "supplier_liability_records"

    supplier_id = Column(UUID(as_uuid=True), ForeignKey("supplier_profiles.id"), nullable=False)
    activity_data_id = Column(UUID(as_uuid=True), ForeignKey("activity_data.id"), nullable=True)
    
    # Liability details
    liability_type = Column(Enum(LiabilityType), nullable=False)
    liability_amount = Column(String(50), nullable=False)  # String for large numbers
    currency = Column(String(3), nullable=False)
    liability_description = Column(Text, nullable=False)
    
    # Trigger events
    trigger_event = Column(String(100), nullable=False)  # e.g., "data_inaccuracy", "non_compliance"
    trigger_date = Column(DateTime(timezone=True), nullable=False)
    detection_method = Column(String(50), nullable=True)  # e.g., "audit", "whistleblower", "automated"
    
    # Status and resolution
    liability_status = Column(String(20), default="active")  # active, resolved, disputed, written_off
    resolution_date = Column(DateTime(timezone=True), nullable=True)
    resolution_method = Column(String(100), nullable=True)
    amount_recovered = Column(String(50), default="0")
    
    # Legal proceedings
    legal_case_reference = Column(String(100), nullable=True)
    legal_status = Column(String(50), nullable=True)
    court_jurisdiction = Column(String(100), nullable=True)
    
    # Insurance claims
    insurance_claim_number = Column(String(50), nullable=True)
    insurance_claim_status = Column(String(20), nullable=True)
    insurance_payout_amount = Column(String(50), default="0")
    
    # Relationships
    supplier = relationship("SupplierProfile", back_populates="liability_records")
    activity_data = relationship("ActivityData")
    
    # Constraints
    __table_args__ = (
        Index('ix_liability_supplier', 'supplier_id', 'trigger_date'),
        Index('ix_liability_status', 'liability_status', 'trigger_date'),
    )
    
    def __repr__(self) -> str:
        return f"<SupplierLiabilityRecord {self.liability_type.value} ({self.liability_status})>"
