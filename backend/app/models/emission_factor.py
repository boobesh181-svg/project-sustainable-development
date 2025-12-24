import uuid
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmissionFactor(Base):
    """
    IMMUTABLE emission factor table.
    Once activated, records can NEVER be edited or deleted.
    New versions must be created instead.
    
    Immutability enforced via:
    - is_active flag (only one active per material)
    - factor_hash (SHA256 lock, unique constraint)
    - PostgreSQL trigger prevents UPDATE/DELETE on active factors
    """

    __tablename__ = "emission_factor"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identification
    material_code: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., CEMENT_OPC, RECYCLED_STEEL
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Versioning
    version: Mapped[int] = mapped_column(nullable=False)

    # CO₂ factor (kg CO₂e per unit)
    co2e_per_unit: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="kg")  # kg, ton, m3
    
    # Validity window
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Integrity lock (SHA256)
    factor_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    
    # Activation (immutable once True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("material_code", "version", name="uq_material_code_version"),
        CheckConstraint("co2e_per_unit > 0", name="ck_positive_co2"),
        CheckConstraint("factor_hash ~ '^[0-9a-f]{64}$'", name="ck_factor_hash_format"),
        Index("ix_emission_factor_active", "material_code", "is_active"),
    )

    def generate_hash(self) -> str:
        """Generate deterministic SHA256 hash to lock factor permanently."""
        co2e_str = str(Decimal(str(self.co2e_per_unit)).quantize(Decimal("0.000001")))
        raw = f"{self.material_code}|{self.version}|{co2e_str}|{self.unit}|{self.valid_from.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def activate(self) -> None:
        """Lock the factor permanently. Can only be called once."""
        if self.is_active:
            raise ValueError("Emission factor already active and immutable")
        if not self.factor_hash:
            self.factor_hash = self.generate_hash()
        self.is_active = True
