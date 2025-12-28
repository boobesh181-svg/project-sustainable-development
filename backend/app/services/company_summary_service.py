from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emission_factor import EmissionFactor
from app.models.material_token import MaterialToken
from app.models.mrv_report import MRVReport, MRVStatus
from app.models.project import Project
from app.schemas.company_summary import (
    CompanyMRVSummary,
    EmissionFactorSource,
    EmissionsByMaterial,
    EmissionsByProject,
    EmissionsBySupplier,
    ReportStatusShare,
)


_TON_UNITS = {"t", "ton", "tonne", "tonnes"}


def _to_float(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except Exception:
        return 0.0


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


async def get_company_mrv_summary(db: AsyncSession) -> CompanyMRVSummary:
    # ---------- Token-based emissions (redeemed-only) ----------
    # Compute emissions using active emission factors.
    # co2e_per_unit is stored as kgCO2e per emission_factor.unit.
    token_unit = func.lower(func.coalesce(MaterialToken.unit, ""))
    ef_unit = func.lower(func.coalesce(EmissionFactor.unit, ""))

    qty = func.coalesce(MaterialToken.quantity, 0)
    ef = func.coalesce(EmissionFactor.co2e_per_unit, 0)

    # Minimal unit conversion between t <-> kg when needed.
    qty_in_ef_unit = case(
        (
            and_(token_unit.in_(list(_TON_UNITS)), ef_unit == "kg"),
            qty * 1000,
        ),
        (
            and_(token_unit == "kg", ef_unit.in_(list(_TON_UNITS))),
            qty / 1000,
        ),
        else_=qty,
    )

    emissions_kg = qty_in_ef_unit * ef
    emissions_t = emissions_kg / 1000.0

    base_from = (
        select(
            MaterialToken.project_id,
            MaterialToken.material_code,
            MaterialToken.material_name,
            MaterialToken.supplier_name,
            MaterialToken.redeemed_at,
            emissions_t.label("emissions_t"),
        )
        .select_from(MaterialToken)
        .join(
            EmissionFactor,
            and_(
                EmissionFactor.material_code == MaterialToken.material_code,
                EmissionFactor.is_active.is_(True),
            ),
            isouter=True,
        )
        .where(MaterialToken.redeemed.is_(True))
    ).subquery()

    # Total emissions
    total_emissions_t = (
        await db.execute(select(func.coalesce(func.sum(base_from.c.emissions_t), 0)))
    ).scalar_one()

    # Reporting window (redeemed tokens)
    period_row = (
        await db.execute(
            select(
                func.min(base_from.c.redeemed_at),
                func.max(base_from.c.redeemed_at),
            )
        )
    ).one()
    reporting_start: datetime | None = period_row[0]
    reporting_end: datetime | None = period_row[1]

    # Emissions by material
    by_material_rows = (
        await db.execute(
            select(
                base_from.c.material_code,
                func.max(base_from.c.material_name),
                func.coalesce(func.sum(base_from.c.emissions_t), 0).label("emissions_t"),
            )
            .group_by(base_from.c.material_code)
            .order_by(func.coalesce(func.sum(base_from.c.emissions_t), 0).desc())
        )
    ).all()

    emissions_by_material = [
        EmissionsByMaterial(
            material_code=str(r[0] or "unknown"),
            material_name=str(r[1]) if r[1] is not None else None,
            emissions_tco2e=_to_float(r[2]),
        )
        for r in by_material_rows
    ]

    # Emissions by supplier
    by_supplier_rows = (
        await db.execute(
            select(
                base_from.c.supplier_name,
                func.coalesce(func.sum(base_from.c.emissions_t), 0).label("emissions_t"),
            )
            .group_by(base_from.c.supplier_name)
            .order_by(func.coalesce(func.sum(base_from.c.emissions_t), 0).desc())
        )
    ).all()

    emissions_by_supplier = [
        EmissionsBySupplier(
            supplier_name=str(r[0] or "Unknown"),
            emissions_tco2e=_to_float(r[1]),
        )
        for r in by_supplier_rows
    ]

    # Emissions by project
    by_project_rows = (
        await db.execute(
            select(
                Project.id,
                Project.name,
                func.coalesce(func.sum(base_from.c.emissions_t), 0).label("emissions_t"),
            )
            .select_from(Project)
            .join(base_from, base_from.c.project_id == Project.id)
            .group_by(Project.id, Project.name)
            .order_by(func.coalesce(func.sum(base_from.c.emissions_t), 0).desc())
        )
    ).all()

    emissions_by_project = [
        EmissionsByProject(
            project_id=r[0],
            project_name=str(r[1]),
            emissions_tco2e=_to_float(r[2]),
        )
        for r in by_project_rows
    ]

    # ---------- MRV workflow status shares ----------
    status_counts = (
        await db.execute(select(MRVReport.status, func.count(MRVReport.id)).group_by(MRVReport.status))
    ).all()
    total_reports = sum(int(r[1]) for r in status_counts)

    by_status = {str(r[0].value if hasattr(r[0], "value") else r[0]): int(r[1]) for r in status_counts}

    verified_count = sum(by_status.get(s.value, 0) for s in [MRVStatus.VERIFIED, MRVStatus.APPROVED, MRVStatus.LOCKED])
    approved_count = sum(by_status.get(s.value, 0) for s in [MRVStatus.APPROVED, MRVStatus.LOCKED])
    locked_count = by_status.get(MRVStatus.LOCKED.value, 0)

    reports_by_status = [
        ReportStatusShare(status=k, count=v, pct=_pct(v, total_reports))
        for k, v in sorted(by_status.items())
    ]

    # ---------- Emission factor sources used ----------
    # Only include active factors that match token material codes present.
    factor_rows = (
        await db.execute(
            select(
                EmissionFactor.material_code,
                EmissionFactor.material_name,
                EmissionFactor.version,
                EmissionFactor.unit,
                EmissionFactor.co2e_per_unit,
                EmissionFactor.factor_hash,
                EmissionFactor.valid_from,
            )
            .where(EmissionFactor.is_active.is_(True))
            .where(
                EmissionFactor.material_code.in_(
                    select(func.distinct(MaterialToken.material_code)).where(MaterialToken.redeemed.is_(True))
                )
            )
            .order_by(EmissionFactor.material_code.asc(), EmissionFactor.version.desc())
        )
    ).all()

    emission_factor_sources = [
        EmissionFactorSource(
            material_code=str(r[0]),
            material_name=str(r[1]),
            version=int(r[2]),
            unit=str(r[3]),
            co2e_per_unit=_to_float(r[4]),
            factor_hash=str(r[5]),
            valid_from=r[6],
        )
        for r in factor_rows
    ]

    return CompanyMRVSummary(
        total_emissions_tco2e=_to_float(total_emissions_t),
        emissions_by_material=emissions_by_material,
        emissions_by_supplier=emissions_by_supplier,
        emissions_by_project=emissions_by_project,
        pct_verified=_pct(verified_count, total_reports),
        pct_approved=_pct(approved_count, total_reports),
        pct_locked=_pct(locked_count, total_reports),
        reporting_period_start=reporting_start,
        reporting_period_end=reporting_end,
        methodology_version="active_emission_factors_v1",
        emission_factor_sources_used=emission_factor_sources,
        reports_by_status=reports_by_status,
    )
