"""Evidence routes: verification and lookup.

Evidence rows are append-only; after verification they are immutable at DB level.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, role_required
from app.models.evidence import Evidence
from app.models.role import RoleName
from app.models.user import User
from app.schemas.evidence import EvidenceOut, EvidenceVerify
from app.services.evidence_service import verify_evidence as verify_evidence_service


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
    try:
        return await verify_evidence_service(
            db,
            evidence_id=evidence_id,
            payload=payload,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
