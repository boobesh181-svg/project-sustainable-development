from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.kpi import DashboardSummary, DashboardCharts
from app.services.dashboard_service_v2 import get_dashboard_summary, get_dashboard_charts
from app.services.dashboard_service import get_comprehensive_kpis
from app.models.user import User

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
  db: AsyncSession = Depends(get_db),
  current_user: User = Depends(get_current_user),
) -> DashboardSummary:
    """
    Get dashboard summary (12 KPIs including CO₂, tokens, anomalies).
    
    Returns legacy DashboardSummary schema for backward compatibility.
    """
    return await get_dashboard_summary(db)


@router.get("/charts", response_model=DashboardCharts)
async def dashboard_charts(
  db: AsyncSession = Depends(get_db),
  current_user: User = Depends(get_current_user),
) -> DashboardCharts:
    """
    Get dashboard charts data (trends, material mix, anomaly timeline, etc.).
    
    Returns comprehensive chart data for visualizations.
    """
    return await get_dashboard_charts(db)


@router.get("/kpis")
async def comprehensive_kpis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Comprehensive KPI aggregation for national-scale dashboards.
    
    Single source of truth for all dashboard metrics:
    - Core KPIs: projects, tokens issued/redeemed, deliveries verified, MRV reports, CO₂
    - Integrity KPIs: verification %, approval %, high-risk anomalies
    - Scalable to national datasets (optimized SQL aggregations)
    
    Frontend consumes this endpoint - NO business logic on UI.
    
    Returns:
    ```json
    {
      "projects": 3,
      "tokens": {
        "issued": 45,
        "redeemed": 40,
        "verified_percent": 92.5
      },
      "deliveries_verified": 37,
      "mrv": {
        "total": 6,
        "draft": 1,
        "submitted": 1,
        "verified": 0,
        "approved": 3,
        "locked": 1,
        "approval_percent": 66.67
      },
      "co2": {
        "total_reported_tco2e": 18450.25
      },
      "anomalies": {
        "total": 9,
        "high": 2,
        "medium": 5,
        "low": 2,
        "high_risk_count": 2
      }
    }
    ```
    """
    return await get_comprehensive_kpis(db)
