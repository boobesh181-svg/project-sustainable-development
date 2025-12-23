from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.mrv_report import MRVReport
from app.mrv.models import MRVSample

router = APIRouter(tags=["mrv"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    # Simple DB connectivity check without extra queries
    try:
        await db.execute(select(func.count()))
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"status": "degraded", "error": str(exc)}


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)) -> dict:
    reports_count = (
        await db.execute(select(func.count(MRVReport.id)))
    ).scalar() or 0
    samples_count = (
        await db.execute(select(func.count(MRVSample.sample_id)))
    ).scalar() or 0
    return {
        "reports": int(reports_count),
        "samples": int(samples_count),
    }


@router.get("/reports")
async def list_reports(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Max reports to return"),
) -> dict:
    # Read only from MRVReport snapshots to ensure determinism
    result = await db.execute(
        select(
            MRVReport.id,
            MRVReport.project_id,
            MRVReport.parameter,
            MRVReport.value,
            MRVReport.status,
            MRVReport.ts,
            MRVReport.emission_factor_version_snapshot,
            MRVReport.emission_factor_hash_snapshot,
            MRVReport.emission_factor_value_snapshot,
        )
        .order_by(MRVReport.ts.desc())
        .limit(limit)
    )
    rows = result.all()
    reports = [
        {
            "id": str(r.id),
            "project_id": str(r.project_id),
            "parameter": r.parameter,
            "value": r.value,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "ts": r.ts.isoformat() if r.ts else None,
            "emission_factor_version": r.emission_factor_version_snapshot,
            "emission_factor_hash": r.emission_factor_hash_snapshot,
            "emission_factor_value": (
                float(r.emission_factor_value_snapshot)
                if r.emission_factor_value_snapshot is not None
                else None
            ),
        }
        for r in rows
    ]

    return {"items": reports, "count": len(reports)}
