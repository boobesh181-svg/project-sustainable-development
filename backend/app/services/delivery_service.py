"""Delivery verification service: tamper-proof evidence creation and validation."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.delivery_verification import (
    DeliveryVerification,
    compute_photo_fingerprint,
    compute_gps_hash,
)
from app.models.material_token import MaterialToken
from app.models.project import Project
from app.schemas.delivery import (
    DeliveryVerificationCreate,
    DeliveryVerificationApprove,
    DeliveryIntegrityCheck,
)
from app.services.audit_log_service import write_audit_log


async def create_delivery_verification(
    db: AsyncSession,
    data: DeliveryVerificationCreate,
    *,
    actor_user_id: UUID,
    actor_email: str,
) -> DeliveryVerification:
    """
    Create a tamper-proof delivery verification record.
    
    Rules:
    - Material token must exist and be redeemed
    - Photo fingerprint auto-computed (SHA256)
    - GPS hash auto-computed (SHA256)
    - Verification starts unverified (pending inspector approval)
    - One verification per material token (unique constraint)
    """
    # Validate material token exists and is redeemed
    result = await db.execute(
        select(MaterialToken).where(MaterialToken.id == data.material_token_id)
    )
    token = result.scalar_one_or_none()

    if not token:
        raise ValueError(f"Material token {data.material_token_id} not found")

    if not token.redeemed:
        raise ValueError("Material token must be redeemed before creating verification")

    # Check if verification already exists
    existing = await db.execute(
        select(DeliveryVerification).where(
            DeliveryVerification.material_token_id == data.material_token_id
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Delivery verification already exists for this token")

    # Compute photo fingerprint (tamper detection)
    try:
        photo_fingerprint = compute_photo_fingerprint(data.photo_path)
    except ValueError as e:
        raise ValueError(f"Photo fingerprint computation failed: {str(e)}")

    # Compute GPS hash (coordinate integrity)
    from datetime import datetime, timezone
    verified_at = datetime.now(timezone.utc)
    gps_hash = compute_gps_hash(data.delivery_lat, data.delivery_lon, verified_at)

    # Create verification record
    verification = DeliveryVerification(
        material_token_id=data.material_token_id,
        photo_path=data.photo_path,
        photo_fingerprint=photo_fingerprint,
        delivery_lat=data.delivery_lat,
        delivery_lon=data.delivery_lon,
        gps_hash=gps_hash,
        verified_at=verified_at,
        verified_by="system",  # Updated when inspector approves
        created_by_user_id=actor_user_id,
        is_verified=False,
    )

    db.add(verification)
    await db.commit()
    await db.refresh(verification)

    # Log to audit trail
    await write_audit_log(
        db=db,
        actor=actor_email,
        actor_user_id=actor_user_id,
        action="DELIVERY_VERIFICATION_CREATED",
        entity_type="DeliveryVerification",
        entity_id=str(verification.id),
        event_payload={
            "material_token_id": str(data.material_token_id),
            "photo_fingerprint": photo_fingerprint,
            "delivery_lat": data.delivery_lat,
            "delivery_lon": data.delivery_lon,
            "gps_hash": gps_hash,
        },
    )

    return verification


async def approve_delivery_verification(
    db: AsyncSession,
    verification_id: UUID,
    data: DeliveryVerificationApprove,
    *,
    actor_user_id: UUID,
    actor_email: str,
) -> DeliveryVerification:
    """
    Approve/lock a delivery verification (one-time, immutable after).
    
    Rules:
    - Verification must exist and be unverified
    - Photo integrity check must pass
    - GPS integrity check must pass
    - Once approved, record is immutable
    - Inspector identity recorded
    """
    result = await db.execute(
        select(DeliveryVerification).where(DeliveryVerification.id == verification_id)
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise ValueError(f"Delivery verification {verification_id} not found")

    if verification.is_verified:
        raise ValueError("Delivery already verified; cannot verify twice")

    # Lock verification (integrity checks inside)
    try:
        verification.lock_verification(
            verified_by=actor_email,
            notes=data.verification_notes,
        )
    except ValueError as e:
        raise ValueError(f"Verification failed: {str(e)}")

    verification.verified_by_user_id = actor_user_id

    db.add(verification)
    await db.commit()
    await db.refresh(verification)

    # Log to audit trail
    await write_audit_log(
        db=db,
        actor=actor_email,
        actor_user_id=actor_user_id,
        action="DELIVERY_VERIFIED",
        entity_type="DeliveryVerification",
        entity_id=str(verification.id),
        event_payload={
            "photo_fingerprint": verification.photo_fingerprint,
            "gps_hash": verification.gps_hash,
            "delivery_lat": verification.delivery_lat,
            "delivery_lon": verification.delivery_lon,
            "notes": data.verification_notes,
        },
    )

    return verification


async def get_delivery_verification_by_id(
    db: AsyncSession, verification_id: UUID
) -> DeliveryVerification | None:
    """Fetch delivery verification by ID."""
    result = await db.execute(
        select(DeliveryVerification).where(DeliveryVerification.id == verification_id)
    )
    return result.scalar_one_or_none()


async def get_verification_by_token(
    db: AsyncSession, material_token_id: UUID
) -> DeliveryVerification | None:
    """Fetch delivery verification by material token ID."""
    result = await db.execute(
        select(DeliveryVerification).where(
            DeliveryVerification.material_token_id == material_token_id
        )
    )
    return result.scalar_one_or_none()


async def list_delivery_verifications(
    db: AsyncSession,
    *,
    project_id: UUID | None = None,
    created_by_user_id: UUID | None = None,
    limit: int = 200,
) -> list[DeliveryVerification]:
    """List delivery verifications, optionally filtered by project and/or project owner."""
    stmt = (
        select(DeliveryVerification)
        .join(MaterialToken, MaterialToken.id == DeliveryVerification.material_token_id)
        .join(Project, Project.id == MaterialToken.project_id)
        .order_by(DeliveryVerification.verified_at.desc())
        .limit(limit)
    )

    if project_id is not None:
        stmt = stmt.where(Project.id == project_id)

    if created_by_user_id is not None:
        stmt = stmt.where(Project.created_by == created_by_user_id)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def check_delivery_integrity(
    db: AsyncSession, verification_id: UUID
) -> DeliveryIntegrityCheck:
    """
    Check if delivery evidence has been tampered with.
    
    Returns:
        Integrity check result (photo + GPS validation)
    """
    verification = await get_delivery_verification_by_id(db, verification_id)

    if not verification:
        raise ValueError(f"Delivery verification {verification_id} not found")

    photo_ok = verification.verify_photo_integrity()
    gps_ok = verification.verify_gps_integrity()
    overall_ok = photo_ok and gps_ok

    if overall_ok:
        message = "Delivery evidence integrity verified; no tampering detected"
    else:
        issues = []
        if not photo_ok:
            issues.append("photo tampered")
        if not gps_ok:
            issues.append("GPS altered")
        message = f"TAMPERING DETECTED: {', '.join(issues)}"

    return DeliveryIntegrityCheck(
        photo_integrity_ok=photo_ok,
        gps_integrity_ok=gps_ok,
        overall_integrity_ok=overall_ok,
        message=message,
    )
