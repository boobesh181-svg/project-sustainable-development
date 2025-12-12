#!/usr/bin/env python3
"""
MRV Sample Data Seeding Script
"""

import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import async_engine
from app.mrv.models import MRVSample, MRVTest, Lab, ChainStep, MRVSampleStatus
from app.models.project import Project


async def create_sample_data():
    """Create sample MRV data"""
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession(async_engine) as db:
        # Create projects
        project1 = Project(
            id=uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),
            name="Green Office Complex",
            status="active",
            lat=37.7749,
            lon=-122.4194,
            budget_usd=50000000,
            created_by=uuid.UUID("550e8400-e29b-41d4-a716-446655440003")
        )
        project2 = Project(
            id=uuid.UUID("550e8400-e29b-41d4-a716-446655440002"),
            name="Eco Residential Tower", 
            status="active",
            lat=47.6062,
            lon=-122.3321,
            budget_usd=75000000,
            created_by=uuid.UUID("550e8400-e29b-41d4-a716-446655440003")
        )
        db.add(project1)
        db.add(project2)
        
        # Create labs
        lab1 = Lab(
            lab_id="lab-001",
            name="Certified Materials Testing Lab",
            address="123 Industrial Blvd, San Francisco, CA 94105",
            accreditation="ISO 17025",
            contact="Dr. Sarah Chen - sarah@certlab.com"
        )
        lab2 = Lab(
            lab_id="lab-002",
            name="Pacific Northwest Testing Services",
            address="456 Tech Park Way, Seattle, WA 98101", 
            accreditation="ISO 17025",
            contact="Prof. Michael Roberts - michael@pntest.com"
        )
        db.add(lab1)
        db.add(lab2)
        
        # Create samples
        sample1 = MRVSample(
            sample_id="SAMP-001",
            project_id="proj-001",
            collected_by="John Smith",
            collected_at=datetime(2025, 11, 15, 9, 0, 0, tzinfo=timezone.utc),
            geotag_lat=37.7749,
            geotag_lon=-122.4194,
            sample_type="concrete",
            notes="Normal concrete sample from foundation",
            status=MRVSampleStatus.TESTED
        )
        sample2 = MRVSample(
            sample_id="SAMP-002",
            project_id="proj-001",
            collected_by="Maria Garcia",
            collected_at=datetime(2025, 11, 16, 10, 30, 0, tzinfo=timezone.utc),
            geotag_lat=40.7128,
            geotag_lon=-74.006,
            sample_type="concrete",
            notes="Anomalous geotag - sample collected far from project site",
            status=MRVSampleStatus.TESTED
        )
        sample3 = MRVSample(
            sample_id="SAMP-003",
            project_id="proj-001",
            collected_by="David Kim",
            collected_at=datetime(2025, 11, 17, 14, 15, 0, tzinfo=timezone.utc),
            geotag_lat=37.7849,
            geotag_lon=-122.4094,
            sample_type="steel",
            notes="Steel sample with anomalous compressive strength",
            status=MRVSampleStatus.TESTED
        )
        db.add(sample1)
        db.add(sample2)
        db.add(sample3)
        
        # Create tests
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
            notes="Normal compressive strength for concrete"
        )
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
            notes="Expected density for concrete"
        )
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
            notes="Normal strength but geotag anomaly detected"
        )
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
            notes="Anomalous low yield strength for steel - should be >250MPa"
        )
        db.add(test1)
        db.add(test2)
        db.add(test3)
        db.add(test4)
        
        # Create chain steps
        step1 = ChainStep(
            id="CHAIN-001",
            sample_id="SAMP-001",
            actor="John Smith",
            action="sample_collected",
            timestamp=datetime(2025, 11, 15, 9, 0, 0, tzinfo=timezone.utc),
            evidence_file="evidence/sample_collection_001.jpg"
        )
        step2 = ChainStep(
            id="CHAIN-002",
            sample_id="SAMP-001",
            actor="John Smith", 
            action="transported_to_lab",
            timestamp=datetime(2025, 11, 15, 10, 30, 0, tzinfo=timezone.utc),
            evidence_file="evidence/transport_001.pdf"
        )
        db.add(step1)
        db.add(step2)
        
        await db.commit()
        print("Sample MRV data seeded successfully!")


if __name__ == "__main__":
    asyncio.run(create_sample_data())
