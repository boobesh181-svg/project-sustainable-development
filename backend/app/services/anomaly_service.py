"""Anomaly detection and flagging service."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.anomaly_alert import AnomalyAlert, AnomalyStatus


async def get_open_anomalies(db: AsyncSession, project_id: str | None = None) -> list[AnomalyAlert]:
    """Fetch all open (unflagged) anomalies, optionally filtered by project."""
    stmt = select(AnomalyAlert).where(AnomalyAlert.status == AnomalyStatus.OPEN)
    if project_id:
        stmt = stmt.where(AnomalyAlert.project_id == project_id)
    result = await db.execute(stmt.order_by(AnomalyAlert.created_at.desc()))
    return result.scalars().all()


async def count_anomalies(db: AsyncSession, project_id: str | None = None) -> int:
    """Count open anomalies."""
    stmt = select(func.count(AnomalyAlert.id)).where(AnomalyAlert.status == AnomalyStatus.OPEN)
    if project_id:
        stmt = stmt.where(AnomalyAlert.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalar() or 0


async def flag_anomaly(db: AsyncSession, anomaly_id: str, resolved_by: str) -> AnomalyAlert:
    """Mark an anomaly as resolved."""
    result = await db.execute(
        select(AnomalyAlert).where(AnomalyAlert.id == anomaly_id)
    )
    anomaly = result.scalar_one_or_none()
    if not anomaly:
        raise ValueError(f"Anomaly {anomaly_id} not found")
    
    anomaly.status = AnomalyStatus.RESOLVED
    anomaly.resolved_by = resolved_by
    await db.commit()
    await db.refresh(anomaly)
    return anomaly
