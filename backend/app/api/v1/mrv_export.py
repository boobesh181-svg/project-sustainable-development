from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, role_required
from app.models.role import RoleName
from app.models.user import User
from app.services.iso_export_service import build_iso_compliance_package, build_iso_export_payload


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
