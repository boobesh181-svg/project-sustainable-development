from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectBase(BaseModel):
    name: str
    status: str
    lat: float
    lon: float
    budget_usd: float | None = None
    pilot: bool = False


class ProjectCreate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: UUID
    created_by: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
