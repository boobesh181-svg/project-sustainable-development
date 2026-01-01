"""Anomaly detection engine: orchestrates all rules and persists alerts."""

import uuid
from uuid import UUID
from fastapi import HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.anomaly_alert import AnomalyAlert
from app.models.material_token import MaterialToken
from app.models.delivery_verification import DeliveryVerification
from app.models.project import Project

from app.services.anomaly_rules import (
    rule_excess_quantity,
    rule_distance_anomaly,
    rule_duplicate_photo,
    rule_suspicious_supplier,
)
from app.services.anomaly_explanation import apply_explanation_defaults


async def run_anomaly_checks(
    db: AsyncSession, token_uid: str
) -> list[AnomalyAlert]:
    """
    Run all anomaly detection rules for a material token.
    
    Rules executed:
    1. EXCESS_QUANTITY — token quantity > threshold
    2. DISTANCE_MISMATCH — delivery GPS far from project site
    3. DUPLICATE_PHOTO — photo fingerprint reused
    4. SUSPICIOUS_SUPPLIER — supplier exceeds frequency threshold
    
    Process:
    - Fetch token, project, delivery
    - Execute each rule independently
    - Persist alerts to database (immutable)
    - Return all detected anomalies
    
    Args:
        db: Database session
        token_uid: Material token unique identifier
        
    Returns:
        List of AnomalyAlert records (empty if no anomalies detected)
    """
    alerts: list[AnomalyAlert] = []

    # Fetch material token
    result = await db.execute(
        select(MaterialToken).where(MaterialToken.token_uid == token_uid)
    )
    token = result.scalar_one_or_none()

    if not token:
        # Token not found; cannot run checks
        return []

    # Fetch project (for GPS distance check)
    project_result = await db.execute(
        select(Project).where(Project.id == token.project_id)
    )
    project = project_result.scalar_one_or_none()

    if settings.DEMO_MODE:
        project_name = getattr(project, "name", "") if project is not None else ""
        if not str(project_name).upper().startswith("DEMO"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Demo mode: anomaly checks are allowed only for seeded DEMO records.",
            )

    # Fetch delivery verification (if redeemed)
    delivery_result = await db.execute(
        select(DeliveryVerification).where(
            DeliveryVerification.material_token_id == token.id
        )
    )
    delivery = delivery_result.scalar_one_or_none()

    # ---------------------
    # RULE 1: Excess quantity
    # ---------------------
    alert1 = await rule_excess_quantity(db, token)
    if alert1:
        alerts.append(alert1)

    # ---------------------
    # RULE 2 & 3: Require delivery verification
    # ---------------------
    if delivery and project:
        # RULE 2: Distance anomaly
        alert2 = await rule_distance_anomaly(db, project, delivery)
        if alert2:
            alerts.append(alert2)

        # RULE 3: Duplicate photo
        alert3 = await rule_duplicate_photo(db, delivery)
        if alert3:
            alerts.append(alert3)

    # ---------------------
    # RULE 4: Suspicious supplier
    # ---------------------
    alert4 = await rule_suspicious_supplier(db, token)
    if alert4:
        alerts.append(alert4)

    for alert in alerts:
        apply_explanation_defaults(alert)

        # In DEMO_MODE we run checks in a read-only posture: do not persist
        # alerts (which are immutable audit records). We still return results.
        if settings.DEMO_MODE:
            if getattr(alert, "id", None) is None:
                alert.id = uuid.uuid4()  # type: ignore[assignment]
            continue

        db.add(alert)

    if not settings.DEMO_MODE:
        await db.commit()

        # Refresh alerts to get IDs
        for alert in alerts:
            await db.refresh(alert)

    return alerts


async def get_project_anomalies(
    db: AsyncSession, project_id: UUID, severity: str | None = None
) -> list[AnomalyAlert]:
    """
    Fetch all anomalies for a project, optionally filtered by severity.
    
    Args:
        db: Database session
        project_id: Project UUID
        severity: Optional filter (LOW, MEDIUM, HIGH)
        
    Returns:
        List of AnomalyAlert records ordered by detection time (newest first)
    """
    from app.models.anomaly_alert import AnomalySeverity

    stmt = select(AnomalyAlert).where(AnomalyAlert.project_id == project_id)

    if severity:
        try:
            severity_enum = AnomalySeverity(severity)
            stmt = stmt.where(AnomalyAlert.severity == severity_enum)
        except ValueError:
            raise ValueError(
                f"Invalid severity: {severity}. Must be one of: "
                f"{', '.join([s.value for s in AnomalySeverity])}"
            )

    stmt = stmt.order_by(AnomalyAlert.detected_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_anomaly_by_id(
    db: AsyncSession, anomaly_id: UUID
) -> AnomalyAlert | None:
    """Fetch anomaly alert by ID."""
    result = await db.execute(
        select(AnomalyAlert).where(AnomalyAlert.id == anomaly_id)
    )
    return result.scalar_one_or_none()
