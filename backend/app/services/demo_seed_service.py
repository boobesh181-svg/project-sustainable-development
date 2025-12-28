"""Demo seed service.

Goal (Module 5):
- Seed *synthetic* but realistic-looking data when DEMO_MODE is enabled.
- Do not change any compliance logic: triggers, immutability, and RBAC remain intact.

Important:
- Demo data is NOT a compliance claim.
- We avoid seeding any "carbon credits issuance" concepts (not in scope).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from app.models.public_metrics import PublicMetrics
from app.models.sensor_reading import SensorReading, SensorType
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

    TARGET_MRV_REPORTS = 12

    # If a DEMO project exists, top-up seeded records as needed.
    project = (
        await db.execute(select(Project).where(Project.name.ilike("DEMO%")).order_by(Project.created_at.asc()))
    ).scalars().first()
    if project is not None:
        admin = (await db.execute(select(User).where(User.email == "admin@example.com"))).scalar_one_or_none()
        pm = (await db.execute(select(User).where(User.email == "pm@example.com"))).scalar_one_or_none()
        mrv_officer = (
            await db.execute(select(User).where(User.email == "verifier@example.com"))
        ).scalar_one_or_none()

        if admin is None or pm is None or mrv_officer is None:
            return

        ef_cement = (
            await db.execute(
                select(EmissionFactor)
                .where(EmissionFactor.material_code == "CEMENT_OPC", EmissionFactor.is_active.is_(True))
                .order_by(EmissionFactor.version.desc())
            )
        ).scalars().first()
        ef_steel = (
            await db.execute(
                select(EmissionFactor)
                .where(EmissionFactor.material_code == "STEEL_REBAR", EmissionFactor.is_active.is_(True))
                .order_by(EmissionFactor.version.desc())
            )
        ).scalars().first()

        if ef_cement is None or ef_steel is None:
            return

        # Company overview (company-summary) only counts REDEEMED tokens.
        redeemed_tokens = (
            await db.execute(
                select(func.count(MaterialToken.id)).where(
                    MaterialToken.project_id == project.id,
                    MaterialToken.redeemed.is_(True),
                )
            )
        ).scalar() or 0
        if int(redeemed_tokens) == 0:
            now = datetime.now(timezone.utc)
            demo_tokens = [
                MaterialToken(
                    project_id=project.id,
                    material_code="CEMENT_OPC",
                    material_name="Cement (OPC)",
                    quantity=Decimal("900.000"),
                    unit="kg",
                    supplier_name="DEMO Supplier",
                    issued_by=_DEMO_ACTOR,
                    redeemed=True,
                    redeemed_at=now,
                    delivery_lat=project.lat,
                    delivery_lon=project.lon,
                    supplier_invoice_ref="DEMO-INV-001",
                ),
                MaterialToken(
                    project_id=project.id,
                    material_code="STEEL_REBAR",
                    material_name="Steel Rebar",
                    quantity=Decimal("350.000"),
                    unit="kg",
                    supplier_name="DEMO Supplier",
                    issued_by=_DEMO_ACTOR,
                    redeemed=True,
                    redeemed_at=now,
                    delivery_lat=project.lat,
                    delivery_lon=project.lon,
                    supplier_invoice_ref="DEMO-INV-002",
                ),
                MaterialToken(
                    project_id=project.id,
                    material_code="CEMENT_OPC",
                    material_name="Cement (OPC)",
                    quantity=Decimal("650.000"),
                    unit="kg",
                    supplier_name="Alt Demo Supplier",
                    issued_by=_DEMO_ACTOR,
                    redeemed=True,
                    redeemed_at=now,
                    delivery_lat=project.lat,
                    delivery_lon=project.lon,
                    supplier_invoice_ref="DEMO-INV-003",
                ),
            ]
            for t in demo_tokens:
                db.add(t)

        # Ensure demo has some operational data so dashboard doesn't show zeros.
        existing_energy = (
            await db.execute(
                select(func.count(SensorReading.id)).where(
                    SensorReading.project_id == project.id,
                    SensorReading.sensor_type == SensorType.ENERGY,
                )
            )
        ).scalar() or 0
        if int(existing_energy) == 0:
            now = datetime.now(timezone.utc)
            mid_month = now.replace(day=15, hour=0, minute=0, second=0, microsecond=0)
            for i in range(12):
                ts = mid_month - timedelta(days=30 * i)
                value_kwh = (Decimal("20000") + (Decimal(i) * Decimal("1250"))).quantize(Decimal("0.001"))
                db.add(
                    SensorReading(
                        project_id=project.id,
                        sensor_type=SensorType.ENERGY,
                        value=value_kwh,
                        unit="kWh",
                        ts=ts,
                        lat=project.lat,
                        lon=project.lon,
                    )
                )

        existing_count = (
            await db.execute(select(func.count(MRVReport.id)).where(MRVReport.project_id == project.id))
        ).scalar() or 0

        if int(existing_count) >= TARGET_MRV_REPORTS:
            # Ensure at least one APPROVED report exists so embodied totals/charts are non-zero.
            approved_count = (
                await db.execute(
                    select(func.count(MRVReport.id)).where(
                        MRVReport.project_id == project.id,
                        MRVReport.status.in_([MRVStatus.APPROVED, MRVStatus.LOCKED]),
                    )
                )
            ).scalar() or 0
            if int(approved_count) == 0:
                quantity_kg = Decimal("800")
                total_co2e = (Decimal(str(ef_cement.co2e_per_unit)) * quantity_kg).quantize(Decimal("0.000001"))
                approved = MRVReport(
                    project_id=project.id,
                    reporting_period="2025-Q4",
                    emission_factor_id=ef_cement.id,
                    sample_desc="Demo approved sample: synthetic batch for non-zero dashboard totals",
                    parameter=f"{ef_cement.material_name} mass",
                    value=f"{quantity_kg} kg",
                    total_co2e=total_co2e,
                    certificate_path=None,
                    emission_factor_version_snapshot=str(ef_cement.version),
                    emission_factor_hash_snapshot=ef_cement.factor_hash,
                    emission_factor_value_snapshot=ef_cement.co2e_per_unit,
                    status=MRVStatus.APPROVED,
                    created_by=pm.id,
                    verified_by=mrv_officer.id,
                    approved_by=admin.id,
                )
                db.add(approved)
                await db.flush()
                await write_audit_log(
                    db,
                    actor=_DEMO_ACTOR,
                    actor_user_id=admin.id,
                    action="MRV_APPROVED",
                    entity_type="MRVReport",
                    entity_id=str(approved.id),
                    event_payload={"status": approved.status.value, "project_id": str(project.id)},
                )

            # Still ensure public metrics are present for dashboard CO2 saved.
            verified_total = (
                await db.execute(
                    select(func.coalesce(func.sum(MRVReport.total_co2e), 0)).where(
                        MRVReport.project_id == project.id,
                        MRVReport.status.in_([MRVStatus.APPROVED, MRVStatus.LOCKED]),
                    )
                )
            ).scalar_one() or 0
            if Decimal(str(verified_total)) == 0:
                verified_total = (
                    await db.execute(
                        select(func.coalesce(func.sum(MRVReport.total_co2e), 0)).where(
                            MRVReport.project_id == project.id,
                            MRVReport.status == MRVStatus.VERIFIED,
                        )
                    )
                ).scalar_one() or 0

            saved_total = (Decimal(str(verified_total)) * Decimal("0.12")).quantize(Decimal("0.000001"))

            pm_row = (
                await db.execute(select(PublicMetrics).where(PublicMetrics.project_id == project.id))
            ).scalar_one_or_none()
            if pm_row is None:
                db.add(
                    PublicMetrics(
                        project_id=project.id,
                        total_co2_saved_t=saved_total,
                        verified_co2_t=Decimal(str(verified_total)).quantize(Decimal("0.000001")),
                        total_materials_t=Decimal("0"),
                    )
                )
            await db.commit()
            return

        to_create = TARGET_MRV_REPORTS - int(existing_count)
        for i in range(to_create):
            idx = int(existing_count) + i + 1
            ef = ef_cement if idx % 2 == 0 else ef_steel
            quantity_kg = Decimal("250") if ef.material_code == "CEMENT_OPC" else Decimal("120")
            total_co2e = (Decimal(str(ef.co2e_per_unit)) * quantity_kg).quantize(Decimal("0.000001"))

            # Cycle through early lifecycle states to keep demo safe and editable.
            status_cycle = [MRVStatus.DRAFT, MRVStatus.SUBMITTED, MRVStatus.VERIFIED]
            status = status_cycle[idx % len(status_cycle)]

            report = MRVReport(
                project_id=project.id,
                reporting_period="2025-Q4",
                emission_factor_id=ef.id,
                sample_desc=f"Demo sample #{idx}: synthetic material batch ({ef.material_name})",
                parameter=f"{ef.material_name} mass",
                value=f"{quantity_kg} kg",
                total_co2e=total_co2e,
                certificate_path=None,
                emission_factor_version_snapshot=str(ef.version),
                emission_factor_hash_snapshot=ef.factor_hash,
                emission_factor_value_snapshot=ef.co2e_per_unit,
                status=status,
                created_by=pm.id,
                verified_by=mrv_officer.id if status == MRVStatus.VERIFIED else None,
                approved_by=None,
            )
            db.add(report)
            await db.flush()

            await write_audit_log(
                db,
                actor=_DEMO_ACTOR,
                actor_user_id=pm.id,
                action="MRV_CREATED",
                entity_type="MRVReport",
                entity_id=str(report.id),
                event_payload={"status": status.value, "project_id": str(project.id)},
            )
            if status == MRVStatus.SUBMITTED:
                await write_audit_log(
                    db,
                    actor=_DEMO_ACTOR,
                    actor_user_id=pm.id,
                    action="MRV_SUBMITTED",
                    entity_type="MRVReport",
                    entity_id=str(report.id),
                    event_payload={"status": status.value, "project_id": str(project.id)},
                )
            if status == MRVStatus.VERIFIED:
                await write_audit_log(
                    db,
                    actor=_DEMO_ACTOR,
                    actor_user_id=mrv_officer.id,
                    action="MRV_VERIFIED",
                    entity_type="MRVReport",
                    entity_id=str(report.id),
                    event_payload={"status": status.value, "project_id": str(project.id)},
                )

        await db.commit()

        # Ensure at least one APPROVED report exists so embodied totals/charts are non-zero.
        approved_count = (
            await db.execute(
                select(func.count(MRVReport.id)).where(
                    MRVReport.project_id == project.id,
                    MRVReport.status.in_([MRVStatus.APPROVED, MRVStatus.LOCKED]),
                )
            )
        ).scalar() or 0
        if int(approved_count) == 0:
            quantity_kg = Decimal("800")
            total_co2e = (Decimal(str(ef_cement.co2e_per_unit)) * quantity_kg).quantize(Decimal("0.000001"))
            approved = MRVReport(
                project_id=project.id,
                reporting_period="2025-Q4",
                emission_factor_id=ef_cement.id,
                sample_desc="Demo approved sample: synthetic batch for non-zero dashboard totals",
                parameter=f"{ef_cement.material_name} mass",
                value=f"{quantity_kg} kg",
                total_co2e=total_co2e,
                certificate_path=None,
                emission_factor_version_snapshot=str(ef_cement.version),
                emission_factor_hash_snapshot=ef_cement.factor_hash,
                emission_factor_value_snapshot=ef_cement.co2e_per_unit,
                status=MRVStatus.APPROVED,
                created_by=pm.id,
                verified_by=mrv_officer.id,
                approved_by=admin.id,
            )
            db.add(approved)
            await db.flush()
            await write_audit_log(
                db,
                actor=_DEMO_ACTOR,
                actor_user_id=admin.id,
                action="MRV_APPROVED",
                entity_type="MRVReport",
                entity_id=str(approved.id),
                event_payload={"status": approved.status.value, "project_id": str(project.id)},
            )
            await db.commit()

        # Public dashboard metrics used by dashboard_service_v2.
        verified_total = (
            await db.execute(
                select(func.coalesce(func.sum(MRVReport.total_co2e), 0)).where(
                    MRVReport.project_id == project.id,
                    MRVReport.status.in_([MRVStatus.APPROVED, MRVStatus.LOCKED]),
                )
            )
        ).scalar_one() or 0
        saved_total = (Decimal(str(verified_total)) * Decimal("0.12")).quantize(Decimal("0.000001"))

        pm_row = (
            await db.execute(select(PublicMetrics).where(PublicMetrics.project_id == project.id))
        ).scalar_one_or_none()
        if pm_row is None:
            db.add(
                PublicMetrics(
                    project_id=project.id,
                    total_co2_saved_t=saved_total,
                    verified_co2_t=Decimal(str(verified_total)).quantize(Decimal("0.000001")),
                    total_materials_t=Decimal("0"),
                )
            )
        else:
            if Decimal(str(pm_row.total_co2_saved_t or 0)) == 0 and saved_total > 0:
                pm_row.total_co2_saved_t = saved_total
            if Decimal(str(pm_row.verified_co2_t or 0)) == 0 and Decimal(str(verified_total)) > 0:
                pm_row.verified_co2_t = Decimal(str(verified_total)).quantize(Decimal("0.000001"))

        await db.commit()
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

    # Redeemed tokens for company overview emissions (requires redeemed_at + delivery coords).
    redeemed_count = (
        await db.execute(
            select(func.count(MaterialToken.id)).where(
                MaterialToken.project_id == project.id,
                MaterialToken.redeemed.is_(True),
            )
        )
    ).scalar() or 0
    if int(redeemed_count) == 0:
        now = datetime.now(timezone.utc)
        t1 = MaterialToken(
            project_id=project.id,
            material_code="CEMENT_OPC",
            material_name="Cement (OPC)",
            quantity=Decimal("900.000"),
            unit="kg",
            supplier_name=supplier.name,
            issued_by=_DEMO_ACTOR,
            redeemed=True,
            redeemed_at=now,
            delivery_lat=project.lat,
            delivery_lon=project.lon,
            supplier_invoice_ref="DEMO-INV-001",
        )
        t2 = MaterialToken(
            project_id=project.id,
            material_code="STEEL_REBAR",
            material_name="Steel Rebar",
            quantity=Decimal("350.000"),
            unit="kg",
            supplier_name=supplier.name,
            issued_by=_DEMO_ACTOR,
            redeemed=True,
            redeemed_at=now,
            delivery_lat=project.lat,
            delivery_lon=project.lon,
            supplier_invoice_ref="DEMO-INV-002",
        )
        t3 = MaterialToken(
            project_id=project.id,
            material_code="CEMENT_OPC",
            material_name="Cement (OPC)",
            quantity=Decimal("650.000"),
            unit="kg",
            supplier_name="Alt Demo Supplier",
            issued_by=_DEMO_ACTOR,
            redeemed=True,
            redeemed_at=now,
            delivery_lat=project.lat,
            delivery_lon=project.lon,
            supplier_invoice_ref="DEMO-INV-003",
        )
        db.add(t1)
        db.add(t2)
        db.add(t3)
        await db.commit()

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

    # Demo-only public metrics + a small energy timeseries so the dashboard isn't all zeros.
    pm_row = (
        await db.execute(select(PublicMetrics).where(PublicMetrics.project_id == project.id))
    ).scalar_one_or_none()
    if pm_row is None:
        # Use VERIFIED report total as a stand-in for verified CO2 (no compliance claim; DEMO-only).
        verified_total = (
            await db.execute(
                select(func.coalesce(func.sum(MRVReport.total_co2e), 0)).where(
                    MRVReport.project_id == project.id,
                    MRVReport.status == MRVStatus.VERIFIED,
                )
            )
        ).scalar_one() or 0
        saved_total = (Decimal(str(verified_total)) * Decimal("0.12")).quantize(Decimal("0.000001"))
        db.add(
            PublicMetrics(
                project_id=project.id,
                total_co2_saved_t=saved_total,
                verified_co2_t=Decimal(str(verified_total)).quantize(Decimal("0.000001")),
                total_materials_t=Decimal("0"),
            )
        )

    existing_energy = (
        await db.execute(
            select(func.count(SensorReading.id)).where(
                SensorReading.project_id == project.id,
                SensorReading.sensor_type == SensorType.ENERGY,
            )
        )
    ).scalar() or 0
    if int(existing_energy) == 0:
        now = datetime.now(timezone.utc)
        mid_month = now.replace(day=15, hour=0, minute=0, second=0, microsecond=0)
        for i in range(12):
            ts = mid_month - timedelta(days=30 * i)
            value_kwh = (Decimal("20000") + (Decimal(i) * Decimal("1250"))).quantize(Decimal("0.001"))
            db.add(
                SensorReading(
                    project_id=project.id,
                    sensor_type=SensorType.ENERGY,
                    value=value_kwh,
                    unit="kWh",
                    ts=ts,
                    lat=project.lat,
                    lon=project.lon,
                )
            )

    await db.commit()
