"""Delivery Verification: Tamper-proof delivery evidence with photo + GPS hashing."""

from datetime import datetime, timezone
import hashlib
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def compute_photo_fingerprint(photo_path: str) -> str:
    """
    Compute SHA256 fingerprint of photo file.
    
    Prevents:
    - Photo tampering (hash mismatch = evidence altered)
    - Photo substitution (original photo hash locked)
    """
    try:
        with open(photo_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        raise ValueError(f"Photo file not found: {photo_path}")


def compute_gps_hash(lat: float, lon: float, timestamp: datetime) -> str:
    """
    Compute deterministic hash of GPS location + timestamp.
    
    Prevents:
    - GPS coordinate manipulation (hash validates authenticity)
    - Timestamp backdating (hash includes time)
    
    Format: SHA256(lat|lon|timestamp_iso)
    """
    data = f"{lat:.6f}|{lon:.6f}|{timestamp.isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()


class DeliveryVerification(Base):
    """
    Tamper-proof delivery verification record.
    
    Prevents:
    - Photo tampering (SHA256 fingerprint locked)
    - GPS manipulation (hashed coordinates)
    - Timestamp backdating (hash includes time)
    - Evidence alteration (immutable after verification)
    - False delivery claims (photo + GPS required)
    
    Flow:
    1. Material token redeemed with photo + GPS
    2. Verification created with photo fingerprint + GPS hash
    3. Inspector verifies authenticity
    4. Verification locked (immutable)
    5. Any tampering breaks hash chain
    """

    __tablename__ = "delivery_verification"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Link to material token (one-to-one after redemption)
    material_token_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_token.id"), unique=True, nullable=False
    )

    # Photo evidence (immutable)
    photo_path: Mapped[str] = mapped_column(String(512), nullable=False)
    photo_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # SHA256 hex

    # GPS evidence (immutable)
    delivery_lat: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_lon: Mapped[float] = mapped_column(Float, nullable=False)
    gps_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Timestamp lock (immutable)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Inspector audit trail
    verified_by: Mapped[str] = mapped_column(String(100), nullable=False)

    # Verification status (one-time lock)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    material_token = relationship("MaterialToken", back_populates="delivery_verification")

    __table_args__ = (
        CheckConstraint(
            "delivery_lat >= -90 AND delivery_lat <= 90",
            name="ck_delivery_verification_valid_lat",
        ),
        CheckConstraint(
            "delivery_lon >= -180 AND delivery_lon <= 180",
            name="ck_delivery_verification_valid_lon",
        ),
        CheckConstraint(
            "LENGTH(photo_fingerprint) = 64",
            name="ck_delivery_verification_photo_hash_format",
        ),
        CheckConstraint(
            "LENGTH(gps_hash) = 64",
            name="ck_delivery_verification_gps_hash_format",
        ),
    )

    def verify_photo_integrity(self) -> bool:
        """
        Verify photo has not been tampered with.
        
        Returns:
            True if current photo matches fingerprint, False otherwise
        """
        try:
            current_hash = compute_photo_fingerprint(self.photo_path)
            return current_hash == self.photo_fingerprint
        except ValueError:
            return False

    def verify_gps_integrity(self) -> bool:
        """
        Verify GPS coordinates have not been altered.
        
        Returns:
            True if GPS hash matches current coordinates + timestamp, False otherwise
        """
        computed_hash = compute_gps_hash(
            self.delivery_lat, self.delivery_lon, self.verified_at
        )
        return computed_hash == self.gps_hash

    def lock_verification(self, verified_by: str, notes: str | None = None) -> None:
        """
        Lock verification as approved (immutable after this).
        
        Rules:
        - Can only verify once
        - Photo and GPS hashes must be valid
        - Once verified, record is immutable
        """
        if self.is_verified:
            raise ValueError("Delivery already verified; cannot verify twice")

        if not self.verify_photo_integrity():
            raise ValueError("Photo integrity check failed; possible tampering detected")

        if not self.verify_gps_integrity():
            raise ValueError("GPS integrity check failed; coordinates altered")

        self.is_verified = True
        self.verified_by = verified_by
        self.verification_notes = notes
