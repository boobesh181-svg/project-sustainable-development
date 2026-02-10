from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, role_required
from app.models.activity_record import ActivityRecord, ActivityType
from app.models.event_notification import DeliveryChannel, EventNotification
from app.models.event_status_ledger import DerivedStatus
from app.models.role import RoleName
from app.models.user import User
from app.schemas.acknowledgement import (
    NotificationOut,
    NotifyEventRequest,
    RespondNotificationRequest,
    ResponseOut,
)
from app.schemas.mrv_approval import MRVReportCreate, MRVReportOut
from app.schemas.project import ProjectCreate, ProjectRead
from app.services import acknowledgement_service
from app.services.mrv_approval_service import advance_mrv_status, create_mrv_report
from app.services.mrv_report_export_service import build_mrv_report_export_package
from app.services.project_service import create_project

router = APIRouter(prefix="/api/demo", tags=["demo-surface"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _seconds_remaining(deadline: datetime) -> int:
    remaining = int((deadline - _utcnow()).total_seconds())
    return max(0, remaining)


async def _get_mrv_created_activity(db: AsyncSession, *, report_id: UUID) -> ActivityRecord | None:
    return (
        (
            await db.execute(
                select(ActivityRecord)
                .where(
                    ActivityRecord.activity_type == ActivityType.MRV_REPORT_CREATED,
                    ActivityRecord.mrv_report_id == report_id,
                )
                .order_by(ActivityRecord.occurred_at.asc(), ActivityRecord.id.asc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )


async def _latest_notification_for_activity(
    db: AsyncSession, *, activity_id: UUID
) -> EventNotification | None:
    return (
        (
            await db.execute(
                select(EventNotification)
                .where(EventNotification.activity_id == activity_id)
                .order_by(
                    EventNotification.notification_timestamp.desc(),
                    EventNotification.id.desc(),
                )
                .limit(1)
            )
        )
        .scalars()
        .first()
    )


@router.post("/project", response_model=ProjectRead, status_code=201)
async def demo_create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.PROJECT_MANAGER])),
) -> ProjectRead:
    try:
        project = await create_project(db, payload, created_by_user_id=current_user.id)
        return ProjectRead.model_validate(project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/event", status_code=201)
async def demo_create_event_and_notify(
    payload: "DemoEventCreateRequest",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.CONTRACTOR, RoleName.PROJECT_MANAGER])),
) -> "DemoEventCreateResponse":
    """Create a single demo "event" backed by an MRV report + acknowledgement notification.

    This is an orchestration layer only:
    - Creates MRV report (DRAFT)
    - Optionally advances to SUBMITTED (so it is ready for verification)
    - Ensures an acknowledgement notification exists for the related activity
    """

    server_payload = payload.mrv_report.model_copy(update={"created_by": current_user.id})

    try:
        report = await create_mrv_report(db, server_payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.auto_submit:
        try:
            report = await advance_mrv_status(
                db=db,
                report_id=report.id,
                next_status="SUBMITTED",
                actor=current_user.id,
                actor_role=current_user.role.name if current_user.role else None,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    activity = await _get_mrv_created_activity(db, report_id=report.id)

    notification_out: NotificationOut | None = None
    if activity is not None:
        existing = await _latest_notification_for_activity(db, activity_id=activity.id)
        notif = existing

        # Best-effort: if notification is missing (e.g., prior failure), create one now.
        if notif is None:
            notify_req = payload.notify or NotifyEventRequest()
            try:
                notif = await acknowledgement_service.notify_activity(
                    db,
                    activity_id=activity.id,
                    requested_notified_user_id=notify_req.notified_user_id,
                    delivery_channel=DeliveryChannel(notify_req.delivery_channel),
                    response_window_hours=notify_req.response_window_hours,
                    actor=current_user,
                )
            except HTTPException:
                # If notification cannot be created (e.g., no MRV officer exists),
                # still return the report/event; caller can inspect error by using v1 endpoints.
                notif = None

        if notif is not None:
            notification_out = NotificationOut(
                id=notif.id,
                activity_id=notif.activity_id,
                notified_user_id=notif.notified_user_id,
                notification_timestamp=notif.notification_timestamp,
                response_deadline_timestamp=notif.response_deadline_timestamp,
                delivery_channel=notif.delivery_channel.value,
                demo_watermark=bool(notif.demo_watermark),
                seconds_remaining=_seconds_remaining(notif.response_deadline_timestamp),
            )

    return DemoEventCreateResponse(
        report=MRVReportOut.model_validate(report),
        activity_id=None if activity is None else activity.id,
        notification=notification_out,
    )


@router.get("/notifications", response_model=list[NotificationOut])
async def demo_pending_notifications(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NotificationOut]:
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


@router.post("/respond", response_model=ResponseOut, status_code=201)
async def demo_respond(
    payload: "DemoRespondRequest",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResponseOut:
    response_type = acknowledgement_service._to_response_type(payload.response.response_type)
    resp = await acknowledgement_service.respond_to_notification(
        db,
        notification_id=payload.notification_id,
        responder=current_user,
        response_type=response_type,
        response_comment=payload.response.response_comment,
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


@router.post("/verify", response_model=MRVReportOut)
async def demo_verify(
    payload: "DemoVerifyRequest",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.MRV_OFFICER])),
) -> MRVReportOut:
    """Verify a submitted report, but only if the related event is observed."""

    activity = await _get_mrv_created_activity(db, report_id=payload.report_id)
    if activity is None:
        raise HTTPException(status_code=409, detail="EVENT MISSING")

    derived_status, _computed_at = await acknowledgement_service.get_acknowledgement_status(
        db, activity_id=activity.id
    )

    if derived_status not in (DerivedStatus.ACKNOWLEDGED, DerivedStatus.DEEMED_OBSERVED):
        raise HTTPException(status_code=409, detail="EVENT NOT YET OBSERVED")

    try:
        report = await advance_mrv_status(
            db=db,
            report_id=payload.report_id,
            next_status="VERIFIED",
            actor=current_user.id,
            actor_role=current_user.role.name if current_user.role else None,
        )
        return MRVReportOut.model_validate(report)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/approve", response_model=MRVReportOut)
async def demo_approve(
    payload: "DemoApproveRequest",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN])),
) -> MRVReportOut:
    try:
        report = await advance_mrv_status(
            db=db,
            report_id=payload.report_id,
            next_status="APPROVED",
            actor=current_user.id,
            actor_role=current_user.role.name if current_user.role else None,
        )
        return MRVReportOut.model_validate(report)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export/{report_id}")
async def demo_export(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        role_required([RoleName.ADMIN, RoleName.MRV_OFFICER, RoleName.PROJECT_MANAGER])
    ),
):
    _ = current_user
    pkg = await build_mrv_report_export_package(db, report_id)
    return StreamingResponse(
        iter([pkg.data]),
        media_type=pkg.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{pkg.filename}"',
            "Cache-Control": "no-store",
        },
    )


# --- Local request/response schemas (kept minimal on purpose) ---


from pydantic import BaseModel


class DemoEventCreateRequest(BaseModel):
    mrv_report: MRVReportCreate
    auto_submit: bool = True
    notify: NotifyEventRequest | None = None


class DemoEventCreateResponse(BaseModel):
    report: MRVReportOut
    activity_id: UUID | None
    notification: NotificationOut | None


class DemoRespondRequest(BaseModel):
    notification_id: UUID
    response: RespondNotificationRequest


class DemoVerifyRequest(BaseModel):
    report_id: UUID


class DemoApproveRequest(BaseModel):
    report_id: UUID
