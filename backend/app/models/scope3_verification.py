from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text, UUID, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class VerificationStatus(str, PyEnum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REVOKED = "revoked"


class AccreditationStatus(str, PyEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"


class VerificationLevel(str, PyEnum):
    LEVEL_1 = "level_1"  # Basic verification
    LEVEL_2 = "level_2"  # Detailed verification
    LEVEL_3 = "level_3"  # Comprehensive verification


class ThirdPartyVerifier(Base, UUIDMixin, TimestampMixin):
    """Accredited third-party verification organization"""
    __tablename__ = "third_party_verifiers"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, unique=True)
    accreditation_number = Column(String(50), unique=True, nullable=False)
    accreditation_body = Column(String(100), nullable=False)  # e.g., "UNFCCC", "GHG Protocol"
    accreditation_status = Column(Enum(AccreditationStatus), default=AccreditationStatus.ACTIVE)
    
    # Accreditation details
    accreditation_date = Column(DateTime(timezone=True), nullable=False)
    expiry_date = Column(DateTime(timezone=True), nullable=False)
    verification_scope = Column(Text, nullable=True)  # JSON array of verification scopes
    geographic_scope = Column(String(200), nullable=True)
    
    # Capabilities
    max_verification_level = Column(Enum(VerificationLevel), nullable=False)
    material_categories = Column(Text, nullable=True)  # JSON array of categories they can verify
    annual_capacity = Column(Integer, nullable=True)  # Maximum projects per year
    
    # Status
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="verifier_profile")
    verifications = relationship("VerificationRecord", back_populates="verifier")
    verifier_users = relationship("User", back_populates="verifier_organization")
    
    def __repr__(self) -> str:
        return f"<ThirdPartyVerifier {self.accreditation_number} ({self.accreditation_status.value})>"


class GovernmentAuthority(Base, UUIDMixin, TimestampMixin):
    """National government authority for oversight and approval"""
    __tablename__ = "government_authorities"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, unique=True)
    authority_type = Column(String(50), nullable=False)  # e.g., "environmental_ministry", "climate_agency"
    jurisdiction_level = Column(String(20), nullable=False)  # e.g., "national", "regional"
    country_code = Column(String(2), nullable=False)
    
    # Authority details
    mandate_description = Column(Text, nullable=False)
    legal_framework = Column(String(100), nullable=False)  # e.g., "Climate Change Act 2021"
    oversight_scope = Column(Text, nullable=True)  # JSON array of oversight areas
    
    # Status
    is_active = Column(Boolean, default=True)
    contact_email = Column(String(255), nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="government_profile")
    approvals = relationship("GovernmentApproval", back_populates="authority")
    authority_users = relationship("User", back_populates="government_organization")
    
    def __repr__(self) -> str:
        return f"<GovernmentAuthority {self.authority_type} ({self.country_code})>"


class VerificationRecord(Base, UUIDMixin, TimestampMixin):
    """Individual verification records with dual-signature workflow"""
    __tablename__ = "verification_records"

    activity_data_id = Column(UUID(as_uuid=True), ForeignKey("activity_data.id"), nullable=False)
    verifier_id = Column(UUID(as_uuid=True), ForeignKey("third_party_verifiers.id"), nullable=False)
    
    # Verification details
    verification_level = Column(Enum(VerificationLevel), nullable=False)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    verification_start = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    verification_complete = Column(DateTime(timezone=True), nullable=True)
    
    # Verification results
    verification_findings = Column(Text, nullable=True)
    identified_issues = Column(Text, nullable=True)  # JSON array of identified issues
    corrective_actions = Column(Text, nullable=True)  # JSON array of required actions
    confidence_level = Column(String(20), nullable=True)  # e.g., "high", "medium", "low"
    
    # Personnel
    primary_verifier_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    secondary_verifier_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_lead_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Signatures and approvals
    primary_signature = Column(String(100), nullable=True)  # Digital signature hash
    secondary_signature = Column(String(100), nullable=True)
    review_signature = Column(String(100), nullable=True)
    
    # Documentation
    verification_report_url = Column(String(500), nullable=True)
    supporting_documents = Column(Text, nullable=True)  # JSON array of document URLs
    
    # Relationships
    activity_data = relationship("ActivityData", back_populates="verification_records")
    verifier = relationship("ThirdPartyVerifier", back_populates="verifications")
    primary_verifier = relationship("User", foreign_keys=[primary_verifier_id])
    secondary_verifier = relationship("User", foreign_keys=[secondary_verifier_id])
    review_lead = relationship("User", foreign_keys=[review_lead_id])
    
    # Constraints
    __table_args__ = (
        Index('ix_verification_activity', 'activity_data_id', 'verification_status'),
        Index('ix_verification_verifier', 'verifier_id', 'verification_start'),
    )
    
    def __repr__(self) -> str:
        return f"<VerificationRecord {self.verification_level.value} ({self.verification_status.value})>"


class GovernmentApproval(Base, UUIDMixin, TimestampMixin):
    """Government authority approval for verified emissions"""
    __tablename__ = "government_approvals"

    verification_record_id = Column(UUID(as_uuid=True), ForeignKey("verification_records.id"), nullable=False, unique=True)
    authority_id = Column(UUID(as_uuid=True), ForeignKey("government_authorities.id"), nullable=False)
    
    # Approval details
    approval_status = Column(String(20), default="pending")  # pending, approved, rejected, returned
    approval_date = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Review findings
    government_findings = Column(Text, nullable=True)
    additional_requirements = Column(Text, nullable=True)  # JSON array of additional requirements
    compliance_notes = Column(Text, nullable=True)
    
    # Personnel
    reviewing_officer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approving_officer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Signatures
    officer_signature = Column(String(100), nullable=True)
    authority_seal = Column(String(100), nullable=True)  # Digital seal/hash
    
    # Documentation
    approval_reference = Column(String(50), nullable=True)  # Official reference number
    approval_document_url = Column(String(500), nullable=True)
    
    # Relationships
    verification_record = relationship("VerificationRecord")
    authority = relationship("GovernmentAuthority", back_populates="approvals")
    reviewing_officer = relationship("User", foreign_keys=[reviewing_officer_id])
    approving_officer = relationship("User", foreign_keys=[approving_officer_id])
    
    def __repr__(self) -> str:
        return f"<GovernmentApproval {self.approval_status} ({self.approval_reference})>"


class VerificationAuditLog(Base, UUIDMixin, TimestampMixin):
    """Complete audit trail for verification activities"""
    __tablename__ = "verification_audit_logs"

    verification_record_id = Column(UUID(as_uuid=True), ForeignKey("verification_records.id"), nullable=True)
    activity_data_id = Column(UUID(as_uuid=True), ForeignKey("activity_data.id"), nullable=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Action details
    action_type = Column(String(50), nullable=False)  # assigned, reviewed, signed, approved, etc.
    action_description = Column(Text, nullable=False)
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=True)
    
    # System metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(100), nullable=True)
    
    # Relationships
    verification_record = relationship("VerificationRecord")
    activity_data = relationship("ActivityData")
    actor = relationship("User")
    
    # Constraints
    __table_args__ = (
        Index('ix_verification_audit_record', 'verification_record_id', 'created_at'),
        Index('ix_verification_audit_actor', 'actor_id', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<VerificationAuditLog {self.action_type}>"
