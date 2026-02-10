from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActivityType(str, PyEnum):
    MATERIAL_TOKEN_REDEEMED = "MATERIAL_TOKEN_REDEEMED"
    DELIVERY_VERIFICATION_CREATED = "DELIVERY_VERIFICATION_CREATED"
    MRV_REPORT_CREATED = "MRV_REPORT_CREATED"


class ActivityRecord(Base):
    """Canonical activity/event record for contemporaneous site acknowledgement.

    This table represents *what happened*, at the time it happened.
    Notifications and responses attach to this record.

    Append-only semantics are enforced at the DB layer via triggers.
    """

    __tablename__ = "activity_record"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    activity_type: Mapped[ActivityType] = mapped_column(
        SAEnum(ActivityType, name="activity_type"),
        nullable=False,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, index=True
    )

    # Exactly one of these should be set for now.
    material_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_token.id"), nullable=True
    )
    delivery_verification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_verification.id"), nullable=True
    )
    mrv_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mrv_report.id"), nullable=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )

    activity_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "activity_hash ~ '^[0-9a-f]{64}$'",
            name="ck_activity_record_hash_format",
        ),
        CheckConstraint(
            "(material_token_id IS NOT NULL)::int + (delivery_verification_id IS NOT NULL)::int + (mrv_report_id IS NOT NULL)::int = 1",
            name="ck_activity_record_exactly_one_source",
        ),
        Index("ix_activity_record_project_type_time", "project_id", "activity_type", "occurred_at"),
    )

    @staticmethod
    def compute_hash(
        *,
        activity_type: ActivityType,
        project_id: uuid.UUID,
        occurred_at: datetime,
        material_token_id: uuid.UUID | None,
        delivery_verification_id: uuid.UUID | None,
        mrv_report_id: uuid.UUID | None,
        created_by_user_id: uuid.UUID | None,
    ) -> str:
        occurred = occurred_at.replace(microsecond=0).isoformat()
        raw = "|".join(
            [
                activity_type.value,
                str(project_id),
                occurred,
                str(material_token_id) if material_token_id else "",
                str(delivery_verification_id) if delivery_verification_id else "",
                str(mrv_report_id) if mrv_report_id else "",
                str(created_by_user_id) if created_by_user_id else "",
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
