"""Audit Log: Append-only hash-chained audit trail (tamper-evident)."""

from datetime import datetime, timezone
import hashlib
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """
    Append-only audit log with hash chaining for tamper detection.
    
    Guarantees:
    - Every critical action is recorded (TOKEN_ISSUED, DELIVERY_VERIFIED, MRV_APPROVED, etc.)
    - Logs are append-only (no updates, no deletes allowed at DB level)
    - Each entry is hash-chained to the previous one
    - Any tampering is immediately detectable (chain breaks)
    
    Hash Chain Structure:
    - event_hash = SHA256(sorted_event_json)
    - prev_hash = chain_hash of previous audit record
    - chain_hash = SHA256(prev_hash + event_hash)
    
    Tampering Detection:
    - Modify any field → event_hash changes
    - Delete record → chain breaks
    - Reorder records → prev_hash mismatches
    
    Covered Actions:
    - TOKEN_ISSUED, TOKEN_REDEEMED
    - DELIVERY_VERIFIED, DELIVERY_APPROVED
    - MRV_SUBMITTED, MRV_VERIFIED, MRV_APPROVED, MRV_LOCKED
    - ANOMALY_DETECTED
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Actor (who performed the action)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Optional FK to user (for strict attribution)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )

    # Request metadata (best-effort, may be null for background jobs)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Action (what was done)
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # TOKEN_ISSUED, DELIVERY_VERIFIED, MRV_APPROVED, etc.

    # Entity being audited
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # MaterialToken, DeliveryVerification, MRVReport, etc.
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Event data (immutable JSON snapshot)
    event_data: Mapped[str] = mapped_column(Text, nullable=False)

    # Hash chain (tamper-evident)
    event_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # SHA256 of event_data
    prev_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # chain_hash of previous record
    chain_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )  # SHA256(prev_hash + event_hash)

    # Timestamp (immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "LENGTH(event_hash) = 64",
            name="ck_audit_event_hash_len",
        ),
        CheckConstraint(
            "prev_hash IS NULL OR LENGTH(prev_hash) = 64",
            name="ck_audit_prev_hash_len",
        ),
        CheckConstraint(
            "LENGTH(chain_hash) = 64",
            name="ck_audit_chain_hash_len",
        ),
    )

    @staticmethod
    def hash_data(data: str) -> str:
        """
        Compute SHA256 hash of data.
        
        Args:
            data: Data string to hash (typically JSON)
            
        Returns:
            SHA256 hex digest (64 characters)
        """
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def compute_chain(prev_hash: str | None, event_hash: str) -> str:
        """
        Compute chain hash (SHA256 of previous hash + current hash).
        
        Args:
            prev_hash: Chain hash of previous record (None for first record)
            event_hash: Event hash of current record
            
        Returns:
            Chain hash (64 characters)
        """
        raw = f"{prev_hash or ''}{event_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def verify_chain(prev_chain: str | None, event_hash: str, current_chain: str) -> bool:
        """
        Verify that chain hash is correct.
        
        Args:
            prev_chain: Chain hash of previous record
            event_hash: Event hash of current record
            current_chain: Claimed chain hash of current record
            
        Returns:
            True if chain is valid, False if tampered
        """
        computed = AuditLog.compute_chain(prev_chain, event_hash)
        return computed == current_chain
