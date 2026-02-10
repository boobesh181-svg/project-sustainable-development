from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganizationRoleType(str, PyEnum):
    DEVELOPER = "DEVELOPER"
    CONTRACTOR = "CONTRACTOR"
    SUPPLIER = "SUPPLIER"
    OPERATOR = "OPERATOR"


class OrganizationRelationship(Base):
    __tablename__ = "organization_relationship"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, index=True
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True
    )

    role_type: Mapped[OrganizationRoleType] = mapped_column(
        SAEnum(OrganizationRoleType, name="organization_role_type"), nullable=False
    )

    ownership_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    financial_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    operational_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "ownership_percentage IS NULL OR (ownership_percentage >= 0 AND ownership_percentage <= 100)",
            name="ck_org_rel_ownership_pct_range",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_org_rel_valid_window",
        ),
        Index(
            "ix_org_rel_project_org_window",
            "project_id",
            "organization_id",
            "valid_from",
        ),
    )
