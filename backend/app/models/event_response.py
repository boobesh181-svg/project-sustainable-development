from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResponseType(str, PyEnum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    COMMENTED = "COMMENTED"
    DISPUTED = "DISPUTED"
    NO_RESPONSE_AUTO = "NO_RESPONSE_AUTO"


class EventResponse(Base):
    """Append-only acknowledgement/dispute response to a notification."""

    __tablename__ = "event_response"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event_notification.id"), nullable=False, index=True
    )

    responder_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True
    )

    response_type: Mapped[ResponseType] = mapped_column(
        SAEnum(ResponseType, name="event_response_type"),
        nullable=False,
    )

    response_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    response_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    response_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    demo_watermark: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    __table_args__ = (
        CheckConstraint(
            "response_hash ~ '^[0-9a-f]{64}$'",
            name="ck_event_response_hash_format",
        ),
        Index("ix_event_response_notification_time", "notification_id", "response_timestamp"),
    )

    @staticmethod
    def compute_hash(
        *,
        notification_id: uuid.UUID,
        responder_user_id: uuid.UUID | None,
        response_type: ResponseType,
        response_timestamp: datetime,
        response_comment: str | None,
        demo_watermark: bool,
    ) -> str:
        raw = "|".join(
            [
                str(notification_id),
                str(responder_user_id) if responder_user_id else "",
                response_type.value,
                response_timestamp.replace(microsecond=0).isoformat(),
                (response_comment or "").strip(),
                "demo" if demo_watermark else "prod",
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
