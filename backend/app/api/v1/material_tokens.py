"""Material token routes: issue, redeem, query."""

import os
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.project import Project
from app.models.role import RoleName
from app.models.user import User
from app.models.material_token import MaterialToken
from app.schemas.material import MaterialTokenCreate, MaterialTokenRedeem, MaterialTokenOut
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

    if project_id is not None:
        await _assert_project_access(db, project_id=project_id, current_user=current_user)
        stmt = stmt.where(MaterialToken.project_id == project_id)
    elif not _can_view_all(current_user):
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
):
    """Issue a new material token (unredeemed state)."""
    try:
        return await issue_material_token(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{token_uid}/redeem", response_model=MaterialTokenOut)
async def redeem_token(
    token_uid: str,
    delivery_lat: float = Form(...),
    delivery_lon: float = Form(...),
    supplier_invoice_ref: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
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
        )
        return await redeem_material_token(
            db=db,
            token_uid=token_uid,
            payload=payload,
            delivery_photo_path=filepath,
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
