"""
Carbon credit calculation and issuance logic
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.mrv.models import CarbonLedger, CarbonCreditIssuance
from app.mrv.carbon import calculate_carbon_credits


# Default carbon credit rate (USD per tonne CO2)
DEFAULT_CREDIT_RATE_USD_PER_TON = 50.0


async def calculate_project_credits(
    db: AsyncSession, 
    project_id: str, 
    credit_rate_usd_per_ton: float = DEFAULT_CREDIT_RATE_USD_PER_TON
) -> Dict[str, Any]:
    """
    Calculate carbon credits for a project based on CO2 ledger
    
    Args:
        db: Database session
        project_id: Project ID
        credit_rate_usd_per_ton: Credit rate in USD per tonne
    
    Returns:
        Dictionary with credit calculation results
    """
    # Get total CO2 from carbon ledger for this project
    ledger_result = await db.execute(
        select(func.sum(CarbonLedger.co2_kg)).where(CarbonLedger.project_id == project_id)
    )
    total_co2_kg = ledger_result.scalar() or 0.0
    total_co2_tonnes = total_co2_kg / 1000.0
    
    # Calculate credits
    credit_calculation = calculate_carbon_credits(total_co2_tonnes, credit_rate_usd_per_ton)
    
    # Get existing credit issuances for this project
    existing_issuances_result = await db.execute(
        select(func.sum(CarbonCreditIssuance.credits_t))
        .where(CarbonCreditIssuance.project_id == project_id)
        .where(CarbonCreditIssuance.status.in_(["issued", "pending"]))
    )
    existing_credits = existing_issuances_result.scalar() or 0.0
    
    # Available credits
    available_credits = total_co2_tonnes - existing_credits
    
    return {
        "project_id": project_id,
        "total_co2_kg": total_co2_kg,
        "total_co2_tonnes": total_co2_tonnes,
        "existing_credits_issued": existing_credits,
        "available_credits": available_credits,
        "credit_rate_usd_per_ton": credit_rate_usd_per_ton,
        "available_credit_value_usd": available_credits * credit_rate_usd_per_ton,
        "calculation": credit_calculation
    }


async def issue_carbon_credits(
    db: AsyncSession,
    project_id: str,
    credits_to_issue: float,
    credit_rate_usd_per_ton: float = DEFAULT_CREDIT_RATE_USD_PER_TON,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Issue carbon credits for a project
    
    Args:
        db: Database session
        project_id: Project ID
        credits_to_issue: Amount of credits to issue (tonnes CO2)
        credit_rate_usd_per_ton: Credit rate in USD per tonne
        notes: Optional notes
    
    Returns:
        Dictionary with issuance results
    """
    # Check available credits
    credit_calculation = await calculate_project_credits(db, project_id, credit_rate_usd_per_ton)
    
    if credits_to_issue > credit_calculation["available_credits"]:
        raise ValueError(
            f"Cannot issue {credits_to_issue} credits. "
            f"Only {credit_calculation['available_credits']} available."
        )
    
    # Create credit issuance
    credit_value_usd = credits_to_issue * credit_rate_usd_per_ton
    
    issuance = CarbonCreditIssuance(
        project_id=project_id,
        credits_t=credits_to_issue,
        value_usd=credit_value_usd,
        credit_rate_usd_per_ton=credit_rate_usd_per_ton,
        status="pending",  # Start as pending, can be approved later
        notes=notes,
        calculation_details=credit_calculation
    )
    
    db.add(issuance)
    await db.commit()
    
    return {
        "issuance_id": issuance.id,
        "project_id": project_id,
        "credits_issued": credits_to_issue,
        "credit_value_usd": credit_value_usd,
        "credit_rate_usd_per_ton": credit_rate_usd_per_ton,
        "status": issuance.status,
        "issued_at": issuance.issued_at.isoformat()
    }


async def get_project_credit_summary(
    db: AsyncSession,
    project_id: str
) -> Dict[str, Any]:
    """
    Get credit summary for a project
    
    Args:
        db: Database session
        project_id: Project ID
    
    Returns:
        Dictionary with credit summary
    """
    # Get all credit issuances for project
    issuances_result = await db.execute(
        select(CarbonCreditIssuance).where(CarbonCreditIssuance.project_id == project_id)
    )
    issuances = issuances_result.scalars().all()
    
    # Calculate totals by status
    total_issued = sum(i.credits_t for i in issuances if i.status == "issued")
    total_pending = sum(i.credits_t for i in issuances if i.status == "pending")
    total_retired = sum(i.credits_t for i in issuances if i.status == "retired")
    total_value = sum(i.value_usd for i in issuances if i.status in ["issued", "pending"])
    
    # Get CO2 calculation
    credit_calculation = await calculate_project_credits(db, project_id)
    
    return {
        "project_id": project_id,
        "total_co2_tonnes": credit_calculation["total_co2_tonnes"],
        "credits_issued": total_issued,
        "credits_pending": total_pending,
        "credits_retired": total_retired,
        "credits_available": credit_calculation["available_credits"],
        "total_credit_value_usd": total_value,
        "issuances": [
            {
                "id": i.id,
                "credits_t": i.credits_t,
                "value_usd": i.value_usd,
                "status": i.status,
                "issued_at": i.issued_at.isoformat(),
                "retired_at": i.retired_at.isoformat() if i.retired_at else None,
                "notes": i.notes
            }
            for i in issuances
        ]
    }


async def approve_credit_issuance(
    db: AsyncSession,
    issuance_id: str
) -> Dict[str, Any]:
    """
    Approve a pending credit issuance
    
    Args:
        db: Database session
        issuance_id: Credit issuance ID
    
    Returns:
        Dictionary with approval results
    """
    # Get issuance
    issuance_result = await db.execute(
        select(CarbonCreditIssuance).where(CarbonCreditIssuance.id == issuance_id)
    )
    issuance = issuance_result.scalar_one_or_none()
    
    if not issuance:
        raise ValueError("Credit issuance not found")
    
    if issuance.status != "pending":
        raise ValueError(f"Cannot approve issuance with status: {issuance.status}")
    
    # Update status
    issuance.status = "issued"
    await db.commit()
    
    return {
        "issuance_id": issuance.id,
        "project_id": issuance.project_id,
        "credits_t": issuance.credits_t,
        "status": issuance.status,
        "approved_at": datetime.now(timezone.utc).isoformat()
    }


async def retire_credit_issuance(
    db: AsyncSession,
    issuance_id: str,
    retirement_notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retire a credit issuance
    
    Args:
        db: Database session
        issuance_id: Credit issuance ID
        retirement_notes: Optional retirement notes
    
    Returns:
        Dictionary with retirement results
    """
    # Get issuance
    issuance_result = await db.execute(
        select(CarbonCreditIssuance).where(CarbonCreditIssuance.id == issuance_id)
    )
    issuance = issuance_result.scalar_one_or_none()
    
    if not issuance:
        raise ValueError("Credit issuance not found")
    
    if issuance.status != "issued":
        raise ValueError(f"Cannot retire issuance with status: {issuance.status}")
    
    # Update status and retirement date
    issuance.status = "retired"
    issuance.retired_at = datetime.now(timezone.utc)
    if retirement_notes:
        issuance.notes = f"{issuance.notes or ''}\n\nRetirement notes: {retirement_notes}"
    
    await db.commit()
    
    return {
        "issuance_id": issuance.id,
        "project_id": issuance.project_id,
        "credits_t": issuance.credits_t,
        "status": issuance.status,
        "retired_at": issuance.retired_at.isoformat()
    }
