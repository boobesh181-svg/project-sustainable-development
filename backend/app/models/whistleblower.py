from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WhistleblowerStatus(str, PyEnum):
    NEW = "new"
    OPEN = "open"
    CLOSED = "closed"
    DISMISSED = "dismissed"


class WhistleblowerPriority(str, PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Whistleblower(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[WhistleblowerStatus] = mapped_column(
        SAEnum(WhistleblowerStatus, name="whistleblower_status"), nullable=False
    )
    priority: Mapped[WhistleblowerPriority] = mapped_column(
        SAEnum(WhistleblowerPriority, name="whistleblower_priority"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="whistleblowers", lazy="joined", overlaps="whistleblowers")
