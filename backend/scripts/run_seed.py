"""S3-C seed script for dev SQLite database.

Run with:  python scripts/run_seed.py   (from backend/)
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random

from sqlalchemy import create_engine, delete, select, text, func
from sqlalchemy.ext.asyncio import AsyncSession


# Ensure backend root (where `app/` lives) is on sys.path when running
CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionLocal
from app.models.role import Role, RoleName
from app.models.user import User
from app.models.project import Project, ProjectStatus
from app.models.material_token import MaterialToken
from app.models.anomaly_alert import AnomalyAlert
from app.models.mrv_report import MRVReport, MRVStatus
from app.models.whistleblower import Whistleblower
from app.models.sensor_reading import SensorReading, SensorType


DATABASE_URL = settings.DATABASE_URL
print("Using DATABASE_URL:", DATABASE_URL)


def _ensure_sqlite_db_exists() -> None:
    """Create dev.db file and schema if missing (SQLite only)."""
    if not DATABASE_URL.startswith("sqlite+aiosqlite"):
        return

    # Extract file path from URL like sqlite+aiosqlite:///./dev.db
    if "///" in DATABASE_URL:
        db_path_str = DATABASE_URL.split("///", 1)[1]
    else:
        db_path_str = "dev.db"

    db_path = Path(db_path_str).resolve()
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    first_create = not db_path.exists()
    if first_create:
        print(f"Creating new SQLite DB {db_path} …")

    sync_url = DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(sync_url, future=True)
    Base.metadata.create_all(bind=engine)


async def _clear_tables(session: AsyncSession) -> None:
    """Delete all rows from seed-related tables so script is idempotent."""
    # Order matters due to foreign keys (children first)
    for model in (SensorReading, AnomalyAlert, MRVReport, MaterialToken, Whistleblower, Project, User, Role):
        await session.execute(delete(model))
    await session.commit()

    # For SQLite, AUTOINCREMENT is handled automatically; no explicit sequence reset needed.


async def seed_roles(session: AsyncSession) -> dict[RoleName, int]:
    role_names = [
        "admin",
        "project_manager",
        "contractor",
        "mrv_officer",
        "supplier",
        "citizen",
    ]

    for r in role_names:
        session.add(Role(name=RoleName(r)))
    await session.commit()

    roles = (await session.execute(select(Role))).scalars().all()
    return {r.name: r.id for r in roles}


async def seed_users(session: AsyncSession, role_ids: dict[RoleName, int]) -> None:
    """Create 6 demo users with bcrypt hashed passwords (<72 bytes)."""
    users_data = [
        {
            "email": "admin@example.com",
            "full_name": "Administrator",
            "password": "Admin123!",
            "role": RoleName.ADMIN,
        },
        {
            "email": "pm@example.com", 
            "full_name": "Project Manager",
            "password": "PM123456!",
            "role": RoleName.PROJECT_MANAGER,
        },
        {
            "email": "contractor@example.com",
            "full_name": "Contractor Lead",
            "password": "Contract789!",
            "role": RoleName.CONTRACTOR,
        },
        {
            "email": "mrv@example.com",
            "full_name": "MRV Officer",
            "password": "MRV456123!",
            "role": RoleName.MRV_OFFICER,
        },
        {
            "email": "supplier@example.com",
            "full_name": "Supplier Manager",
            "password": "Supply789!",
            "role": RoleName.SUPPLIER,
        },
        {
            "email": "citizen@example.com",
            "full_name": "Citizen User",
            "password": "Citizen123!",
            "role": RoleName.CITIZEN,
        },
    ]

    for user_data in users_data:
        user = User(
            email=user_data["email"],
            full_name=user_data["full_name"],
            hashed_password=get_password_hash(user_data["password"]),
            is_active=True,
            role_id=role_ids[user_data["role"]],
            created_at=datetime.now(timezone.utc),
        )
        session.add(user)
    
    await session.commit()


async def get_admin_user(session: AsyncSession) -> User | None:
    res = await session.execute(select(User).join(Role).where(Role.name == RoleName.ADMIN))
    return res.scalar_one_or_none()


async def seed_projects(session: AsyncSession, admin: User) -> list[Project]:
    """Create three demo projects with coordinates and budgets."""
    now = datetime.now(timezone.utc)
    defs = [
        {
            "name": "Riverfront Affordable Housing",
            "status": ProjectStatus.ACTIVE,
            "lat": 13.0892,
            "lon": 80.2788,
            "budget_usd": 5_000_000,
            "offset_days": 0,
        },
        {
            "name": "Urban Retrofit - Block A",
            "status": ProjectStatus.IN_PROGRESS,
            "lat": 12.9716,
            "lon": 77.5946,
            "budget_usd": 1_200_000,
            "offset_days": 40,
        },
        {
            "name": "School Solar Microgrid",
            "status": ProjectStatus.COMPLETED,
            "lat": 11.0168,
            "lon": 76.9558,
            "budget_usd": 350_000,
            "offset_days": 300,
        },
    ]

    projects: list[Project] = []
    for p in defs:
        proj = Project(
            name=p["name"],
            status=p["status"],
            lat=p["lat"],
            lon=p["lon"],
            budget_usd=p["budget_usd"],
            created_by=admin.id,
            created_at=now - timedelta(days=p["offset_days"]),
        )
        session.add(proj)
        projects.append(proj)

    await session.commit()
    return projects


async def seed_material_tokens(session: AsyncSession, projects: list[Project]) -> None:
    """Create 30 MaterialToken entries across projects with realistic data."""
    material_types = ["cement", "steel", "recycled_steel", "aggregates", "bricks", "glass", "insulation"]
    suppliers = ["EcoMaterials Ltd", "GreenBuild Supply", "Sustainable Steel Co", "Recycled Aggregates Inc", "Smart Glass Systems"]
    now = datetime.now(timezone.utc)

    for i in range(30):
        project = random.choice(projects)
        mtype = random.choice(material_types)
        qty = round(random.uniform(5.0, 500.0), 2)
        redeemed = random.choice([True, False])
        unit_price = round(random.uniform(50.0, 800.0), 2)
        
        # Add realistic redemption coordinates if redeemed
        if redeemed:
            redemption_lat = project.lat + random.uniform(-0.01, 0.01)
            redemption_lon = project.lon + random.uniform(-0.01, 0.01)
        else:
            redemption_lat = None
            redemption_lon = None
            
        token = MaterialToken(
            project_id=project.id,
            material_type=mtype,
            qty=qty,
            unit_price=unit_price,
            supplier=random.choice(suppliers),
            issued_at=now - timedelta(days=random.randint(0, 180)),
            redeemed=redeemed,
            redemption_lat=redemption_lat,
            redemption_lon=redemption_lon,
            recycled=random.choice([True, False]) if "recycled" not in mtype else True,
        )
        session.add(token)

    await session.commit()


async def seed_mrv_reports(session: AsyncSession, projects: list[Project]) -> None:
    """Create 10 MRVReport entries with fake values."""
    now = datetime.now(timezone.utc)
    params = ["co2_sample", "energy_audit", "waste_audit", "water_audit"]

    for _ in range(10):
        project = random.choice(projects)
        param = random.choice(params)
        report = MRVReport(
            project_id=project.id,
            sample_desc=f"Sample for {param}",
            parameter=param,
            value=str(round(random.uniform(10.0, 500.0), 2)),
            ts=now - timedelta(days=random.randint(0, 90)),
            status=random.choice([MRVStatus.PENDING, MRVStatus.VERIFIED]),
        )
        session.add(report)

    await session.commit()


async def seed_anomalies(session: AsyncSession, projects: list[Project]) -> None:
    """Create 15 anomaly alerts with random severity scores."""
    now = datetime.now(timezone.utc)

    for _ in range(15):
        project = random.choice(projects)
        score = round(random.uniform(0.1, 1.0), 3)
        rule_score = round(score * random.uniform(0.3, 0.7), 3)
        ml_score = round(score - rule_score, 3)
        alert = AnomalyAlert(
            project_id=project.id,
            entity_type=random.choice(["sensor", "delivery", "token"]),
            score=score,
            rule_score=rule_score,
            ml_score=ml_score,
            flagged=score > 0.7,
            reviewed=False,
            payload={"note": "auto-generated demo anomaly"},
            created_at=now - timedelta(days=random.randint(0, 30)),
        )
        session.add(alert)

    await session.commit()


async def seed_sensor_readings(session: AsyncSession, projects: list[Project]) -> None:
    """Create 50 SensorReading entries for energy and water_saving."""
    now = datetime.now(timezone.utc)

    for _ in range(50):
        project = random.choice(projects)
        stype = random.choice([SensorType.ENERGY, SensorType.WATER_SAVING])
        if stype == SensorType.ENERGY:
            value = round(random.uniform(100.0, 5000.0), 2)
            unit = "kWh"
        else:
            value = round(random.uniform(1000.0, 50000.0), 2)
            unit = "liters"

        reading = SensorReading(
            project_id=project.id,
            sensor_type=stype,
            value=value,
            unit=unit,
            ts=now - timedelta(days=random.randint(0, 90)),
            lat=project.lat + random.uniform(-0.001, 0.001),
            lon=project.lon + random.uniform(-0.001, 0.001),
        )
        session.add(reading)

    await session.commit()


async def seed_whistleblower_cases(session: AsyncSession, projects: list[Project]) -> None:
    """Create 5 whistleblower cases."""
    from app.models.whistleblower import WhistleblowerStatus
    
    cases = [
        {
            "message": "Materials delivered after hours without proper documentation",
            "priority": "high",
            "status": WhistleblowerStatus.OPEN,
        },
        {
            "message": "Suspected use of non-certified materials on structural elements",
            "priority": "high", 
            "status": WhistleblowerStatus.NEW,
        },
        {
            "message": "Waste disposal procedures not being followed correctly",
            "priority": "medium",
            "status": WhistleblowerStatus.OPEN,
        },
        {
            "message": "Energy consumption readings appear manipulated",
            "priority": "high",
            "status": WhistleblowerStatus.OPEN,
        },
        {
            "message": "Safety protocols being bypassed during rush periods",
            "priority": "medium",
            "status": WhistleblowerStatus.CLOSED,
        },
    ]
    
    now = datetime.now(timezone.utc)
    
    for i, case_data in enumerate(cases):
        project = random.choice(projects)
        report = Whistleblower(
            project_id=project.id,
            message=case_data["message"],
            evidence_path=f"/uploads/evidence_{i+1}.pdf",
            status=case_data["status"],
            priority=case_data["priority"],
            created_at=now - timedelta(days=random.randint(1, 60)),
        )
        session.add(report)

    await session.commit()


async def main() -> None:
    _ensure_sqlite_db_exists()

    async with AsyncSessionLocal() as session:
        # Make script safe to run multiple times
        await _clear_tables(session)

        # Seed core entities
        role_ids = await seed_roles(session)
        await seed_users(session, role_ids)
        admin = await get_admin_user(session)
        if admin is None:
            raise RuntimeError("Admin user not found after seeding users")

        projects = await seed_projects(session, admin)
        await seed_material_tokens(session, projects)
        await seed_mrv_reports(session, projects)
        await seed_anomalies(session, projects)
        await seed_sensor_readings(session, projects)
        await seed_whistleblower_cases(session, projects)

        # Summary counts
        async def _count(model: type[Base]) -> int:
            result = await session.execute(select(func.count()).select_from(model))
            return int(result.scalar_one())

        users_count = await _count(User)
        roles_count = await _count(Role)
        projects_count = await _count(Project)
        tokens_count = await _count(MaterialToken)
        alerts_count = await _count(AnomalyAlert)

    print(
        "Seed complete. Counts  "
        f"users: {users_count}, roles: {roles_count}, "
        f"projects: {projects_count}, tokens: {tokens_count}, alerts: {alerts_count}"
    )
    print("Run seed:  python scripts/run_seed.py")


if __name__ == "__main__":
    asyncio.run(main())
