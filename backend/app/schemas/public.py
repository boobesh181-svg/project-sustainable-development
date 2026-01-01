from __future__ import annotations

from pydantic import BaseModel, Field


class PublicEmissionsTrendPoint(BaseModel):
    month: str = Field(..., description="YYYY-MM")
    verified_emissions_tco2e: float


class PublicMetricsResponse(BaseModel):
    total_projects: int
    verified_mrvs: int
    emissions_trend: list[PublicEmissionsTrendPoint]
    anomaly_count: int
