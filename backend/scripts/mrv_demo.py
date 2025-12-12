"""MRV demo data creation script.

Run with: python scripts/mrv_demo.py
"""

import asyncio
import sys
from pathlib import Path
import uuid

# Ensure backend root is on sys.path
CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import AsyncSessionLocal
from app.mrv.models import MRVSample, MRVTest, Lab, ChainStep, MRVEventLog, MRVSampleStatus
from app.models.project import Project
from sqlalchemy import select


async def create_mrv_demo_data():
    """Create demo data for MRV system."""
    print("Creating MRV demo data...")
    
    async with AsyncSessionLocal() as session:
        # Get existing projects or create demo ones
        projects_result = await session.execute(select(Project).limit(3))
        projects = projects_result.scalars().all()
        
        if not projects:
            # Create demo projects
            demo_projects = [
                Project(
                    name="Urban Retrofit - Block A",
                    status="active",
                    lat=13.0892,
                    lon=80.2788,
                    budget_usd=1200000.0,
                    created_by=uuid.uuid4(),
                ),
                Project(
                    name="Riverfront Affordable Housing",
                    status="active", 
                    lat=13.0895,
                    lon=80.2792,
                    budget_usd=5000000.0,
                    created_by=uuid.uuid4(),
                ),
                Project(
                    name="School Solar Microgrid",
                    status="active",
                    lat=13.0888,
                    lon=80.2785,
                    budget_usd=350000.0,
                    created_by=uuid.uuid4(),
                ),
            ]
            
            for project in demo_projects:
                session.add(project)
            await session.commit()
            for project in demo_projects:
                await session.refresh(project)
            projects = demo_projects
        
        # Create demo labs
        demo_labs = [
            Lab(
                name="Sustainable Materials Testing Lab",
                address="123 Green Street, Chennai, Tamil Nadu 600001",
                accreditation="ISO 17025:2017, NABL",
                contact="contact@sustainablelab.in",
            ),
            Lab(
                name="Advanced Concrete Research Center",
                address="456 Tech Park, Chennai, Tamil Nadu 600013",
                accreditation="ISO 9001:2015, BIS",
                contact="info@concreteresearch.co.in",
            ),
            Lab(
                name="Environmental Testing Services",
                address="789 Industrial Area, Chennai, Tamil Nadu 600045",
                accreditation="ISO 14001:2015, CPCB",
                contact="test@envlab.in",
            ),
        ]
        
        for lab in demo_labs:
            session.add(lab)
        await session.commit()
        for lab in demo_labs:
            await session.refresh(lab)
        
        # Create demo samples
        demo_samples = []
        sample_types = ["concrete", "steel", "soil", "water", "aggregates", "insulation"]
        
        for i, project in enumerate(projects):
            for j in range(3):  # 3 samples per project
                sample = MRVSample(
                    sample_id=f"DEMO-{i+1:02d}-{j+1:02d}",
                    project_id=str(project.id),  # Convert UUID to string
                    collected_by=f"Field Technician {j+1}",
                    geotag_lat=project.lat + (j * 0.001),
                    geotag_lon=project.lon + (j * 0.001),
                    sample_type=sample_types[j % len(sample_types)],
                    notes=f"Demo sample {j+1} for {project.name}",
                    status=MRVSampleStatus.TESTED if j < 2 else MRVSampleStatus.COLLECTED,
                )
                session.add(sample)
                demo_samples.append(sample)
        
        await session.commit()
        for sample in demo_samples:
            await session.refresh(sample)
        
        # Create chain of custody steps
        for sample in demo_samples:
            # Collection step
            chain_step1 = ChainStep(
                sample_id=sample.sample_id,
                actor=sample.collected_by,
                action="Sample collected from construction site",
                evidence_file="/uploads/evidence/collection.jpg",
            )
            session.add(chain_step1)
            
            # Transport step
            chain_step2 = ChainStep(
                sample_id=sample.sample_id,
                actor="Transport Service",
                action="Sample transported to laboratory",
                evidence_file="/uploads/evidence/transport.pdf",
            )
            session.add(chain_step2)
        
        await session.commit()
        
        # Create demo tests for tested samples
        tested_samples = [s for s in demo_samples if s.status == MRVSampleStatus.TESTED]
        
        test_parameters = {
            "concrete": [
                ("Compressive Strength", "MPa", "ASTM C39", True, "32.5"),
                ("Slump", "mm", "ASTM C143", True, "75"),
                ("Water Absorption", "%", "ASTM C642", True, "4.2"),
            ],
            "steel": [
                ("Tensile Strength", "MPa", "ASTM A370", True, "450"),
                ("Yield Strength", "MPa", "ASTM A370", True, "250"),
                ("Elongation", "%", "ASTM A370", True, "22"),
            ],
            "soil": [
                ("pH", "", "ASTM D4972", True, "7.2"),
                ("Moisture Content", "%", "ASTM D2216", True, "15.3"),
                ("Organic Matter", "%", "ASTM D2974", True, "2.8"),
            ],
            "water": [
                ("pH", "", "APHA 2110B", True, "6.8"),
                ("Turbidity", "NTU", "APHA 2130B", True, "2.1"),
                ("Dissolved Oxygen", "mg/L", "APHA 4500-O", True, "8.5"),
            ],
            "aggregates": [
                ("Specific Gravity", "", "ASTM C127", True, "2.65"),
                ("Absorption", "%", "ASTM C127", True, "1.2"),
                ("Fineness Modulus", "", "ASTM C136", True, "2.8"),
            ],
            "insulation": [
                ("Thermal Conductivity", "W/mK", "ASTM C518", True, "0.035"),
                ("Fire Resistance", "hours", "ASTM E119", True, "2.5"),
                ("Compressive Strength", "kPa", "ASTM C165", True, "120"),
            ],
        }
        
        for sample in tested_samples:
            parameters = test_parameters.get(sample.sample_type, test_parameters["concrete"])
            lab = demo_labs[int(sample.sample_id[-1]) % len(demo_labs)]  # Convert last digit to int
            
            for i, (param, unit, method, passed, value) in enumerate(parameters[:2]):  # 2 tests per sample
                test = MRVTest(
                    sample_id=sample.sample_id,
                    lab_id=str(lab.lab_id),  # Convert UUID to string
                    parameter=param,
                    value=value,
                    unit=unit,
                    method=method,
                    lab_report_id=f"LAB-{lab.name[:3].upper()}-{sample.sample_id}-{i+1}",
                    passed=passed,
                    notes=f"Test performed according to {method} standards",
                )
                session.add(test)
        
        await session.commit()
        
        # Create event logs
        for sample in demo_samples:
            # Sample creation event
            event1 = MRVEventLog(
                ref_type="sample",
                ref_id=sample.sample_id,
                event="sample_created",
                actor=sample.collected_by,
                details={
                    "sample_type": sample.sample_type,
                    "location": {"lat": float(sample.geotag_lat), "lon": float(sample.geotag_lon)},
                },
            )
            session.add(event1)
            
            # Status change event for tested samples
            if sample.status == MRVSampleStatus.TESTED:
                event2 = MRVEventLog(
                    ref_type="sample",
                    ref_id=sample.sample_id,
                    event="status_changed",
                    actor="Lab Technician",
                    details={
                        "old_status": "in_lab",
                        "new_status": "tested",
                        "tests_completed": 2,
                    },
                )
                session.add(event2)
        
        await session.commit()
        
        # Print summary
        print(f"Created MRV demo data:")
        print(f"  - Projects: {len(projects)}")
        print(f"  - Labs: {len(demo_labs)}")
        print(f"  - Samples: {len(demo_samples)}")
        print(f"  - Chain Steps: {len(demo_samples) * 2}")
        print(f"  - Tests: {len(tested_samples) * 2}")
        print(f"  - Event Logs: {len(demo_samples) + len(tested_samples)}")
        
        print("\nSample IDs created:")
        for sample in demo_samples[:5]:  # Show first 5
            print(f"  - {sample.sample_id}: {sample.sample_type} ({sample.status})")
        
        print("\nMRV demo data created successfully!")


if __name__ == "__main__":
    asyncio.run(create_mrv_demo_data())
