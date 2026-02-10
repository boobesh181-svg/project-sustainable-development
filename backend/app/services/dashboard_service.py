from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt

from sqlalchemy import func, select, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectStatus
from app.models.material_token import MaterialToken
from app.models.sensor_reading import SensorReading, SensorType
from app.models.mrv_report import MRVReport
from app.models.anomaly_alert import AnomalyAlert
from app.models.whistleblower import Whistleblower, WhistleblowerStatus
from app.services.mrv_calculation_service import authoritative_report_total_co2e
from app.schemas.kpi import (
    DashboardSummary,
    DashboardCharts,
    Co2TrendPoint,
    MaterialMixSlice,
    AnomalyTimelinePoint,
    DistanceBucket,
    SupplierScatterPoint,
    Co2CostPoint,
)


async def get_dashboard_summary(db: AsyncSession) -> DashboardSummary:
    """Calculate all 12 KPIs using real SQL queries."""
    
    # 1. Active Projects - COUNT(*) WHERE status IN ('active','in_progress')
    active_statuses = [ProjectStatus.ACTIVE, ProjectStatus.IN_PROGRESS]
    active_projects_q = await db.execute(
        select(func.count()).select_from(Project).where(Project.status.in_(active_statuses))
    )
    active_projects = int(active_projects_q.scalar_one() or 0)

    # 2. Total CO₂ Saved (tCO₂e) - SUM(embodied_saved_kg + operational_saved_kg) / 1000
    # Calculate from material tokens and sensor readings
    tokens_co2_q = await db.execute(
        select(func.coalesce(func.sum(
            MaterialToken.qty * 0.5  # Assume 0.5 tCO2 saved per tonne when recycled
        ), 0)).where(MaterialToken.recycled.is_(True))
    )
    tokens_co2_saved = float(tokens_co2_q.scalar_one() or 0)
    
    # Operational CO2 from energy sensors
    energy_co2_q = await db.execute(
        select(func.coalesce(func.sum(
            SensorReading.value * 0.0005  # GRID_FACTOR conversion
        ), 0)).where(SensorReading.sensor_type == SensorType.ENERGY)
    )
    operational_co2_saved = float(energy_co2_q.scalar_one() or 0)
    
    total_co2_saved_t = tokens_co2_saved + operational_co2_saved

    # 3. Estimated Embodied CO₂ - qty * carbon_factor * recycling_factor
    embodied_co2_q = await db.execute(
        select(func.coalesce(func.sum(
            MaterialToken.qty * 1.2 * (0.3 if MaterialToken.recycled else 1.0)
        ), 0))
    )
    estimated_embodied_co2_t = float(embodied_co2_q.scalar_one() or 0)

    # 4. Operational CO₂ (yearly) - SUM(energy_kWh) * GRID_FACTOR / 1000
    operational_yearly_q = await db.execute(
        select(func.coalesce(func.sum(SensorReading.value) * 0.0005, 0))
        .where(SensorReading.sensor_type == SensorType.ENERGY)
    )
    operational_co2_yearly_t = float(operational_yearly_q.scalar_one() or 0)

    # 5. Material Tokens Issued (month) - current month
    current_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    tokens_month_q = await db.execute(
        select(func.count()).select_from(MaterialToken)
        .where(MaterialToken.issued_at >= current_month)
    )
    material_tokens_issued_month = int(tokens_month_q.scalar_one() or 0)

    # 6. Tokens Redeemed (%) - percentage of tokens that are redeemed
    total_tokens_q = await db.execute(select(func.count()).select_from(MaterialToken))
    total_tokens = int(total_tokens_q.scalar_one() or 0)
    
    redeemed_tokens_q = await db.execute(
        select(func.count()).select_from(MaterialToken).where(MaterialToken.redeemed.is_(True))
    )
    redeemed_tokens = int(redeemed_tokens_q.scalar_one() or 0)
    
    tokens_redeemed_pct = (redeemed_tokens / total_tokens * 100) if total_tokens > 0 else 0.0

    # 7. Open Anomalies - where flagged=True and reviewed=False
    open_anomalies_q = await db.execute(
        select(func.count()).select_from(AnomalyAlert)
        .where(AnomalyAlert.flagged.is_(True), AnomalyAlert.reviewed.is_(False))
    )
    open_anomalies = int(open_anomalies_q.scalar_one() or 0)

    # 8. Open Whistleblower Cases
    open_statuses = [WhistleblowerStatus.NEW, WhistleblowerStatus.OPEN]
    open_wb_q = await db.execute(
        select(func.count()).select_from(Whistleblower)
        .where(Whistleblower.status.in_(open_statuses))
    )
    open_whistleblower_cases = int(open_wb_q.scalar_one() or 0)

    # 9. Avg Delivery Geotag Distance (meters)
    # Calculate distance between project location and redemption location
    redeemed_tokens_q = await db.execute(
        select(
            Project.lat,
            Project.lon, 
            MaterialToken.redemption_lat,
            MaterialToken.redemption_lon
        )
        .join(Project, MaterialToken.project_id == Project.id)
        .where(MaterialToken.redeemed.is_(True), 
               MaterialToken.redemption_lat.isnot(None),
               MaterialToken.redemption_lon.isnot(None))
    )
    
    total_distance = 0
    count_distances = 0
    for proj_lat, proj_lon, red_lat, red_lon in redeemed_tokens_q:
        # Haversine distance formula (simplified)
        from math import radians, cos, sin, asin, sqrt
        lat1, lon1, lat2, lon2 = map(radians, [proj_lat, proj_lon, red_lat, red_lon])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        distance = 6371000 * c  # Earth radius in meters
        total_distance += distance
        count_distances += 1
    
    avg_delivery_distance_m = total_distance / count_distances if count_distances > 0 else 0.0

    # 10. Low-carbon Material Fraction (%) - percentage of recycled materials
    low_carbon_q = await db.execute(
        select(func.count()).select_from(MaterialToken).where(MaterialToken.recycled.is_(True))
    )
    low_carbon_count = int(low_carbon_q.scalar_one() or 0)
    low_carbon_material_fraction_pct = (low_carbon_count / total_tokens * 100) if total_tokens > 0 else 0.0

    # 11. Supplier Money Saved - calculate savings from recycled materials
    supplier_savings_q = await db.execute(
        select(func.coalesce(func.sum(
            MaterialToken.qty * MaterialToken.unit_price * 0.2  # 20% savings assumption
        ), 0)).where(MaterialToken.recycled.is_(True), MaterialToken.unit_price.isnot(None))
    )
    supplier_money_saved_usd = float(supplier_savings_q.scalar_one() or 0)

    # 12. Project Budget Utilization (%) - spent vs total budget
    budget_utilization_q = await db.execute(
        select(
            func.coalesce(func.sum(Project.budget_usd), 0),
            func.count()
        ).where(Project.budget_usd.isnot(None))
    )
    total_budget, budget_count = budget_utilization_q.first()
    total_budget = float(total_budget or 0)
    
    # Estimate spent as 70% of budget for active projects
    spent_budget = total_budget * 0.7 if active_projects > 0 else 0
    project_budget_utilization_pct = (spent_budget / total_budget * 100) if total_budget > 0 else 0.0

    return DashboardSummary(
        active_projects=active_projects,
        total_co2_saved_t=total_co2_saved_t,
        estimated_embodied_co2_t=estimated_embodied_co2_t,
        operational_co2_yearly_t=operational_co2_yearly_t,
        material_tokens_issued_month=material_tokens_issued_month,
        tokens_redeemed_pct=tokens_redeemed_pct,
        open_anomalies=open_anomalies,
        open_whistleblower_cases=open_whistleblower_cases,
        avg_delivery_distance_m=avg_delivery_distance_m,
        low_carbon_material_fraction_pct=low_carbon_material_fraction_pct,
        supplier_money_saved_usd=supplier_money_saved_usd,
        project_budget_utilization_pct=project_budget_utilization_pct,
    )


async def get_dashboard_charts(db: AsyncSession) -> DashboardCharts:
    """Compute chart-friendly aggregations from existing seed data."""

    # ---- CO2 Trend (12 months) ----
    # Get last 12 months of material tokens and sensor data
    co2_trend: list[Co2TrendPoint] = []
    for i in range(12):
        month_date = datetime.now().replace(day=1) - timedelta(days=30*i)
        month_str = month_date.strftime("%Y-%m")
        
        # Embodied CO2 from materials
        embodied_q = await db.execute(
            select(func.coalesce(func.sum(MaterialToken.qty), 0))
            .where(func.strftime("%Y-%m", MaterialToken.issued_at) == month_str)
        )
        embodied = float(embodied_q.scalar_one() or 0) * 1.2
        
        # Operational CO2 from energy sensors
        operational_q = await db.execute(
            select(func.coalesce(func.sum(SensorReading.value), 0))
            .where(
                func.strftime("%Y-%m", SensorReading.ts) == month_str,
                SensorReading.sensor_type == SensorType.ENERGY
            )
        )
        operational = float(operational_q.scalar_one() or 0) * 0.0005
        
        # Saved CO2 (recycled materials + energy efficiency)
        saved_q = await db.execute(
            select(func.coalesce(func.sum(MaterialToken.qty), 0))
            .where(
                func.strftime("%Y-%m", MaterialToken.issued_at) == month_str,
                MaterialToken.recycled.is_(True)
            )
        )
        saved = float(saved_q.scalar_one() or 0) * 0.5
        
        co2_trend.append(Co2TrendPoint(month=month_str, embodied=embodied, operational=operational, saved=saved))

    # ---- Material Mix donut ----
    mix_rows = (
        await db.execute(
            select(MaterialToken.material_type, func.coalesce(func.sum(MaterialToken.qty), 0))
            .group_by(MaterialToken.material_type)
        )
    ).all()
    material_mix = [
        MaterialMixSlice(material_type=mt, qty=float(qty or 0)) for mt, qty in mix_rows
    ]

    # ---- Anomalies Timeline ----
    an_rows = (
        await db.execute(
            select(
                func.date(AnomalyAlert.created_at),
                func.count(),
            ).group_by(func.date(AnomalyAlert.created_at))
            .order_by(func.date(AnomalyAlert.created_at))
        )
    ).all()
    anomaly_timeline = [
        AnomalyTimelinePoint(date=str(d), count=int(c)) for d, c in an_rows
    ]

    # ---- Delivery Distance Histogram ----
    # Calculate actual distances from redeemed tokens
    redeemed_tokens_q = await db.execute(
        select(
            Project.lat,
            Project.lon, 
            MaterialToken.redemption_lat,
            MaterialToken.redemption_lon
        )
        .join(Project, MaterialToken.project_id == Project.id)
        .where(MaterialToken.redeemed.is_(True), 
               MaterialToken.redemption_lat.isnot(None),
               MaterialToken.redemption_lon.isnot(None))
    )
    
    distances = []
    for proj_lat, proj_lon, red_lat, red_lon in redeemed_tokens_q:
        from math import radians, cos, sin, asin, sqrt
        lat1, lon1, lat2, lon2 = map(radians, [proj_lat, proj_lon, red_lat, red_lon])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        distance = 6371000 * c  # Earth radius in meters
        distances.append(distance)
    
    # Create histogram buckets
    distance_histogram = [
        DistanceBucket(bucket_label="0-1km", count=len([d for d in distances if d <= 1000])),
        DistanceBucket(bucket_label="1-5km", count=len([d for d in distances if 1000 < d <= 5000])),
        DistanceBucket(bucket_label="5-20km", count=len([d for d in distances if 5000 < d <= 20000])),
        DistanceBucket(bucket_label="20km+", count=len([d for d in distances if d > 20000])),
    ]

    # ---- Supplier Risk Scatter ----
    # Calculate supplier performance metrics
    supplier_data_q = await db.execute(
        select(
            MaterialToken.supplier,
            func.count(MaterialToken.id).label('project_count'),
            func.coalesce(func.sum(MaterialToken.qty * MaterialToken.unit_price), 0).label('total_value'),
            func.coalesce(func.sum(func.cast(MaterialToken.recycled, Integer) * MaterialToken.qty), 0).label('recycled_qty')
        )
        .where(MaterialToken.supplier.isnot(None))
        .group_by(MaterialToken.supplier)
    )
    
    supplier_scatter = []
    for supplier, project_count, total_value, recycled_qty in supplier_data_q:
        total_qty = float(recycled_qty or 0)
        risk_score = max(0, 100 - (total_qty / max(project_count, 1) * 10))  # Simple risk calculation
        supplier_scatter.append(
            SupplierScatterPoint(supplier=supplier, total_value=float(total_value), project_count=int(project_count))
        )

    # ---- CO2 vs Cost Scatter ----
    proj_budget_rows = (
        await db.execute(
            select(
                Project.name,
                Project.budget_usd,
                func.coalesce(func.sum(MaterialToken.qty), 0).label('total_materials')
            )
            .outerjoin(MaterialToken, Project.id == MaterialToken.project_id)
            .group_by(Project.id, Project.name, Project.budget_usd)
        )
    ).all()
    
    co2_cost_scatter = []
    for name, budget, total_materials in proj_budget_rows:
        budget_val = float(budget or 0)
        materials_val = float(total_materials or 0)
        # Estimate CO2 based on material quantity and budget
        co2_est = (materials_val * 1.2) + (budget_val / 10000.0) if budget_val > 0 else materials_val * 1.2
        co2_cost_scatter.append(
            Co2CostPoint(project_name=name, co2_t=co2_est, cost_usd=budget_val)
        )

    return DashboardCharts(
        co2_trend=co2_trend,
        material_mix=material_mix,
        anomaly_timeline=anomaly_timeline,
        distance_histogram=distance_histogram,
        supplier_scatter=supplier_scatter,
        co2_cost_scatter=co2_cost_scatter,
    )


async def get_comprehensive_kpis(db: AsyncSession) -> dict:
    """
    Comprehensive KPI aggregation for national-scale dashboards.
    
    Provides:
    - Core metrics: projects, tokens, deliveries, MRV reports, CO₂
    - Integrity metrics: verification rates, approval rates, high-risk anomalies
    - Scalable to national datasets (optimized aggregations)
    
    This is the single source of truth for dashboard consumption.
    Frontend performs NO business logic - all aggregations done server-side.
    """
    from app.models.delivery_verification import DeliveryVerification
    from app.models.mrv_report import MRVStatus

    # CORE KPIs
    
    # Total projects
    total_projects_q = await db.execute(select(func.count()).select_from(Project))
    total_projects = int(total_projects_q.scalar_one() or 0)

    # Material tokens
    total_tokens_q = await db.execute(select(func.count()).select_from(MaterialToken))
    total_tokens = int(total_tokens_q.scalar_one() or 0)

    redeemed_tokens_q = await db.execute(
        select(func.count()).select_from(MaterialToken).where(MaterialToken.redeemed.is_(True))
    )
    redeemed_tokens = int(redeemed_tokens_q.scalar_one() or 0)

    # Deliveries verified
    verified_deliveries_q = await db.execute(
        select(func.count()).select_from(DeliveryVerification)
        .where(DeliveryVerification.is_verified.is_(True))
    )
    verified_deliveries = int(verified_deliveries_q.scalar_one() or 0)

    # MRV reports (by status)
    mrv_total_q = await db.execute(select(func.count()).select_from(MRVReport))
    mrv_total = int(mrv_total_q.scalar_one() or 0)

    mrv_draft_q = await db.execute(
        select(func.count()).select_from(MRVReport).where(MRVReport.status == MRVStatus.DRAFT)
    )
    mrv_draft = int(mrv_draft_q.scalar_one() or 0)

    mrv_submitted_q = await db.execute(
        select(func.count()).select_from(MRVReport).where(MRVReport.status == MRVStatus.SUBMITTED)
    )
    mrv_submitted = int(mrv_submitted_q.scalar_one() or 0)

    mrv_verified_q = await db.execute(
        select(func.count()).select_from(MRVReport).where(MRVReport.status == MRVStatus.VERIFIED)
    )
    mrv_verified = int(mrv_verified_q.scalar_one() or 0)

    mrv_approved_q = await db.execute(
        select(func.count()).select_from(MRVReport).where(MRVReport.status == MRVStatus.APPROVED)
    )
    mrv_approved = int(mrv_approved_q.scalar_one() or 0)

    mrv_locked_q = await db.execute(
        select(func.count()).select_from(MRVReport).where(MRVReport.status == MRVStatus.LOCKED)
    )
    mrv_locked = int(mrv_locked_q.scalar_one() or 0)

    # Total CO₂ reported (only APPROVED + LOCKED)
    approved_locked_statuses = [MRVStatus.APPROVED, MRVStatus.LOCKED]
    approved_locked_reports = list(
        (
            await db.execute(
                select(MRVReport)
                .where(MRVReport.status.in_(approved_locked_statuses))
                .order_by(MRVReport.created_at.asc(), MRVReport.id.asc())
            )
        )
        .scalars()
        .all()
    )
    total_co2_d = Decimal("0")
    for r in approved_locked_reports:
        total, _used_snapshot = authoritative_report_total_co2e(r)
        total_co2_d += total
    total_co2_tco2e = float(total_co2_d)

    # Anomalies (by severity)
    from app.models.anomaly_alert import AnomalySeverity
    
    anomalies_total_q = await db.execute(select(func.count()).select_from(AnomalyAlert))
    anomalies_total = int(anomalies_total_q.scalar_one() or 0)

    anomalies_high_q = await db.execute(
        select(func.count()).select_from(AnomalyAlert).where(AnomalyAlert.severity == AnomalySeverity.HIGH)
    )
    anomalies_high = int(anomalies_high_q.scalar_one() or 0)

    anomalies_medium_q = await db.execute(
        select(func.count()).select_from(AnomalyAlert).where(AnomalyAlert.severity == AnomalySeverity.MEDIUM)
    )
    anomalies_medium = int(anomalies_medium_q.scalar_one() or 0)

    anomalies_low_q = await db.execute(
        select(func.count()).select_from(AnomalyAlert).where(AnomalyAlert.severity == AnomalySeverity.LOW)
    )
    anomalies_low = int(anomalies_low_q.scalar_one() or 0)

    # INTEGRITY KPIs

    # % tokens verified (delivery verification rate)
    verified_percent = round((verified_deliveries / redeemed_tokens) * 100, 2) if redeemed_tokens > 0 else 0.0

    # % MRV approved (approval rate)
    mrv_approval_percent = round((mrv_approved / mrv_total) * 100, 2) if mrv_total > 0 else 0.0

    # High-risk anomaly count
    high_risk_count = anomalies_high

    return {
        "projects": total_projects,
        "tokens": {
            "issued": total_tokens,
            "redeemed": redeemed_tokens,
            "verified_percent": verified_percent,
        },
        "deliveries_verified": verified_deliveries,
        "mrv": {
            "total": mrv_total,
            "draft": mrv_draft,
            "submitted": mrv_submitted,
            "verified": mrv_verified,
            "approved": mrv_approved,
            "locked": mrv_locked,
            "approval_percent": mrv_approval_percent,
        },
        "co2": {
            "total_reported_tco2e": round(total_co2_tco2e, 2),
        },
        "anomalies": {
            "total": anomalies_total,
            "high": anomalies_high,
            "medium": anomalies_medium,
            "low": anomalies_low,
            "high_risk_count": high_risk_count,
        },
    }
