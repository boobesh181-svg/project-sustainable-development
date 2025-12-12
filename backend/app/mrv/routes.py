"""MRV ingestion API routes with role-based access control."""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.mrv.models import (
    MRVSample, MRVTest, ChainStep, MRVEventLog, MRVSampleStatus, Lab
)
from app.mrv.schemas import (
    MRVSampleCreate, MRVSampleResponse, MRVTestCreate, MRVTestResponse,
    ChainStepCreate, ChainStepResponse, MRVSampleDetailResponse
)
from app.mrv.utils_file import (
    save_upload, compute_geotag_distance, validate_file_type, 
    validate_file_size, get_file_size_mb
)
from app.services.mrv_service import MRVService
from app.models.project import Project
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["mrv"])


def require_role(required_roles: List[str]):
    """Dependency to check if user has required role."""
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Access denied. Required roles: {', '.join(required_roles)}"
            )
        return current_user
    return role_checker


# Sample endpoints
@router.post("/api/mrv/samples/", response_model=MRVSampleResponse)
async def create_sample(
    project_id: str = Form(...),
    collected_by: str = Form(...),
    collected_at: Optional[str] = Form(None),
    geotag_lat: Optional[float] = Form(None),
    geotag_lon: Optional[float] = Form(None),
    sample_type: str = Form(...),
    notes: Optional[str] = Form(None),
    evidence_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['contractor', 'collector']))
):
    """Create a new MRV sample with optional evidence file."""
    
    # Verify project exists
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Handle evidence file upload
    evidence_path = None
    if evidence_file:
        allowed_types = ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx']
        if not validate_file_type(evidence_file, allowed_types):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
            )
        
        if not validate_file_size(evidence_file, max_size_mb=10.0):
            raise HTTPException(
                status_code=400, 
                detail=f"File too large. Max size: 10.0 MB"
            )
        
        evidence_path = save_upload(evidence_file, prefix="sample_evidence_")
    
    # Parse collected_at timestamp
    collected_dt = datetime.now(timezone.utc)
    if collected_at:
        try:
            collected_dt = datetime.fromisoformat(collected_at.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid collected_at format")
    
    # Create sample
    sample_data = MRVSampleCreate(
        project_id=project_id,
        collected_by=collected_by,
        collected_at=collected_dt,
        geotag_lat=geotag_lat,
        geotag_lon=geotag_lon,
        sample_type=sample_type,
        notes=notes,
        evidence_file=evidence_path
    )
    
    sample = MRVSample(
        **sample_data.model_dump(),
        status=MRVSampleStatus.COLLECTED,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(sample)
    await db.commit()
    await db.refresh(sample)
    
    # Log event
    await MRVService._log_event(
        db, "sample", sample.sample_id, "created", current_user.email,
        {"project_id": project_id, "sample_type": sample_type}
    )
    
    return MRVSampleResponse.model_validate(sample)


@router.post("/api/mrv/samples/{sample_id}/chain")
async def add_chain_step(
    sample_id: str,
    actor: str = Form(...),
    action: str = Form(...),
    timestamp: Optional[str] = Form(None),
    evidence_file: Optional[UploadFile] = File(None),
    notes: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a chain of custody step to a sample."""
    
    # Verify sample exists
    sample_result = await db.execute(
        select(MRVSample).where(MRVSample.sample_id == sample_id)
    )
    sample = sample_result.scalar_one_or_none()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    # Handle evidence file
    evidence_path = None
    if evidence_file:
        allowed_types = ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx']
        if not validate_file_type(evidence_file, allowed_types):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
            )
        
        evidence_path = save_upload(evidence_file, prefix="chain_evidence_")
    
    # Parse timestamp
    step_timestamp = datetime.now(timezone.utc)
    if timestamp:
        try:
            step_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")
    
    # Create chain step
    chain_step = ChainStep(
        sample_id=sample_id,
        actor=actor,
        action=action,
        timestamp=step_timestamp,
        evidence_file=evidence_path,
        notes=notes
    )
    
    db.add(chain_step)
    
    # Update sample's chain_of_custody
    sample.chain_of_custody.append(action)
    
    await db.commit()
    await db.refresh(chain_step)
    
    # Log event
    await MRVService._log_event(
        db, "sample", sample_id, "chain_step_added", current_user.email,
        {"actor": actor, "action": action}
    )
    
    return ChainStepResponse.model_validate(chain_step)


@router.post("/api/mrv/samples/{sample_id}/submit_lab")
async def submit_to_lab(
    sample_id: str,
    lab_id: str = Form(...),
    expected_tests: List[str] = Form(...),
    submitted_at: Optional[str] = Form(None),
    sample_condition: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['contractor', 'collector']))
):
    """Submit sample to laboratory for testing."""
    
    # Verify sample exists
    sample_result = await db.execute(
        select(MRVSample).where(MRVSample.sample_id == sample_id)
    )
    sample = sample_result.scalar_one_or_none()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    # Verify lab exists
    lab_result = await db.execute(
        select(Lab).where(Lab.lab_id == lab_id)
    )
    lab = lab_result.scalar_one_or_none()
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratory not found")
    
    # Parse submitted_at
    submitted_dt = datetime.now(timezone.utc)
    if submitted_at:
        try:
            submitted_dt = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid submitted_at format")
    
    # Update sample status and lab info
    sample.status = MRVSampleStatus.IN_LAB
    sample.lab_id = lab_id
    sample.submitted_at = submitted_dt
    sample.expected_tests = expected_tests
    sample.sample_condition = sample_condition
    
    await db.commit()
    await db.refresh(sample)
    
    # Log event
    await MRVService._log_event(
        db, "sample", sample_id, "submitted_to_lab", current_user.email,
        {"lab_id": lab_id, "expected_tests": expected_tests}
    )
    
    return MRVSampleResponse.model_validate(sample)


@router.post("/api/mrv/tests/{sample_id}/upload")
async def upload_test_result(
    sample_id: str,
    parameter: str = Form(...),
    value: str = Form(...),
    unit: str = Form(...),
    method: str = Form(...),
    tested_at: Optional[str] = Form(None),
    certificate_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['lab', 'mrv_officer']))
):
    """Upload test result with certificate file."""
    
    # Verify sample exists
    sample_result = await db.execute(
        select(MRVSample).where(MRVSample.sample_id == sample_id)
    )
    sample = sample_result.scalar_one_or_none()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    # Validate certificate file
    allowed_types = ['.pdf', '.jpg', '.jpeg', '.png']
    if not validate_file_type(certificate_file, allowed_types):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid certificate file type. Allowed: {', '.join(allowed_types)}"
        )
    
    if not validate_file_size(certificate_file, max_size_mb=20.0):
        raise HTTPException(
            status_code=400, 
            detail=f"Certificate file too large. Max size: 20.0 MB"
        )
    
    # Save certificate file
    certificate_path = save_upload(certificate_file, prefix="test_certificate_")
    
    # Parse tested_at
    tested_dt = datetime.now(timezone.utc)
    if tested_at:
        try:
            tested_dt = datetime.fromisoformat(tested_at.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tested_at format")
    
    # Create test record with comprehensive QA checks
    test_data = MRVTestCreate(
        sample_id=sample_id,
        parameter=parameter,
        value=value,
        unit=unit,
        method=method,
        tested_at=tested_dt,
        certificate_file=certificate_path
    )
    
    test = MRVTest(**test_data.model_dump())
    
    # Calculate certificate hash for duplicate detection
    from app.mrv.qa import calculate_certificate_hash
    if certificate_path:
        test.certificate_hash = calculate_certificate_hash(certificate_path)
    
    db.add(test)
    await db.commit()
    await db.refresh(test)
    
    # Run comprehensive QA checks
    from app.mrv.qa import run_quick_mrv_checks
    from app.mrv.notifications import notify_mrv_officer, create_event_log_notification
    
    # Get existing tests for this sample
    existing_tests_result = await db.execute(
        select(MRVTest).where(MRVTest.sample_id == sample_id)
    )
    existing_tests = existing_tests_result.scalars().all()
    existing_test_params = [t.parameter for t in existing_tests if t.id != test.id]
    
    # Get project geotag (placeholder - in real implementation, get from project record)
    project_geotag = (40.7128, -74.0060)  # Default NYC coordinates
    
    # Run QA checks
    qa_results = await run_quick_mrv_checks(
        db=db,
        sample=sample,
        test=test,
        project_geotag=project_geotag,
        existing_tests=existing_test_params
    )
    
    # Update test and sample based on QA results
    test.passed = qa_results["overall_pass"]
    sample.mrv_flags = qa_results
    sample.status = MRVSampleStatus.TESTED  # Always set to tested after upload
    
    await db.commit()
    await db.refresh(test)
    await db.refresh(sample)
    
    # Send notifications based on QA results
    if qa_results["overall_pass"]:
        # Test passed - notify MRV officer for review
        await notify_mrv_officer(
            sample_id=sample_id,
            event_type="test_passed",
            details={
                "parameter": parameter,
                "value": value,
                "unit": unit,
                "qa_summary": qa_results["summary"],
                "warnings": qa_results["warnings"]
            }
        )
        
        # Log successful test event
        await create_event_log_notification(
            ref_type="test",
            ref_id=test.id,
            event="test_passed_qa",
            actor=current_user.email,
            details={
                "parameter": parameter,
                "qa_results": qa_results
            }
        )
    else:
        # Test failed QA - flag for attention
        await notify_mrv_officer(
            sample_id=sample_id,
            event_type="qa_flags",
            details={
                "parameter": parameter,
                "value": value,
                "unit": unit,
                "failed_checks": [k for k, v in qa_results.items() if k.endswith("_flag") and not v["passed"]],
                "warnings": qa_results["warnings"],
                "qa_summary": qa_results["summary"]
            }
        )
        
        # Log QA failure event
        await create_event_log_notification(
            ref_type="test",
            ref_id=test.id,
            event="qa_flags_detected",
            actor=current_user.email,
            details={
                "parameter": parameter,
                "failed_checks": [k for k, v in qa_results.items() if k.endswith("_flag") and not v["passed"]],
                "qa_results": qa_results
            }
        )
    
    # Log test upload event
    await MRVService._log_event(
        db, "test", test.id, "uploaded", current_user.email,
        {
            "parameter": parameter,
            "value": value,
            "unit": unit,
            "passed": test.passed,
            "qa_results": qa_results
        }
    )
    
    return {
        "test_id": test.id,
        "parameter": parameter,
        "value": value,
        "unit": unit,
        "passed": test.passed,
        "qa_results": qa_results,
        "certificate_file": certificate_path
    }


@router.get("/api/mrv/queue")
async def get_review_queue(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['mrv_officer', 'admin']))
):
    """Get list of tests pending review, sorted by highest risk."""
    
    # Get tests that need review (passed is NULL or flagged by QA)
    stmt = select(MRVTest, MRVSample, Project).join(
        MRVSample, MRVTest.sample_id == MRVSample.sample_id
    ).join(
        Project, MRVSample.project_id == Project.id
    ).where(
        MRVTest.passed.is_(None)  # Not yet reviewed
    ).order_by(
        # Sort by risk: samples with QA flags first, then by test date
        MRVSample.created_at.desc()
    )
    
    result = await db.execute(stmt)
    queue_items = result.all()
    
    queue = []
    for test, sample, project in queue_items:
        # Calculate risk score based on QA flags
        risk_score = 0
        qa_flags = sample.mrv_flags or {}
        
        if not qa_flags.get("overall_pass", True):
            risk_score += 10  # High risk for failed QA
        
        if qa_flags.get("geotag_flag", {}).get("passed", True) == False:
            risk_score += 3
        
        if qa_flags.get("age_flag", {}).get("passed", True) == False:
            risk_score += 2
        
        if qa_flags.get("value_range_flag", {}).get("passed", True) == False:
            risk_score += 4
        
        if qa_flags.get("duplicate_cert_flag", {}).get("passed", True) == False:
            risk_score += 5
        
        queue.append({
            "test_id": test.id,
            "sample_id": test.sample_id,
            "project_id": project.id,
            "project_name": project.name,
            "parameter": test.parameter,
            "value": test.value,
            "unit": test.unit,
            "method": test.method,
            "tested_at": test.tested_at.isoformat(),
            "certificate_file": test.certificate_file,
            "sample_type": sample.sample_type,
            "sample_collected_at": sample.collected_at.isoformat(),
            "qa_flags": qa_flags,
            "risk_score": risk_score,
            "uploaded_by": test.lab_id  # Could be enhanced with user info
        })
    
    # Sort by risk score (highest first)
    queue.sort(key=lambda x: x["risk_score"], reverse=True)
    
    return {
        "queue": queue,
        "total_pending": len(queue),
        "high_risk_count": len([item for item in queue if item["risk_score"] >= 5])
    }


@router.get("/api/mrv/projects/{project_id}/co2-breakdown")
async def get_project_co2_breakdown(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get CO2 breakdown for a project"""
    
    # Verify project exists
    from app.models.project import Project
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Calculate CO2 breakdown
    from app.mrv.carbon import calculate_project_co2_breakdown
    breakdown = await calculate_project_co2_breakdown(db, project_id)
    
    return breakdown


@router.post("/api/mrv/tests/{test_id}/review")
async def review_test(
    test_id: str,
    action: str = Form(...),
    reviewer_id: str = Form(...),
    comments: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['mrv_officer', 'admin']))
):
    """Review and approve/reject MRV test."""
    
    # Verify test exists
    test_result = await db.execute(
        select(MRVTest).where(MRVTest.id == test_id)
    )
    test = test_result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Get associated sample
    sample_result = await db.execute(
        select(MRVSample).where(MRVSample.sample_id == test.sample_id)
    )
    sample = sample_result.scalar_one_or_none()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    # Validate action
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")
    
    # Process review
    if action == "approve":
        test.passed = True
        
        # Calculate CO2 contribution for approved test
        from app.mrv.carbon import compute_embodied_co2
        from app.mrv.models import CarbonLedger
        
        # Get all tests for this sample to compute CO2
        all_tests_result = await db.execute(
            select(MRVTest).where(MRVTest.sample_id == test.sample_id)
        )
        all_tests = all_tests_result.scalars().all()
        
        # Calculate CO2 for this sample
        co2_result = compute_embodied_co2(sample, all_tests)
        
        # Update test with CO2 contribution
        test.co2_contribution_kg = co2_result["co2_kg"]
        test.lca_method = co2_result.get("lca_method", "hybrid_epd")
        
        # Create carbon ledger entry
        ledger_entry = CarbonLedger(
            project_id=sample.project_id,
            sample_id=sample.sample_id,
            test_id=test.id,
            co2_kg=co2_result["co2_kg"],
            source="mrv_test_approval",
            material_type=sample.sample_type,
            quantity_tonnes=co2_result.get("quantity_tonnes", 0),
            lca_method=co2_result.get("lca_method", "hybrid_epd"),
            calculation_details=co2_result
        )
        db.add(ledger_entry)
        
        # Check if all tests for sample are now passed
        all_passed = all(t.passed for t in all_tests)
        
        if all_passed:
            sample.status = MRVSampleStatus.APPROVED
        else:
            sample.status = MRVSampleStatus.TESTED
            
        event_type = "test_approved"
        
    else:  # reject
        test.passed = False
        sample.status = MRVSampleStatus.REJECTED
        event_type = "test_rejected"
    
    # Update sample mrv_flags with review info
    if sample.mrv_flags:
        sample.mrv_flags["review"] = {
            "action": action,
            "reviewer_id": reviewer_id,
            "comments": comments,
            "reviewed_at": datetime.now(timezone.utc).isoformat()
        }
    
    await db.commit()
    
    # Log review event
    await MRVService._log_event(
        db, "test", test_id, event_type, current_user.email,
        {
            "action": action,
            "reviewer_id": reviewer_id,
            "comments": comments,
            "sample_status": sample.status.value
        }
    )
    
    # Send notification
    from app.mrv.notifications import create_event_log_notification
    await create_event_log_notification(
        ref_type="test",
        ref_id=test_id,
        event=event_type,
        actor=current_user.email,
        details={
            "action": action,
            "reviewer_id": reviewer_id,
            "comments": comments,
            "sample_id": test.sample_id
        }
    )
    
    return {
        "test_id": test_id,
        "action": action,
        "reviewer_id": reviewer_id,
        "sample_status": sample.status.value,
        "test_passed": test.passed
    }


@router.get("/api/mrv/samples/{sample_id}", response_model=MRVSampleDetailResponse)
async def get_sample_detail(
    sample_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get full sample details with tests and chain steps."""
    
    # Get sample with related data
    sample_result = await db.execute(
        select(MRVSample).where(MRVSample.sample_id == sample_id)
    )
    sample = sample_result.scalar_one_or_none()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    # Get tests
    tests_result = await db.execute(
        select(MRVTest).where(MRVTest.sample_id == sample_id)
        .order_by(MRVTest.tested_at.desc())
    )
    tests = tests_result.scalars().all()
    
    # Get chain steps
    chain_result = await db.execute(
        select(ChainStep).where(ChainStep.sample_id == sample_id)
        .order_by(ChainStep.timestamp.desc())
    )
    chain_steps = chain_result.scalars().all()
    
    return MRVSampleDetailResponse(
        sample=sample,
        tests=[MRVTestResponse.model_validate(test) for test in tests],
        chain_steps=[ChainStepResponse.model_validate(step) for step in chain_steps]
    )


@router.get("/api/mrv/projects/{project_id}/samples")
async def get_project_samples(
    project_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of samples for a project."""
    
    # Verify project exists
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Build query
    query = select(MRVSample).where(MRVSample.project_id == project_id)
    
    if status:
        try:
            status_enum = MRVSampleStatus(status)
            query = query.where(MRVSample.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Get total count
    result = await db.execute(query)
    total = len(result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.order_by(MRVSample.created_at.desc()).offset(offset).limit(size)
    
    result = await db.execute(query)
    samples = result.scalars().all()
    
    return {
        "samples": [MRVSampleResponse.model_validate(sample) for sample in samples],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }
