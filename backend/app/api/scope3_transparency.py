from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, or_

from app.db.session import get_db
from app.models.scope3_materials import MaterialCategory, EmissionFactor, ActivityData
from app.models.scope3_boundaries import ProjectBoundary
from app.models.scope3_verification import VerificationRecord, GovernmentApproval
from app.models.scope3_credits import CarbonCredit
from app.models.projects import Project
from app.schemas.transparency import (
    ProjectStatusResponse,
    MaterialCategoryResponse,
    MethodologyInfoResponse,
    VerificationStateResponse,
    PublicProjectSummary
)

router = APIRouter()


@router.get("/projects/status", response_model=List[ProjectStatusResponse])
async def get_project_status(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for project status information.
    No authentication required - read-only public data.
    """
    query = select(
        Project.id,
        Project.name,
        Project.description,
        Project.status,
        Project.created_at,
        ProjectBoundary.status.label("boundary_status"),
        func.count(ActivityData.id).label("activity_data_count"),
        func.sum(ActivityData.co2_calculated).label("total_co2")
    ).select_from(
        Project.__table__.outerjoin(
            ProjectBoundary, Project.id == ProjectBoundary.project_id
        ).outerjoin(
            ActivityData, Project.id == ActivityData.project_id
        )
    ).group_by(
        Project.id, Project.name, Project.description, 
        Project.status, Project.created_at, ProjectBoundary.status
    ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    projects = result.all()
    
    return [
        ProjectStatusResponse(
            project_id=str(project.id),
            project_name=project.name,
            project_description=project.description or "",
            project_status=project.status,
            boundary_status=project.boundary_status or "not_set",
            activity_data_count=project.activity_data_count or 0,
            total_co2_tonnes=float(project.total_co2 or 0),
            created_at=project.created_at
        )
        for project in projects
    ]


@router.get("/materials/categories", response_model=List[MaterialCategoryResponse])
async def get_material_categories(
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for material categories covered by the MRV system.
    """
    query = select(
        MaterialCategory.id,
        MaterialCategory.name,
        MaterialCategory.description,
        MaterialCategory.standardized_unit,
        func.count(EmissionFactor.id).label("emission_factor_count")
    ).outerjoin(
        EmissionFactor, MaterialCategory.id == EmissionFactor.material_category_id
    ).group_by(
        MaterialCategory.id, MaterialCategory.name, 
        MaterialCategory.description, MaterialCategory.standardized_unit
    ).order_by(MaterialCategory.name)
    
    result = await db.execute(query)
    categories = result.all()
    
    return [
        MaterialCategoryResponse(
            category_id=str(category.id),
            category_name=category.name.value,
            description=category.description or "",
            standardized_unit=category.standardized_unit.value,
            emission_factor_count=category.emission_factor_count or 0
        )
        for category in categories
    ]


@router.get("/methodology/info", response_model=MethodologyInfoResponse)
async def get_methodology_info(
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for methodology version and standards information.
    """
    # Get latest methodology version from project boundaries
    methodology_query = select(
        ProjectBoundary.methodology_version,
        ProjectBoundary.emission_factor_version,
        func.count(ProjectBoundary.id).label("project_count")
    ).group_by(
        ProjectBoundary.methodology_version,
        ProjectBoundary.emission_factor_version
    ).order_by(ProjectBoundary.methodology_version.desc())
    
    methodology_result = await db.execute(methodology_query)
    methodology_info = methodology_result.first()
    
    # Get emission factor statistics
    factor_query = select(
        func.count(EmissionFactor.id).label("total_factors"),
        func.count(func.distinct(EmissionFactor.material_category_id)).label("categories_covered"),
        func.count(func.distinct(EmissionFactor.supplier_id)).label("suppliers_contributing")
    )
    
    factor_result = await db.execute(factor_query)
    factor_stats = factor_result.first()
    
    return MethodologyInfoResponse(
        methodology_version=methodology_info.methodology_version if methodology_info else "v1.0",
        emission_factor_version=methodology_info.emission_factor_version if methodology_info else "v1.0",
        projects_using_methodology=methodology_info.project_count if methodology_info else 0,
        total_emission_factors=factor_stats.total_factors or 0,
        material_categories_covered=factor_stats.categories_covered or 0,
        contributing_suppliers=factor_stats.suppliers_contributing or 0,
        compliance_standards=["ISO 14064-1:2018", "GHG Protocol Corporate Standard"],
        last_updated=datetime.utcnow()
    )


@router.get("/verification/state", response_model=List[VerificationStateResponse])
async def get_verification_state(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for verification state information.
    """
    query = select(
        VerificationRecord.id,
        VerificationRecord.verification_level,
        VerificationRecord.verification_status,
        VerificationRecord.verification_start,
        VerificationRecord.verification_complete,
        Project.name.label("project_name"),
        GovernmentApproval.approval_status,
        GovernmentApproval.approval_reference
    ).select_from(
        VerificationRecord.__table__.join(
            ActivityData, VerificationRecord.activity_data_id == ActivityData.id
        ).join(
            Project, ActivityData.project_id == Project.id
        ).outerjoin(
            GovernmentApproval, VerificationRecord.id == GovernmentApproval.verification_record_id
        )
    ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    verifications = result.all()
    
    return [
        VerificationStateResponse(
            verification_id=str(verification.id),
            project_name=verification.project_name,
            verification_level=verification.verification_level.value,
            verification_status=verification.verification_status.value,
            verification_start=verification.verification_start,
            verification_complete=verification.verification_complete,
            government_approval_status=verification.approval_status or "pending",
            government_approval_reference=verification.approval_reference or ""
        )
        for verification in verifications
    ]


@router.get("/projects/{project_id}/summary", response_model=PublicProjectSummary)
async def get_public_project_summary(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for detailed project summary.
    """
    # Get project details
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get activity data summary
    activity_query = select(
        func.count(ActivityData.id).label("total_submissions"),
        func.sum(ActivityData.co2_calculated).label("total_co2"),
        func.count(func.distinct(ActivityData.supplier_id)).label("suppliers_count"),
        func.count(func.distinct(ActivityData.material_category_id)).label("materials_count")
    ).where(ActivityData.project_id == project_id)
    
    activity_result = await db.execute(activity_query)
    activity_summary = activity_result.first()
    
    # Get verification status
    verification_query = select(
        func.count(VerificationRecord.id).label("total_verifications"),
        func.count(func.distinct(VerificationRecord.verification_status)).label("status_count")
    ).select_from(
        VerificationRecord.__table__.join(
            ActivityData, VerificationRecord.activity_data_id == ActivityData.id
        )
    ).where(ActivityData.project_id == project_id)
    
    verification_result = await db.execute(verification_query)
    verification_summary = verification_result.first()
    
    # Get carbon credits
    credit_query = select(
        func.count(CarbonCredit.id).label("total_credits"),
        func.sum(CarbonCredit.co2_amount).label("total_credit_amount"),
        func.count(func.distinct(CarbonCredit.credit_status)).label("status_types")
    ).select_from(
        CarbonCredit.__table__.join(
            ActivityData, CarbonCredit.activity_data_id == ActivityData.id
        )
    ).where(ActivityData.project_id == project_id)
    
    credit_result = await db.execute(credit_query)
    credit_summary = credit_result.first()
    
    return PublicProjectSummary(
        project_id=str(project.id),
        project_name=project.name,
        project_description=project.description or "",
        project_status=project.status,
        total_submissions=activity_summary.total_submissions or 0,
        total_co2_tonnes=float(activity_summary.total_co2 or 0),
        suppliers_count=activity_summary.suppliers_count or 0,
        material_categories_count=activity_summary.materials_count or 0,
        total_verifications=verification_summary.total_verifications or 0,
        total_carbon_credits=credit_summary.total_credits or 0,
        total_credit_amount_tonnes=float(credit_summary.total_credit_amount or 0),
        created_at=project.created_at,
        last_updated=project.updated_at
    )


@router.get("/statistics/overview")
async def get_public_statistics(
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for system-wide statistics.
    """
    # Project statistics
    project_stats = await db.execute(
        select(
            func.count(Project.id).label("total_projects"),
            func.count(func.distinct(Project.owner_id)).label("organizations_count")
        )
    )
    projects = project_stats.first()
    
    # Activity data statistics
    activity_stats = await db.execute(
        select(
            func.count(ActivityData.id).label("total_submissions"),
            func.sum(ActivityData.co2_calculated).label("total_co2"),
            func.count(func.distinct(ActivityData.supplier_id)).label("suppliers_count")
        )
    )
    activity = activity_stats.first()
    
    # Verification statistics
    verification_stats = await db.execute(
        select(
            func.count(VerificationRecord.id).label("total_verifications"),
            func.count(func.distinct(VerificationRecord.verifier_id)).label("verifiers_count")
        )
    )
    verification = verification_stats.first()
    
    # Carbon credit statistics
    credit_stats = await db.execute(
        select(
            func.count(CarbonCredit.id).label("total_credits"),
            func.sum(CarbonCredit.co2_amount).label("total_credit_amount")
        )
    )
    credits = credit_stats.first()
    
    return {
        "projects": {
            "total_count": projects.total_projects or 0,
            "organizations_participating": projects.organizations_count or 0
        },
        "activity_data": {
            "total_submissions": activity.total_submissions or 0,
            "total_co2_tonnes": float(activity.total_co2 or 0),
            "suppliers_participating": activity.suppliers_count or 0
        },
        "verification": {
            "total_verifications": verification.total_verifications or 0,
            "accredited_verifiers": verification.verifiers_count or 0
        },
        "carbon_credits": {
            "total_credits_issued": credits.total_credits or 0,
            "total_credit_amount_tonnes": float(credits.total_credit_amount or 0)
        },
        "last_updated": datetime.utcnow()
    }
