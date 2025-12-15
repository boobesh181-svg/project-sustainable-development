from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text, Numeric, Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDMixin, TimestampMixin


class MaterialCategory(str, PyEnum):
    CEMENT = "cement"
    CONCRETE = "concrete"
    STEEL = "steel"
    ALUMINUM = "aluminum"
    TIMBER = "timber"
    GLASS = "glass"
    PLASTICS = "plastics"
    INSULATION = "insulation"
    MASONRY = "masonry"
    ROOFING = "roofing"
    PAINTS_COATINGS = "paints_coatings"
    ADHESIVES_SEALANTS = "adhesives_sealants"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    HVAC = "hvac"
    FINISHES = "finishes"


class StandardUnit(str, PyEnum):
    KILOGRAM = "kg"
    METRIC_TON = "tonne"
    CUBIC_METER = "m3"
    SQUARE_METER = "m2"
    LINEAR_METER = "m"
    LITER = "L"
    PIECE = "piece"
    KILOWATT_HOUR = "kWh"


class DataQualityTier(str, PyEnum):
    TIER_1 = "tier_1"  # Verified primary data
    TIER_2 = "tier_2"  # Unverified primary data
    TIER_3 = "tier_3"  # National default factors
    TIER_4 = "tier_4"  # International fallback


class EmissionFactorType(str, PyEnum):
    PRIMARY_VERIFIED = "primary_verified"
    PRIMARY_UNVERIFIED = "primary_unverified"
    NATIONAL_DEFAULT = "national_default"
    INTERNATIONAL_FALLBACK = "international_fallback"


class MaterialCategory(Base, UUIDMixin, TimestampMixin):
    """Standardized material categories for Scope 3 construction materials"""
    __tablename__ = "material_categories"

    name = Column(Enum(MaterialCategory), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    standardized_unit = Column(Enum(StandardUnit), nullable=False)
    requires_batch_tracking = Column(Boolean, default=True)
    co2_calculation_method = Column(String(100), nullable=False)  # e.g., "mass_based", "volume_based"
    
    # Relationships
    subtypes = relationship("MaterialSubtype", back_populates="category")
    emission_factors = relationship("EmissionFactor", back_populates="material_category")
    
    def __repr__(self) -> str:
        return f"<MaterialCategory {self.name.value} ({self.standardized_unit.value})>"


class MaterialSubtype(Base, UUIDMixin, TimestampMixin):
    """Specific material subtypes within each category"""
    __tablename__ = "material_subtypes"

    name = Column(String(100), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("material_categories.id"), nullable=False)
    description = Column(Text, nullable=True)
    standard_density = Column(Numeric(10, 4), nullable=True)  # kg/m3 for conversion calculations
    standard_specification = Column(String(50), nullable=True)  # e.g., "ASTM C150", "EN 206"
    is_active = Column(Boolean, default=True)
    
    # Relationships
    category = relationship("MaterialCategory", back_populates="subtypes")
    emission_factors = relationship("EmissionFactor", back_populates="material_subtype")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('category_id', 'name', name='uq_category_subtype'),
    )
    
    def __repr__(self) -> str:
        return f"<MaterialSubtype {self.name} ({self.category.name.value if self.category else 'Unknown'})>"


class EmissionFactor(Base, UUIDMixin, TimestampMixin):
    """Emission factors with hierarchical precedence and quality indicators"""
    __tablename__ = "emission_factors"

    material_category_id = Column(UUID(as_uuid=True), ForeignKey("material_categories.id"), nullable=False)
    material_subtype_id = Column(UUID(as_uuid=True), ForeignKey("material_subtypes.id"), nullable=True)
    
    # Factor metadata
    factor_type = Column(Enum(EmissionFactorType), nullable=False)
    co2_factor_kg = Column(Numeric(12, 6), nullable=False)  # CO2e per standardized unit
    uncertainty_lower = Column(Numeric(12, 6), nullable=True)  # Lower bound of uncertainty range
    uncertainty_upper = Column(Numeric(12, 6), nullable=True)  # Upper bound of uncertainty range
    data_quality_tier = Column(Enum(DataQualityTier), nullable=False)
    
    # Source and validity
    source_reference = Column(String(200), nullable=False)
    source_document_url = Column(String(500), nullable=True)
    validity_start = Column(DateTime(timezone=True), nullable=False)
    validity_end = Column(DateTime(timezone=True), nullable=True)
    last_updated = Column(DateTime(timezone=True), nullable=False)
    
    # Supplier-specific data (for primary factors)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    verification_status = Column(String(20), default="unverified")  # verified, unverified, rejected
    
    # Technical details
    calculation_methodology = Column(String(100), nullable=False)
    geographic_scope = Column(String(100), nullable=True)  # e.g., "US", "EU", "Global"
    temporal_scope = Column(String(50), nullable=True)  # e.g., "2020-2023"
    included_gases = Column(String(50), default="CO2,CH4,N2O")  # GHG gases included
    
    # Relationships
    material_category = relationship("MaterialCategory", back_populates="emission_factors")
    material_subtype = relationship("MaterialSubtype", back_populates="emission_factors")
    supplier = relationship("Organization", back_populates="emission_factors")
    activity_data = relationship("ActivityData", back_populates="emission_factor")
    
    # Constraints and indexes
    __table_args__ = (
        Index('ix_emission_factor_lookup', 'material_category_id', 'material_subtype_id', 'factor_type', 'validity_start'),
        Index('ix_emission_factor_validity', 'validity_start', 'validity_end'),
    )
    
    def __repr__(self) -> str:
        return f"<EmissionFactor {self.co2_factor_kg} kg CO2/{self.material_category.standardized_unit.value} ({self.factor_type.value})>"


class ActivityData(Base, UUIDMixin, TimestampMixin):
    """Activity data submissions with unit normalization and audit trails"""
    __tablename__ = "activity_data"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    material_category_id = Column(UUID(as_uuid=True), ForeignKey("material_categories.id"), nullable=False)
    material_subtype_id = Column(UUID(as_uuid=True), ForeignKey("material_subtypes.id"), nullable=True)
    emission_factor_id = Column(UUID(as_uuid=True), ForeignKey("emission_factors.id"), nullable=False)
    
    # Submission details
    batch_identifier = Column(String(100), nullable=False, index=True)  # Unique material batch ID
    quantity_submitted = Column(Numeric(15, 4), nullable=False)
    unit_submitted = Column(String(20), nullable=False)
    quantity_normalized = Column(Numeric(15, 4), nullable=False)  # In standardized units
    unit_normalized = Column(Enum(StandardUnit), nullable=False)
    
    # Calculation results (locked at submission time)
    emission_factor_used = Column(Numeric(12, 6), nullable=False)  # Snapshot of factor at calculation time
    co2_calculated = Column(Numeric(15, 6), nullable=False)
    uncertainty_lower = Column(Numeric(15, 6), nullable=True)
    uncertainty_upper = Column(Numeric(15, 6), nullable=True)
    
    # Submission metadata
    submission_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    submitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Status and verification
    status = Column(String(20), default="submitted")  # submitted, under_review, verified, rejected
    verification_date = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # Relationships
    project = relationship("Project", back_populates="activity_data")
    material_category = relationship("MaterialCategory")
    material_subtype = relationship("MaterialSubtype")
    emission_factor = relationship("EmissionFactor", back_populates="activity_data")
    supplier = relationship("Organization", back_populates="activity_data_submissions")
    submitter = relationship("User", foreign_keys=[submitted_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    
    # Evidence and audit trail
    evidence_files = relationship("EvidenceFile", back_populates="activity_data")
    attestations = relationship("SupplierAttestation", back_populates="activity_data")
    correction_history = relationship("ActivityDataCorrection", back_populates="original_submission")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('batch_identifier', 'project_id', name='uq_batch_project'),
        Index('ix_activity_data_project', 'project_id', 'submission_date'),
        Index('ix_activity_data_supplier', 'supplier_id', 'submission_date'),
    )
    
    def __repr__(self) -> str:
        return f"<ActivityData {self.quantity_normalized} {self.unit_normalized.value} ({self.status})>"


class ActivityDataCorrection(Base, UUIDMixin, TimestampMixin):
    """Correction records for activity data (no overwrites, only new revisions)"""
    __tablename__ = "activity_data_corrections"

    original_submission_id = Column(UUID(as_uuid=True), ForeignKey("activity_data.id"), nullable=False)
    corrected_submission_id = Column(UUID(as_uuid=True), ForeignKey("activity_data.id"), nullable=False)
    
    correction_reason = Column(Text, nullable=False)
    correction_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    corrected_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Change tracking
    field_changes = Column(Text, nullable=False)  # JSON string of changed fields
    old_values = Column(Text, nullable=False)  # JSON string of old values
    new_values = Column(Text, nullable=False)  # JSON string of new values
    
    # Approval workflow
    approval_status = Column(String(20), default="pending")  # pending, approved, rejected
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approval_date = Column(DateTime(timezone=True), nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # Relationships
    original_submission = relationship("ActivityData", foreign_keys=[original_submission_id], back_populates="correction_history")
    corrected_submission = relationship("ActivityData", foreign_keys=[corrected_submission_id])
    corrector = relationship("User", foreign_keys=[corrected_by])
    approver = relationship("User", foreign_keys=[approved_by])
    
    def __repr__(self) -> str:
        return f"<ActivityDataCorrection {self.correction_reason[:50]}... ({self.approval_status})>"
