from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProjectBase(BaseModel):
    name: str
    status: str
    lat: float
    lon: float
    budget_usd: float | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: UUID
    created_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True
