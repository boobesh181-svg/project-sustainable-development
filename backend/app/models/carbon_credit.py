import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    Sequence,
    String,
    Text,
    UniqueConstraint,
    event,
    DDL,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LifecycleStatus(str, PyEnum):
    ISSUED = "issued"
    VERIFIED = "verified"
    APPROVED = "approved"
    RETIRED = "retired"


class CarbonCreditLifecycle(Base):
    """Immutable carbon credit lifecycle; retired rows cannot be updated or deleted."""

    __tablename__ = "carbon_credit_lifecycle"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Unique serial namespace (monotonic sequence per DB)
    serial_number: Mapped[int] = mapped_column(
        Sequence("carbon_credit_lifecycle_serial_seq", metadata=Base.metadata),
        nullable=False,
        unique=True,
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=True
    )

    status: Mapped[LifecycleStatus] = mapped_column(
        SAEnum(LifecycleStatus, name="carbon_credit_lifecycle_status"),
        nullable=False,
        default=LifecycleStatus.ISSUED,
    )

    co2e_amount_tonnes: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)
    emission_factor_version: Mapped[str] = mapped_column(String(64), nullable=False)

    issuer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    verifier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    approver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    retired_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    retirement_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retirement_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    project = relationship("Project", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("serial_number", name="uq_ccl_serial"),
        CheckConstraint(
            "verified_at IS NULL OR issued_at IS NOT NULL",
            name="ck_ccl_verify_after_issue",
        ),
        CheckConstraint(
            "approved_at IS NULL OR verified_at IS NOT NULL",
            name="ck_ccl_approve_after_verify",
        ),
        CheckConstraint(
            "retired_at IS NULL OR (approved_at IS NOT NULL AND status = 'retired')",
            name="ck_ccl_retire_after_approval",
        ),
        CheckConstraint(
            "issuer_id IS DISTINCT FROM verifier_id "
            "AND verifier_id IS DISTINCT FROM approver_id "
            "AND issuer_id IS DISTINCT FROM approver_id",
            name="ck_ccl_separation_of_duties",
        ),
        CheckConstraint(
            "status <> 'retired' OR (retired_at IS NOT NULL AND retired_by IS NOT NULL AND retirement_reason IS NOT NULL)",
            name="ck_ccl_retirement_requires_fields",
        ),
        Index("ix_ccl_status_serial", "status", "serial_number"),
    )


immutability_fn = DDL(
    """
    CREATE OR REPLACE FUNCTION ccl_block_mutation_when_retired() RETURNS trigger AS $$
    BEGIN
        IF (OLD.status = 'retired') THEN
            RAISE EXCEPTION 'Retired carbon credit lifecycle rows are immutable';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

immutability_update_trigger = DDL(
    """
    CREATE TRIGGER trg_ccl_no_update_after_retirement
    BEFORE UPDATE ON carbon_credit_lifecycle
    FOR EACH ROW
    WHEN (OLD.status = 'retired')
    EXECUTE FUNCTION ccl_block_mutation_when_retired();
    """
)

immutability_delete_trigger = DDL(
    """
    CREATE TRIGGER trg_ccl_no_delete_after_retirement
    BEFORE DELETE ON carbon_credit_lifecycle
    FOR EACH ROW
    WHEN (OLD.status = 'retired')
    EXECUTE FUNCTION ccl_block_mutation_when_retired();
    """
)

event.listen(
    CarbonCreditLifecycle.__table__,
    "after_create",
    immutability_fn.execute_if(dialect="postgresql"),
)
event.listen(
    CarbonCreditLifecycle.__table__,
    "after_create",
    immutability_update_trigger.execute_if(dialect="postgresql"),
)
event.listen(
    CarbonCreditLifecycle.__table__,
    "after_create",
    immutability_delete_trigger.execute_if(dialect="postgresql"),
)
