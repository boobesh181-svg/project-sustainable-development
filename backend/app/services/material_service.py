"""Material token service: issuance, redemption, and one-time enforcement."""

from uuid import UUID
from fastapi import HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.material_token import MaterialToken
from app.schemas.material import MaterialTokenCreate, MaterialTokenRedeem
from app.models.supplier import Supplier
from app.services.audit_log_service import write_audit_log


async def issue_material_token(
    db: AsyncSession,
    data: MaterialTokenCreate,
    *,
    actor_email: str,
    actor_user_id: UUID | None,
) -> MaterialToken:
    """
    Issue a new material token (unredeemed state).
    
    Rules:
    - Token starts unredeemed
    - Quantity locked at issuance
    - Used to authorize one delivery
    - Action is logged to audit trail
    """
    if settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode: material token issuance is disabled.",
        )

    token = MaterialToken(
        project_id=data.project_id,
        material_code=data.material_code,
        material_name=data.material_name,
        quantity=data.quantity,
        unit=data.unit,
        supplier_name=data.supplier_name,
        supplier_id=data.supplier_id,
        issued_by=actor_email,
        redeemed=False,
    )

    db.add(token)
    await db.commit()
    await db.refresh(token)

    # Log to audit trail
    await write_audit_log(
        db=db,
        actor=actor_email,
        actor_user_id=actor_user_id,
        action="TOKEN_ISSUED",
        entity_type="MaterialToken",
        entity_id=token.token_uid,
        event_payload={
            "project_id": str(data.project_id),
            "material_code": data.material_code,
            "material_name": data.material_name,
            "quantity": float(data.quantity),
            "unit": data.unit,
            "supplier_name": data.supplier_name,
            "supplier_id": str(data.supplier_id) if data.supplier_id else None,
            "token_uid": token.token_uid,
        },
    )

    return token


async def redeem_material_token(
    db: AsyncSession,
    token_uid: str,
    payload: MaterialTokenRedeem,
    delivery_photo_path: str,
    *,
    actor: str = "system",
    actor_user_id: UUID | None = None,
    supplier_id: UUID | None = None,
) -> MaterialToken:
    """
    Redeem a material token with delivery evidence (one-time only).
    
    Rules:
    - Token must exist and be unredeemed
    - Photo evidence is mandatory
    - GPS location is mandatory
    - Invoice reference is mandatory
    - Once redeemed, token is immutable
    - Second redemption blocked
    - Action is logged to audit trail
    """
    if settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode: material token redemption is disabled.",
        )

    result = await db.execute(
        select(MaterialToken).where(MaterialToken.token_uid == token_uid)
    )
    token = result.scalar_one_or_none()

    if not token:
        raise ValueError(f"Token {token_uid} not found")

    if token.redeemed:
        raise ValueError("Token already redeemed; cannot redeem twice")

    # Store evidence (immutable after this point)
    token.delivery_photo_path = delivery_photo_path
    token.delivery_lat = payload.delivery_lat
    token.delivery_lon = payload.delivery_lon
    token.supplier_invoice_ref = payload.supplier_invoice_ref
    token.batch_id = payload.batch_id
    token.supplier_id = supplier_id or token.supplier_id
    token.delivery_timestamp = payload.delivery_timestamp

    # If the supplier did not provide a timestamp, use system receipt time.
    if token.delivery_timestamp is None:
        from datetime import datetime, timezone

        token.delivery_timestamp = datetime.now(timezone.utc)

    # Mark as redeemed (triggers immutability)
    token.redeem()

    db.add(token)
    await db.commit()
    await db.refresh(token)

    # Log to audit trail
    await write_audit_log(
        db=db,
        actor=actor,
        action="TOKEN_REDEEMED",
        entity_type="MaterialToken",
        entity_id=token.token_uid,
        event_payload={
            "delivery_lat": payload.delivery_lat,
            "delivery_lon": payload.delivery_lon,
            "delivery_timestamp": token.delivery_timestamp.isoformat() if token.delivery_timestamp else None,
            "batch_id": payload.batch_id,
            "supplier_id": str(token.supplier_id) if token.supplier_id else None,
            "supplier_invoice_ref": payload.supplier_invoice_ref,
            "photo_path": delivery_photo_path,
        },
        actor_user_id=actor_user_id,
    )

    return token


async def get_token_by_uid(db: AsyncSession, token_uid: str) -> MaterialToken | None:
    """Fetch token by unique identifier."""
    result = await db.execute(
        select(MaterialToken).where(MaterialToken.token_uid == token_uid)
    )
    return result.scalar_one_or_none()


async def get_project_tokens(
    db: AsyncSession, project_id: UUID, redeemed_only: bool = False
) -> list[MaterialToken]:
    """Fetch all tokens for a project, optionally filtered by redemption status."""
    stmt = select(MaterialToken).where(MaterialToken.project_id == project_id)
    if redeemed_only:
        stmt = stmt.where(MaterialToken.redeemed == True)
    result = await db.execute(stmt.order_by(MaterialToken.issued_at.desc()))
    return result.scalars().all()

