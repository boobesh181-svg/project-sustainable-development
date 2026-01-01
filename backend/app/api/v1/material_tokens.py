"""Material token routes: issue, redeem, query."""

import os
import uuid
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, role_required
from app.models.project import Project
from app.models.role import RoleName
from app.models.user import User
from app.models.material_token import MaterialToken
from app.models.evidence import Evidence
from app.models.supplier import Supplier
from app.schemas.material import MaterialTokenCreate, MaterialTokenRedeem, MaterialTokenOut
from app.schemas.evidence import EvidenceOut
from app.services.material_service import (
    issue_material_token,
    redeem_material_token,
    get_token_by_uid,
)

# Create uploads directory
UPLOAD_DIR = "uploads/material_evidence"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/api/v1/material-tokens", tags=["Material Tokens"])


def _can_view_all(current_user: User) -> bool:
    if current_user.role is None:
        return False
    return current_user.role.name in {RoleName.ADMIN, RoleName.MRV_OFFICER}


def _supplier_scope_name(current_user: User) -> str | None:
    if current_user.role is None or current_user.role.name != RoleName.SUPPLIER:
        return None
    if getattr(current_user, "supplier", None) is not None:
        return current_user.supplier.name
    return None


async def _assert_project_access(
    db: AsyncSession, *, project_id: UUID, current_user: User
) -> None:
    if _can_view_all(current_user):
        return

    result = await db.execute(
        select(Project.id).where(Project.id == project_id, Project.created_by == current_user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not authorized for this project")


@router.get("/", response_model=list[MaterialTokenOut])
async def list_tokens(
    project_id: UUID | None = Query(None, description="Optional filter: only tokens for a project"),
    redeemed_only: bool = Query(False, description="If true, return only redeemed tokens"),
    limit: int = Query(200, ge=1, le=500, description="Max tokens to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List material tokens (read-only visibility for dashboard/screens)."""
    stmt = select(MaterialToken).order_by(MaterialToken.issued_at.desc()).limit(limit)

    # Supplier-scoped visibility: never allow suppliers to see other suppliers' tokens.
    supplier_name = _supplier_scope_name(current_user)
    if supplier_name is not None:
        stmt = stmt.where(MaterialToken.supplier_name == supplier_name)

    if project_id is not None:
        await _assert_project_access(db, project_id=project_id, current_user=current_user)
        stmt = stmt.where(MaterialToken.project_id == project_id)
    elif not _can_view_all(current_user) and supplier_name is None:
        stmt = (
            stmt.join(Project, Project.id == MaterialToken.project_id)
            .where(Project.created_by == current_user.id)
        )

    if redeemed_only:
        stmt = stmt.where(MaterialToken.redeemed == True)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/", response_model=MaterialTokenOut, status_code=201)
async def issue_token(
    payload: MaterialTokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.PROJECT_MANAGER, RoleName.CONTRACTOR])),
):
    """Issue a new material token (unredeemed state)."""
    try:
        return await issue_material_token(
            db,
            payload,
            actor_email=current_user.email,
            actor_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{token_uid}/redeem", response_model=MaterialTokenOut)
async def redeem_token(
    token_uid: str,
    delivery_lat: float = Form(...),
    delivery_lon: float = Form(...),
    supplier_invoice_ref: str = Form(...),
    batch_id: str | None = Form(None),
    delivery_timestamp: datetime | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.SUPPLIER])),
):
    """
    Redeem a material token with delivery evidence.
    
    Rules:
    - Token must be unredeemed
    - Photo evidence is mandatory
    - GPS location is mandatory
    - Invoice reference is mandatory
    - Once redeemed, token is immutable
    - Second redemption is blocked
    """
    # Enforce supplier scope before accepting any submission.
    supplier_name = _supplier_scope_name(current_user)
    if supplier_name is None:
        raise HTTPException(status_code=403, detail="Supplier scope not configured")

    token = await get_token_by_uid(db, token_uid)
    if token is None:
        raise HTTPException(status_code=404, detail=f"Token {token_uid} not found")
    if token.supplier_name != supplier_name:
        raise HTTPException(status_code=403, detail="Not authorized for this supplier")

    # Validate file upload
    if not file.filename:
        raise HTTPException(status_code=400, detail="Photo file is required")

    # Save photo evidence
    filename = f"{token_uid}_{uuid.uuid4()}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    try:
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

    # Redeem token with evidence
    try:
        payload = MaterialTokenRedeem(
            delivery_lat=delivery_lat,
            delivery_lon=delivery_lon,
            supplier_invoice_ref=supplier_invoice_ref,
            batch_id=batch_id,
            delivery_timestamp=delivery_timestamp,
        )
        # Record who submitted in the audit log.
        return await redeem_material_token(
            db=db,
            token_uid=token_uid,
            payload=payload,
            delivery_photo_path=filepath,
            actor=current_user.email,
            actor_user_id=current_user.id,
            supplier_id=current_user.supplier.id if getattr(current_user, "supplier", None) is not None else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{token_uid}", response_model=MaterialTokenOut)
async def get_token(
    token_uid: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch token details by UID."""
    token = await get_token_by_uid(db, token_uid)
    if not token:
        raise HTTPException(status_code=404, detail=f"Token {token_uid} not found")
    return token


@router.get("/{token_uid}/evidence", response_model=list[EvidenceOut])
async def list_token_evidence(
    token_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = await get_token_by_uid(db, token_uid)
    if token is None:
        raise HTTPException(status_code=404, detail=f"Token {token_uid} not found")

    supplier_name = _supplier_scope_name(current_user)
    if supplier_name is not None and token.supplier_name != supplier_name:
        raise HTTPException(status_code=403, detail="Not authorized for this supplier")

    # Non-privileged users must have project access as well.
    if not _can_view_all(current_user) and supplier_name is None:
        await _assert_project_access(db, project_id=token.project_id, current_user=current_user)

    result = await db.execute(
        select(Evidence)
        .where(Evidence.material_token_id == token.id)
        .order_by(Evidence.created_at.desc())
    )
    return list(result.scalars().all())
