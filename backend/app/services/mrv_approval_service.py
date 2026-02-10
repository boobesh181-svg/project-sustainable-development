"""MRV approval service: enforce immutable-after-approval workflow."""

import logging
from decimal import Decimal
from fastapi import HTTPException
from starlette import status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.mrv_report import MRVReport, MRVStatus
from app.models.role import RoleName
from app.models.user import User
from app.schemas.mrv_approval import MRVReportCreate
from app.services.audit_log_service import write_audit_log
from app.services.acknowledgement_service import (
    create_activity_for_mrv_report_created,
    get_acknowledgement_status,
    notify_activity,
)
from app.models.event_notification import DeliveryChannel
from app.services.mrv_calculation_service import authoritative_report_total_co2e


logger = logging.getLogger(__name__)


async def create_mrv_report(
    db: AsyncSession, payload: MRVReportCreate
) -> MRVReport:
    """
    Create a new MRV report (starts in DRAFT state).
    
    Rules:
    - Status defaults to DRAFT
    - Report is editable until APPROVED
    - CO₂ value locked at creation (immutable with snapshots)
    - Emission factor snapshot captured for ISO-14064 reproducibility
    """
    if settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode: MRV report creation is disabled.",
        )

    # Capture emission factor snapshot if provided (ISO-14064 compliance)
    emission_factor_snapshot = None
    if payload.emission_factor_id:
        from app.models.emission_factor import EmissionFactor
        
        ef_result = await db.execute(
            select(EmissionFactor).where(EmissionFactor.id == payload.emission_factor_id)
        )
        emission_factor = ef_result.scalar_one_or_none()
        
        if emission_factor:
            emission_factor_snapshot = {
                "version": f"{emission_factor.material_code}_v{emission_factor.version}",
                "hash": emission_factor.factor_hash,
                "value": emission_factor.co2e_per_unit,
            }
    
    report = MRVReport(
        project_id=payload.project_id,
        reporting_period=payload.reporting_period,
        sample_desc=payload.sample_desc,
        parameter=payload.parameter,
        value=payload.value,
        # total_co2e is derived from snapshot inputs when available; payload value is accepted
        # for backward compatibility but is not authoritative if a snapshot exists.
        total_co2e=payload.total_co2e,
        created_by=payload.created_by,
        emission_factor_id=payload.emission_factor_id,
        certificate_path=payload.certificate_path,
        status=MRVStatus.DRAFT,
        # Snapshot for reproducibility
        emission_factor_version_snapshot=emission_factor_snapshot["version"] if emission_factor_snapshot else None,
        emission_factor_hash_snapshot=emission_factor_snapshot["hash"] if emission_factor_snapshot else None,
        emission_factor_value_snapshot=emission_factor_snapshot["value"] if emission_factor_snapshot else None,
    )

    # If snapshot inputs exist, deterministically derive total_co2e from them.
    try:
        derived_total, used_snapshot = authoritative_report_total_co2e(report)
        if used_snapshot:
            report.total_co2e = derived_total
    except Exception:
        # Never fail creation due to calculation mismatch; snapshot is already captured.
        logger.exception("Failed to derive MRV total_co2e from snapshot; using provided total")

    db.add(report)
    await db.commit()
    await db.refresh(report)

    # Log to audit trail
    await write_audit_log(
        db=db,
        actor=str(payload.created_by),
        actor_user_id=payload.created_by,
        action="MRV_CREATED",
        entity_type="MRVReport",
        entity_id=str(report.id),
        event_payload={
            "project_id": str(payload.project_id),
            "reporting_period": payload.reporting_period,
            "total_co2e": float(Decimal(str(report.total_co2e))),
            "status": "DRAFT",
        },
    )

    # Contemporaneous acknowledgement record + notification (does not change MRV lifecycle).
    try:
        activity = await create_activity_for_mrv_report_created(
            db,
            report=report,
            actor_user_id=payload.created_by,
            occurred_at=report.created_at,
        )

        actor_user = await db.get(User, payload.created_by)
        if actor_user is not None:
            await notify_activity(
                db,
                activity_id=activity.id,
                requested_notified_user_id=None,
                delivery_channel=DeliveryChannel.IN_APP,
                response_window_hours=None,
                actor=actor_user,
            )
    except Exception:
        # Acknowledgement layer must never block MRV report creation.
        logger.exception("Acknowledgement layer failed during MRV report creation")

    return report


async def advance_mrv_status(
    db: AsyncSession,
    report_id: UUID,
    next_status: str,
    actor: UUID,
    actor_role: RoleName | None = None,
) -> MRVReport:
    """
    Advance MRV report to next workflow state (strict progression).
    
    Rules:
    - DRAFT → SUBMITTED (creator submits)
    - SUBMITTED → VERIFIED (verifier approves samples)
    - VERIFIED → APPROVED (approver locks CO₂ numbers)
    - APPROVED → LOCKED (final immutable state)
    - Cannot skip steps
    - Cannot revert after APPROVED
    - Role separation: creator ≠ verifier ≠ approver
    
    Args:
        db: Database session
        report_id: MRV report UUID
        next_status: Target status (SUBMITTED, VERIFIED, APPROVED, LOCKED)
        actor: User advancing workflow
        
    Returns:
        Updated MRV report
        
    Raises:
        ValueError: If transition is invalid or report is immutable
    """
    if settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode: MRV workflow advancement is disabled.",
        )

    result = await db.execute(
        select(MRVReport).where(MRVReport.id == report_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise ValueError(f"MRV report {report_id} not found")

    # Parse target status
    try:
        target_status = MRVStatus(next_status)
    except ValueError:
        raise ValueError(
            f"Invalid status: {next_status}. Must be one of: "
            f"{', '.join([s.value for s in MRVStatus])}"
        )

    previous_status = report.status

    # Role gating + separation of duties (ISO-style workflow enforcement)
    # DRAFT -> SUBMITTED: creator submits
    if target_status == MRVStatus.SUBMITTED:
        if actor != report.created_by:
            raise ValueError("Only the report creator can submit (DRAFT → SUBMITTED)")

    # SUBMITTED -> VERIFIED: MRV officer verifies, must differ from creator
    if target_status == MRVStatus.VERIFIED:
        if actor_role != RoleName.MRV_OFFICER:
            raise ValueError("Only MRV officers can verify (SUBMITTED → VERIFIED)")
        if actor == report.created_by:
            raise ValueError("Separation of duties violated: verifier cannot be creator")

        # Acknowledgement gate: do not verify unless the MRV_REPORT_CREATED activity is ACKNOWLEDGED
        # or DEEMED_OBSERVED.
        from app.models.activity_record import ActivityRecord, ActivityType

        activity = (
            (
                await db.execute(
                    select(ActivityRecord)
                    .where(
                        ActivityRecord.activity_type == ActivityType.MRV_REPORT_CREATED,
                        ActivityRecord.mrv_report_id == report.id,
                    )
                    .order_by(ActivityRecord.occurred_at.asc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

        if activity is None:
            # Best-effort backfill for legacy reports created before acknowledgements were wired.
            try:
                activity = await create_activity_for_mrv_report_created(
                    db,
                    report=report,
                    actor_user_id=report.created_by,
                    occurred_at=report.created_at,
                )
                actor_user = await db.get(User, actor)
                if actor_user is not None:
                    await notify_activity(
                        db,
                        activity_id=activity.id,
                        requested_notified_user_id=None,
                        delivery_channel=DeliveryChannel.IN_APP,
                        response_window_hours=None,
                        actor=actor_user,
                    )
            except Exception:
                logger.exception("Failed to backfill acknowledgement activity/notification for MRV report")

        if activity is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot verify MRV report: acknowledgement activity record missing",
            )

        from app.models.event_status_ledger import DerivedStatus

        derived_status, _computed_at = await get_acknowledgement_status(db, activity_id=activity.id)
        if derived_status not in (DerivedStatus.ACKNOWLEDGED, DerivedStatus.DEEMED_OBSERVED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot verify MRV report until related activity is ACKNOWLEDGED or DEEMED_OBSERVED; "
                    f"current derived_status={derived_status.value}"
                ),
            )

    # VERIFIED -> APPROVED: admin approves, must differ from creator and verifier
    if target_status == MRVStatus.APPROVED:
        if actor_role != RoleName.ADMIN:
            raise ValueError("Only admins can approve (VERIFIED → APPROVED)")
        if actor == report.created_by:
            raise ValueError("Separation of duties violated: approver cannot be creator")
        if report.verified_by and actor == report.verified_by:
            raise ValueError("Separation of duties violated: approver cannot be verifier")

    # APPROVED -> LOCKED: admin finalizes lock
    if target_status == MRVStatus.LOCKED:
        if actor_role != RoleName.ADMIN:
            raise ValueError("Only admins can lock (APPROVED → LOCKED)")
        if report.approved_by and actor != report.approved_by:
            raise ValueError("Only the approving admin can lock this report")

    # Assign roles based on transition
    if target_status == MRVStatus.VERIFIED:
        if report.verified_by and report.verified_by != actor:
            raise ValueError("Report already verified; verifier cannot be changed")
        report.verified_by = actor
    elif target_status == MRVStatus.APPROVED:
        if report.approved_by and report.approved_by != actor:
            raise ValueError("Report already approved; approver cannot be changed")
        report.approved_by = actor

    # Advance state (validates transition logic)
    report.advance(target_status)

    db.add(report)
    await db.commit()
    await db.refresh(report)

    # Log to audit trail
    await write_audit_log(
        db=db,
        actor=str(actor),
        actor_user_id=actor,
        action=f"MRV_{target_status.value}",
        entity_type="MRVReport",
        entity_id=str(report.id),
        event_payload={
            "project_id": str(report.project_id),
            "previous_status": previous_status.value,
            "new_status": target_status.value,
            "total_co2e": float(report.total_co2e),
        },
    )

    return report


async def get_mrv_report_by_id(
    db: AsyncSession, report_id: UUID
) -> MRVReport | None:
    """Fetch MRV report by ID."""
    result = await db.execute(
        select(MRVReport).where(MRVReport.id == report_id)
    )
    return result.scalar_one_or_none()


async def list_mrv_reports_by_project(
    db: AsyncSession, project_id: UUID, status: str | None = None
) -> list[MRVReport]:
    """
    List MRV reports for a project, optionally filtered by status.
    
    Args:
        db: Database session
        project_id: Project UUID
        status: Optional status filter (DRAFT, SUBMITTED, VERIFIED, APPROVED, LOCKED)
        
    Returns:
        List of MRV reports ordered by creation date (newest first)
    """
    stmt = select(MRVReport).where(MRVReport.project_id == project_id)

    if status:
        try:
            status_enum = MRVStatus(status)
            stmt = stmt.where(MRVReport.status == status_enum)
        except ValueError:
            raise ValueError(
                f"Invalid status: {status}. Must be one of: "
                f"{', '.join([s.value for s in MRVStatus])}"
            )

    stmt = stmt.order_by(MRVReport.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
