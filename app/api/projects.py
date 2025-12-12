from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import Project, User, RoleEnum
from app.schemas.project import ProjectCreate, ProjectUpdate, Project, ProjectInDB
from app.api.deps import get_current_user
from datetime import datetime
import math

router = APIRouter()

@router.get("/", response_model=List[Project])
async def read_projects(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve projects with role-based access control.
    """
    if current_user.role in [RoleEnum.admin, RoleEnum.project_manager]:
        result = await db.execute(select(Project).offset(skip).limit(limit))
    else:
        # For other roles, only show projects they're associated with
        # This is a placeholder - you'll need to implement project-user associations
        result = await db.execute(
            select(Project)
            .where(Project.id.in_([]))  # Add project-user association query here
            .offset(skip).limit(limit)
        )
    return result.scalars().all()

@router.post("/", response_model=Project)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create new project (admin and project_manager only).
    """
    if current_user.role not in [RoleEnum.admin, RoleEnum.project_manager]:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )
    
    db_project = Project(**project_in.dict())
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    return db_project

@router.get("/{project_id}", response_model=Project)
async def read_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get project by ID.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Add permission check here based on project-user associations
    return project

@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a project (admin and project_manager only).
    """
    if current_user.role not in [RoleEnum.admin, RoleEnum.project_manager]:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )
    
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = project_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    await db.commit()
    await db.refresh(project)
    return project

@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a project (admin only).
    """
    if current_user.role != RoleEnum.admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await db.delete(project)
    await db.commit()
    return {"ok": True}
