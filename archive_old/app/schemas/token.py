from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class TokenStatus(str, Enum):
    issued = "issued"
    redeemed = "redeemed"
    recycled = "recycled"

class MaterialTokenBase(BaseModel):
    project_id: int
    material_type: str
    qty: float = Field(..., gt=0, description="Quantity in tonnes")
    unit_price: Optional[float] = None
    supplier: Optional[str] = None
    redemption_lat: Optional[float] = None
    redemption_lon: Optional[float] = None

class MaterialTokenCreate(MaterialTokenBase):
    pass

class MaterialTokenUpdate(BaseModel):
    qty: Optional[float] = None
    unit_price: Optional[float] = None
    supplier: Optional[str] = None
    redemption_lat: Optional[float] = None
    redemption_lon: Optional[float] = None
    redeemed: Optional[bool] = None
    recycled: Optional[bool] = None

class MaterialTokenInDBBase(MaterialTokenBase):
    id: int
    issued_at: datetime
    redeemed: bool = False
    recycled: bool = False

    class Config:
        orm_mode = True

class MaterialToken(MaterialTokenInDBBase):
    pass

class MaterialTokenInDB(MaterialTokenInDBBase):
    pass
