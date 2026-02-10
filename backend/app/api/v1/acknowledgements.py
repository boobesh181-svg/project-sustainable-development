from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, role_required
from app.models.event_notification import EventNotification, DeliveryChannel
from app.models.event_response import EventResponse
from app.models.role import RoleName
from app.models.user import User
from app.schemas.acknowledgement import (
    AcknowledgementStatusOut,
    NotificationOut,
    NotificationWithResponses,
    NotifyEventRequest,
    ProjectAcknowledgementSummaryOut,
    RespondNotificationRequest,
    ResponseOut,
)
from app.services import acknowledgement_service

router = APIRouter(prefix="/api/v1", tags=["Acknowledgements"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _seconds_remaining(deadline: datetime) -> int:
    remaining = int((deadline - _utcnow()).total_seconds())
    return max(0, remaining)


@router.post("/events/{activity_id}/notify", response_model=NotificationOut, status_code=201)
async def notify_event(
    activity_id: UUID,
    payload: NotifyEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        role_required(
            [RoleName.ADMIN, RoleName.PROJECT_MANAGER, RoleName.CONTRACTOR, RoleName.MRV_OFFICER]
        )
    ),
):
    delivery_channel = DeliveryChannel(payload.delivery_channel)
    notif = await acknowledgement_service.notify_activity(
        db,
        activity_id=activity_id,
        requested_notified_user_id=payload.notified_user_id,
        delivery_channel=delivery_channel,
        response_window_hours=payload.response_window_hours,
        actor=current_user,
    )

    return NotificationOut(
        id=notif.id,
        activity_id=notif.activity_id,
        notified_user_id=notif.notified_user_id,
        notification_timestamp=notif.notification_timestamp,
        response_deadline_timestamp=notif.response_deadline_timestamp,
        delivery_channel=notif.delivery_channel.value,
        demo_watermark=bool(notif.demo_watermark),
        seconds_remaining=_seconds_remaining(notif.response_deadline_timestamp),
    )


@router.get("/notifications/pending", response_model=list[NotificationOut])
async def pending_notifications(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifs = await acknowledgement_service.list_pending_notifications(
        db, current_user=current_user, limit=limit
    )
    return [
        NotificationOut(
            id=n.id,
            activity_id=n.activity_id,
            notified_user_id=n.notified_user_id,
            notification_timestamp=n.notification_timestamp,
            response_deadline_timestamp=n.response_deadline_timestamp,
            delivery_channel=n.delivery_channel.value,
            demo_watermark=bool(n.demo_watermark),
            seconds_remaining=_seconds_remaining(n.response_deadline_timestamp),
        )
        for n in notifs
    ]


@router.post("/notifications/{notification_id}/respond", response_model=ResponseOut, status_code=201)
async def respond_to_notification(
    notification_id: UUID,
    payload: RespondNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response_type = acknowledgement_service._to_response_type(payload.response_type)
    resp = await acknowledgement_service.respond_to_notification(
        db,
        notification_id=notification_id,
        responder=current_user,
        response_type=response_type,
        response_comment=payload.response_comment,
    )

    return ResponseOut(
        id=resp.id,
        notification_id=resp.notification_id,
        responder_user_id=resp.responder_user_id,
        response_type=resp.response_type.value,
        response_timestamp=resp.response_timestamp,
        response_comment=resp.response_comment,
        demo_watermark=bool(resp.demo_watermark),
    )


@router.get("/events/{activity_id}/acknowledgement-status", response_model=AcknowledgementStatusOut)
async def acknowledgement_status(
    activity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Status is viewable for any authenticated user (dashboard-only).
    derived_status, computed_at = await acknowledgement_service.get_acknowledgement_status(
        db, activity_id=activity_id
    )

    notifs = (
        await db.execute(
            select(EventNotification)
            .where(EventNotification.activity_id == activity_id)
            .order_by(EventNotification.notification_timestamp.asc(), EventNotification.id.asc())
        )
    ).scalars().all()

    out_notifs: list[NotificationWithResponses] = []
    for n in notifs:
        responses = (
            await db.execute(
                select(EventResponse)
                .where(EventResponse.notification_id == n.id)
                .order_by(EventResponse.response_timestamp.asc(), EventResponse.id.asc())
            )
        ).scalars().all()

        out_notifs.append(
            NotificationWithResponses(
                notification=NotificationOut(
                    id=n.id,
                    activity_id=n.activity_id,
                    notified_user_id=n.notified_user_id,
                    notification_timestamp=n.notification_timestamp,
                    response_deadline_timestamp=n.response_deadline_timestamp,
                    delivery_channel=n.delivery_channel.value,
                    demo_watermark=bool(n.demo_watermark),
                    seconds_remaining=_seconds_remaining(n.response_deadline_timestamp),
                ),
                responses=[
                    ResponseOut(
                        id=r.id,
                        notification_id=r.notification_id,
                        responder_user_id=r.responder_user_id,
                        response_type=r.response_type.value,
                        response_timestamp=r.response_timestamp,
                        response_comment=r.response_comment,
                        demo_watermark=bool(r.demo_watermark),
                    )
                    for r in responses
                ],
            )
        )

    return AcknowledgementStatusOut(
        activity_id=activity_id,
        derived_status=derived_status.value,
        computed_at=computed_at,
        notifications=out_notifs,
    )


@router.get(
    "/ack/projects/{project_id}/summary", response_model=ProjectAcknowledgementSummaryOut
)
async def project_ack_summary(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    summary = await acknowledgement_service.get_project_ack_summary(db, project_id=project_id)
    return ProjectAcknowledgementSummaryOut(**summary)
