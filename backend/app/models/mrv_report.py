"""MRV Report: Immutable-after-approval workflow with strict state machine."""

from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MRVStatus(str, PyEnum):
    """
    MRV report lifecycle states (strict progression, no reversion).
    
    Flow: DRAFT → SUBMITTED → VERIFIED → APPROVED → LOCKED
    Rules:
    - Cannot skip steps
    - Cannot revert after APPROVED
    - LOCKED = immutable forever
    """
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    LOCKED = "LOCKED"


class MRVReport(Base):
    """
    Immutable-after-approval MRV report.
    
    Prevents:
    - Silent edits after approval (ISO-14064 compliance)
    - Retroactive CO₂ changes (audit trail broken)
    - Status regression (cannot downgrade from APPROVED)
    - Role confusion (separation of duties: creator ≠ verifier ≠ approver)
    """

    __tablename__ = "mrv_report"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Project linkage
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=False
    )

    # Reporting metadata
    reporting_period: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "2025-Q1"

    # Sample/test details
    emission_factor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emission_factor.id"), nullable=True
    )
    sample_desc: Mapped[str] = mapped_column(Text, nullable=False)
    parameter: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)

    # CO₂ calculation (immutable after approval)
    total_co2e: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)

    # Evidence
    certificate_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Snapshot for reproducibility (ISO-14064)
    emission_factor_version_snapshot: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    emission_factor_hash_snapshot: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    emission_factor_value_snapshot: Mapped[float | None] = mapped_column(
        Numeric(18, 6), nullable=True
    )

    # Workflow state (strict progression)
    status: Mapped[MRVStatus] = mapped_column(
        SAEnum(MRVStatus, name="mrv_status_workflow"),
        nullable=False,
        default=MRVStatus.DRAFT,
    )

    # Role separation (creator ≠ verifier ≠ approver)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="mrv_reports")
    emission_factor = relationship("EmissionFactor", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "emission_factor_hash_snapshot IS NULL OR char_length(emission_factor_hash_snapshot) = 64",
            name="ck_mrv_snapshot_hash_len",
        ),
        # Status ↔ actor requirements
        CheckConstraint(
            "(status IN ('VERIFIED','APPROVED','LOCKED')) = (verified_by IS NOT NULL)",
            name="ck_mrv_verified_by_required",
        ),
        CheckConstraint(
            "(status IN ('APPROVED','LOCKED')) = (approved_by IS NOT NULL)",
            name="ck_mrv_approved_by_required",
        ),
        # Separation of duties (null-safe)
        CheckConstraint(
            "created_by IS DISTINCT FROM verified_by",
            name="ck_mrv_creator_ne_verifier",
        ),
        CheckConstraint(
            "created_by IS DISTINCT FROM approved_by",
            name="ck_mrv_creator_ne_approver",
        ),
        CheckConstraint(
            "verified_by IS NULL OR approved_by IS NULL OR verified_by IS DISTINCT FROM approved_by",
            name="ck_mrv_verifier_ne_approver",
        ),
    )

    def assert_editable(self) -> None:
        """
        Enforce immutability after approval.
        
        Raises:
            ValueError: If report is APPROVED or LOCKED (immutable state)
        """
        if self.status in (MRVStatus.APPROVED, MRVStatus.LOCKED):
            raise ValueError(
                f"MRV report is immutable after approval (current status: {self.status.value})"
            )

    def advance(self, next_status: MRVStatus) -> None:
        """
        Advance MRV report to next workflow state (strict progression).
        
        Rules:
        - DRAFT → SUBMITTED
        - SUBMITTED → VERIFIED
        - VERIFIED → APPROVED
        - APPROVED → LOCKED
        - Cannot skip steps
        - Cannot revert
        
        Args:
            next_status: Target state
            
        Raises:
            ValueError: If transition is invalid
        """
        if self.status == MRVStatus.LOCKED:
            raise ValueError("Invalid MRV state transition: LOCKED reports are immutable")

        # Define allowed transitions
        allowed_transitions = {
            MRVStatus.DRAFT: MRVStatus.SUBMITTED,
            MRVStatus.SUBMITTED: MRVStatus.VERIFIED,
            MRVStatus.VERIFIED: MRVStatus.APPROVED,
            MRVStatus.APPROVED: MRVStatus.LOCKED,
        }

        if self.status not in allowed_transitions:
            raise ValueError(f"Invalid current state: {self.status.value}")

        expected_next = allowed_transitions[self.status]
        if expected_next != next_status:
            raise ValueError(
                f"Invalid MRV state transition: {self.status.value} → {next_status.value} "
                f"(expected {self.status.value} → {expected_next.value})"
            )

        # Advance state
        self.status = next_status
