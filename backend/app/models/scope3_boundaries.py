from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text, UUID, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class BoundaryType(str, PyEnum):
    ORGANIZATIONAL = "organizational"
    OPERATIONAL = "operational"


class InclusionBasis(str, PyEnum):
    FINANCIAL_CONTROL = "financial_control"
    OPERATIONAL_CONTROL = "operational_control"
    EQUITY_SHARE = "equity_share"


class ProjectBoundaryStatus(str, PyEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    LOCKED = "locked"
    REJECTED = "rejected"


class OrganizationalBoundary(Base, UUIDMixin, TimestampMixin):
    """Organizational boundary definition following ISO 14064-1 requirements"""
    __tablename__ = "organizational_boundaries"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    boundary_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Boundary definition
    inclusion_basis = Column(Enum(InclusionBasis), nullable=False)
    consolidation_approach = Column(String(50), nullable=False)  # equity, control, operational
    
    # Geographic and temporal scope
    country_code = Column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    geographic_scope = Column(String(500), nullable=True)  # Specific regions/states
    reporting_period_start = Column(DateTime(timezone=True), nullable=False)
    reporting_period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Legal and operational details
    legal_entity_identifiers = Column(Text, nullable=True)  # JSON array of legal entity IDs
    operational_segments = Column(Text, nullable=True)  # JSON array of business segments
    
    # Status and approval
    status = Column(String(20), default="draft")
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approval_date = Column(DateTime(timezone=True), nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="organizational_boundaries")
    approver = relationship("User", foreign_keys=[approved_by])
    operational_boundaries = relationship("OperationalBoundary", back_populates="organizational_boundary")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'boundary_name', name='uq_org_boundary_name'),
        Index('ix_org_boundary_period', 'reporting_period_start', 'reporting_period_end'),
    )
    
    def __repr__(self) -> str:
        return f"<OrganizationalBoundary {self.boundary_name} ({self.inclusion_basis.value})>"


class OperationalBoundary(Base, UUIDMixin, TimestampMixin):
    """Operational boundary definition with Scope 3 category inclusion/exclusion"""
    __tablename__ = "operational_boundaries"

    organizational_boundary_id = Column(UUID(as_uuid=True), ForeignKey("organizational_boundaries.id"), nullable=False)
    boundary_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Scope definitions
    scope1_included = Column(Boolean, default=True)
    scope2_included = Column(Boolean, default=True)
    scope3_categories_included = Column(Text, nullable=True)  # JSON array of included Scope 3 categories
    
    # Construction project specific
    construction_projects_included = Column(Boolean, default=True)
    construction_material_categories = Column(Text, nullable=True)  # JSON array of material categories
    
    # Exclusion justifications
    excluded_categories = Column(Text, nullable=True)  # JSON array of excluded categories
    exclusion_justifications = Column(Text, nullable=True)  # JSON object mapping categories to justifications
    
    # Methodology and standards
    methodology_version = Column(String(20), nullable=False)  # e.g., "ISO 14064-1:2018"
    calculation_methodology = Column(String(100), nullable=False)
    reporting_framework = Column(String(50), nullable=True)  # e.g., "GHG Protocol", "GRI"
    
    # Status and approval
    status = Column(String(20), default="draft")
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approval_date = Column(DateTime(timezone=True), nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # Relationships
    organizational_boundary = relationship("OrganizationalBoundary", back_populates="operational_boundaries")
    approver = relationship("User", foreign_keys=[approved_by])
    project_boundaries = relationship("ProjectBoundary", back_populates="operational_boundary")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('organizational_boundary_id', 'boundary_name', name='uq_op_boundary_name'),
    )
    
    def __repr__(self) -> str:
        return f"<OperationalBoundary {self.boundary_name} (Scope3: {len(self.scope3_categories_included or [])} categories)"


class ProjectBoundary(Base, UUIDMixin, TimestampMixin):
    """Project-specific boundary snapshot that becomes immutable after verification"""
    __tablename__ = "project_boundaries"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, unique=True)
    operational_boundary_id = Column(UUID(as_uuid=True), ForeignKey("operational_boundaries.id"), nullable=False)
    
    # Boundary snapshot (immutable after lock)
    boundary_snapshot = Column(Text, nullable=False)  # JSON snapshot of operational boundary at time of lock
    included_material_categories = Column(Text, nullable=False)  # JSON array of material categories
    excluded_material_categories = Column(Text, nullable=True)  # JSON array with justifications
    
    # Project-specific adjustments
    project_specific_inclusions = Column(Text, nullable=True)  # JSON array of additional inclusions
    project_specific_exclusions = Column(Text, nullable=True)  # JSON array with justifications
    adjustment_justifications = Column(Text, nullable=True)  # JSON object mapping adjustments to reasons
    
    # Locking and verification
    status = Column(Enum(ProjectBoundaryStatus), default=ProjectBoundaryStatus.DRAFT)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Methodology snapshot
    methodology_version = Column(String(20), nullable=False)
    emission_factor_version = Column(String(20), nullable=False)
    calculation_rules = Column(Text, nullable=False)  # JSON object of calculation rules
    
    # Relationships
    project = relationship("Project", back_populates="boundary")
    operational_boundary = relationship("OperationalBoundary", back_populates="project_boundaries")
    locker = relationship("User", foreign_keys=[locked_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    
    # Constraints
    __table_args__ = (
        Index('ix_project_boundary_status', 'status', 'locked_at'),
    )
    
    def __repr__(self) -> str:
        return f"<ProjectBoundary {self.project_id} ({self.status.value})>"


class BoundaryChangeRequest(Base, UUIDMixin, TimestampMixin):
    """Formal change requests for project boundaries (only allowed before verification)"""
    __tablename__ = "boundary_change_requests"

    project_boundary_id = Column(UUID(as_uuid=True), ForeignKey("project_boundaries.id"), nullable=False)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Change details
    change_type = Column(String(50), nullable=False)  # inclusion, exclusion, methodology_update
    change_description = Column(Text, nullable=False)
    current_configuration = Column(Text, nullable=False)  # JSON of current state
    proposed_configuration = Column(Text, nullable=False)  # JSON of proposed state
    
    # Justification and impact
    change_justification = Column(Text, nullable=False)
    impact_assessment = Column(Text, nullable=True)  # JSON object of impact analysis
    material_impact = Column(Text, nullable=True)  # Description of material impact on emissions
    
    # Approval workflow
    status = Column(String(20), default="pending")  # pending, under_review, approved, rejected
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_date = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # Implementation tracking
    implemented_at = Column(DateTime(timezone=True), nullable=True)
    implemented_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    project_boundary = relationship("ProjectBoundary")
    requester = relationship("User", foreign_keys=[requested_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    implementer = relationship("User", foreign_keys=[implemented_by])
    
    def __repr__(self) -> str:
        return f"<BoundaryChangeRequest {self.change_type} ({self.status})>"


class BoundaryAuditLog(Base, UUIDMixin, TimestampMixin):
    """Complete audit trail for all boundary-related activities"""
    __tablename__ = "boundary_audit_logs"

    project_boundary_id = Column(UUID(as_uuid=True), ForeignKey("project_boundaries.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # created, modified, locked, verified, etc.
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Action details
    action_description = Column(Text, nullable=False)
    previous_state = Column(Text, nullable=True)  # JSON of previous state
    new_state = Column(Text, nullable=True)  # JSON of new state
    
    # System metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(100), nullable=True)
    
    # Relationships
    project_boundary = relationship("ProjectBoundary")
    actor = relationship("User")
    
    # Constraints
    __table_args__ = (
        Index('ix_boundary_audit_project', 'project_boundary_id', 'created_at'),
        Index('ix_boundary_audit_actor', 'actor_id', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<BoundaryAuditLog {self.action_type} by {self.actor_id}>"
