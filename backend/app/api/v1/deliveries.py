"""Delivery verification routes: tamper-proof evidence validation."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, role_required
from app.models.project import Project
from app.models.role import RoleName
from app.models.user import User
from app.schemas.delivery import (
    DeliveryVerificationCreate,
    DeliveryVerificationApprove,
    DeliveryVerificationOut,
    DeliveryIntegrityCheck,
)
from app.services.delivery_service import (
    create_delivery_verification,
    approve_delivery_verification,
    get_delivery_verification_by_id,
    check_delivery_integrity,
    list_delivery_verifications,
)

router = APIRouter(prefix="/api/v1/deliveries", tags=["Delivery Verification"])


def _can_view_all(current_user: User) -> bool:
    if current_user.role is None:
        return False
    return current_user.role.name in {RoleName.ADMIN, RoleName.MRV_OFFICER}


async def _assert_project_access(db: AsyncSession, *, project_id: UUID, current_user: User) -> None:
    if _can_view_all(current_user):
        return

    result = await db.execute(
        select(Project.id).where(Project.id == project_id, Project.created_by == current_user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not authorized for this project")


@router.get("/", response_model=list[DeliveryVerificationOut])
async def list_verifications(
    project_id: UUID | None = Query(None, description="Optional filter: only verifications for a project"),
    limit: int = Query(200, ge=1, le=500, description="Max verifications to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List delivery verifications (read-only visibility for dashboard/screens)."""
    if project_id is not None:
        await _assert_project_access(db, project_id=project_id, current_user=current_user)
        return await list_delivery_verifications(db, project_id=project_id, limit=limit)

    if _can_view_all(current_user):
        return await list_delivery_verifications(db, limit=limit)

    return await list_delivery_verifications(db, created_by_user_id=current_user.id, limit=limit)


@router.post("/verify", response_model=DeliveryVerificationOut, status_code=201)
async def create_verification(
    payload: DeliveryVerificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        role_required([RoleName.CONTRACTOR, RoleName.PROJECT_MANAGER, RoleName.SUPPLIER])
    ),
):
    """
    Create a tamper-proof delivery verification record.
    
    Rules:
    - Material token must be redeemed
    - Photo fingerprint auto-computed (SHA256)
    - GPS hash auto-computed (SHA256)
    - Starts unverified (pending inspector approval)
    - One verification per token
    """
    try:
        return await create_delivery_verification(
            db,
            payload,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{verification_id}/approve", response_model=DeliveryVerificationOut)
async def approve_verification(
    verification_id: UUID,
    payload: DeliveryVerificationApprove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.MRV_OFFICER, RoleName.ADMIN])),
):
    """
    Approve/lock a delivery verification (one-time, immutable after).
    
    Rules:
    - Verification must exist and be unverified
    - Photo integrity check must pass
    - GPS integrity check must pass
    - Once approved, record is immutable
    - Inspector identity recorded
    """
    try:
        return await approve_delivery_verification(
            db,
            verification_id,
            payload,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{verification_id}", response_model=DeliveryVerificationOut)
async def get_verification(
    verification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch delivery verification by ID."""
    verification = await get_delivery_verification_by_id(db, verification_id)
    if not verification:
        raise HTTPException(
            status_code=404, detail=f"Delivery verification {verification_id} not found"
        )
    return verification


@router.get("/{verification_id}/integrity", response_model=DeliveryIntegrityCheck)
async def check_integrity(
    verification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check if delivery evidence has been tampered with.
    
    Returns:
        Integrity check result:
        - photo_integrity_ok: True if photo hash matches file
        - gps_integrity_ok: True if GPS hash matches coordinates
        - overall_integrity_ok: True if both checks pass
        - message: Human-readable integrity status
        
    Use this endpoint to detect:
    - Photo substitution/editing (hash mismatch)
    - GPS coordinate manipulation (hash mismatch)
    - Timestamp backdating (hash includes time)
    """
    try:
        return await check_delivery_integrity(db, verification_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
