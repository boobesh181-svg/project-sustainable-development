"""Audit logs routes: read-only access for audit trail visibility."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.api.deps import get_db, role_required
from app.models.role import RoleName
from app.models.user import User
from app.services.audit_log_service import (
    get_audit_logs,
    verify_audit_chain,
)


# Response schemas
class AuditLogOut(BaseModel):
    """Audit log entry response."""
    id: str
    actor: str
    actor_user_id: str | None = None
    action: str
    entity_type: str
    entity_id: str
    event_hash: str
    prev_hash: str | None
    chain_hash: str
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ChainVerificationResult(BaseModel):
    """Audit chain verification result (tamper detection)."""
    chain_valid: bool
    total_records: int
    first_break_at_record: int | None
    message: str


router = APIRouter(prefix="/api/v1/audit-logs", tags=["Audit Logs"])


@router.get("/", response_model=list[AuditLogOut])
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    actor: str | None = Query(None, description="Filter by actor (user/system)"),
    action: str | None = Query(None, description="Filter by action (TOKEN_ISSUED, MRV_APPROVED, etc.)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.MRV_OFFICER])),
):
    """
    Fetch audit logs (read-only, newest first).
    
    Optional Filters:
    - actor: Filter by user/system performing action
    - action: Filter by action type (TOKEN_ISSUED, DELIVERY_VERIFIED, MRV_APPROVED, etc.)
    
    Use for:
    - Audit trail visibility (regulatory compliance)
    - Incident investigation
    - Action traceability
    """
    try:
        logs = await get_audit_logs(db, limit=limit, actor=actor, action=action)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit logs: {str(e)}")


@router.get("/verify-chain", response_model=ChainVerificationResult)
async def verify_chain(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.MRV_OFFICER])),
):
    """
    Verify integrity of audit chain (detect tampering).
    
    Checks:
    - First record has no prev_hash
    - Each record's chain_hash matches computed hash
    - prev_hash of each record matches previous record's chain_hash
    - No gaps or reorderings
    
    Returns:
    - chain_valid: True if no tampering detected
    - total_records: Number of audit records
    - first_break_at_record: Index of first invalid record (if tampering detected)
    - message: Human-readable status
    
    Use for:
    - Compliance audits (proof of tamper-evidence)
    - Incident response (validate evidence chain)
    - Periodic integrity checks
    """
    try:
        result = await verify_audit_chain(db)
        return ChainVerificationResult(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chain verification failed: {str(e)}")
