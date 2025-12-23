"""Whistleblower case management service."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.whistleblower import Whistleblower, WhistleblowerStatus


async def get_open_cases(db: AsyncSession, project_id: str | None = None) -> list[Whistleblower]:
    """Fetch all open whistleblower cases."""
    stmt = select(Whistleblower).where(Whistleblower.status == WhistleblowerStatus.OPEN)
    if project_id:
        stmt = stmt.where(Whistleblower.project_id == project_id)
    result = await db.execute(stmt.order_by(Whistleblower.created_at.desc()))
    return result.scalars().all()


async def close_case(
    db: AsyncSession, case_id: str, resolution: str, closed_by: str
) -> Whistleblower:
    """Close a whistleblower case with resolution."""
    result = await db.execute(
        select(Whistleblower).where(Whistleblower.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found")
    
    case.status = WhistleblowerStatus.RESOLVED
    case.resolution = resolution
    case.closed_by = closed_by
    await db.commit()
    await db.refresh(case)
    return case
