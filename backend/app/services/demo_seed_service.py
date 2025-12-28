"""Demo seed service.

Goal (Module 5):
- Seed *synthetic* but realistic-looking data when DEMO_MODE is enabled.
- Do not change any compliance logic: triggers, immutability, and RBAC remain intact.

Important:
- Demo data is NOT a compliance claim.
- We avoid seeding any "carbon credits issuance" concepts (not in scope).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.role import Role, RoleName
from app.models.user import User
from app.models.supplier import Supplier
from app.models.project import Project, ProjectStatus
from app.models.emission_factor import EmissionFactor
from app.models.mrv_report import MRVReport, MRVStatus
from app.models.material_token import MaterialToken
from app.services.audit_log_service import write_audit_log


_DEMO_ACTOR = "demo_seed"


async def _ensure_roles(db: AsyncSession) -> dict[RoleName, Role]:
    """Ensure core roles exist."""

    existing = (await db.execute(select(Role))).scalars().all()
    by_name = {r.name: r for r in existing}

    for rn in RoleName:
        if rn not in by_name:
            r = Role(name=rn)
            db.add(r)
            await db.flush()
            by_name[rn] = r

    await db.commit()
    return by_name


async def _get_or_create_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    role_id: int,
    supplier_id=None,
) -> User:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user:
        return user

    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        is_active=True,
        role_id=role_id,
        supplier_id=supplier_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def ensure_demo_seeded(db: AsyncSession) -> None:
    """Seed demo data if the database appears empty.

    This is idempotent: if a DEMO project already exists, it does nothing.
    """

    # If any DEMO project exists, assume seeding was already done.
    demo_exists = (
        await db.execute(
            select(func.count(Project.id)).where(Project.name.ilike("DEMO%"))
        )
    ).scalar()
    if (demo_exists or 0) > 0:
        return

    # Create roles and demo users
    roles = await _ensure_roles(db)

    supplier = (await db.execute(select(Supplier).where(Supplier.name == "DEMO Supplier"))).scalar_one_or_none()
    if not supplier:
        supplier = Supplier(name="DEMO Supplier", partnership_discount=Decimal("0.0500"), total_value_supplied=Decimal("0"))
        db.add(supplier)
        await db.commit()
        await db.refresh(supplier)

    admin = await _get_or_create_user(
        db,
        email="admin@example.com",
        password="Admin123!",
        full_name="Demo Admin",
        role_id=roles[RoleName.ADMIN].id,
    )
    mrv_officer = await _get_or_create_user(
        db,
        email="verifier@example.com",
        password="verifier123",
        full_name="Demo MRV Officer",
        role_id=roles[RoleName.MRV_OFFICER].id,
    )
    pm = await _get_or_create_user(
        db,
        email="pm@example.com",
        password="PM123456!",
        full_name="Demo Project Manager",
        role_id=roles[RoleName.PROJECT_MANAGER].id,
    )
    supplier_user = await _get_or_create_user(
        db,
        email="supplier@example.com",
        password="Supply789!",
        full_name="Demo Supplier User",
        role_id=roles[RoleName.SUPPLIER].id,
        supplier_id=supplier.id,
    )

    # Project
    project = Project(
        name="DEMO – Green Concrete Pilot",
        status=ProjectStatus.ACTIVE,
        lat=13.0827,
        lon=80.2707,
        budget_usd=Decimal("2500000.00"),
        created_by=pm.id,
        reporting_period_start=datetime(2025, 10, 1, tzinfo=timezone.utc),
        reporting_period_end=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Emission factors (synthetic, but within plausible ranges; demo is explicitly watermarked elsewhere)
    ef_cement = EmissionFactor(
        material_code="CEMENT_OPC",
        material_name="Cement (OPC)",
        version=1,
        co2e_per_unit=Decimal("0.600000"),
        unit="kg",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        factor_hash="",
        is_active=False,
        created_by=_DEMO_ACTOR,
        created_by_user_id=admin.id,
    )
    ef_cement.activate()
    db.add(ef_cement)

    ef_steel = EmissionFactor(
        material_code="STEEL_REBAR",
        material_name="Steel Rebar",
        version=1,
        co2e_per_unit=Decimal("1.700000"),
        unit="kg",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        factor_hash="",
        is_active=False,
        created_by=_DEMO_ACTOR,
        created_by_user_id=admin.id,
    )
    ef_steel.activate()
    db.add(ef_steel)

    await db.commit()
    await db.refresh(ef_cement)
    await db.refresh(ef_steel)

    # MRV report (seed at SUBMITTED and VERIFIED to show workflow, but do not lock or claim compliance)
    quantity_kg = Decimal("1000")
    total_co2e = (Decimal(str(ef_cement.co2e_per_unit)) * quantity_kg).quantize(Decimal("0.000001"))

    report_submitted = MRVReport(
        project_id=project.id,
        reporting_period="2025-Q4",
        emission_factor_id=ef_cement.id,
        sample_desc="Demo batch: 1000 kg concrete cement content (synthetic demo)",
        parameter="Cement mass",
        value="1000 kg",
        total_co2e=total_co2e,
        certificate_path=None,
        emission_factor_version_snapshot=str(ef_cement.version),
        emission_factor_hash_snapshot=ef_cement.factor_hash,
        emission_factor_value_snapshot=ef_cement.co2e_per_unit,
        status=MRVStatus.SUBMITTED,
        created_by=pm.id,
        verified_by=None,
        approved_by=None,
    )
    db.add(report_submitted)

    report_verified = MRVReport(
        project_id=project.id,
        reporting_period="2025-Q4",
        emission_factor_id=ef_steel.id,
        sample_desc="Demo material: 500 kg steel rebar (synthetic demo)",
        parameter="Steel mass",
        value="500 kg",
        total_co2e=(Decimal(str(ef_steel.co2e_per_unit)) * Decimal("500")).quantize(Decimal("0.000001")),
        certificate_path=None,
        emission_factor_version_snapshot=str(ef_steel.version),
        emission_factor_hash_snapshot=ef_steel.factor_hash,
        emission_factor_value_snapshot=ef_steel.co2e_per_unit,
        status=MRVStatus.VERIFIED,
        created_by=pm.id,
        verified_by=mrv_officer.id,
        approved_by=None,
    )
    db.add(report_verified)

    await db.commit()
    await db.refresh(report_submitted)
    await db.refresh(report_verified)

    # Audit log entries to make exports meaningful
    await write_audit_log(
        db,
        actor=_DEMO_ACTOR,
        actor_user_id=pm.id,
        action="MRV_CREATED",
        entity_type="MRVReport",
        entity_id=str(report_submitted.id),
        event_payload={"status": report_submitted.status.value, "project_id": str(project.id)},
    )
    await write_audit_log(
        db,
        actor=_DEMO_ACTOR,
        actor_user_id=pm.id,
        action="MRV_SUBMITTED",
        entity_type="MRVReport",
        entity_id=str(report_submitted.id),
        event_payload={"status": report_submitted.status.value, "project_id": str(project.id)},
    )

    await write_audit_log(
        db,
        actor=_DEMO_ACTOR,
        actor_user_id=pm.id,
        action="MRV_CREATED",
        entity_type="MRVReport",
        entity_id=str(report_verified.id),
        event_payload={"status": report_verified.status.value, "project_id": str(project.id)},
    )
    await write_audit_log(
        db,
        actor=_DEMO_ACTOR,
        actor_user_id=mrv_officer.id,
        action="MRV_VERIFIED",
        entity_type="MRVReport",
        entity_id=str(report_verified.id),
        event_payload={"status": report_verified.status.value, "project_id": str(project.id)},
    )

    # Material token designed to trigger a deterministic anomaly (excess quantity)
    token = MaterialToken(
        project_id=project.id,
        material_code="CEMENT_OPC",
        material_name="Cement (OPC)",
        quantity=Decimal("1500.000"),
        unit="kg",
        supplier_name=supplier.name,
        issued_by=_DEMO_ACTOR,
        redeemed=False,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)

    await write_audit_log(
        db,
        actor=_DEMO_ACTOR,
        actor_user_id=admin.id,
        action="TOKEN_ISSUED",
        entity_type="MaterialToken",
        entity_id=str(token.id),
        event_payload={"token_uid": token.token_uid, "project_id": str(project.id)},
    )

    # Supplier user exists for portal login
    _ = supplier_user
