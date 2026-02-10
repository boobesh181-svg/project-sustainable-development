from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly_alert import AnomalyAlert
from app.models.mrv_report import MRVReport, MRVStatus
from app.models.project import Project
from app.schemas.public import PublicEmissionsTrendPoint, PublicMetricsResponse
from app.services.mrv_calculation_service import authoritative_report_total_co2e


_CACHE_TTL_SECONDS = 30
_cache_lock = asyncio.Lock()
_cache_expires_at_monotonic: float = 0.0
_cache_value: PublicMetricsResponse | None = None


def cache_ttl_seconds() -> int:
    return _CACHE_TTL_SECONDS


def _to_float(value: float | int | Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _add_month(dt: datetime) -> datetime:
    year = dt.year
    month = dt.month + 1
    if month == 13:
        month = 1
        year += 1
    return dt.replace(year=year, month=month)


async def get_public_metrics(db: AsyncSession) -> PublicMetricsResponse:
    """Return strictly aggregated, public-safe KPI metrics.

    Notes:
    - No project/supplier identifiers or names.
    - Emissions trend uses APPROVED+LOCKED MRV reports only (authoritative).
    - A small in-process TTL cache reduces DB load; it is per-worker.
    """

    global _cache_value, _cache_expires_at_monotonic

    now_mono = time.monotonic()
    if _cache_value is not None and now_mono < _cache_expires_at_monotonic:
        return _cache_value

    async with _cache_lock:
        now_mono = time.monotonic()
        if _cache_value is not None and now_mono < _cache_expires_at_monotonic:
            return _cache_value

        total_projects = int((await db.execute(select(func.count(Project.id)))).scalar_one() or 0)

        verified_statuses = [MRVStatus.VERIFIED, MRVStatus.APPROVED, MRVStatus.LOCKED]
        verified_mrvs = int(
            (
                await db.execute(
                    select(func.count(MRVReport.id)).where(MRVReport.status.in_(verified_statuses))
                )
            ).scalar_one()
            or 0
        )

        anomaly_count = int((await db.execute(select(func.count(AnomalyAlert.id)))).scalar_one() or 0)

        # ---- Emissions trend (last 12 months) ----
        now = datetime.now(timezone.utc)
        start_12 = _month_start(now - timedelta(days=365))
        end_month = _month_start(now)

        authoritative_statuses = [MRVStatus.APPROVED, MRVStatus.LOCKED]
        reports = list(
            (
                await db.execute(
                    select(MRVReport)
                    .where(
                        MRVReport.created_at >= start_12,
                        MRVReport.status.in_(authoritative_statuses),
                    )
                    .order_by(MRVReport.created_at.asc(), MRVReport.id.asc())
                )
            )
            .scalars()
            .all()
        )

        by_month_d: dict[str, Decimal] = {}
        for r in reports:
            total, _used_snapshot = authoritative_report_total_co2e(r)
            key = _month_key(r.created_at)
            by_month_d[key] = (by_month_d.get(key, Decimal("0")) + total)

        by_month = {k: _to_float(v) for k, v in by_month_d.items()}

        trend: list[PublicEmissionsTrendPoint] = []
        cur = start_12
        while cur <= end_month:
            key = _month_key(cur)
            trend.append(
                PublicEmissionsTrendPoint(
                    month=key,
                    verified_emissions_tco2e=by_month.get(key, 0.0),
                )
            )
            cur = _add_month(cur)

        result = PublicMetricsResponse(
            total_projects=total_projects,
            verified_mrvs=verified_mrvs,
            emissions_trend=trend,
            anomaly_count=anomaly_count,
        )

        _cache_value = result
        _cache_expires_at_monotonic = time.monotonic() + _CACHE_TTL_SECONDS
        return result
