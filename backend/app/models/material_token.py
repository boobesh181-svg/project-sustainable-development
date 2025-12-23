"""Material Token: One-time redeemable material authorization (anti-corruption core)."""

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MaterialToken(Base):
    """
    One-time redeemable material authorization token.
    
    Prevents:
    - Fake materials (token must be issued first)
    - Over-billing (quantity locked at issue)
    - Duplicate deliveries (one redeem per token)
    - Ghost materials (photo + GPS evidence required)
    
    Flow:
    1. Contractor issues token (unredeed)
    2. Supplier delivers material
    3. Evidence uploaded (photo, geo, invoice)
    4. Token redeemed (becomes immutable)
    5. No second redemption allowed
    """

    __tablename__ = "material_token"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Unique token identifier (immutable)
    token_uid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )

    # Project linkage
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=False
    )

    # Material specification (immutable)
    material_code: Mapped[str] = mapped_column(String(100), nullable=False)
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Quantity authorization (immutable)
    quantity: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)  # tonnes, m3, etc.
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="kg")

    # Supplier (immutable)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Issuance audit
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    issued_by: Mapped[str] = mapped_column(String(100), nullable=False)

    # Redemption status (one-time only)
    redeemed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Evidence linkage (immutable after redemption)
    delivery_photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    delivery_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    supplier_invoice_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="material_tokens")
    delivery_verification = relationship(
        "DeliveryVerification", back_populates="material_token", uselist=False
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_material_token_positive_qty"),
        CheckConstraint(
            "redeemed = false OR (redeemed_at IS NOT NULL AND delivery_lat IS NOT NULL AND delivery_lon IS NOT NULL)",
            name="ck_material_token_redemption_complete",
        ),
        UniqueConstraint("project_id", "token_uid", name="uq_material_token_project_uid"),
    )

    def redeem(self) -> None:
        """Mark token as redeemed (one-time only, immutable after)."""
        if self.redeemed:
            raise ValueError("Token already redeemed; cannot redeem twice")
        self.redeemed = True
        self.redeemed_at = datetime.now(timezone.utc)
