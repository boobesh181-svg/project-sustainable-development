from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, role_required
from app.models.project import Project, ProjectStatus
from app.models.role import RoleName
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectRead
from app.schemas.kpi import DashboardCharts
from app.schemas.project_insights import ProjectImpact
from app.services.project_insights_service import get_project_charts, get_project_impact

router = APIRouter()


def _can_view_all_projects(current_user: User) -> bool:
    if current_user.role is None:
        return False
    return current_user.role.name in {RoleName.ADMIN, RoleName.MRV_OFFICER}


async def _get_project_for_user(db: AsyncSession, project_id: UUID, current_user: User) -> Project:
    stmt = select(Project).where(Project.id == project_id)
    if not _can_view_all_projects(current_user):
        stmt = stmt.where(Project.created_by == current_user.id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/", response_model=list[ProjectRead])
async def list_projects(
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Project]:
    stmt = select(Project).order_by(Project.created_at.desc()).limit(limit)
    if not _can_view_all_projects(current_user):
        stmt = stmt.where(Project.created_by == current_user.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    return await _get_project_for_user(db, project_id, current_user)


@router.get("/{project_id}/charts", response_model=DashboardCharts)
async def project_charts(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardCharts:
    await _get_project_for_user(db, project_id, current_user)
    return await get_project_charts(db, project_id)


@router.get("/{project_id}/impact", response_model=ProjectImpact)
async def project_impact(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectImpact:
    await _get_project_for_user(db, project_id, current_user)
    return await get_project_impact(db, project_id)


@router.post("/", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.PROJECT_MANAGER])),
) -> Project:
    try:
        status_enum = ProjectStatus(payload.status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {payload.status}. Must be one of: {', '.join([s.value for s in ProjectStatus])}",
        )

    project = Project(
        name=payload.name,
        status=status_enum,
        lat=payload.lat,
        lon=payload.lon,
        budget_usd=payload.budget_usd,
        created_by=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project
