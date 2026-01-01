"""Evidence service: verification and audit logging."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceVerify
from app.services.audit_log_service import write_audit_log


async def verify_evidence(
    db: AsyncSession,
    *,
    evidence_id: UUID,
    payload: EvidenceVerify,
    actor_user_id: UUID,
    actor_email: str,
) -> Evidence:
    if settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode: evidence verification is disabled.",
        )

    evidence = await db.get(Evidence, evidence_id)
    if evidence is None:
        raise ValueError("Evidence not found")

    if evidence.verified_at is not None:
        raise ValueError("Evidence already verified")

    evidence.verified_at = datetime.now(timezone.utc)
    evidence.verified_by = actor_user_id
    evidence.decision = payload.decision
    evidence.verification_notes = payload.verification_notes

    db.add(evidence)
    await db.commit()
    await db.refresh(evidence)

    await write_audit_log(
        db=db,
        actor=actor_email,
        actor_user_id=actor_user_id,
        action="EVIDENCE_VERIFIED",
        entity_type="Evidence",
        entity_id=str(evidence.id),
        event_payload={
            "sha256": evidence.sha256,
            "report_id": str(evidence.report_id) if evidence.report_id else None,
            "decision": payload.decision,
            "verification_notes": payload.verification_notes,
        },
    )

    return evidence
