"""Tests for MRV models."""

import asyncio
import sys
from pathlib import Path
import uuid
from datetime import datetime, timezone

# Ensure backend root is on sys.path
CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import AsyncSessionLocal
from app.mrv.models import (
    MRVSample, MRVTest, Lab, ChainStep, MRVEventLog, MRVSampleStatus
)
from app.models.project import Project


async def test_mrv_models():
    """Test creating and querying MRV models."""
    print("Testing MRV models...")
    
    async with AsyncSessionLocal() as session:
        # Create a test project first
        project_uuid = uuid.uuid4()
        project = Project(
            name="Test MRV Project",
            status="active",
            lat=13.0892,
            lon=80.2788,
            budget_usd=1000000.0,
            created_by=project_uuid,  # Use UUID object for Project model
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        
        # Test Lab creation
        lab = Lab(
            name="Test Laboratory",
            address="123 Test St, Test City",
            accreditation="ISO 17025",
            contact="test@lab.com",
        )
        session.add(lab)
        await session.commit()
        await session.refresh(lab)
        
        # Test MRVSample creation with unique ID
        sample_id = f"TEST-{str(uuid.uuid4())[:8]}"
        sample = MRVSample(
            sample_id=sample_id,
            project_id=str(project.id),  # Convert UUID to string for MRV model
            collected_by="Test Collector",
            geotag_lat=13.0892,
            geotag_lon=80.2788,
            sample_type="concrete",
            notes="Test sample for concrete testing",
            status=MRVSampleStatus.COLLECTED,
        )
        session.add(sample)
        await session.commit()
        await session.refresh(sample)
        
        # Test ChainStep creation
        chain_step = ChainStep(
            sample_id=sample.sample_id,
            actor="Test Collector",
            action="Sample collected from site",
            evidence_file="/uploads/evidence/test.jpg",
        )
        session.add(chain_step)
        await session.commit()
        await session.refresh(chain_step)
        
        # Test MRVTest creation
        test = MRVTest(
            sample_id=sample.sample_id,
            lab_id=lab.lab_id,
            parameter="Compressive Strength",
            value="30.5",
            unit="MPa",
            method="ASTM C39",
            lab_report_id="LAB-001",
            passed=True,
            notes="Test passed successfully",
        )
        session.add(test)
        await session.commit()
        await session.refresh(test)
        
        # Test MRVEventLog creation
        event_log = MRVEventLog(
            ref_type="sample",
            ref_id=sample.sample_id,
            event="sample_created",
            actor="Test Collector",
            details={
                "sample_type": sample.sample_type,
                "location": {"lat": float(sample.geotag_lat), "lon": float(sample.geotag_lon)},
                "project": project.name,
            },
        )
        session.add(event_log)
        await session.commit()
        await session.refresh(event_log)
        
        # Test basic functionality
        print(f"Created sample: {sample.sample_id}")
        print(f"Sample status: {sample.status}")
        print(f"Sample project: {project.name}")  # Use project object directly
        print(f"Lab: {lab.name}")
        print(f"Test result: {test.parameter} = {test.value} {test.unit}")
        print(f"Test passed: {test.passed}")
        print(f"Chain steps: {len(sample.chain_steps)}")
        print(f"Event logs: {len([event_log])}")
        
        # Test to_dict methods
        sample_dict = sample.to_dict()
        test_dict = test.to_dict()
        lab_dict = lab.to_dict()
        
        print(f"Sample dict keys: {list(sample_dict.keys())}")
        print(f"Test dict keys: {list(test_dict.keys())}")
        print(f"Lab dict keys: {list(lab_dict.keys())}")
        
        # Test __repr__ methods
        print(f"Sample repr: {repr(sample)}")
        print(f"Test repr: {repr(test)}")
        print(f"Lab repr: {repr(lab)}")
        print(f"Chain step repr: {repr(chain_step)}")
        print(f"Event log repr: {repr(event_log)}")
        
        # Clean up
        await session.delete(event_log)
        await session.delete(test)
        await session.delete(chain_step)
        await session.delete(sample)
        await session.delete(lab)
        await session.delete(project)
        await session.commit()
        
        print("MRV models test completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_mrv_models())
