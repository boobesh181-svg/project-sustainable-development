from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SensorType(str, PyEnum):
    ENERGY = "energy"
    WATER_SAVING = "water_saving"
    OTHER = "other"


class SensorReading(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"))
    sensor_type: Mapped[SensorType] = mapped_column(
        SAEnum(SensorType, name="sensor_type"), nullable=False
    )
    value: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="sensor_readings")
