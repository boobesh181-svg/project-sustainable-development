from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text, UUID, ForeignKey, UniqueConstraint, Index, Numeric
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class CreditStatus(str, PyEnum):
    CALCULATED = "calculated"
    VERIFIED = "verified"
    ISSUED = "issued"
    RETIRED = "retired"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CreditType(str, PyEnum):
    EMISSION_REDUCTION = "emission_reduction"
    EMISSION_AVOIDANCE = "emission_avoidance"
    CARBON_REMOVAL = "carbon_removal"
    SUSTAINABLE_MATERIALS = "sustainable_materials"


class RetirementReason(str, PyEnum):
    COMPENSATION = "compensation"
    CLIMATE_NEUTRALITY = "climate_neutrality"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    VOLUNTARY_OFFSET = "voluntary_offset"
    CORPORATE_COMMITMENT = "corporate_commitment"


class CarbonCredit(Base, UUIDMixin, TimestampMixin):
    """Individual carbon credits with full lifecycle tracking"""
    __tablename__ = "carbon_credits"

    credit_identifier = Column(String(50), unique=True, nullable=False, index=True)
    activity_data_id = Column(UUID(as_uuid=True), ForeignKey("activity_data.id"), nullable=False)
    
    # Credit details
    credit_type = Column(Enum(CreditType), nullable=False)
    credit_status = Column(Enum(CreditStatus), default=CreditStatus.CALCULATED)
    co2_amount = Column(Numeric(15, 6), nullable=False)  # CO2e in tonnes
    baseline_co2 = Column(Numeric(15, 6), nullable=True)  # Baseline emissions for reduction calculations
    methodology_version = Column(String(20), nullable=False)
    
    # Verification and issuance
    verification_date = Column(DateTime(timezone=True), nullable=True)
    verification_reference = Column(String(50), nullable=True)
    issuance_date = Column(DateTime(timezone=True), nullable=True)
    issuance_reference = Column(String(50), nullable=True)
    registry_id = Column(String(50), nullable=True)  # National registry identifier
    
    # Validity period
    vintage_year = Column(Integer, nullable=False)
    issuance_year = Column(Integer, nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    
    # Quality indicators
    additionality = Column(Boolean, nullable=False)
    permanence = Column(String(20), nullable=True)  # e.g., "100_years", "permanent"
    leakage = Column(Numeric(10, 6), nullable=True)  # Leakage percentage
    uncertainty = Column(Numeric(5, 2), nullable=True)  # Uncertainty percentage
    
    # Co-benefits
    sustainable_development_goals = Column(Text, nullable=True)  # JSON array of SDG numbers
    environmental_co_benefits = Column(Text, nullable=True)  # JSON array of co-benefits
    social_co_benefits = Column(Text, nullable=True)  # JSON array of social benefits
    
    # Status tracking
    current_holder_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    retirement_date = Column(DateTime(timezone=True), nullable=True)
    retirement_reason = Column(Enum(RetirementReason), nullable=True)
    retirement_certificate = Column(String(100), nullable=True)
    
    # Relationships
    activity_data = relationship("ActivityData", back_populates="carbon_credits")
    current_holder = relationship("Organization", back_populates="carbon_credits")
    credit_transfers = relationship("CreditTransfer", back_populates="carbon_credit")
    credit_retirements = relationship("CreditRetirement", back_populates="carbon_credit")
    
    # Constraints
    __table_args__ = (
        Index('ix_credit_status', 'credit_status', 'issuance_date'),
        Index('ix_credit_vintage', 'vintage_year', 'credit_type'),
        Index('ix_credit_holder', 'current_holder_id', 'credit_status'),
    )
    
    def __repr__(self) -> str:
        return f"<CarbonCredit {self.credit_identifier} ({self.co2_amount} tCO2e, {self.credit_status.value})>"


class CreditTransfer(Base, UUIDMixin, TimestampMixin):
    """Complete audit trail for credit transfers"""
    __tablename__ = "credit_transfers"

    carbon_credit_id = Column(UUID(as_uuid=True), ForeignKey("carbon_credits.id"), nullable=False)
    transfer_from_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    transfer_to_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Transfer details
    transfer_amount = Column(Numeric(15, 6), nullable=False)
    transfer_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    transfer_reference = Column(String(50), nullable=True)
    
    # Transfer purpose
    transfer_purpose = Column(String(100), nullable=False)
    project_reference = Column(String(100), nullable=True)
    
    # Authorization
    authorized_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    authorization_reference = Column(String(100), nullable=True)
    
    # Financial details
    transfer_price = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(3), nullable=True)
    payment_reference = Column(String(100), nullable=True)
    
    # Status
    transfer_status = Column(String(20), default="completed")  # pending, completed, failed, reversed
    
    # Relationships
    carbon_credit = relationship("CarbonCredit", back_populates="credit_transfers")
    transfer_from = relationship("Organization", foreign_keys=[transfer_from_id])
    transfer_to = relationship("Organization", foreign_keys=[transfer_to_id])
    authorizer = relationship("User", foreign_keys=[authorized_by])
    
    # Constraints
    __table_args__ = (
        Index('ix_transfer_credit', 'carbon_credit_id', 'transfer_date'),
        Index('ix_transfer_from', 'transfer_from_id', 'transfer_date'),
        Index('ix_transfer_to', 'transfer_to_id', 'transfer_date'),
    )
    
    def __repr__(self) -> str:
        return f"<CreditTransfer {self.transfer_amount} tCO2e ({self.transfer_status})>"


class CreditRetirement(Base, UUIDMixin, TimestampMixin):
    """Irreversible retirement of carbon credits"""
    __tablename__ = "credit_retirements"

    carbon_credit_id = Column(UUID(as_uuid=True), ForeignKey("carbon_credits.id"), nullable=False)
    retiring_organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Retirement details
    retirement_amount = Column(Numeric(15, 6), nullable=False)
    retirement_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    retirement_reason = Column(Enum(RetirementReason), nullable=False)
    
    # Retirement purpose
    retirement_purpose = Column(Text, nullable=False)
    offset_project = Column(String(200), nullable=True)
    offset_reference = Column(String(100), nullable=True)
    
    # Authorization
    authorized_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    retirement_certificate = Column(String(100), nullable=False)
    public_announcement = Column(Boolean, default=False)
    
    # Registry details
    registry_reference = Column(String(100), nullable=True)
    blockchain_reference = Column(String(100), nullable=True)
    
    # Relationships
    carbon_credit = relationship("CarbonCredit", back_populates="credit_retirements")
    retiring_organization = relationship("Organization", back_populates="credit_retirements")
    authorizer = relationship("User", foreign_keys=[authorized_by])
    
    # Constraints
    __table_args__ = (
        Index('ix_retirement_credit', 'carbon_credit_id', 'retirement_date'),
        Index('ix_retirement_org', 'retiring_organization_id', 'retirement_date'),
        Index('ix_retirement_reason', 'retirement_reason', 'retirement_date'),
    )
    
    def __repr__(self) -> str:
        return f"<CreditRetirement {self.retirement_amount} tCO2e ({self.retirement_reason.value})>"


class CreditPool(Base, UUIDMixin, TimestampMixin):
    """Pools of credits for bulk operations"""
    __tablename__ = "credit_pools"

    pool_name = Column(String(200), nullable=False)
    pool_type = Column(String(50), nullable=False)  # e.g., "project_pool", "regional_pool", "national_pool"
    managing_organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Pool composition
    total_credits = Column(Numeric(15, 6), default=0)
    available_credits = Column(Numeric(15, 6), default=0)
    retired_credits = Column(Numeric(15, 6), default=0)
    
    # Pool characteristics
    vintage_start = Column(Integer, nullable=True)
    vintage_end = Column(Integer, nullable=True)
    credit_types = Column(Text, nullable=True)  # JSON array of credit types
    quality_tiers = Column(Text, nullable=True)  # JSON array of quality tiers
    
    # Status
    is_active = Column(Boolean, default=True)
    creation_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_updated = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Relationships
    managing_organization = relationship("Organization", back_populates="credit_pools")
    pool_memberships = relationship("CreditPoolMembership", back_populates="credit_pool")
    
    def __repr__(self) -> str:
        return f"<CreditPool {self.pool_name} ({self.available_credits} tCO2e available)>"


class CreditPoolMembership(Base, UUIDMixin, TimestampMixin):
    """Membership of individual credits in pools"""
    __tablename__ = "credit_pool_memberships"

    credit_pool_id = Column(UUID(as_uuid=True), ForeignKey("credit_pools.id"), nullable=False)
    carbon_credit_id = Column(UUID(as_uuid=True), ForeignKey("carbon_credits.id"), nullable=False)
    
    # Membership details
    joined_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    left_date = Column(DateTime(timezone=True), nullable=True)
    membership_status = Column(String(20), default="active")  # active, transferred, retired
    
    # Relationships
    credit_pool = relationship("CreditPool", back_populates="pool_memberships")
    carbon_credit = relationship("CarbonCredit")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('credit_pool_id', 'carbon_credit_id', name='uq_pool_credit'),
        Index('ix_pool_membership_status', 'membership_status', 'joined_date'),
    )
    
    def __repr__(self) -> str:
        return f"<CreditPoolMembership {self.membership_status}>"
