#!/usr/bin/env python3
"""
MRV Sample Data Seeding Script
"""

import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure backend root is on sys.path when run from backend/
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.base import Base
from app.db.session import async_engine
from app.mrv.models import MRVSample, MRVTest, Lab, ChainStep, MRVSampleStatus
from app.core.security import get_password_hash
from app.models.project import Project, ProjectStatus
from app.models.role import Role, RoleName
from app.models.user import User

from sqlalchemy import select


SEED_CREATOR_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440003")


async def _ensure_roles(db: AsyncSession) -> dict[RoleName, int]:
    existing = (await db.execute(select(Role))).scalars().all()
    if not existing:
        for name in RoleName:
            db.add(Role(name=name))
        await db.commit()
        existing = (await db.execute(select(Role))).scalars().all()
    return {r.name: r.id for r in existing}


async def _ensure_seed_user(db: AsyncSession, role_ids: dict[RoleName, int]) -> User:
    user = (
        await db.execute(select(User).where(User.id == SEED_CREATOR_ID))
    ).scalar_one_or_none()
    if user:
        return user

    # Create a deterministic seed user so seeded Projects satisfy FK constraints.
    user = User(
        id=SEED_CREATOR_ID,
        email="seed.creator@example.com",
        full_name="Seed Creator",
        hashed_password=get_password_hash("SeedCreator123!"),
        is_active=True,
        role_id=role_ids[RoleName.ADMIN],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_sample_data():
    """Create sample MRV data"""
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession(async_engine) as db:
        role_ids = await _ensure_roles(db)
        seed_user = await _ensure_seed_user(db, role_ids)

        # Create projects (idempotent)
        project1_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440001")
        project2_id = uuid.UUID("550e8400-e29b-41d4-a716-446655440002")

        project1 = await db.get(Project, project1_id)
        if project1 is None:
            project1 = Project(
                id=project1_id,
                name="Green Office Complex",
                status=ProjectStatus.ACTIVE,
                lat=37.7749,
                lon=-122.4194,
                budget_usd=50000000,
                created_by=seed_user.id,
            )
            db.add(project1)

        project2 = await db.get(Project, project2_id)
        if project2 is None:
            project2 = Project(
                id=project2_id,
                name="Eco Residential Tower",
                status=ProjectStatus.ACTIVE,
                lat=47.6062,
                lon=-122.3321,
                budget_usd=75000000,
                created_by=seed_user.id,
            )
            db.add(project2)
        
        # Create labs (idempotent)
        lab1 = await db.get(Lab, "lab-001")
        if lab1 is None:
            lab1 = Lab(
                lab_id="lab-001",
                name="Certified Materials Testing Lab",
                address="123 Industrial Blvd, San Francisco, CA 94105",
                accreditation="ISO 17025",
                contact="Dr. Sarah Chen - sarah@certlab.com",
            )
            db.add(lab1)

        lab2 = await db.get(Lab, "lab-002")
        if lab2 is None:
            lab2 = Lab(
                lab_id="lab-002",
                name="Pacific Northwest Testing Services",
                address="456 Tech Park Way, Seattle, WA 98101",
                accreditation="ISO 17025",
                contact="Prof. Michael Roberts - michael@pntest.com",
            )
            db.add(lab2)
        
        # Create samples (idempotent)
        sample1 = await db.get(MRVSample, "SAMP-001")
        if sample1 is None:
            sample1 = MRVSample(
                sample_id="SAMP-001",
                project_id=project1.id,
                collected_by="John Smith",
                collected_at=datetime(2025, 11, 15, 9, 0, 0, tzinfo=timezone.utc),
                geotag_lat=37.7749,
                geotag_lon=-122.4194,
                sample_type="concrete",
                notes="Normal concrete sample from foundation",
                status=MRVSampleStatus.TESTED,
            )
            db.add(sample1)

        sample2 = await db.get(MRVSample, "SAMP-002")
        if sample2 is None:
            sample2 = MRVSample(
                sample_id="SAMP-002",
                project_id=project1.id,
                collected_by="Maria Garcia",
                collected_at=datetime(2025, 11, 16, 10, 30, 0, tzinfo=timezone.utc),
                geotag_lat=40.7128,
                geotag_lon=-74.006,
                sample_type="concrete",
                notes="Anomalous geotag - sample collected far from project site",
                status=MRVSampleStatus.TESTED,
            )
            db.add(sample2)

        sample3 = await db.get(MRVSample, "SAMP-003")
        if sample3 is None:
            sample3 = MRVSample(
                sample_id="SAMP-003",
                project_id=project1.id,
                collected_by="David Kim",
                collected_at=datetime(2025, 11, 17, 14, 15, 0, tzinfo=timezone.utc),
                geotag_lat=37.7849,
                geotag_lon=-122.4094,
                sample_type="steel",
                notes="Steel sample with anomalous compressive strength",
                status=MRVSampleStatus.TESTED,
            )
            db.add(sample3)
        
        # Create tests (idempotent)
        test1 = await db.get(MRVTest, "TEST-001")
        if test1 is None:
            test1 = MRVTest(
                id="TEST-001",
                sample_id="SAMP-001",
                lab_id="lab-001",
                parameter="compressive_strength",
                value="30.5",
                unit="MPa",
                method="ASTM C39",
                tested_at=datetime(2025, 11, 20, 10, 0, 0, tzinfo=timezone.utc),
                passed=True,
                notes="Normal compressive strength for concrete",
            )
            db.add(test1)

        test2 = await db.get(MRVTest, "TEST-002")
        if test2 is None:
            test2 = MRVTest(
                id="TEST-002",
                sample_id="SAMP-001",
                lab_id="lab-001",
                parameter="density",
                value="2400",
                unit="kg/m3",
                method="ASTM C138",
                tested_at=datetime(2025, 11, 20, 10, 30, 0, tzinfo=timezone.utc),
                passed=True,
                notes="Expected density for concrete",
            )
            db.add(test2)

        test3 = await db.get(MRVTest, "TEST-003")
        if test3 is None:
            test3 = MRVTest(
                id="TEST-003",
                sample_id="SAMP-002",
                lab_id="lab-001",
                parameter="compressive_strength",
                value="28.0",
                unit="MPa",
                method="ASTM C39",
                tested_at=datetime(2025, 11, 21, 9, 15, 0, tzinfo=timezone.utc),
                passed=True,
                notes="Normal strength but geotag anomaly detected",
            )
            db.add(test3)

        test4 = await db.get(MRVTest, "TEST-004")
        if test4 is None:
            test4 = MRVTest(
                id="TEST-004",
                sample_id="SAMP-003",
                lab_id="lab-002",
                parameter="yield_strength",
                value="150",
                unit="MPa",
                method="ASTM A370",
                tested_at=datetime(2025, 11, 22, 14, 0, 0, tzinfo=timezone.utc),
                passed=False,
                notes="Anomalous low yield strength for steel - should be >250MPa",
            )
            db.add(test4)
        
        # Create chain steps (idempotent)
        step1 = await db.get(ChainStep, "CHAIN-001")
        if step1 is None:
            step1 = ChainStep(
                id="CHAIN-001",
                sample_id="SAMP-001",
                actor="John Smith",
                action="sample_collected",
                timestamp=datetime(2025, 11, 15, 9, 0, 0, tzinfo=timezone.utc),
                evidence_file="evidence/sample_collection_001.jpg",
            )
            db.add(step1)

        step2 = await db.get(ChainStep, "CHAIN-002")
        if step2 is None:
            step2 = ChainStep(
                id="CHAIN-002",
                sample_id="SAMP-001",
                actor="John Smith",
                action="transported_to_lab",
                timestamp=datetime(2025, 11, 15, 10, 30, 0, tzinfo=timezone.utc),
                evidence_file="evidence/transport_001.pdf",
            )
            db.add(step2)
        
        await db.commit()
        print("Sample MRV data seeded successfully!")


if __name__ == "__main__":
    asyncio.run(create_sample_data())
