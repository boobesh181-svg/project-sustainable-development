from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, role_required
from app.models.role import RoleName
from app.models.user import User
from app.schemas.company_summary import CompanyMRVSummary
from app.services.company_summary_service import get_company_mrv_summary

router = APIRouter(prefix="/api/v1/mrv", tags=["mrv"])


@router.get("/company-summary", response_model=CompanyMRVSummary)
async def company_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        role_required([RoleName.ADMIN, RoleName.MRV_OFFICER, RoleName.PROJECT_MANAGER, RoleName.CONTRACTOR])
    ),
) -> CompanyMRVSummary:
    # Read-only summary for authenticated users.
    # Authorization can be tightened later (e.g., admin/mrv_officer) for pilots.
    _ = current_user
    return await get_company_mrv_summary(db)
