"""Material token service: issuance, redemption, and one-time enforcement."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.material_token import MaterialToken
from app.schemas.material import MaterialTokenCreate, MaterialTokenRedeem
from app.services.audit_log_service import write_audit_log


async def issue_material_token(
    db: AsyncSession, data: MaterialTokenCreate
) -> MaterialToken:
    """
    Issue a new material token (unredeemed state).
    
    Rules:
    - Token starts unredeemed
    - Quantity locked at issuance
    - Used to authorize one delivery
    - Action is logged to audit trail
    """
    token = MaterialToken(
        project_id=data.project_id,
        material_code=data.material_code,
        material_name=data.material_name,
        quantity=data.quantity,
        unit=data.unit,
        supplier_name=data.supplier_name,
        issued_by=data.issued_by,
        redeemed=False,
    )

    db.add(token)
    await db.commit()
    await db.refresh(token)

    # Log to audit trail
    await write_audit_log(
        db=db,
        actor=data.issued_by,
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

