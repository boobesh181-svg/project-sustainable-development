"""Anomaly Alert: Immutable rule-based anomaly detection records."""

from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, Float, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnomalySeverity(str, PyEnum):
    """Anomaly severity levels (deterministic, explainable)."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AnomalyAlert(Base):
    """
    Immutable anomaly record for audit & investigation.
    
    Detects:
    - Quantity inflation (token.quantity > threshold)
    - Delivery far from project site (GPS distance check)
    - Duplicate delivery photos (photo fingerprint reuse)
    - Suspicious supplier behavior (patterns)
    - Token misuse patterns (time-based, frequency)
    
    Principles:
    - Rules > ML for first deployment (deterministic)
    - Every anomaly is recorded (no silent suppression)
    - Immutable once created (audit trail)
    - Linked to evidence (token_uid, project_id)
    """

    __tablename__ = "anomaly_alert"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Project linkage
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=False
    )

    # Evidence linkage (optional token reference)
    token_uid: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Rule identification
    rule_code: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # EXCESS_QUANTITY, DISTANCE_MISMATCH, DUPLICATE_PHOTO

    # Severity classification
    severity: Mapped[AnomalySeverity] = mapped_column(
        SAEnum(AnomalySeverity, name="anomaly_severity"),
        nullable=False,
        default=AnomalySeverity.MEDIUM,
    )

    # Human-readable description
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Numeric evidence (for threshold-based rules)
    numeric_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    threshold: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)

    # Detection timestamp (immutable)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="anomalies")

    __table_args__ = (
        CheckConstraint(
            "(numeric_value IS NULL AND threshold IS NULL) OR (numeric_value IS NOT NULL AND threshold IS NOT NULL)",
            name="ck_anomaly_numeric_consistency",
        ),
    )
