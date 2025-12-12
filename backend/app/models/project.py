from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProjectStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="project_status"), nullable=False
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    budget_usd: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    material_tokens: Mapped[list["MaterialToken"]] = relationship("MaterialToken", back_populates="project")
    sensor_readings: Mapped[list["SensorReading"]] = relationship("SensorReading", back_populates="project")
    mrv_reports: Mapped[list["MRVReport"]] = relationship("MRVReport", back_populates="project")
    mrv_samples: Mapped[list["MRVSample"]] = relationship("MRVSample", back_populates="project")
    anomalies: Mapped[list["AnomalyAlert"]] = relationship("AnomalyAlert", back_populates="project")
    whistleblowers: Mapped[list["Whistleblower"]] = relationship("Whistleblower", back_populates="project")
