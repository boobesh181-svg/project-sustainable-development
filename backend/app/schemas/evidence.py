from __future__ import annotations

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceOut(BaseModel):
    id: UUID
    upload_type: str
    storage_path: str
    sha256: str
    size_bytes: int
    content_type: str | None
    original_filename: str | None
    created_at: datetime
    created_by: UUID | None
    report_id: UUID | None
    verified_at: datetime | None
    verified_by: UUID | None
    verification_notes: str | None

    model_config = ConfigDict(from_attributes=True)


class EvidenceVerify(BaseModel):
    verification_notes: str | None = Field(None, max_length=2000)
