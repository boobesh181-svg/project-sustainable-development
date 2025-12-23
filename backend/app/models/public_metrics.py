"""Public Metrics: Read-only transparency table for public dashboard."""

from datetime import datetime, timezone
import uuid

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PublicMetrics(Base):
    """
    Read-only public transparency metrics.
    
    Purpose:
    - Public dashboard data
    - No sensitive information
    - Aggregated statistics only
    - Updated after MRV approval
    
    Security:
    - No PII (Personally Identifiable Information)
    - No contract details
    - No supplier names
    - Only CO₂ totals
    """

    __tablename__ = "public_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Project reference (FK without relationship to prevent data leaks)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, unique=True
    )

    # Aggregated CO₂ data
    total_co2_saved_t: Mapped[float] = mapped_column(
        Numeric(18, 6), nullable=False, default=0.0,
        comment="Total CO₂ emissions saved (metric tons)"
    )

    verified_co2_t: Mapped[float] = mapped_column(
        Numeric(18, 6), nullable=False, default=0.0,
        comment="Verified CO₂ (approved MRV reports only)"
    )

    # Material quantity (non-sensitive aggregate)
    total_materials_t: Mapped[float] = mapped_column(
        Numeric(18, 6), nullable=False, default=0.0,
        comment="Total materials delivered (metric tons)"
    )

    # Update tracking
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
