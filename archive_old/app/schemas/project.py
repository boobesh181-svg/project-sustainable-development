from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ProjectStatus(str, Enum):
    draft = "draft"
    active = "active"
    in_progress = "in_progress"
    completed = "completed"
    archived = "archived"

class ProjectBase(BaseModel):
    name: str
    status: ProjectStatus = ProjectStatus.draft
    lat: Optional[float] = None
    lon: Optional[float] = None
    budget_usd: float = 0.0

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    name: Optional[str] = None
    status: Optional[ProjectStatus] = None
    budget_usd: Optional[float] = None

class ProjectInDBBase(ProjectBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class Project(ProjectInDBBase):
    pass

class ProjectInDB(ProjectInDBBase):
    pass
