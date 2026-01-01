"""Pydantic schemas for material tokens (anti-corruption core)."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class MaterialTokenCreate(BaseModel):
    """Issue a new material token (unredemed state)."""
    project_id: UUID
    material_code: str = Field(..., min_length=1, max_length=100)
    material_name: str = Field(..., min_length=1, max_length=255)
    quantity: float = Field(..., gt=0, description="Quantity in specified unit")
    unit: str = Field(default="kg", max_length=50)
    supplier_name: str = Field(..., min_length=1, max_length=255)
    supplier_id: UUID | None = Field(
        None, description="Optional supplier FK for real-world ingestion"
    )
    issued_by: str = Field(..., min_length=1, max_length=100)


class MaterialTokenRedeem(BaseModel):
    """Redeem a material token with delivery evidence."""
    delivery_lat: float = Field(..., ge=-90, le=90)
    delivery_lon: float = Field(..., ge=-180, le=180)
    supplier_invoice_ref: str = Field(..., min_length=1, max_length=100)
    batch_id: str | None = Field(None, max_length=100)
    delivery_timestamp: datetime | None = Field(
        None, description="Supplier-reported delivery timestamp"
    )


class MaterialTokenOut(BaseModel):
    """Material token response (full details)."""
    id: UUID
    token_uid: str
    project_id: UUID
    material_code: str
    material_name: str
    quantity: float
    unit: str
    supplier_name: str
    supplier_id: UUID | None
    batch_id: str | None
    issued_at: datetime
    issued_by: str
    redeemed: bool
    redeemed_at: datetime | None
    delivery_timestamp: datetime | None
    delivery_photo_path: str | None
    delivery_lat: float | None
    delivery_lon: float | None
    supplier_invoice_ref: str | None
    
    model_config = ConfigDict(from_attributes=True)

