from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotifyEventRequest(BaseModel):
    notified_user_id: UUID | None = Field(
        None,
        description="Optional explicit user to notify; if omitted, server derives counterparty from activity type.",
    )
    delivery_channel: str = Field(
        "in_app",
        description="Delivery channel: in_app | email | webhook",
        pattern="^(in_app|email|webhook)$",
    )
    response_window_hours: int | None = Field(
        None,
        ge=1,
        le=168,
        description="Optional override of response window; defaults to server config (48h).",
    )


class NotificationOut(BaseModel):
    id: UUID
    activity_id: UUID
    notified_user_id: UUID
    notification_timestamp: datetime
    response_deadline_timestamp: datetime
    delivery_channel: str
    demo_watermark: bool = False
    seconds_remaining: int | None = None

    model_config = ConfigDict(from_attributes=True)


class RespondNotificationRequest(BaseModel):
    response_type: str = Field(
        ...,
        description="acknowledge | comment | dispute",
        pattern="^(acknowledge|comment|dispute)$",
    )
    response_comment: str | None = Field(None, max_length=2000)


class ResponseOut(BaseModel):
    id: UUID
    notification_id: UUID
    responder_user_id: UUID | None
    response_type: str
    response_timestamp: datetime
    response_comment: str | None
    demo_watermark: bool = False

    model_config = ConfigDict(from_attributes=True)


class NotificationWithResponses(BaseModel):
    notification: NotificationOut
    responses: list[ResponseOut]


class AcknowledgementStatusOut(BaseModel):
    activity_id: UUID
    derived_status: str
    computed_at: datetime
    notifications: list[NotificationWithResponses]


class ProjectAcknowledgementSummaryOut(BaseModel):
    project_id: UUID
    derived_status: str
    disputed_count: int
    acknowledged_count: int
    deemed_observed_count: int
    unseen_count: int
    computed_at: datetime
