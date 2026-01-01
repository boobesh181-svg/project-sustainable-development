from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.public import PublicMetricsResponse
from app.services import public_metrics_service

router = APIRouter()


@router.get("/metrics", response_model=PublicMetricsResponse)
async def get_public_metrics(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> PublicMetricsResponse:
    ttl = public_metrics_service.cache_ttl_seconds()
    response.headers["Cache-Control"] = f"public, max-age={ttl}"
    return await public_metrics_service.get_public_metrics(db)
