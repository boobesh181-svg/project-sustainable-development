"""Emission factor routes: create, activate, list.

Governance rules:
- Only admins can create/activate factors.
- Actor identity is derived from JWT (client cannot spoof created_by).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, role_required
from app.models.emission_factor import EmissionFactor
from app.schemas.emission_factor import EmissionFactorCreate, EmissionFactorOut, EmissionFactorActivate
from app.services.emission_calc_service import (
    create_emission_factor,
    activate_emission_factor,
    get_active_emission_factor,
)
from app.models.role import RoleName
from app.models.user import User

router = APIRouter(prefix="/api/v1/emission-factors", tags=["Emission Factors"])


@router.post("/", response_model=EmissionFactorOut, status_code=201)
async def create_factor(
    payload: EmissionFactorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN])),
):
    """Create a new emission factor version (starts INACTIVE)."""
    try:
        return await create_emission_factor(
            db,
            payload,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{factor_id}/activate", response_model=EmissionFactorOut)
async def activate_factor(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN])),
):
    """
    Activate (lock) an emission factor permanently.
    
    Once active:
    - Factor is immutable (no edits, no deletes)
    - Previous versions auto-deactivated
    - Hash-locked for reproducibility
    """
    try:
        return await activate_emission_factor(db, factor_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/by-material/{material_code}", response_model=EmissionFactorOut | None)
async def get_active_by_material(
    material_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the currently active emission factor for a material."""
    factor = await get_active_emission_factor(db, material_code)
    if not factor:
        raise HTTPException(status_code=404, detail=f"No active factor for {material_code}")
    return factor
