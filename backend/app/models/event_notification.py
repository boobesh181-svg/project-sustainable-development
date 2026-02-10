from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeliveryChannel(str, PyEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"


class EventNotification(Base):
    """Notification sent to a counterparty for contemporaneous acknowledgement."""

    __tablename__ = "event_notification"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_record.id"), nullable=False, index=True
    )

    notified_party_org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    notified_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True
    )

    notification_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    response_deadline_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    notification_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    delivery_channel: Mapped[DeliveryChannel] = mapped_column(
        SAEnum(
            DeliveryChannel,
            name="delivery_channel",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        default=DeliveryChannel.IN_APP,
    )

    demo_watermark: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "notification_hash ~ '^[0-9a-f]{64}$'",
            name="ck_event_notification_hash_format",
        ),
        Index(
            "ix_event_notification_user_deadline",
            "notified_user_id",
            "response_deadline_timestamp",
        ),
    )

    @staticmethod
    def compute_hash(
        *,
        activity_id: uuid.UUID,
        notified_user_id: uuid.UUID,
        notification_timestamp: datetime,
        response_deadline_timestamp: datetime,
        delivery_channel: DeliveryChannel,
        demo_watermark: bool,
    ) -> str:
        raw = "|".join(
            [
                str(activity_id),
                str(notified_user_id),
                notification_timestamp.replace(microsecond=0).isoformat(),
                response_deadline_timestamp.replace(microsecond=0).isoformat(),
                delivery_channel.value,
                "demo" if demo_watermark else "prod",
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
