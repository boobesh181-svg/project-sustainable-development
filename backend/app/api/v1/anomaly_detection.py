"""Anomaly detection routes: fraud detection and audit visibility."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from app.api.deps import get_db
from app.services.anomaly_engine import (
    run_anomaly_checks,
    get_project_anomalies,
    get_anomaly_by_id,
)
from app.services.anomaly_explanation import build_anomaly_explanation


# Response schemas
class AnomalyAlertOut(BaseModel):
    """Anomaly alert response."""
    id: UUID
    project_id: UUID
    token_uid: str | None
    rule_id: str
    rule_code: str
    severity: str
    description: str
    explanation: str
    requires_action: bool
    numeric_value: float | None
    threshold: float | None
    detected_at: str
    
    model_config = ConfigDict(from_attributes=True)


class AnomalyCheckResult(BaseModel):
    """Result of running anomaly checks on a token."""
    token_uid: str
    anomalies_detected: int
    details: list[dict]


router = APIRouter(prefix="/api/v1/anomalies", tags=["Anomaly Detection"])


def _serialize_alert(alert) -> AnomalyAlertOut:
    meta = build_anomaly_explanation(alert)
    return AnomalyAlertOut(
        id=alert.id,
        project_id=alert.project_id,
        token_uid=alert.token_uid,
        rule_id=alert.rule_id or meta.rule_id,
        rule_code=alert.rule_code,
        severity=alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
        description=alert.description,
        explanation=alert.explanation or meta.explanation,
        requires_action=bool(getattr(alert, "requires_action", False) or meta.requires_action),
        numeric_value=float(alert.numeric_value) if alert.numeric_value is not None else None,
        threshold=float(alert.threshold) if alert.threshold is not None else None,
        detected_at=alert.detected_at.isoformat() if hasattr(alert.detected_at, "isoformat") else str(alert.detected_at),
    )


@router.post("/run/{token_uid}", response_model=AnomalyCheckResult)
async def run_checks(
    token_uid: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Run all anomaly detection rules for a material token.
    
    Rules executed:
    1. EXCESS_QUANTITY — token quantity > 1000 units
    2. DISTANCE_MISMATCH — delivery GPS > 2km from project site
    3. DUPLICATE_PHOTO — photo fingerprint reused across tokens
    4. SUSPICIOUS_SUPPLIER — supplier > 10 tokens per day
    
    Process:
    - Fetch token, project, delivery verification
    - Execute rules independently
    - Persist alerts (immutable audit records)
    - Return summary with detected anomalies
    
    Use after:
    - Material token redemption (to validate delivery)
    - Periodic audits (batch check all tokens)
    """
    try:
        alerts = await run_anomaly_checks(db, token_uid)
        
        return AnomalyCheckResult(
            token_uid=token_uid,
            anomalies_detected=len(alerts),
            details=[
                {
                    "id": str(alert.id),
                    "rule": alert.rule_code,
                    "severity": alert.severity.value,
                    "description": alert.description,
                    "numeric_value": float(alert.numeric_value) if alert.numeric_value else None,
                    "threshold": float(alert.threshold) if alert.threshold else None,
                }
                for alert in alerts
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anomaly check failed: {str(e)}")


@router.get("/projects/{project_id}", response_model=list[AnomalyAlertOut])
async def get_project_anomaly_alerts(
    project_id: UUID,
    severity: str | None = Query(
        None, description="Filter by severity: LOW, MEDIUM, HIGH"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch all anomaly alerts for a project (newest first).
    
    Optional Filters:
    - severity: LOW, MEDIUM, HIGH
    
    Use for:
    - Dashboard anomaly timeline
    - Project audit reports
    - Fraud investigation
    """
    try:
        alerts = await get_project_anomalies(db, project_id, severity)
        return [_serialize_alert(a) for a in alerts]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{anomaly_id}", response_model=AnomalyAlertOut)
async def get_anomaly_details(
    anomaly_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch anomaly alert by ID (full details)."""
    alert = await get_anomaly_by_id(db, anomaly_id)
    if not alert:
        raise HTTPException(
            status_code=404, detail=f"Anomaly alert {anomaly_id} not found"
        )
    return _serialize_alert(alert)
