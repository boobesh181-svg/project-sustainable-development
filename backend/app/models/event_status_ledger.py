from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DerivedStatus(str, PyEnum):
    UNSEEN = "UNSEEN"
    SEEN = "SEEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISPUTED = "DISPUTED"
    DEEMED_OBSERVED = "DEEMED_OBSERVED"


class EventStatusLedger(Base):
    """Append-only derived status for an activity, computed from notifications/responses."""

    __tablename__ = "event_status_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_record.id"), nullable=False, index=True
    )

    derived_status: Mapped[DerivedStatus] = mapped_column(
        SAEnum(DerivedStatus, name="event_derived_status"), nullable=False
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    computation_basis_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    __table_args__ = (
        CheckConstraint(
            "computation_basis_hash ~ '^[0-9a-f]{64}$'",
            name="ck_event_status_ledger_basis_hash_format",
        ),
        Index("ix_event_status_ledger_activity_time", "activity_id", "computed_at"),
    )

    @staticmethod
    def compute_basis_hash(*parts: str) -> str:
        raw = "|".join([p for p in parts if p is not None])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
