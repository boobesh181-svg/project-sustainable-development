from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("role.id"), nullable=False)

    # Optional linkage for supplier-scoped visibility.
    # Only used for RoleName.SUPPLIER accounts.
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    supplier: Mapped["Supplier | None"] = relationship("Supplier", lazy="selectin")
