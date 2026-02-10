from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, role_required
from app.models.methodology_version import MethodologyVersion
from app.models.organization import Organization
from app.models.organization_relationship import OrganizationRelationship, OrganizationRoleType
from app.models.report_view import ReportView
from app.models.reporting_context import ConsolidationMethod, ReportingContext, ReportingPurpose
from app.models.role import RoleName
from app.models.user import User
from app.schemas.accounting import (
    MethodologyVersionCreate,
    MethodologyVersionOut,
    OrganizationCreate,
    OrganizationOut,
    OrganizationRelationshipCreate,
    OrganizationRelationshipOut,
    ReportGenerateRequest,
    ReportViewExportOut,
    ReportViewOut,
    ReportingContextCreate,
    ReportingContextOut,
)
from app.services.accounting_report_service import export_report_view, generate_report_view

router = APIRouter(tags=["Accounting Context"])


# -------------------- Reference data (append-only) --------------------


@router.post("/api/v1/accounting/organizations", response_model=OrganizationOut, status_code=201)
async def create_organization(
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.MRV_OFFICER])),
):
    _ = current_user
    org = Organization(name=payload.name)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@router.get("/api/v1/accounting/organizations", response_model=list[OrganizationOut])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    rows = (await db.execute(select(Organization).order_by(Organization.name.asc()))).scalars().all()
    return list(rows)


@router.post("/api/v1/accounting/methodologies", response_model=MethodologyVersionOut, status_code=201)
async def create_methodology_version(
    payload: MethodologyVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.MRV_OFFICER])),
):
    _ = current_user
    m = MethodologyVersion(code=payload.code, description=payload.description)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@router.get("/api/v1/accounting/methodologies", response_model=list[MethodologyVersionOut])
async def list_methodology_versions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    rows = (
        await db.execute(select(MethodologyVersion).order_by(MethodologyVersion.created_at.desc()))
    ).scalars().all()
    return list(rows)


@router.post("/api/v1/accounting/contexts", response_model=ReportingContextOut, status_code=201)
async def create_reporting_context(
    payload: ReportingContextCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.MRV_OFFICER, RoleName.PROJECT_MANAGER])),
):
    _ = current_user
    ctx = ReportingContext(
        reporting_entity_id=payload.reporting_entity_id,
        consolidation_method=ConsolidationMethod(payload.consolidation_method),
        reporting_purpose=ReportingPurpose(payload.reporting_purpose),
        methodology_version_id=payload.methodology_version_id,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    db.add(ctx)
    await db.commit()
    await db.refresh(ctx)
    return ctx


@router.get("/api/v1/accounting/contexts", response_model=list[ReportingContextOut])
async def list_reporting_contexts(
    reporting_entity_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    stmt = select(ReportingContext)
    if reporting_entity_id is not None:
        stmt = stmt.where(ReportingContext.reporting_entity_id == reporting_entity_id)
    rows = (
        await db.execute(stmt.order_by(ReportingContext.created_at.desc()).limit(200))
    ).scalars().all()
    return list(rows)


@router.post(
    "/api/v1/accounting/relationships",
    response_model=OrganizationRelationshipOut,
    status_code=201,
)
async def create_organization_relationship(
    payload: OrganizationRelationshipCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.MRV_OFFICER, RoleName.PROJECT_MANAGER])),
):
    _ = current_user
    rel = OrganizationRelationship(
        project_id=payload.project_id,
        organization_id=payload.organization_id,
        role_type=OrganizationRoleType(payload.role_type),
        ownership_percentage=float(payload.ownership_percentage) if payload.ownership_percentage is not None else None,
        financial_control=payload.financial_control,
        operational_control=payload.operational_control,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    db.add(rel)
    await db.commit()
    await db.refresh(rel)
    return rel


@router.get(
    "/api/v1/accounting/projects/{project_id}/relationships",
    response_model=list[OrganizationRelationshipOut],
)
async def list_project_relationships(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    rows = (
        await db.execute(
            select(OrganizationRelationship)
            .where(OrganizationRelationship.project_id == project_id)
            .order_by(OrganizationRelationship.valid_from.desc(), OrganizationRelationship.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


# -------------------- Report generation + export --------------------


@router.post("/api/v1/reports/generate", response_model=ReportViewOut, status_code=201)
@router.post("/reports/generate", response_model=ReportViewOut, status_code=201)
async def generate_report(
    payload: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(role_required([RoleName.ADMIN, RoleName.MRV_OFFICER, RoleName.PROJECT_MANAGER])),
):
    _ = current_user
    view = await generate_report_view(
        db,
        project_id=payload.project_id,
        reporting_context_id=payload.reporting_context_id,
    )
    return view


@router.get("/api/v1/reports/views/{report_view_id}", response_model=ReportViewOut)
@router.get("/reports/views/{report_view_id}", response_model=ReportViewOut)
async def get_report_view(
    report_view_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    view = await db.get(ReportView, report_view_id)
    if view is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Report view not found")
    return view


@router.get("/api/v1/reports/views/{report_view_id}/export", response_model=ReportViewExportOut)
@router.get("/reports/views/{report_view_id}/export", response_model=ReportViewExportOut)
async def export_view(
    report_view_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    payload = await export_report_view(db, report_view_id=report_view_id)
    return ReportViewExportOut(
        report_view=ReportViewOut(**payload["report_view"]),
        reporting_context=ReportingContextOut(**payload["reporting_context"]),
        methodology_version=MethodologyVersionOut(**payload["methodology_version"]),
        reporting_entity=OrganizationOut(**payload["reporting_entity"]),
        boundary_method=payload["boundary_method"],
        reporting_purpose=payload["reporting_context"]["reporting_purpose"],
        calculation_timestamp=payload["calculation_timestamp"],
        total_emissions=payload["total_emissions"],
        calculation_hash=payload["calculation_hash"],
    )
