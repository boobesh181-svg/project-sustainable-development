from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.kpi import DashboardSummary, DashboardCharts
from app.services.dashboard_service import get_dashboard_summary, get_dashboard_charts

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(db: AsyncSession = Depends(get_db)) -> DashboardSummary:
    return await get_dashboard_summary(db)


@router.get("/charts", response_model=DashboardCharts)
async def dashboard_charts(db: AsyncSession = Depends(get_db)) -> DashboardCharts:
    return await get_dashboard_charts(db)
