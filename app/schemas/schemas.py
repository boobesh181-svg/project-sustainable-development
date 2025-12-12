from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: int
    exp: int

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "citizen"

class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    role: str

    class Config:
        orm_mode = True

class ProjectCreate(BaseModel):
    name: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    budget_usd: float = 0.0
    status: str = "draft"

class ProjectOut(ProjectCreate):
    id: int

    class Config:
        orm_mode = True

class MaterialTokenCreate(BaseModel):
    project_id: int
    material_type: str
    qty: float
    unit_price: Optional[float] = None
    supplier: Optional[str] = None

class MaterialTokenOut(MaterialTokenCreate):
    id: int
    issued_at: datetime
    redeemed: bool = False
    recycled: bool = False

    class Config:
        orm_mode = True

class SensorReadingCreate(BaseModel):
    project_id: int
    sensor_type: str
    value: float
    unit: str

class SensorReadingOut(SensorReadingCreate):
    id: int
    ts: datetime

    class Config:
        orm_mode = True

class MRVReportCreate(BaseModel):
    project_id: int
    parameter: str
    value: str

class MRVReportOut(MRVReportCreate):
    id: int
    status: str
    ts: datetime
    certificate_path: Optional[str] = None

    class Config:
        orm_mode = True

class AnomalyAlertCreate(BaseModel):
    project_id: int
    entity_type: Optional[str] = None
    score: float = 0.0
    rule_score: float = 0.0
    ml_score: float = 0.0
    payload: Optional[dict] = None

class AnomalyAlertOut(AnomalyAlertCreate):
    id: int
    flagged: bool = False
    reviewed: bool = False
    created_at: datetime

    class Config:
        orm_mode = True

class WhistleblowerCreate(BaseModel):
    project_id: Optional[int] = None
    message: str
    priority: str = "medium"

class WhistleblowerOut(WhistleblowerCreate):
    id: int
    status: str = "new"
    created_at: datetime
    evidence_path: Optional[str] = None

    class Config:
        orm_mode = True
