from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from starlette import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.activity_record import ActivityRecord, ActivityType
from app.models.event_notification import DeliveryChannel, EventNotification
from app.models.event_response import EventResponse, ResponseType
from app.models.event_status_ledger import DerivedStatus, EventStatusLedger
from app.models.delivery_verification import DeliveryVerification
from app.models.material_token import MaterialToken
from app.models.mrv_report import MRVReport
from app.models.project import Project
from app.models.role import Role, RoleName
from app.models.user import User
from app.services.audit_log_service import write_audit_log


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_response_type(value: str) -> ResponseType:
    mapping = {
        "acknowledge": ResponseType.ACKNOWLEDGED,
        "comment": ResponseType.COMMENTED,
        "dispute": ResponseType.DISPUTED,
    }
    if value not in mapping:
        raise HTTPException(status_code=400, detail="Invalid response_type")
    return mapping[value]


async def create_activity_for_material_token_redemption(
    db: AsyncSession,
    *,
    token: MaterialToken,
    actor_user_id: UUID | None,
    occurred_at: datetime,
) -> ActivityRecord:
    activity_hash = ActivityRecord.compute_hash(
        activity_type=ActivityType.MATERIAL_TOKEN_REDEEMED,
        project_id=token.project_id,
        occurred_at=occurred_at,
        material_token_id=token.id,
        delivery_verification_id=None,
        mrv_report_id=None,
        created_by_user_id=actor_user_id,
    )

    activity = ActivityRecord(
        activity_type=ActivityType.MATERIAL_TOKEN_REDEEMED,
        project_id=token.project_id,
        material_token_id=token.id,
        delivery_verification_id=None,
        mrv_report_id=None,
        occurred_at=occurred_at,
        created_by_user_id=actor_user_id,
        activity_hash=activity_hash,
    )

    db.add(activity)
    await db.commit()
    await db.refresh(activity)

    await write_audit_log(
        db=db,
        actor="system" if actor_user_id is None else "user",
        actor_user_id=actor_user_id,
        action="ACTIVITY_RECORDED",
        entity_type="ActivityRecord",
        entity_id=str(activity.id),
        event_payload={
            "activity_type": activity.activity_type.value,
            "project_id": str(activity.project_id),
            "material_token_id": str(token.id),
            "token_uid": token.token_uid,
            "occurred_at": occurred_at.replace(microsecond=0).isoformat(),
            "activity_hash": activity.activity_hash,
            "demo_mode": bool(settings.DEMO_MODE),
        },
    )

    return activity


async def create_activity_for_delivery_verification_created(
    db: AsyncSession,
    *,
    verification: DeliveryVerification,
    token: MaterialToken,
    actor_user_id: UUID | None,
    occurred_at: datetime,
) -> ActivityRecord:
    activity_hash = ActivityRecord.compute_hash(
        activity_type=ActivityType.DELIVERY_VERIFICATION_CREATED,
        project_id=token.project_id,
        occurred_at=occurred_at,
        material_token_id=None,
        delivery_verification_id=verification.id,
        mrv_report_id=None,
        created_by_user_id=actor_user_id,
    )

    activity = ActivityRecord(
        activity_type=ActivityType.DELIVERY_VERIFICATION_CREATED,
        project_id=token.project_id,
        material_token_id=None,
        delivery_verification_id=verification.id,
        mrv_report_id=None,
        occurred_at=occurred_at,
        created_by_user_id=actor_user_id,
        activity_hash=activity_hash,
    )

    db.add(activity)
    await db.commit()
    await db.refresh(activity)

    await write_audit_log(
        db=db,
        actor="system" if actor_user_id is None else "user",
        actor_user_id=actor_user_id,
        action="ACTIVITY_RECORDED",
        entity_type="ActivityRecord",
        entity_id=str(activity.id),
        event_payload={
            "activity_type": activity.activity_type.value,
            "project_id": str(activity.project_id),
            "delivery_verification_id": str(verification.id),
            "material_token_id": str(token.id),
            "token_uid": token.token_uid,
            "occurred_at": occurred_at.replace(microsecond=0).isoformat(),
            "activity_hash": activity.activity_hash,
            "demo_mode": bool(settings.DEMO_MODE),
        },
    )

    return activity


async def create_activity_for_mrv_report_created(
    db: AsyncSession,
    *,
    report: MRVReport,
    actor_user_id: UUID | None,
    occurred_at: datetime,
) -> ActivityRecord:
    activity_hash = ActivityRecord.compute_hash(
        activity_type=ActivityType.MRV_REPORT_CREATED,
        project_id=report.project_id,
        occurred_at=occurred_at,
        material_token_id=None,
        delivery_verification_id=None,
        mrv_report_id=report.id,
        created_by_user_id=actor_user_id,
    )

    activity = ActivityRecord(
        activity_type=ActivityType.MRV_REPORT_CREATED,
        project_id=report.project_id,
        material_token_id=None,
        delivery_verification_id=None,
        mrv_report_id=report.id,
        occurred_at=occurred_at,
        created_by_user_id=actor_user_id,
        activity_hash=activity_hash,
    )

    db.add(activity)
    await db.commit()
    await db.refresh(activity)

    await write_audit_log(
        db=db,
        actor="system" if actor_user_id is None else "user",
        actor_user_id=actor_user_id,
        action="ACTIVITY_RECORDED",
        entity_type="ActivityRecord",
        entity_id=str(activity.id),
        event_payload={
            "activity_type": activity.activity_type.value,
            "project_id": str(activity.project_id),
            "mrv_report_id": str(report.id),
            "occurred_at": occurred_at.replace(microsecond=0).isoformat(),
            "activity_hash": activity.activity_hash,
            "demo_mode": bool(settings.DEMO_MODE),
        },
    )

    return activity


async def notify_activity(
    db: AsyncSession,
    *,
    activity_id: UUID,
    requested_notified_user_id: UUID | None,
    delivery_channel: DeliveryChannel,
    response_window_hours: int | None,
    actor: User,
) -> EventNotification:
    activity = await db.get(ActivityRecord, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    notified_user_id = requested_notified_user_id

    # Default routing rules (counterparty selection)
    if notified_user_id is None:
        if activity.activity_type == ActivityType.MATERIAL_TOKEN_REDEEMED:
            project = await db.get(Project, activity.project_id)
            if project is None:
                raise HTTPException(status_code=404, detail="Project not found")
            notified_user_id = project.created_by
        elif activity.activity_type == ActivityType.DELIVERY_VERIFICATION_CREATED:
            # Best-effort: notify the supplier user for the token supplier.
            if activity.delivery_verification_id is None:
                raise HTTPException(status_code=400, detail="Activity missing delivery_verification_id")
            verification = await db.get(DeliveryVerification, activity.delivery_verification_id)
            if verification is None:
                raise HTTPException(status_code=404, detail="Delivery verification not found")
            token = await db.get(MaterialToken, verification.material_token_id)
            if token is None or token.supplier_id is None:
                raise HTTPException(status_code=400, detail="Supplier not configured for this activity")
            supplier_user = (
                await db.execute(
                    select(User)
                    .where(User.supplier_id == token.supplier_id)
                    .order_by(User.created_at.asc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if supplier_user is None:
                raise HTTPException(status_code=409, detail="No supplier user exists to notify")
            notified_user_id = supplier_user.id
        elif activity.activity_type == ActivityType.MRV_REPORT_CREATED:
            # Default routing: notify an MRV officer.
            officer = (
                await db.execute(
                    select(User)
                    .join(Role, Role.id == User.role_id)
                    .where(Role.name == RoleName.MRV_OFFICER, User.is_active == True)
                    .order_by(User.created_at.asc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if officer is None:
                raise HTTPException(status_code=409, detail="No MRV officer exists to notify")
            notified_user_id = officer.id
        else:
            raise HTTPException(
                status_code=400,
                detail="Notified user must be provided for this activity type",
            )

    # Governance: creator cannot notify themselves for acknowledgement.
    if activity.created_by_user_id is not None and notified_user_id == activity.created_by_user_id:
        raise HTTPException(status_code=400, detail="Creator cannot notify themselves")

    window_hours = response_window_hours or settings.ACK_RESPONSE_WINDOW_HOURS
    notification_ts = _utcnow()
    deadline_ts = notification_ts + timedelta(hours=window_hours)

    demo_watermark = bool(settings.DEMO_MODE)
    notification_hash = EventNotification.compute_hash(
        activity_id=activity.id,
        notified_user_id=notified_user_id,
        notification_timestamp=notification_ts,
        response_deadline_timestamp=deadline_ts,
        delivery_channel=delivery_channel,
        demo_watermark=demo_watermark,
    )

    notif = EventNotification(
        activity_id=activity.id,
        notified_party_org_id=None,
        notified_user_id=notified_user_id,
        notification_timestamp=notification_ts,
        response_deadline_timestamp=deadline_ts,
        notification_hash=notification_hash,
        delivery_channel=delivery_channel,
        demo_watermark=demo_watermark,
    )

    db.add(notif)
    await db.commit()
    await db.refresh(notif)

    await write_audit_log(
        db=db,
        actor=actor.email,
        actor_user_id=actor.id,
        action="EVENT_NOTIFICATION_CREATED",
        entity_type="EventNotification",
        entity_id=str(notif.id),
        event_payload={
            "activity_id": str(activity.id),
            "activity_type": activity.activity_type.value,
            "notified_user_id": str(notified_user_id),
            "notification_timestamp": notification_ts.replace(microsecond=0).isoformat(),
            "response_deadline_timestamp": deadline_ts.replace(microsecond=0).isoformat(),
            "notification_hash": notif.notification_hash,
            "delivery_channel": notif.delivery_channel.value,
            "demo_watermark": demo_watermark,
            "watermark": "DEMO_ACKNOWLEDGEMENT" if demo_watermark else None,
        },
    )

    # Initial derived status for the activity.
    await _compute_and_record_status(db, activity_id=activity.id)

    return notif


async def list_pending_notifications(
    db: AsyncSession,
    *,
    current_user: User,
    limit: int = 50,
) -> list[EventNotification]:
    now = _utcnow()

    # Auto-close expired notifications (deemed observed) before listing.
    expired = (
        await db.execute(
            select(EventNotification)
            .where(
                EventNotification.notified_user_id == current_user.id,
                EventNotification.response_deadline_timestamp < now,
            )
            .order_by(EventNotification.response_deadline_timestamp.asc())
            .limit(200)
        )
    ).scalars().all()

    for notif in expired:
        await ensure_auto_no_response(db, notification_id=notif.id)

    # Pending = no responses yet and deadline in the future.
    stmt = (
        select(EventNotification)
        .where(
            EventNotification.notified_user_id == current_user.id,
            EventNotification.response_deadline_timestamp >= now,
            ~select(EventResponse.id)
            .where(EventResponse.notification_id == EventNotification.id)
            .exists(),
        )
        .order_by(EventNotification.response_deadline_timestamp.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def respond_to_notification(
    db: AsyncSession,
    *,
    notification_id: UUID,
    responder: User,
    response_type: ResponseType,
    response_comment: str | None,
) -> EventResponse:
    notif = await db.get(EventNotification, notification_id)
    if notif is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notif.notified_user_id != responder.id:
        raise HTTPException(status_code=403, detail="Not authorized for this notification")

    activity = await db.get(ActivityRecord, notif.activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Governance: creator cannot acknowledge/dispute their own event.
    if activity.created_by_user_id is not None and activity.created_by_user_id == responder.id:
        raise HTTPException(status_code=400, detail="Creator cannot respond to own event")

    # Governance: if this activity is about an MRV report and the responder is already verifier, block.
    if activity.mrv_report_id is not None:
        report = await db.get(MRVReport, activity.mrv_report_id)
        if report is not None and report.verified_by is not None and report.verified_by == responder.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Verifier cannot respond to acknowledgement for an MRV report they verified",
            )

    now = _utcnow()
    if now > notif.response_deadline_timestamp and response_type != ResponseType.NO_RESPONSE_AUTO:
        raise HTTPException(status_code=409, detail="Response deadline has passed")

    demo_watermark = bool(settings.DEMO_MODE)
    comment = response_comment
    if demo_watermark:
        prefix = "DEMO_ACKNOWLEDGEMENT: "
        if comment:
            comment = prefix + comment
        else:
            comment = prefix.rstrip()

    response_hash = EventResponse.compute_hash(
        notification_id=notif.id,
        responder_user_id=responder.id,
        response_type=response_type,
        response_timestamp=now,
        response_comment=comment,
        demo_watermark=demo_watermark,
    )

    resp = EventResponse(
        notification_id=notif.id,
        responder_user_id=responder.id,
        response_type=response_type,
        response_timestamp=now,
        response_comment=comment,
        response_hash=response_hash,
        demo_watermark=demo_watermark,
    )

    db.add(resp)
    await db.commit()
    await db.refresh(resp)

    await write_audit_log(
        db=db,
        actor=responder.email,
        actor_user_id=responder.id,
        action="EVENT_RESPONSE_RECORDED",
        entity_type="EventResponse",
        entity_id=str(resp.id),
        event_payload={
            "notification_id": str(notif.id),
            "activity_id": str(activity.id),
            "response_type": resp.response_type.value,
            "response_timestamp": resp.response_timestamp.replace(microsecond=0).isoformat(),
            "response_hash": resp.response_hash,
            "demo_watermark": demo_watermark,
            "watermark": "DEMO_ACKNOWLEDGEMENT" if demo_watermark else None,
        },
    )

    await _compute_and_record_status(db, activity_id=activity.id)
    return resp


async def ensure_auto_no_response(db: AsyncSession, *, notification_id: UUID) -> EventResponse | None:
    notif = await db.get(EventNotification, notification_id)
    if notif is None:
        return None

    now = _utcnow()
    if now <= notif.response_deadline_timestamp:
        return None

    existing = (
        await db.execute(
            select(EventResponse.id)
            .where(EventResponse.notification_id == notif.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    demo_watermark = bool(settings.DEMO_MODE)
    ts = notif.response_deadline_timestamp
    comment = "Auto-generated: no response by deadline"
    if demo_watermark:
        comment = "DEMO_ACKNOWLEDGEMENT: " + comment

    response_hash = EventResponse.compute_hash(
        notification_id=notif.id,
        responder_user_id=notif.notified_user_id,
        response_type=ResponseType.NO_RESPONSE_AUTO,
        response_timestamp=ts,
        response_comment=comment,
        demo_watermark=demo_watermark,
    )

    resp = EventResponse(
        notification_id=notif.id,
        responder_user_id=notif.notified_user_id,
        response_type=ResponseType.NO_RESPONSE_AUTO,
        response_timestamp=ts,
        response_comment=comment,
        response_hash=response_hash,
        demo_watermark=demo_watermark,
    )

    db.add(resp)
    try:
        await db.commit()
    except IntegrityError:
        # Race-safe: another worker/request created the auto-response first.
        await db.rollback()
        return None

    await db.refresh(resp)

    await write_audit_log(
        db=db,
        actor="system",
        actor_user_id=None,
        action="EVENT_NO_RESPONSE_AUTO",
        entity_type="EventResponse",
        entity_id=str(resp.id),
        event_payload={
            "notification_id": str(notif.id),
            "activity_id": str(notif.activity_id),
            "response_type": resp.response_type.value,
            "response_timestamp": ts.replace(microsecond=0).isoformat(),
            "response_hash": resp.response_hash,
            "demo_watermark": demo_watermark,
            "watermark": "DEMO_ACKNOWLEDGEMENT" if demo_watermark else None,
        },
    )

    await _compute_and_record_status(db, activity_id=notif.activity_id)
    return resp


async def sweep_expired_notifications(
    db: AsyncSession,
    *,
    limit: int,
) -> int:
    """Append NO_RESPONSE_AUTO responses for expired, unanswered notifications.

    This is safe to run periodically (best-effort). It never updates/deletes rows.
    Returns the number of notifications for which an auto-response was appended.
    """

    now = _utcnow()
    expired_ids = (
        await db.execute(
            select(EventNotification.id)
            .where(
                EventNotification.response_deadline_timestamp < now,
                ~select(EventResponse.id)
                .where(EventResponse.notification_id == EventNotification.id)
                .exists(),
            )
            .order_by(EventNotification.response_deadline_timestamp.asc())
            .limit(limit)
        )
    ).scalars().all()

    appended = 0
    for nid in expired_ids:
        resp = await ensure_auto_no_response(db, notification_id=nid)
        if resp is not None:
            appended += 1
    return appended


async def get_acknowledgement_status(
    db: AsyncSession, *, activity_id: UUID
) -> tuple[DerivedStatus, datetime]:
    await _compute_and_record_status(db, activity_id=activity_id)

    last = (
        await db.execute(
            select(EventStatusLedger)
            .where(EventStatusLedger.activity_id == activity_id)
            .order_by(EventStatusLedger.computed_at.desc(), EventStatusLedger.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if last is None:
        return (DerivedStatus.UNSEEN, _utcnow())

    return (last.derived_status, last.computed_at)


async def get_project_ack_summary(
    db: AsyncSession, *, project_id: UUID
) -> dict[str, Any]:
    # Consider all activity records in the project.
    activities = (
        await db.execute(
            select(ActivityRecord.id)
            .where(ActivityRecord.project_id == project_id)
            .order_by(ActivityRecord.occurred_at.desc())
            .limit(500)
        )
    ).scalars().all()

    counts = {
        DerivedStatus.DISPUTED: 0,
        DerivedStatus.ACKNOWLEDGED: 0,
        DerivedStatus.DEEMED_OBSERVED: 0,
        DerivedStatus.SEEN: 0,
        DerivedStatus.UNSEEN: 0,
    }

    now = _utcnow()
    for aid in activities:
        st, _ = await get_acknowledgement_status(db, activity_id=aid)
        counts[st] = counts.get(st, 0) + 1

    derived = (
        DerivedStatus.DISPUTED
        if counts[DerivedStatus.DISPUTED] > 0
        else (DerivedStatus.ACKNOWLEDGED if counts[DerivedStatus.ACKNOWLEDGED] > 0 else (
            DerivedStatus.DEEMED_OBSERVED if counts[DerivedStatus.DEEMED_OBSERVED] > 0 else (
                DerivedStatus.SEEN if counts[DerivedStatus.SEEN] > 0 else DerivedStatus.UNSEEN
            )
        ))
    )

    return {
        "project_id": project_id,
        "derived_status": derived.value,
        "disputed_count": counts[DerivedStatus.DISPUTED],
        "acknowledged_count": counts[DerivedStatus.ACKNOWLEDGED],
        "deemed_observed_count": counts[DerivedStatus.DEEMED_OBSERVED],
        "unseen_count": counts[DerivedStatus.UNSEEN],
        "computed_at": now,
    }


async def _compute_and_record_status(db: AsyncSession, *, activity_id: UUID) -> None:
    # Ensure auto no-response for any expired notifications.
    now = _utcnow()
    notifs = (
        await db.execute(
            select(EventNotification)
            .where(EventNotification.activity_id == activity_id)
            .order_by(EventNotification.notification_timestamp.asc(), EventNotification.id.asc())
        )
    ).scalars().all()

    for n in notifs:
        if now > n.response_deadline_timestamp:
            await ensure_auto_no_response(db, notification_id=n.id)

    responses = (
        await db.execute(
            select(EventResponse)
            .join(EventNotification, EventNotification.id == EventResponse.notification_id)
            .where(EventNotification.activity_id == activity_id)
            .order_by(EventResponse.response_timestamp.asc(), EventResponse.id.asc())
        )
    ).scalars().all()

    response_types = [r.response_type for r in responses]

    if ResponseType.DISPUTED in response_types:
        derived = DerivedStatus.DISPUTED
    elif ResponseType.ACKNOWLEDGED in response_types:
        derived = DerivedStatus.ACKNOWLEDGED
    elif ResponseType.NO_RESPONSE_AUTO in response_types:
        derived = DerivedStatus.DEEMED_OBSERVED
    elif ResponseType.COMMENTED in response_types:
        derived = DerivedStatus.SEEN
    else:
        derived = DerivedStatus.UNSEEN

    last = (
        await db.execute(
            select(EventStatusLedger)
            .where(EventStatusLedger.activity_id == activity_id)
            .order_by(EventStatusLedger.computed_at.desc(), EventStatusLedger.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if last is not None and last.derived_status == derived:
        return

    activity = await db.get(ActivityRecord, activity_id)
    activity_hash = activity.activity_hash if activity is not None else str(activity_id)

    notif_hashes = [n.notification_hash for n in notifs]
    resp_hashes = [r.response_hash for r in responses]

    basis_hash = EventStatusLedger.compute_basis_hash(
        activity_hash,
        derived.value,
        ",".join(sorted(notif_hashes)),
        ",".join(sorted(resp_hashes)),
    )

    ledger = EventStatusLedger(
        activity_id=activity_id,
        derived_status=derived,
        computed_at=now,
        computation_basis_hash=basis_hash,
    )

    db.add(ledger)
    await db.commit()

    await write_audit_log(
        db=db,
        actor="system",
        actor_user_id=None,
        action="EVENT_DERIVED_STATUS_COMPUTED",
        entity_type="EventStatusLedger",
        entity_id=str(ledger.id),
        event_payload={
            "activity_id": str(activity_id),
            "derived_status": derived.value,
            "computed_at": now.replace(microsecond=0).isoformat(),
            "computation_basis_hash": basis_hash,
            "demo_mode": bool(settings.DEMO_MODE),
        },
    )
