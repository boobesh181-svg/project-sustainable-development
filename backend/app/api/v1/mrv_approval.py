"""MRV approval workflow routes: immutable-after-approval enforcement."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db, role_required
from app.core.config import settings
from app.models.project import Project
from app.models.mrv_report import MRVReport
from app.models.role import RoleName
from app.models.user import User
from app.schemas.mrv_approval import (
    MRVReportCreate,
    MRVReportAdvance,
    MRVReportOut,
    MRVReportSummary,
)
from app.services.mrv_approval_service import (
    create_mrv_report,
    advance_mrv_status,
    get_mrv_report_by_id,
    list_mrv_reports_by_project,
)

router = APIRouter(prefix="/api/v1/mrv-approval", tags=["MRV Approval Workflow"])


def _can_view_all_reports(current_user: User) -> bool:
    if current_user.role is None:
        return False
    return current_user.role.name in {RoleName.ADMIN, RoleName.MRV_OFFICER}


async def _assert_project_access(db: AsyncSession, *, project_id: UUID, current_user: User) -> None:
    if _can_view_all_reports(current_user):
        return

    result = await db.execute(
        select(Project.id).where(Project.id == project_id, Project.created_by == current_user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not authorized for this project")


@router.get("/reports", response_model=list[MRVReportSummary])
async def list_reports(
    project_id: UUID | None = Query(
        None,
        description="Optional filter: only reports for a specific project",
    ),
    status: str | None = Query(
        None,
        description="Optional filter by status: DRAFT, SUBMITTED, VERIFIED, APPROVED, LOCKED",
    ),
    limit: int = Query(50, ge=1, le=200, description="Max reports to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MRVReportSummary]:
    query = select(MRVReport).order_by(MRVReport.created_at.desc()).limit(limit)
    if project_id is not None:
        await _assert_project_access(db, project_id=project_id, current_user=current_user)
        query = query.where(MRVReport.project_id == project_id)
    if status is not None:
        query = query.where(MRVReport.status == status)

    if not _can_view_all_reports(current_user):
        query = query.where(MRVReport.created_by == current_user.id)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/reports", response_model=MRVReportOut, status_code=201)
async def create_report(
    payload: MRVReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        role_required([RoleName.CONTRACTOR, RoleName.PROJECT_MANAGER])
    ),
):
    """
    Create a new MRV report (starts in DRAFT state).
    
    Rules:
    - Status defaults to DRAFT
    - Report is editable until APPROVED
    - CO₂ value locked at creation
    """
    try:
        server_payload = payload.model_copy(update={"created_by": current_user.id})
        return await create_mrv_report(db, server_payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reports/{report_id}/advance", response_model=MRVReportOut)
async def advance_report(
    report_id: UUID,
    payload: MRVReportAdvance,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Advance MRV report to next workflow state (strict progression).
    
    State Machine:
    - DRAFT → SUBMITTED (creator submits)
    - SUBMITTED → VERIFIED (verifier approves samples)
    - VERIFIED → APPROVED (approver locks CO₂ numbers)
    - APPROVED → LOCKED (final immutable state)
    
    Rules:
    - Cannot skip steps
    - Cannot revert after APPROVED
    - Role separation enforced
    - Once APPROVED or LOCKED, report is immutable
    
    Example Transitions:
    - ✅ Valid: DRAFT → SUBMITTED → VERIFIED → APPROVED → LOCKED
    - ❌ Invalid: DRAFT → VERIFIED (skipped SUBMITTED)
    - ❌ Invalid: APPROVED → VERIFIED (reversion blocked)
    - ❌ Invalid: Edit CO₂ after APPROVED (immutability enforced)
    """
    try:
        return await advance_mrv_status(
            db=db,
            report_id=report_id,
            next_status=payload.next_status,
            actor=current_user.id,
            actor_role=current_user.role.name if current_user.role else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reports/{report_id}", response_model=MRVReportOut)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch MRV report by ID (full details)."""
    report = await get_mrv_report_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"MRV report {report_id} not found")

    if not _can_view_all_reports(current_user) and report.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this report")
    return report


@router.get("/projects/{project_id}/reports", response_model=list[MRVReportSummary])
async def list_project_reports(
    project_id: UUID,
    status: str | None = Query(
        None,
        description="Filter by status: DRAFT, SUBMITTED, VERIFIED, APPROVED, LOCKED"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List MRV reports for a project (newest first).
    
    Optional Filters:
    - status: DRAFT, SUBMITTED, VERIFIED, APPROVED, LOCKED
    """
    await _assert_project_access(db, project_id=project_id, current_user=current_user)
    try:
        reports = await list_mrv_reports_by_project(db, project_id, status)
        if _can_view_all_reports(current_user):
            return reports
        return [r for r in reports if r.created_by == current_user.id]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
