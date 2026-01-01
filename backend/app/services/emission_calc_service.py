"""Emission factor service: creation, activation, and immutability enforcement."""

from decimal import Decimal
from uuid import UUID
from fastapi import HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.emission_factor import EmissionFactor
from app.schemas.emission_factor import EmissionFactorCreate


async def create_emission_factor(
    db: AsyncSession,
    data: EmissionFactorCreate,
    *,
    actor_user_id: UUID,
    actor_email: str,
) -> EmissionFactor:
    """
    Create a new emission factor version.
    
    Rules:
    - No duplicate material_code + version combinations.
    - Factor starts INACTIVE; must be explicitly activated.
    """
    if settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode: emission factor creation is disabled.",
        )

    existing = await db.execute(
        select(EmissionFactor).where(
            EmissionFactor.material_code == data.material_code,
            EmissionFactor.version == data.version,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(
            f"Emission factor {data.material_code} v{data.version} already exists"
        )

    factor = EmissionFactor(
        material_code=data.material_code,
        material_name=data.material_name,
        version=data.version,
        co2e_per_unit=data.co2e_per_unit,
        unit=data.unit,
        source_type=str(data.source_type.value if hasattr(data.source_type, "value") else data.source_type),
        jurisdiction=data.jurisdiction,
        methodology_reference=data.methodology_reference,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
        created_by=actor_email,
        created_by_user_id=actor_user_id,
        is_active=False,  # Start inactive
    )
    # factor_hash is required by schema; compute once and keep immutable.
    factor.factor_hash = factor.generate_hash()

    db.add(factor)
    await db.commit()
    await db.refresh(factor)
    return factor


async def activate_emission_factor(db: AsyncSession, factor_id: str) -> EmissionFactor:
    """
    Activate (lock) an emission factor permanently.
    
    Rules:
    - Only one factor per material_code can be active at a time.
    - Deactivate previous versions automatically.
    - Once active, the factor is immutable at the DB level.
    """
    if settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode: emission factor activation is disabled.",
        )

    factor = await db.get(EmissionFactor, factor_id)
    if not factor:
        raise ValueError(f"Emission factor {factor_id} not found")

    if factor.is_active:
        raise ValueError("Emission factor already active and immutable")

    # Deactivate previous active version (only toggles is_active True->False)
    prev_active = (
        await db.execute(
            select(EmissionFactor).where(
                EmissionFactor.material_code == factor.material_code,
                EmissionFactor.is_active == True,
            )
        )
    ).scalar_one_or_none()
    if prev_active:
        prev_active.is_active = False

    # Activate (hash is already computed and immutable)
    factor.activate()
    
    db.add(factor)
    await db.commit()
    await db.refresh(factor)
    return factor


async def get_active_emission_factor(
    db: AsyncSession, material_code: str
) -> EmissionFactor | None:
    """Get the currently active emission factor for a material."""
    result = await db.execute(
        select(EmissionFactor).where(
            EmissionFactor.material_code == material_code,
            EmissionFactor.is_active == True,
        )
    )
    return result.scalar_one_or_none()


def calculate_co2_with_factor(quantity: Decimal, factor: Decimal) -> Decimal:
    """Deterministic CO₂ calculation using Decimal math (no floating-point drift)."""
    return (quantity * factor).quantize(Decimal("0.000001"))

