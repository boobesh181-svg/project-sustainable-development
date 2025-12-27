"""Seed canonical MRV tables for the dashboard.

Run from backend/:
  python scripts/seed_dashboard.py

This seeds a minimal, realistic dataset compatible with the canonical models
(Project, MaterialToken, DeliveryVerification, MRVReport, SensorReading,
AnomalyAlert, Whistleblower, PublicMetrics).

It is idempotent (won't duplicate if data already exists).
"""

import asyncio
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import select

# Ensure backend root is on sys.path when run from backend/
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.anomaly_alert import AnomalyAlert, AnomalySeverity
from app.models.delivery_verification import DeliveryVerification
from app.models.material_token import MaterialToken
from app.models.mrv_report import MRVReport, MRVStatus
from app.models.project import Project, ProjectStatus
from app.models.public_metrics import PublicMetrics
from app.models.role import Role, RoleName
from app.models.sensor_reading import SensorReading, SensorType
from app.models.user import User
from app.models.whistleblower import (
    Whistleblower,
    WhistleblowerPriority,
    WhistleblowerStatus,
)


async def _get_or_create_roles(session) -> dict[RoleName, int]:
    existing = (await session.execute(select(Role))).scalars().all()
    if not existing:
        for name in RoleName:
            session.add(Role(name=name))
        await session.commit()
        existing = (await session.execute(select(Role))).scalars().all()
    return {r.name: r.id for r in existing}


async def _get_or_create_admin(session, role_ids: dict[RoleName, int]) -> User:
    admin = (
        await session.execute(select(User).where(User.email == "admin@example.com"))
    ).scalar_one_or_none()
    if admin:
        # Keep demo credentials deterministic even across repeated runs.
        admin.full_name = "Administrator"
        admin.hashed_password = get_password_hash("Admin123!")
        admin.is_active = True
        admin.role_id = role_ids[RoleName.ADMIN]
        await session.commit()
        await session.refresh(admin)
        return admin

    admin = User(
        email="admin@example.com",
        full_name="Administrator",
        hashed_password=get_password_hash("Admin123!"),
        is_active=True,
        role_id=role_ids[RoleName.ADMIN],
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def _get_or_create_user(
    session,
    *,
    email: str,
    full_name: str,
    password: str,
    role_ids: dict[RoleName, int],
    role: RoleName,
) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user:
        # Keep demo credentials deterministic even across repeated runs.
        user.full_name = full_name
        user.hashed_password = get_password_hash(password)
        user.is_active = True
        user.role_id = role_ids[role]
        await session.commit()
        await session.refresh(user)
        return user

    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(password),
        is_active=True,
        role_id=role_ids[role],
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def seed_dashboard() -> None:
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        role_ids = await _get_or_create_roles(session)
        admin = await _get_or_create_admin(session, role_ids)

        # Ensure demo login accounts exist (dev/demo only)
        mrv_user = await _get_or_create_user(
            session,
            email="mrv@example.com",
            full_name="MRV Creator",
            password="mrv123",
            role_ids=role_ids,
            role=RoleName.CONTRACTOR,
        )
        verifier_user = await _get_or_create_user(
            session,
            email="verifier@example.com",
            full_name="Verifier",
            password="verifier123",
            role_ids=role_ids,
            role=RoleName.MRV_OFFICER,
        )
        approver_user = await _get_or_create_user(
            session,
            email="approver@example.com",
            full_name="Approver",
            password="approver123",
            role_ids=role_ids,
            role=RoleName.ADMIN,
        )
        await _get_or_create_user(
            session,
            email="contractor@example.com",
            full_name="Contractor Lead",
            password="Contract789!",
            role_ids=role_ids,
            role=RoleName.CONTRACTOR,
        )
        await _get_or_create_user(
            session,
            email="pm@example.com",
            full_name="Project Manager",
            password="PM123456!",
            role_ids=role_ids,
            role=RoleName.PROJECT_MANAGER,
        )
        await _get_or_create_user(
            session,
            email="supplier@example.com",
            full_name="Supplier Manager",
            password="Supply789!",
            role_ids=role_ids,
            role=RoleName.SUPPLIER,
        )
        await _get_or_create_user(
            session,
            email="citizen@example.com",
            full_name="Citizen User",
            password="Citizen123!",
            role_ids=role_ids,
            role=RoleName.CITIZEN,
        )

        # Projects: create missing, otherwise reuse existing
        existing_projects = (
            await session.execute(select(Project).order_by(Project.created_at.asc()))
        ).scalars().all()

        desired = [
            {
                "name": "Riverfront Affordable Housing",
                "status": ProjectStatus.ACTIVE,
                "lat": 13.0892,
                "lon": 80.2788,
                "budget_usd": 5_000_000,
            },
            {
                "name": "Urban Retrofit - Block A",
                "status": ProjectStatus.IN_PROGRESS,
                "lat": 12.9716,
                "lon": 77.5946,
                "budget_usd": 1_200_000,
            },
            {
                "name": "School Solar Microgrid",
                "status": ProjectStatus.COMPLETED,
                "lat": 11.0168,
                "lon": 76.9558,
                "budget_usd": 350_000,
            },
        ]

        by_name = {p.name: p for p in existing_projects}
        projects: list[Project] = []
        for d in desired:
            p = by_name.get(d["name"])
            if p is None:
                p = Project(created_by=admin.id, **d)
                session.add(p)
            projects.append(p)

        await session.commit()
        for p in projects:
            await session.refresh(p)

        # If downstream tables already have data, avoid duplicating.
        tokens_exist = (
            await session.execute(select(MaterialToken.id).limit(1))
        ).scalar_one_or_none()
        reports_exist = (
            await session.execute(select(MRVReport.id).limit(1))
        ).scalar_one_or_none()
        readings_exist = (
            await session.execute(select(SensorReading.id).limit(1))
        ).scalar_one_or_none()
        anomalies_exist = (
            await session.execute(select(AnomalyAlert.id).limit(1))
        ).scalar_one_or_none()
        whistle_exist = (
            await session.execute(select(Whistleblower.id).limit(1))
        ).scalar_one_or_none()
        public_metrics_exist = (
            await session.execute(select(PublicMetrics.id).limit(1))
        ).scalar_one_or_none()

        # Material tokens (mix of redeemed and unredeemed)
        tokens: list[MaterialToken] = []
        if tokens_exist is None:
            material_defs = [
                ("CEM-OPC", "Ordinary Portland Cement", "t"),
                ("STL-RB", "Rebar Steel", "t"),
                ("AGG-20", "Aggregates (20mm)", "t"),
                ("GLS-L", "Low-E Glass", "m2"),
            ]
            suppliers = ["EcoMaterials Ltd", "GreenBuild Supply", "Sustainable Steel Co"]

            for i in range(18):
                project = projects[i % len(projects)]
                code, name, unit = material_defs[i % len(material_defs)]
                redeemed = (i % 3) != 0  # ~66% redeemed

                token = MaterialToken(
                    project_id=project.id,
                    material_code=code,
                    material_name=name,
                    quantity=round(10 + (i * 2.25), 3),
                    unit=unit,
                    supplier_name=suppliers[i % len(suppliers)],
                    issued_by="contractor@example.com",
                    issued_at=now - timedelta(days=30 - i),
                    redeemed=redeemed,
                    redeemed_at=(now - timedelta(days=5)) if redeemed else None,
                    delivery_photo_path=(
                        "/app/uploads/material_evidence/demo.jpg" if redeemed else None
                    ),
                    delivery_lat=(project.lat + 0.0005 * (i + 1)) if redeemed else None,
                    delivery_lon=(project.lon + 0.0005 * (i + 1)) if redeemed else None,
                    supplier_invoice_ref=(f"INV-{1000+i}" if redeemed else None),
                )
                session.add(token)
                tokens.append(token)

            await session.commit()
            for t in tokens:
                await session.refresh(t)
        else:
            tokens = (await session.execute(select(MaterialToken))).scalars().all()

        # Delivery verifications for some redeemed tokens
        verifications_exist = (
            await session.execute(select(DeliveryVerification.id).limit(1))
        ).scalar_one_or_none()
        if verifications_exist is None and tokens:
            for t in [x for x in tokens if x.redeemed][:10]:
                dv = DeliveryVerification(
                    material_token_id=t.id,
                    photo_path=t.delivery_photo_path or "/app/uploads/material_evidence/demo.jpg",
                    photo_fingerprint=("0" * 64),
                    delivery_lat=float(t.delivery_lat or 0.0),
                    delivery_lon=float(t.delivery_lon or 0.0),
                    gps_hash=("1" * 64),
                    verified_at=now - timedelta(days=3),
                    verified_by="inspector@example.com",
                    is_verified=True,
                    verification_notes="Seeded verification record",
                )
                session.add(dv)

        # Sensor readings (energy)
        if readings_exist is None:
            for i, project in enumerate(projects):
                for j in range(8):
                    sr = SensorReading(
                        project_id=project.id,
                        sensor_type=SensorType.ENERGY,
                        value=round(500 + (i * 100) + (j * 25), 3),
                        unit="kWh",
                        ts=now - timedelta(days=60 - (j * 7)),
                        lat=project.lat,
                        lon=project.lon,
                    )
                    session.add(sr)

        # MRV reports (approved/locked for CO2 totals)
        if reports_exist is None:
            for i, project in enumerate(projects):
                for q in ["2025-Q1", "2025-Q2"]:
                    status = MRVStatus.APPROVED if q == "2025-Q1" else MRVStatus.LOCKED
                    r = MRVReport(
                        project_id=project.id,
                        reporting_period=q,
                        sample_desc=f"Quarterly MRV report {q}",
                        parameter="co2e_total",
                        value=str(1000 + (i * 250)),
                        total_co2e=round(1000 + (i * 250) + (100 if q == "2025-Q2" else 0), 6),
                        status=status,
                        created_by=mrv_user.id,
                        verified_by=verifier_user.id,
                        approved_by=approver_user.id,
                    )
                    session.add(r)

        # Anomalies
        if anomalies_exist is None and tokens:
            anomalies = [
                AnomalyAlert(
                    project_id=projects[0].id,
                    token_uid=tokens[0].token_uid,
                    rule_code="DISTANCE_MISMATCH",
                    severity=AnomalySeverity.MEDIUM,
                    description="Delivery GPS distance exceeded expected tolerance.",
                    numeric_value=1200.0,
                    threshold=500.0,
                    detected_at=now - timedelta(days=7),
                ),
                AnomalyAlert(
                    project_id=projects[1].id,
                    token_uid=tokens[1].token_uid,
                    rule_code="DUPLICATE_PHOTO",
                    severity=AnomalySeverity.HIGH,
                    description="Photo fingerprint reuse detected across deliveries.",
                    detected_at=now - timedelta(days=12),
                ),
            ]
            session.add_all(anomalies)

        # Whistleblower cases
        if whistle_exist is None:
            whistle = [
                Whistleblower(
                    project_id=projects[0].id,
                    message="Supplier documentation appears inconsistent.",
                    evidence_path=None,
                    status=WhistleblowerStatus.OPEN,
                    priority=WhistleblowerPriority.MEDIUM,
                    created_at=now - timedelta(days=4),
                ),
                Whistleblower(
                    project_id=None,
                    message="General concern about material quality verification.",
                    evidence_path=None,
                    status=WhistleblowerStatus.NEW,
                    priority=WhistleblowerPriority.LOW,
                    created_at=now - timedelta(days=2),
                ),
            ]
            session.add_all(whistle)

        # Public metrics (aggregates) per project
        if public_metrics_exist is None:
            for i, project in enumerate(projects):
                pm = PublicMetrics(
                    project_id=project.id,
                    total_co2_saved_t=round(250 + i * 75, 6),
                    verified_co2_t=round(200 + i * 60, 6),
                    total_materials_t=round(500 + i * 150, 6),
                    last_updated=now,
                    created_at=now,
                )
                session.add(pm)

        await session.commit()

    print("Seed complete: dashboard demo data created.")


if __name__ == "__main__":
    asyncio.run(seed_dashboard())
