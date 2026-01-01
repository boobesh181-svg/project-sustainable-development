"""Evidence: file metadata with SHA-256 for integrity and auditability."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    upload_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )

    # Optional linkage (e.g. evidence attached to an MRV report)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mrv_report.id"), nullable=True
    )

    # Optional linkage (e.g. evidence attached to a material token delivery / EPD / invoice)
    material_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_token.id"), nullable=True
    )

    # Optional geo metadata (real-world ingestion)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Demo-mode safety flags
    demo_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    non_compliant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        CheckConstraint("LENGTH(sha256) = 64", name="ck_evidence_sha256_len"),
        CheckConstraint("size_bytes >= 0", name="ck_evidence_size_nonneg"),
        CheckConstraint("lat IS NULL OR (lat >= -90 AND lat <= 90)", name="ck_evidence_valid_lat"),
        CheckConstraint("lon IS NULL OR (lon >= -180 AND lon <= 180)", name="ck_evidence_valid_lon"),
        CheckConstraint(
            "decision IS NULL OR decision IN ('accepted','rejected','needs_correction')",
            name="ck_evidence_decision_allowed",
        ),
        CheckConstraint(
            "verified_at IS NULL OR verified_by IS NOT NULL",
            name="ck_evidence_verified_requires_actor",
        ),
    )

    @property
    def evidence_hash(self) -> str:
        """Alias for sha256 (integrity hash) to match ingestion terminology."""
        return self.sha256
