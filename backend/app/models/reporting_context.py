from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConsolidationMethod(str, PyEnum):
    EQUITY = "EQUITY"
    FINANCIAL_CONTROL = "FINANCIAL_CONTROL"
    OPERATIONAL_CONTROL = "OPERATIONAL_CONTROL"


class ReportingPurpose(str, PyEnum):
    ESG = "ESG"
    PROCUREMENT = "PROCUREMENT"
    TAX = "TAX"
    DISCLOSURE = "DISCLOSURE"


class ReportingContext(Base):
    __tablename__ = "reporting_context"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    reporting_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True
    )

    consolidation_method: Mapped[ConsolidationMethod] = mapped_column(
        SAEnum(ConsolidationMethod, name="consolidation_method"), nullable=False
    )

    reporting_purpose: Mapped[ReportingPurpose] = mapped_column(
        SAEnum(ReportingPurpose, name="reporting_purpose"), nullable=False
    )

    methodology_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("methodology_version.id"), nullable=False, index=True
    )

    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_reporting_context_valid_window",
        ),
        Index(
            "ix_reporting_context_entity_method_window",
            "reporting_entity_id",
            "methodology_version_id",
            "valid_from",
        ),
    )
