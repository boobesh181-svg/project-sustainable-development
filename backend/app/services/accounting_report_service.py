from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emission_factor import EmissionFactor
from app.models.material_token import MaterialToken
from app.models.mrv_report import MRVReport
from app.models.sensor_reading import SensorReading, SensorType
from app.services.mrv_calculation_service import authoritative_report_total_co2e
from app.models.methodology_version import MethodologyVersion
from app.models.reporting_context import ConsolidationMethod, ReportingContext
from app.models.organization_relationship import OrganizationRelationship, OrganizationRoleType
from app.models.report_view import ReportView


CALC_ENGINE_VERSION = "accounting_context_v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_Q6 = Decimal("0.000001")


def _q6(value: Decimal) -> Decimal:
    return value.quantize(_Q6, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class EmissionActivity:
    source_type: Literal["material_token", "sensor_reading", "mrv_report"]
    source_id: UUID
    project_id: UUID
    occurred_at: datetime

    operator_org_id: UUID | None

    activity_kind: Literal["combustion", "electricity", "other"]

    # For factor-based calculation
    material_code: str | None
    quantity: Decimal | None
    unit: str | None

    # For measured emissions (already computed upstream)
    measured_emissions_tco2e: Decimal | None


def calculate_scope(activity: EmissionActivity, ctx: ReportingContext) -> str:
    """Classify an activity into Scope 1/2/3.

    Rules (as requested):
    - If activity operator == reporting_entity AND combustion → Scope 1
    - If purchased electricity consumed by reporting_entity → Scope 2
    - Else → Scope 3

    Notes:
    - This function does not store scope numbers in any activity record.
    """

    if activity.operator_org_id == ctx.reporting_entity_id and activity.activity_kind == "combustion":
        return "SCOPE_1"

    if activity.operator_org_id == ctx.reporting_entity_id and activity.activity_kind == "electricity":
        return "SCOPE_2"

    return "SCOPE_3"


async def _relationship_for_entity_at(
    db: AsyncSession,
    *,
    project_id: UUID,
    organization_id: UUID,
    ts: datetime,
) -> OrganizationRelationship | None:
    return (
        await db.execute(
            select(OrganizationRelationship)
            .where(
                OrganizationRelationship.project_id == project_id,
                OrganizationRelationship.organization_id == organization_id,
                OrganizationRelationship.valid_from <= ts,
                (OrganizationRelationship.valid_to.is_(None) | (OrganizationRelationship.valid_to > ts)),
            )
            .order_by(OrganizationRelationship.valid_from.desc(), OrganizationRelationship.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _operator_org_for_project_at(
    db: AsyncSession, *, project_id: UUID, ts: datetime
) -> UUID | None:
    # Best-effort operator selection from relationships.
    # Priority: OPERATOR (operational_control true) → CONTRACTOR (operational_control true) → DEVELOPER.
    rel = (
        await db.execute(
            select(OrganizationRelationship)
            .where(
                OrganizationRelationship.project_id == project_id,
                OrganizationRelationship.valid_from <= ts,
                (OrganizationRelationship.valid_to.is_(None) | (OrganizationRelationship.valid_to > ts)),
                OrganizationRelationship.operational_control.is_(True),
                OrganizationRelationship.role_type.in_(
                    [
                        OrganizationRoleType.OPERATOR,
                        OrganizationRoleType.CONTRACTOR,
                        OrganizationRoleType.DEVELOPER,
                    ]
                ),
            )
            .order_by(
                # enum ordering isn't stable across DBs; do simple multi-pass in Python by fetching a few.
                OrganizationRelationship.valid_from.desc(),
                OrganizationRelationship.created_at.desc(),
            )
            .limit(25)
        )
    ).scalars().all()

    for role in (OrganizationRoleType.OPERATOR, OrganizationRoleType.CONTRACTOR, OrganizationRoleType.DEVELOPER):
        match = next((r for r in rel if r.role_type == role), None)
        if match is not None:
            return match.organization_id

    return None


def _convert_quantity_unit(*, quantity: Decimal, from_unit: str, to_unit: str) -> Decimal:
    fu = (from_unit or "").strip().lower()
    tu = (to_unit or "").strip().lower()

    if fu == tu:
        return quantity

    ton_aliases = {"t", "ton", "tonne", "tonnes", "metric_ton"}
    kg_aliases = {"kg", "kilogram", "kilograms"}

    if fu in ton_aliases and tu in kg_aliases:
        return quantity * Decimal("1000")
    if fu in kg_aliases and tu in ton_aliases:
        return quantity / Decimal("1000")

    raise HTTPException(status_code=400, detail=f"Unsupported unit conversion: {from_unit} -> {to_unit}")


async def _select_emission_factor(
    db: AsyncSession,
    *,
    material_code: str,
    ts: datetime,
    methodology_code: str,
) -> EmissionFactor:
    ef = (
        await db.execute(
            select(EmissionFactor)
            .where(
                EmissionFactor.material_code == material_code,
                EmissionFactor.methodology_reference == methodology_code,
                EmissionFactor.valid_from <= ts,
                (EmissionFactor.valid_to.is_(None) | (EmissionFactor.valid_to > ts)),
                EmissionFactor.is_active.is_(True),
            )
            .order_by(EmissionFactor.valid_from.desc(), EmissionFactor.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if ef is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No active emission factor found for material_code='{material_code}' "
                f"under methodology='{methodology_code}' valid at {ts.isoformat()}"
            ),
        )

    return ef


async def _fetch_activities(
    db: AsyncSession,
    *,
    project_id: UUID,
    window_from: datetime,
    window_to: datetime | None,
) -> list[EmissionActivity]:
    activities: list[EmissionActivity] = []

    # Material tokens (redeemed) within window.
    mt_stmt = select(MaterialToken).where(
        MaterialToken.project_id == project_id,
        MaterialToken.redeemed.is_(True),
        MaterialToken.delivery_timestamp.is_not(None),
        MaterialToken.delivery_timestamp >= window_from,
    )
    if window_to is not None:
        mt_stmt = mt_stmt.where(MaterialToken.delivery_timestamp < window_to)

    for t in (await db.execute(mt_stmt)).scalars().all():
        occurred = t.delivery_timestamp
        if occurred is None:
            continue
        activities.append(
            EmissionActivity(
                source_type="material_token",
                source_id=t.id,
                project_id=project_id,
                occurred_at=occurred,
                operator_org_id=t.supplier_id,
                activity_kind="other",
                material_code=t.material_code,
                quantity=Decimal(str(t.quantity)),
                unit=t.unit,
                measured_emissions_tco2e=None,
            )
        )

    # Sensor readings (energy) within window.
    sr_stmt = select(SensorReading).where(
        SensorReading.project_id == project_id,
        SensorReading.ts >= window_from,
        SensorReading.sensor_type == SensorType.ENERGY,
    )
    if window_to is not None:
        sr_stmt = sr_stmt.where(SensorReading.ts < window_to)

    for s in (await db.execute(sr_stmt)).scalars().all():
        operator_org = await _operator_org_for_project_at(db, project_id=project_id, ts=s.ts)
        activities.append(
            EmissionActivity(
                source_type="sensor_reading",
                source_id=s.id,
                project_id=project_id,
                occurred_at=s.ts,
                operator_org_id=operator_org,
                activity_kind="electricity",
                material_code="GRID_ELECTRICITY",
                quantity=Decimal(str(s.value)),
                unit=s.unit,
                measured_emissions_tco2e=None,
            )
        )

    # MRV reports within window (treated as measured tCO2e; boundary still applies).
    mr_stmt = select(MRVReport).where(
        MRVReport.project_id == project_id,
        MRVReport.created_at >= window_from,
    )
    if window_to is not None:
        mr_stmt = mr_stmt.where(MRVReport.created_at < window_to)

    for r in (await db.execute(mr_stmt)).scalars().all():
        operator_org = await _operator_org_for_project_at(db, project_id=project_id, ts=r.created_at)
        total, _used_snapshot = authoritative_report_total_co2e(r)
        activities.append(
            EmissionActivity(
                source_type="mrv_report",
                source_id=r.id,
                project_id=project_id,
                occurred_at=r.created_at,
                operator_org_id=operator_org,
                activity_kind="other",
                material_code=None,
                quantity=None,
                unit=None,
                measured_emissions_tco2e=Decimal(str(total)),
            )
        )

    activities.sort(key=lambda a: (a.occurred_at, str(a.source_id)))
    return activities


async def _boundary_multiplier(
    db: AsyncSession,
    *,
    project_id: UUID,
    ctx: ReportingContext,
    ts: datetime,
) -> Decimal:
    rel = await _relationship_for_entity_at(
        db, project_id=project_id, organization_id=ctx.reporting_entity_id, ts=ts
    )
    if rel is None:
        return Decimal("0")

    method = ctx.consolidation_method

    if method == ConsolidationMethod.EQUITY:
        if rel.ownership_percentage is None:
            return Decimal("0")
        return Decimal(str(rel.ownership_percentage)) / Decimal("100")

    if method == ConsolidationMethod.FINANCIAL_CONTROL:
        return Decimal("1") if bool(rel.financial_control) else Decimal("0")

    if method == ConsolidationMethod.OPERATIONAL_CONTROL:
        return Decimal("1") if bool(rel.operational_control) else Decimal("0")

    return Decimal("0")


async def generate_report_view(
    db: AsyncSession,
    *,
    project_id: UUID,
    reporting_context_id: UUID,
) -> ReportView:
    ctx = await db.get(ReportingContext, reporting_context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Reporting context not found")

    methodology = await db.get(MethodologyVersion, ctx.methodology_version_id)
    if methodology is None:
        raise HTTPException(status_code=404, detail="Methodology version not found")

    activities = await _fetch_activities(
        db,
        project_id=project_id,
        window_from=ctx.valid_from,
        window_to=ctx.valid_to,
    )

    line_items: list[dict] = []
    total = Decimal("0")

    for a in activities:
        if a.measured_emissions_tco2e is not None:
            base_t = Decimal(a.measured_emissions_tco2e)
            factor_hash = None
            factor_unit = None
        else:
            if a.material_code is None or a.quantity is None or a.unit is None:
                raise HTTPException(status_code=400, detail="Activity missing factor inputs")
            ef = await _select_emission_factor(
                db,
                material_code=a.material_code,
                ts=a.occurred_at,
                methodology_code=methodology.code,
            )
            qty_in_factor_unit = _convert_quantity_unit(
                quantity=Decimal(a.quantity),
                from_unit=a.unit,
                to_unit=ef.unit,
            )
            # ef.co2e_per_unit is Numeric in DB; cast to Decimal via str.
            base_kg = qty_in_factor_unit * Decimal(str(ef.co2e_per_unit))
            base_t = base_kg / Decimal("1000")
            factor_hash = ef.factor_hash
            factor_unit = ef.unit

        multiplier = await _boundary_multiplier(
            db, project_id=project_id, ctx=ctx, ts=a.occurred_at
        )
        included_t = base_t * multiplier

        scope = calculate_scope(a, ctx)

        total += included_t
        line_items.append(
            {
                "source_type": a.source_type,
                "source_id": str(a.source_id),
                "occurred_at": a.occurred_at.replace(microsecond=0).isoformat(),
                "operator_org_id": str(a.operator_org_id) if a.operator_org_id else None,
                "activity_kind": a.activity_kind,
                "scope": scope,
                "base_emissions_tco2e": str(_q6(base_t)),
                "boundary_multiplier": str(_q6(multiplier)),
                "included_emissions_tco2e": str(_q6(included_t)),
                "factor": {
                    "material_code": a.material_code,
                    "unit": factor_unit,
                    "factor_hash": factor_hash,
                    "methodology_code": methodology.code,
                },
            }
        )

    total_q = _q6(total)

    calc_payload = {
        "engine": CALC_ENGINE_VERSION,
        "project_id": str(project_id),
        "reporting_context_id": str(ctx.id),
        "reporting_entity_id": str(ctx.reporting_entity_id),
        "consolidation_method": ctx.consolidation_method.value,
        "reporting_purpose": ctx.reporting_purpose.value,
        "methodology_version_id": str(ctx.methodology_version_id),
        "methodology_code": methodology.code,
        "valid_from": ctx.valid_from.replace(microsecond=0).isoformat(),
        "valid_to": ctx.valid_to.replace(microsecond=0).isoformat() if ctx.valid_to else None,
        "line_items": line_items,
        "total_emissions_tco2e": str(total_q),
    }

    calc_json = json.dumps(calc_payload, sort_keys=True, separators=(",", ":"))
    calculation_hash = hashlib.sha256(calc_json.encode("utf-8")).hexdigest()

    view = ReportView(
        project_id=project_id,
        reporting_context_id=ctx.id,
        generated_at=_utcnow(),
        total_emissions=total_q,
        calculation_hash=calculation_hash,
    )

    db.add(view)
    await db.commit()
    await db.refresh(view)
    return view


async def export_report_view(
    db: AsyncSession,
    *,
    report_view_id: UUID,
) -> dict:
    view = await db.get(ReportView, report_view_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Report view not found")

    ctx = await db.get(ReportingContext, view.reporting_context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Reporting context not found")

    methodology = await db.get(MethodologyVersion, ctx.methodology_version_id)
    if methodology is None:
        raise HTTPException(status_code=404, detail="Methodology version not found")

    # Reporting entity metadata is required for export.
    from app.models.organization import Organization

    org = await db.get(Organization, ctx.reporting_entity_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Reporting entity organization not found")

    return {
        "report_view": {
            "id": str(view.id),
            "project_id": str(view.project_id),
            "reporting_context_id": str(view.reporting_context_id),
            "generated_at": view.generated_at,
            "total_emissions": str(view.total_emissions),
            "calculation_hash": view.calculation_hash,
        },
        "reporting_context": {
            "id": str(ctx.id),
            "reporting_entity_id": str(ctx.reporting_entity_id),
            "consolidation_method": ctx.consolidation_method.value,
            "reporting_purpose": ctx.reporting_purpose.value,
            "methodology_version_id": str(ctx.methodology_version_id),
            "valid_from": ctx.valid_from,
            "valid_to": ctx.valid_to,
            "created_at": ctx.created_at,
        },
        "methodology_version": {
            "id": str(methodology.id),
            "code": methodology.code,
            "description": methodology.description,
            "created_at": methodology.created_at,
        },
        "reporting_entity": {
            "id": str(org.id),
            "name": org.name,
            "created_at": org.created_at,
        },
        "boundary_method": ctx.consolidation_method.value,
        "calculation_timestamp": view.generated_at,
        "total_emissions": str(view.total_emissions),
        "calculation_hash": view.calculation_hash,
    }
