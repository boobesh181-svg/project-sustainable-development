"""Project service: creation and governance."""

from __future__ import annotations

from fastapi import HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.project import Project, ProjectStatus
from app.schemas.project import ProjectCreate


async def create_project(
    db: AsyncSession,
    payload: ProjectCreate,
    *,
    created_by_user_id,
) -> Project:
    if settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode: project creation is disabled.",
        )

    try:
        status_enum = ProjectStatus(payload.status)
    except ValueError:
        raise ValueError(
            f"Invalid status: {payload.status}. Must be one of: {', '.join([s.value for s in ProjectStatus])}"
        )

    project = Project(
        name=payload.name,
        status=status_enum,
        lat=payload.lat,
        lon=payload.lon,
        budget_usd=payload.budget_usd,
        created_by=created_by_user_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project
