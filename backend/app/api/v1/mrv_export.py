from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, role_required
from app.models.role import RoleName
from app.models.user import User
from app.services.iso_export_service import build_iso_compliance_package, build_iso_export_payload
from app.services.mrv_report_export_service import build_mrv_report_export_package


router = APIRouter(prefix="/api/v1/mrv/export", tags=["mrv"])


@router.get("/iso")
async def export_iso(
    format: str = Query(
        "zip",
        description="Export format: zip (json+csv), json",
        pattern="^(zip|json)$",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        role_required([RoleName.ADMIN, RoleName.MRV_OFFICER, RoleName.PROJECT_MANAGER])
    ),
):
    _ = current_user

    try:
        if format == "json":
            payload = await build_iso_export_payload(db)
            return JSONResponse(payload)

        pkg = await build_iso_compliance_package(db, include_csv=True, include_json=True)

        return StreamingResponse(
            iter([pkg.data]),
            media_type=pkg.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{pkg.filename}"',
                "Cache-Control": "no-store",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build compliance export: {e}")


@router.get("/{report_id}")
async def export_mrv_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        role_required([RoleName.ADMIN, RoleName.MRV_OFFICER, RoleName.PROJECT_MANAGER])
    ),
):
    """Deterministic per-report compliance export.

    Rules:
    - Only APPROVED/LOCKED reports
    - Deterministic output: stable ordering, fixed ZIP metadata, no wall-clock timestamps
    - Includes: MRV summary, emission factor snapshot, audit trail, evidence hashes
    - DEMO watermark file if DEMO_MODE=true
    """
    _ = current_user

    pkg = await build_mrv_report_export_package(db, report_id)
    return StreamingResponse(
        iter([pkg.data]),
        media_type=pkg.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{pkg.filename}"',
            "Cache-Control": "no-store",
        },
    )
