from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text, UUID, ForeignKey, UniqueConstraint, Index, LargeBinary
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class EvidenceType(str, PyEnum):
    TEST_CERTIFICATE = "test_certificate"
    MATERIAL_SPECIFICATION = "material_specification"
    SUPPLIER_DECLARATION = "supplier_declaration"
    PHOTOGRAPH = "photograph"
    VIDEO = "video"
    INVOICE = "invoice"
    TRANSPORT_DOCUMENT = "transport_document"
    QUALITY_REPORT = "quality_report"
    THIRD_PARTY_CERTIFICATION = "third_party_certification"
    LAB_RESULTS = "lab_results"
    BATCH_RECORD = "batch_record"
    CHAIN_OF_CUSTODY = "chain_of_custody"


class EvidenceStatus(str, PyEnum):
    UPLOADED = "uploaded"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class EvidenceFile(Base, UUIDMixin, TimestampMixin):
    """Evidence files with SHA-256 hashing and integrity verification"""
    __tablename__ = "evidence_files"

    file_identifier = Column(String(100), unique=True, nullable=False, index=True)
    activity_data_id = Column(UUID(as_uuid=True), ForeignKey("activity_data.id"), nullable=True)
    
    # File metadata
    original_filename = Column(String(255), nullable=False)
    file_type = Column(Enum(EvidenceType), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(String(20), nullable=False)  # String for large files
    
    # Hash and integrity
    sha256_hash = Column(String(64), nullable=False, unique=True, index=True)
    md5_hash = Column(String(32), nullable=True)  # Legacy support
    checksum_verified = Column(Boolean, default=False)
    verification_date = Column(DateTime(timezone=True), nullable=True)
    
    # File storage
    storage_path = Column(String(500), nullable=False)
    storage_provider = Column(String(50), nullable=False)  # e.g., "local", "s3", "azure"
    storage_reference = Column(String(200), nullable=True)
    is_encrypted = Column(Boolean, default=False)
    encryption_key_reference = Column(String(100), nullable=True)
    
    # Content metadata
    content_description = Column(Text, nullable=True)
    document_date = Column(DateTime(timezone=True), nullable=True)
    document_reference = Column(String(100), nullable=True)
    issuing_authority = Column(String(200), nullable=True)
    
    # Upload details
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    upload_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    upload_ip = Column(String(45), nullable=True)
    
    # Verification status
    evidence_status = Column(Enum(EvidenceStatus), default=EvidenceStatus.UPLOADED)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verification_date = Column(DateTime(timezone=True), nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # Expiry and validity
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    is_valid = Column(Boolean, default=True)
    invalidation_reason = Column(Text, nullable=True)
    
    # Relationships
    activity_data = relationship("ActivityData", back_populates="evidence_files")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    hash_verifications = relationship("HashVerification", back_populates="evidence_file")
    
    # Constraints
    __table_args__ = (
        Index('ix_evidence_activity', 'activity_data_id', 'evidence_status'),
        Index('ix_evidence_hash', 'sha256_hash'),
        Index('ix_evidence_type', 'file_type', 'upload_date'),
    )
    
    def __repr__(self) -> str:
        return f"<EvidenceFile {self.original_filename} ({self.evidence_status.value})>"


class HashVerification(Base, UUIDMixin, TimestampMixin):
    """Hash verification records for evidence integrity"""
    __tablename__ = "hash_verifications"

    evidence_file_id = Column(UUID(as_uuid=True), ForeignKey("evidence_files.id"), nullable=False)
    verification_attempt = Column(String(64), nullable=False)  # Hash being verified
    
    # Verification details
    verification_result = Column(String(20), nullable=False)  # match, mismatch, error
    verification_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    verification_method = Column(String(50), nullable=False)  # e.g., "sha256", "md5", "file_comparison"
    
    # System details
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    verification_ip = Column(String(45), nullable=True)
    verification_user_agent = Column(String(500), nullable=True)
    
    # Results
    expected_hash = Column(String(64), nullable=False)
    actual_hash = Column(String(64), nullable=True)
    algorithm_used = Column(String(20), nullable=False)
    verification_time_ms = Column(String(10), nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    error_code = Column(String(20), nullable=True)
    
    # Relationships
    evidence_file = relationship("EvidenceFile", back_populates="hash_verifications")
    verifier = relationship("User")
    
    # Constraints
    __table_args__ = (
        Index('ix_hash_verification_file', 'evidence_file_id', 'verification_date'),
        Index('ix_hash_verification_result', 'verification_result', 'verification_date'),
    )
    
    def __repr__(self) -> str:
        return f"<HashVerification {self.verification_result}>"


class EvidenceAuditLog(Base, UUIDMixin, TimestampMixin):
    """Complete audit trail for evidence file operations"""
    __tablename__ = "evidence_audit_logs"

    evidence_file_id = Column(UUID(as_uuid=True), ForeignKey("evidence_files.id"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Action details
    action_type = Column(String(50), nullable=False)  # uploaded, viewed, downloaded, verified, deleted, etc.
    action_description = Column(Text, nullable=False)
    
    # File state changes
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=True)
    previous_hash = Column(String(64), nullable=True)
    new_hash = Column(String(64), nullable=True)
    
    # Access details
    access_ip = Column(String(45), nullable=True)
    access_user_agent = Column(String(500), nullable=True)
    session_id = Column(String(100), nullable=True)
    
    # System metadata
    processing_time_ms = Column(String(10), nullable=True)
    error_details = Column(Text, nullable=True)
    
    # Relationships
    evidence_file = relationship("EvidenceFile")
    actor = relationship("User")
    
    # Constraints
    __table_args__ = (
        Index('ix_evidence_audit_file', 'evidence_file_id', 'created_at'),
        Index('ix_evidence_audit_actor', 'actor_id', 'created_at'),
        Index('ix_evidence_audit_action', 'action_type', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<EvidenceAuditLog {self.action_type}>"


class EvidenceTemplate(Base, UUIDMixin, TimestampMixin):
    """Standardized templates for evidence submission"""
    __tablename__ = "evidence_templates"

    template_name = Column(String(200), nullable=False)
    template_type = Column(Enum(EvidenceType), nullable=False)
    material_category_id = Column(UUID(as_uuid=True), ForeignKey("material_categories.id"), nullable=True)
    
    # Template requirements
    required_fields = Column(Text, nullable=False)  # JSON array of required fields
    optional_fields = Column(Text, nullable=True)  # JSON array of optional fields
    field_validations = Column(Text, nullable=False)  # JSON object of field validation rules
    
    # File specifications
    allowed_file_types = Column(Text, nullable=False)  # JSON array of MIME types
    max_file_size_mb = Column(String(10), nullable=False)
    min_file_size_mb = Column(String(10), nullable=True)
    
    # Template metadata
    template_description = Column(Text, nullable=True)
    template_version = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Usage tracking
    usage_count = Column(String(10), default="0")
    last_used_date = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    material_category = relationship("MaterialCategory")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('template_name', 'template_version', name='uq_template_name_version'),
        Index('ix_template_type', 'template_type', 'is_active'),
    )
    
    def __repr__(self) -> str:
        return f"<EvidenceTemplate {self.template_name} v{self.template_version}>"
