"""Emission factor service: creation, activation, and immutability enforcement."""

from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.emission_factor import EmissionFactor
from app.schemas.emission_factor import EmissionFactorCreate


async def create_emission_factor(
    db: AsyncSession, data: EmissionFactorCreate
) -> EmissionFactor:
    """
    Create a new emission factor version.
    
    Rules:
    - No duplicate material_code + version combinations.
    - Factor starts INACTIVE; must be explicitly activated.
    """
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
        valid_from=data.valid_from,
        created_by=data.created_by,
        is_active=False,  # Start inactive
    )

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
    factor = await db.get(EmissionFactor, factor_id)
    if not factor:
        raise ValueError(f"Emission factor {factor_id} not found")

    if factor.is_active:
        raise ValueError("Emission factor already active and immutable")

    # Deactivate previous active versions
    await db.execute(
        select(EmissionFactor)
        .where(
            EmissionFactor.material_code == factor.material_code,
            EmissionFactor.is_active == True,
        )
    )
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

    # Activate and hash-lock
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

