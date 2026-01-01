from __future__ import annotations

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceOut(BaseModel):
    id: UUID
    upload_type: str
    storage_path: str
    sha256: str
    evidence_hash: str
    size_bytes: int
    content_type: str | None
    original_filename: str | None
    created_at: datetime
    created_by: UUID | None
    report_id: UUID | None
    material_token_id: UUID | None
    lat: float | None = None
    lon: float | None = None
    verified_at: datetime | None
    verified_by: UUID | None
    decision: str | None = None
    verification_notes: str | None

    demo_only: bool = False
    non_compliant: bool = False

    model_config = ConfigDict(from_attributes=True)


class EvidenceVerify(BaseModel):
    decision: str | None = Field(
        None,
        description="Optional decision tag: accepted | rejected | needs_correction",
        max_length=32,
    )
    verification_notes: str | None = Field(None, max_length=2000)
