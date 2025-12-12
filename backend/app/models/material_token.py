from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MaterialToken(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"))
    material_type: Mapped[str] = mapped_column(String(128), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)  # tonnes
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    redeemed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    redemption_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    redemption_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    recycled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="material_tokens")
