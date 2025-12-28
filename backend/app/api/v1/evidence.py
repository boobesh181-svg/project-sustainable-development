"""Evidence routes: verification and lookup.

Evidence rows are append-only; after verification they are immutable at DB level.
"""

from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, role_required
from app.models.evidence import Evidence
from app.models.role import RoleName
from app.models.user import User
from app.schemas.evidence import EvidenceOut, EvidenceVerify
from app.services.audit_log_service import write_audit_log


router = APIRouter(prefix="/api/v1/evidence", tags=["Evidence"])


@router.get("/{evidence_id}", response_model=EvidenceOut)
async def get_evidence(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvidenceOut:
    evidence = await db.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")

    # Simple rule: uploader can view; admins/mrv officers can view all
    if evidence.created_by != current_user.id:
        if current_user.role is None or current_user.role.name not in {RoleName.ADMIN, RoleName.MRV_OFFICER}:
            raise HTTPException(status_code=403, detail="Not authorized to view this evidence")

    return evidence


@router.post("/{evidence_id}/verify", response_model=EvidenceOut)
async def verify_evidence(
    evidence_id: UUID,
    payload: EvidenceVerify,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.MRV_OFFICER])),
) -> EvidenceOut:
    evidence = await db.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")

    if evidence.verified_at is not None:
        raise HTTPException(status_code=400, detail="Evidence already verified")

    evidence.verified_at = datetime.now(timezone.utc)
    evidence.verified_by = current_user.id
    evidence.decision = payload.decision
    evidence.verification_notes = payload.verification_notes

    db.add(evidence)
    await db.commit()
    await db.refresh(evidence)

    await write_audit_log(
        db=db,
        actor=current_user.email,
        actor_user_id=current_user.id,
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
