"""Pydantic schemas for delivery verification (tamper-proof evidence)."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DeliveryVerificationCreate(BaseModel):
    """Create a delivery verification record (auto-hashes photo + GPS)."""
    material_token_id: UUID
    photo_path: str = Field(..., min_length=1, max_length=512)
    delivery_lat: float = Field(..., ge=-90, le=90)
    delivery_lon: float = Field(..., ge=-180, le=180)


class DeliveryVerificationApprove(BaseModel):
    """Approve/lock a delivery verification (one-time)."""
    # Deprecated: server derives actor identity from JWT; retained for backward compatibility.
    verified_by: str | None = Field(None, min_length=1, max_length=100)
    verification_notes: str | None = Field(None, max_length=1000)


class DeliveryVerificationOut(BaseModel):
    """Delivery verification response (full details)."""
    id: UUID
    material_token_id: UUID
    photo_path: str
    photo_fingerprint: str
    delivery_lat: float
    delivery_lon: float
    gps_hash: str
    verified_at: datetime
    verified_by: str
    created_by_user_id: UUID | None = None
    verified_by_user_id: UUID | None = None
    is_verified: bool
    verification_notes: str | None
    
    model_config = ConfigDict(from_attributes=True)


class DeliveryIntegrityCheck(BaseModel):
    """Integrity check response (tamper detection)."""
    photo_integrity_ok: bool
    gps_integrity_ok: bool
    overall_integrity_ok: bool
    message: str
