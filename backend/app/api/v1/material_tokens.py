"""Material token routes: issue, redeem, query."""

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
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
