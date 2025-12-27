"""Audit log service: ONLY place logs are written (append-only enforcement)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.models.audit_log import AuditLog
from app.core.audit_context import (
    get_audit_ip_address,
    get_audit_request_id,
    get_audit_user_agent,
)


async def write_audit_log(
    db: AsyncSession,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    event_payload: dict,
    *,
    actor_user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: uuid.UUID | None = None,
) -> AuditLog:
    """
    Write an audit log entry with hash chaining.
    
    This is the ONLY place logs are written. All critical actions
    call this function to ensure tamper-evident audit trail.
    
    Args:
        db: Database session
        actor: User/system performing action
        action: Action name (TOKEN_ISSUED, DELIVERY_VERIFIED, MRV_APPROVED, etc.)
        entity_type: Type of entity being audited (MaterialToken, DeliveryVerification, etc.)
        entity_id: ID of entity being audited
        event_payload: Dictionary of event data (will be JSON serialized)
        
    Returns:
        Created AuditLog record
        
    Process:
    1. Fetch last audit record (to get prev_hash)
    2. Serialize event_payload as sorted JSON (deterministic)
    3. Compute event_hash = SHA256(event_json)
    4. Compute chain_hash = SHA256(prev_hash + event_hash)
    5. Store in database
    6. No updates/deletes allowed (enforced at DB level)
    """
    # Fetch last audit record to get prev_hash
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    )
    last_audit = result.scalar_one_or_none()

    prev_hash = last_audit.chain_hash if last_audit else None

    # Serialize event data as sorted JSON (deterministic)
    event_data = json.dumps(event_payload, sort_keys=True, default=str)

    # Compute hashes
    event_hash = AuditLog.hash_data(event_data)
    chain_hash = AuditLog.compute_chain(prev_hash, event_hash)

    # Create audit record
    record = AuditLog(
        actor=actor,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        event_data=event_data,
        event_hash=event_hash,
        prev_hash=prev_hash,
        chain_hash=chain_hash,
        ip_address=ip_address or get_audit_ip_address(),
        user_agent=user_agent or get_audit_user_agent(),
        request_id=request_id or get_audit_request_id(),
    )

    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_audit_logs(
    db: AsyncSession, limit: int = 100, actor: str | None = None, action: str | None = None
) -> list[AuditLog]:
    """
    Fetch audit logs (read-only, for visibility).
    
    Args:
        db: Database session
        limit: Maximum number of records to return
        actor: Optional filter by actor
        action: Optional filter by action
        
    Returns:
        List of AuditLog records (newest first)
    """
    stmt = select(AuditLog)

    if actor:
        stmt = stmt.where(AuditLog.actor == actor)

    if action:
        stmt = stmt.where(AuditLog.action == action)

    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def verify_audit_chain(db: AsyncSession) -> dict:
    """
    Verify integrity of audit chain (detect tampering).
    
    Returns:
        {
            "chain_valid": bool,
            "total_records": int,
            "first_break_at_record": int (or None if valid),
            "message": str
        }
    """
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.asc(), AuditLog.id.asc()))
    logs = list(result.scalars().all())

    if not logs:
        return {
            "chain_valid": True,
            "total_records": 0,
            "first_break_at_record": None,
            "message": "Audit log is empty",
        }

    # Verify first record has no prev_hash
    if logs[0].prev_hash is not None:
        return {
            "chain_valid": False,
            "total_records": len(logs),
            "first_break_at_record": 0,
            "message": "First record has non-null prev_hash (tampered)",
        }

    # Verify each record's chain
    for i, log in enumerate(logs):
        is_valid = AuditLog.verify_chain(log.prev_hash, log.event_hash, log.chain_hash)
        if not is_valid:
            return {
                "chain_valid": False,
                "total_records": len(logs),
                "first_break_at_record": i,
                "message": f"Chain break at record {i}: computed hash != stored hash (TAMPERING DETECTED)",
            }

        # Verify prev_hash matches previous record's chain_hash
        if i > 0:
            if log.prev_hash != logs[i - 1].chain_hash:
                return {
                    "chain_valid": False,
                    "total_records": len(logs),
                    "first_break_at_record": i,
                    "message": f"Chain break at record {i}: prev_hash doesn't match previous chain_hash (RECORD DELETED OR REORDERED)",
                }

    return {
        "chain_valid": True,
        "total_records": len(logs),
        "first_break_at_record": None,
        "message": "Audit chain is valid (no tampering detected)",
    }
