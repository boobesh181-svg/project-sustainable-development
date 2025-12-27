from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import CARBON_FACTORS_BASELINE, CARBON_FACTORS_GREEN, settings
from app.models.anomaly_alert import AnomalyAlert
from app.models.material_token import MaterialToken
from app.models.mrv_report import MRVReport, MRVStatus
from app.models.project import Project
from app.models.sensor_reading import SensorReading, SensorType
from app.schemas.kpi import (
    AnomalyTimelinePoint,
    Co2CostPoint,
    Co2TrendPoint,
    DashboardCharts,
    DistanceBucket,
    MaterialMixSlice,
    SupplierScatterPoint,
)
from app.schemas.project_insights import ProjectImpact


def _to_float(value: float | int | Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1r, lon1r, lat2r, lon2r = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = sin(dlat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371000.0 * c


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _normalize_material_key(code: str | None, name: str | None) -> str:
    key = (code or name or "").strip().lower()
    return key.replace(" ", "_")


def _to_kg(quantity: float, unit: str | None) -> float:
    u = (unit or "").strip().lower()
    if u in {"kg", "kilogram", "kilograms"}:
        return float(quantity)
    if u in {"t", "ton", "tons", "tonne", "tonnes", "metric_ton"}:
        return float(quantity) * 1000.0
    return float(quantity)


async def get_project_charts(db: AsyncSession, project_id: UUID) -> DashboardCharts:
    now = datetime.now(timezone.utc)
    start_12 = _month_start(now - timedelta(days=365))

    embodied_statuses = [MRVStatus.APPROVED, MRVStatus.LOCKED]

    embodied_rows = (
        await db.execute(
            select(
                func.date_trunc("month", MRVReport.created_at).label("m"),
                func.coalesce(func.sum(MRVReport.total_co2e), 0).label("v"),
            )
            .where(
                MRVReport.project_id == project_id,
                MRVReport.created_at >= start_12,
                MRVReport.status.in_(embodied_statuses),
            )
            .group_by("m")
            .order_by("m")
        )
    ).all()
    embodied_by_month = {_month_key(r.m): _to_float(r.v) for r in embodied_rows}

    operational_rows = (
        await db.execute(
            select(
                func.date_trunc("month", SensorReading.ts).label("m"),
                func.coalesce(func.sum(SensorReading.value), 0).label("v"),
            )
            .where(
                SensorReading.project_id == project_id,
                SensorReading.ts >= start_12,
                SensorReading.sensor_type == SensorType.ENERGY,
            )
            .group_by("m")
            .order_by("m")
        )
    ).all()
    operational_by_month = {
        _month_key(r.m): _to_float(r.v) * (settings.GRID_EMISSION_FACTOR / 1000.0)
        for r in operational_rows
    }

    co2_trend: list[Co2TrendPoint] = []
    cursor = _month_start(now)
    for _ in range(12):
        key = _month_key(cursor)
        co2_trend.append(
            Co2TrendPoint(
                month=key,
                embodied=embodied_by_month.get(key, 0.0),
                operational=operational_by_month.get(key, 0.0),
                saved=0.0,
            )
        )
        cursor = _month_start(cursor - timedelta(days=1))
    co2_trend.reverse()

    mix_rows = (
        await db.execute(
            select(
                MaterialToken.material_name,
                func.coalesce(func.sum(MaterialToken.quantity), 0),
            )
            .where(MaterialToken.project_id == project_id)
            .group_by(MaterialToken.material_name)
        )
    ).all()
    material_mix = [
        MaterialMixSlice(material_type=name, qty=_to_float(total)) for name, total in mix_rows
    ]

    an_rows = (
        await db.execute(
            select(func.date(AnomalyAlert.detected_at), func.count(AnomalyAlert.id))
            .where(AnomalyAlert.project_id == project_id, AnomalyAlert.detected_at >= start_12)
            .group_by(func.date(AnomalyAlert.detected_at))
            .order_by(func.date(AnomalyAlert.detected_at))
        )
    ).all()
    anomaly_timeline = [AnomalyTimelinePoint(date=str(d), count=int(c)) for d, c in an_rows]

    project_row = (
        await db.execute(select(Project.lat, Project.lon).where(Project.id == project_id))
    ).one_or_none()
    project_lat = float(project_row[0]) if project_row and project_row[0] is not None else None
    project_lon = float(project_row[1]) if project_row and project_row[1] is not None else None

    redeemed_rows = (
        await db.execute(
            select(MaterialToken.delivery_lat, MaterialToken.delivery_lon)
            .where(
                MaterialToken.project_id == project_id,
                MaterialToken.redeemed.is_(True),
                MaterialToken.delivery_lat.isnot(None),
                MaterialToken.delivery_lon.isnot(None),
            )
        )
    ).all()

    buckets = {
        "0-50m": 0,
        "50-100m": 0,
        "100-200m": 0,
        "200-500m": 0,
        ">500m": 0,
    }

    if project_lat is not None and project_lon is not None:
        for (dl, dn) in redeemed_rows:
            dist = _haversine_m(float(project_lat), float(project_lon), float(dl), float(dn))
            if dist <= 50:
                buckets["0-50m"] += 1
            elif dist <= 100:
                buckets["50-100m"] += 1
            elif dist <= 200:
                buckets["100-200m"] += 1
            elif dist <= 500:
                buckets["200-500m"] += 1
            else:
                buckets[">500m"] += 1

    distance_histogram = [DistanceBucket(bucket_label=k, count=v) for k, v in buckets.items()]

    supplier_rows = (
        await db.execute(
            select(
                MaterialToken.supplier_name,
                func.coalesce(func.sum(MaterialToken.quantity), 0),
                func.count(distinct(MaterialToken.project_id)),
            )
            .where(MaterialToken.project_id == project_id)
            .group_by(MaterialToken.supplier_name)
        )
    ).all()

    supplier_scatter = [
        SupplierScatterPoint(
            supplier=supp,
            total_value=_to_float(total_qty),
            project_count=int(project_count),
        )
        for supp, total_qty, project_count in supplier_rows
    ]

    co2_t = _to_float(
        (
            await db.execute(
                select(func.coalesce(func.sum(MRVReport.total_co2e), 0)).where(
                    MRVReport.project_id == project_id,
                    MRVReport.status.in_(embodied_statuses),
                )
            )
        ).scalar_one()
    )

    proj = (
        await db.execute(
            select(Project.name, func.coalesce(Project.budget_usd, 0)).where(Project.id == project_id)
        )
    ).one()

    co2_cost_scatter = [
        Co2CostPoint(project_name=str(proj[0]), co2_t=co2_t, cost_usd=_to_float(proj[1]))
    ]

    return DashboardCharts(
        co2_trend=co2_trend,
        material_mix=material_mix,
        anomaly_timeline=anomaly_timeline,
        distance_histogram=distance_histogram,
        supplier_scatter=supplier_scatter,
        co2_cost_scatter=co2_cost_scatter,
    )


async def get_project_impact(db: AsyncSession, project_id: UUID) -> ProjectImpact:
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one()

    # Reported embodied CO2 from MRV (approved/locked)
    embodied_statuses = [MRVStatus.APPROVED, MRVStatus.LOCKED]
    reported_embodied_co2_t = _to_float(
        (
            await db.execute(
                select(func.coalesce(func.sum(MRVReport.total_co2e), 0)).where(
                    MRVReport.project_id == project_id,
                    MRVReport.status.in_(embodied_statuses),
                )
            )
        ).scalar_one()
    )

    # Operational CO2 (yearly) from energy sensors for this project
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    energy_sum = _to_float(
        (
            await db.execute(
                select(func.coalesce(func.sum(SensorReading.value), 0)).where(
                    SensorReading.project_id == project_id,
                    SensorReading.sensor_type == SensorType.ENERGY,
                    SensorReading.ts >= one_year_ago,
                )
            )
        ).scalar_one()
    )
    operational_co2_yearly_t = energy_sum * (settings.GRID_EMISSION_FACTOR / 1000.0)

    # Baseline vs green embodied CO2 based on token material factors
    token_rows = (
        await db.execute(
            select(
                MaterialToken.material_code,
                MaterialToken.material_name,
                MaterialToken.quantity,
                MaterialToken.unit,
            ).where(MaterialToken.project_id == project_id)
        )
    ).all()

    baseline_embodied_co2_t = 0.0
    green_embodied_co2_t = 0.0

    for code, name, qty, unit in token_rows:
        key = _normalize_material_key(str(code) if code is not None else None, str(name) if name is not None else None)
        qty_kg = _to_kg(_to_float(qty), str(unit) if unit is not None else None)

        baseline_factor = float(CARBON_FACTORS_BASELINE.get(key, 0.0))
        green_factor = float(CARBON_FACTORS_GREEN.get(key, 0.0))

        baseline_embodied_co2_t += (qty_kg * baseline_factor) / 1000.0
        green_embodied_co2_t += (qty_kg * green_factor) / 1000.0

    embodied_co2_savings_t = max(0.0, baseline_embodied_co2_t - green_embodied_co2_t)

    # Credit value is an estimate; credits are not issued unless the dedicated carbon-credit workflow is enabled.
    assumed_credit_price_usd_per_t = 50.0
    potential_credit_value_usd = embodied_co2_savings_t * assumed_credit_price_usd_per_t

    budget_usd = _to_float(project.budget_usd)
    roi_pct = (potential_credit_value_usd / budget_usd * 100.0) if budget_usd > 0 else 0.0

    lifetime_years = 50

    return ProjectImpact(
        project_id=project.id,
        project_name=project.name,
        lifetime_years=lifetime_years,
        budget_usd=budget_usd,
        baseline_embodied_co2_t=baseline_embodied_co2_t,
        green_embodied_co2_t=green_embodied_co2_t,
        embodied_co2_savings_t=embodied_co2_savings_t,
        reported_embodied_co2_t=reported_embodied_co2_t,
        operational_co2_yearly_t=operational_co2_yearly_t,
        potential_carbon_credits_t=embodied_co2_savings_t,
        assumed_credit_price_usd_per_t=assumed_credit_price_usd_per_t,
        potential_credit_value_usd=potential_credit_value_usd,
        roi_pct=roi_pct,
        methodology_version="token_factors_v1",
        emission_factor_version="config.CARBON_FACTORS_BASELINE/GREEN",
        notes=(
            "Baseline/green embodied CO2 is computed from material tokens using config factor maps. "
            "Unknown materials contribute 0. Reported embodied CO2 is from MRV (approved/locked). "
            "Carbon credits shown are potential credits (not issuance) and use a fixed assumed price." 
        ),
    )
