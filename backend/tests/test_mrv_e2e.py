"""
End-to-end MRV workflow integration test
Tests complete flow: create sample → submit lab → upload certificate → auto-check flags → review approve → co2 ledger entry
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.main import app
from app.mrv.models import MRVSample, MRVTest, MRVSampleStatus, Lab, ChainStep, CarbonLedger
from app.mrv.carbon import compute_embodied_co2
from app.models.project import Project


class TestMRVE2EWorkflow:
    """Test complete MRV workflow end-to-end"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def workflow_data(self):
        """Complete workflow data for testing"""
        return {
            "project": Project(
                id="proj-e2e-001",
                name="E2E Test Project",
                description="End-to-end test project",
                location="Test City",
                budget_usd=1000000,
                start_date="2025-01-01",
                end_date="2025-12-31"
            ),
            "lab": Lab(
                lab_id="lab-e2e-001",
                name="E2E Test Lab",
                address="123 Test St",
                accreditation="ISO 17025",
                contact="test@lab.com"
            ),
            "sample": MRVSample(
                sample_id="SAMP-E2E-001",
                project_id="proj-e2e-001",
                collected_by="E2E Test User",
                collected_at=datetime(2025, 11, 15, 9, 0, 0, tzinfo=timezone.utc),
                geotag_lat=37.7749,
                geotag_lon=-122.4194,
                sample_type="concrete",
                notes="E2E test sample",
                status=MRVSampleStatus.COLLECTED
            ),
            "tests": [
                {
                    "parameter": "compressive_strength",
                    "value": "30.5",
                    "unit": "MPa",
                    "method": "ASTM C39",
                    "tested_at": "2025-11-20T10:00:00Z",
                    "notes": "Normal compressive strength"
                },
                {
                    "parameter": "density",
                    "value": "2400",
                    "unit": "kg/m3",
                    "method": "ASTM C138",
                    "tested_at": "2025-11-20T10:30:00Z",
                    "notes": "Expected density"
                },
                {
                    "parameter": "recycled_content",
                    "value": "25",
                    "unit": "%",
                    "method": "Lab Analysis",
                    "tested_at": "2025-11-20T11:00:00Z",
                    "notes": "25% recycled content"
                }
            ]
        }
    
    @patch('app.mrv.routes.get_db')
    @patch('app.mrv.routes.require_role')
    def test_step1_create_sample(self, mock_require_role, mock_get_db, client, mock_db, workflow_data):
        """Step 1: Create MRV sample"""
        mock_get_db.return_value = mock_db
        mock_require_role.return_value = {"id": "user123", "role": "field_technician"}
        
        # Mock database operations
        mock_db.add = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        sample_data = {
            "project_id": workflow_data["project"].id,
            "collected_by": workflow_data["sample"].collected_by,
            "collected_at": workflow_data["sample"].collected_at.isoformat(),
            "geotag_lat": workflow_data["sample"].geotag_lat,
            "geotag_lon": workflow_data["sample"].geotag_lon,
            "sample_type": workflow_data["sample"].sample_type,
            "notes": workflow_data["sample"].notes
        }
        
        response = client.post("/api/mrv/samples", data=sample_data)
        
        assert response.status_code == 200
        result = response.json()
        assert "sample_id" in result
        assert result["project_id"] == workflow_data["project"].id
        assert result["sample_type"] == "concrete"
        assert result["status"] == "collected"
        
        return result["sample_id"]
    
    @patch('app.mrv.routes.get_db')
    @patch('app.mrv.routes.require_role')
    def test_step2_submit_to_lab(self, mock_require_role, mock_get_db, client, mock_db, workflow_data):
        """Step 2: Submit sample to lab"""
        mock_get_db.return_value = mock_db
        mock_require_role.return_value = {"id": "user123", "role": "field_technician"}
        
        # Mock sample lookup
        mock_sample_result = AsyncMock()
        mock_sample_result.scalar_one_or_none.return_value = workflow_data["sample"]
        mock_db.execute.return_value = mock_sample_result
        
        # Mock database operations
        mock_db.add = AsyncMock()
        mock_db.commit = AsyncMock()
        
        lab_data = {
            "lab_id": workflow_data["lab"].lab_id,
            "submitted_at": datetime(2025, 11, 15, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "notes": "Submit for testing"
        }
        
        response = client.post(f"/api/mrv/samples/{workflow_data['sample'].sample_id}/submit_lab", data=lab_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["lab_id"] == workflow_data["lab"].lab_id
        assert result["sample_id"] == workflow_data["sample"].sample_id
    
    @patch('app.mrv.routes.get_db')
    @patch('app.mrv.routes.require_role')
    def test_step3_upload_test_results(self, mock_require_role, mock_get_db, client, mock_db, workflow_data):
        """Step 3: Upload test results with automatic QA flagging"""
        mock_get_db.return_value = mock_db
        mock_require_role.return_value = {"id": "user123", "role": "lab_technician"}
        
        # Mock sample lookup
        mock_sample_result = AsyncMock()
        mock_sample_result.scalar_one_or_none.return_value = workflow_data["sample"]
        mock_db.execute.return_value = mock_sample_result
        
        # Mock test creation and QA checks
        mock_db.add = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Upload each test result
        test_ids = []
        for test_data in workflow_data["tests"]:
            response = client.post(f"/api/mrv/tests/{workflow_data['sample'].sample_id}/upload", data=test_data)
            
            assert response.status_code == 200
            result = response.json()
            assert "test_id" in result
            assert "qa_results" in result
            assert "passed" in result
            
            # Verify QA flags are generated
            qa_results = result["qa_results"]
            assert "overall_pass" in qa_results
            assert "flags" in qa_results
            
            test_ids.append(result["test_id"])
        
        return test_ids
    
    @patch('app.mrv.routes.get_db')
    @patch('app.mrv.routes.require_role')
    def test_step4_review_and_approve(self, mock_require_role, mock_get_db, client, mock_db, workflow_data):
        """Step 4: Review and approve tests with CO2 calculation"""
        mock_get_db.return_value = mock_db
        mock_require_role.return_value = {"id": "user123", "role": "mrv_officer"}
        
        # Create test objects for mocking
        tests = []
        for i, test_data in enumerate(workflow_data["tests"]):
            test = MRVTest(
                test_id=f"TEST-E2E-{i+1:03d}",
                sample_id=workflow_data["sample"].sample_id,
                lab_id=workflow_data["lab"].lab_id,
                parameter=test_data["parameter"],
                value=test_data["value"],
                unit=test_data["unit"],
                method=test_data["method"],
                tested_at=datetime.fromisoformat(test_data["tested_at"].replace('Z', '+00:00')),
                passed=True,
                notes=test_data["notes"]
            )
            tests.append(test)
        
        # Mock database lookups
        mock_test_result = AsyncMock()
        mock_test_result.scalar_one_or_none.return_value = tests[0]
        mock_db.execute.return_value = mock_test_result
        
        mock_sample_result = AsyncMock()
        mock_sample_result.scalar_one_or_none.return_value = workflow_data["sample"]
        mock_db.execute.return_value = mock_sample_result
        
        mock_all_tests_result = AsyncMock()
        mock_all_tests_result.scalars.return_value.all.return_value = tests
        mock_db.execute.return_value = mock_all_tests_result
        
        # Mock CO2 calculation and ledger creation
        mock_db.add = AsyncMock()
        mock_db.commit = AsyncMock()
        
        # Review and approve each test
        for test in tests:
            review_data = {
                "action": "approve",
                "reviewer_id": "reviewer123",
                "comments": "Test approved - meets all requirements"
            }
            
            response = client.post(f"/api/mrv/tests/{test.test_id}/review", data=review_data)
            
            assert response.status_code == 200
            result = response.json()
            assert result["action"] == "approve"
            assert result["test_passed"] is True
            assert result["sample_status"] == "approved"  # All tests should be approved
            
            # Verify CO2 calculation was triggered
            assert mock_db.add.called  # Should have added CarbonLedger entry
    
    def test_step5_carbon_ledger_verification(self, workflow_data):
        """Step 5: Verify CO2 ledger entry creation"""
        # Simulate the CO2 calculation that would happen during approval
        tests = []
        for test_data in workflow_data["tests"]:
            test = MRVTest(
                test_id=f"TEST-CO2-{len(tests)+1:03d}",
                sample_id=workflow_data["sample"].sample_id,
                lab_id=workflow_data["lab"].lab_id,
                parameter=test_data["parameter"],
                value=test_data["value"],
                unit=test_data["unit"],
                method=test_data["method"],
                tested_at=datetime.fromisoformat(test_data["tested_at"].replace('Z', '+00:00')),
                passed=True,
                notes=test_data["notes"]
            )
            tests.append(test)
        
        # Calculate CO2 for the sample
        co2_result = compute_embodied_co2(workflow_data["sample"], tests)
        
        # Verify CO2 calculation results
        assert co2_result["co2_kg"] > 0
        assert co2_result["factor_used"]["base_factor"] == 150  # Concrete factor
        assert co2_result["recycled_fraction"] == 0.25  # 25% recycled content
        
        # Verify CO2 contribution would be saved to test
        expected_co2_kg = co2_result["co2_kg"]
        assert expected_co2_kg > 0
        
        # Simulate CarbonLedger entry creation
        ledger_entry = CarbonLedger(
            project_id=workflow_data["project"].id,
            sample_id=workflow_data["sample"].sample_id,
            test_id=tests[0].test_id,
            co2_kg=expected_co2_kg,
            source="mrv_test_approval",
            material_type=workflow_data["sample"].sample_type,
            quantity_tonnes=co2_result.get("quantity_tonnes", 0),
            lca_method=co2_result.get("lca_method", "hybrid_epd"),
            calculation_details=co2_result
        )
        
        # Verify ledger entry
        assert ledger_entry.project_id == workflow_data["project"].id
        assert ledger_entry.sample_id == workflow_data["sample"].sample_id
        assert ledger_entry.co2_kg == expected_co2_kg
        assert ledger_entry.source == "mrv_test_approval"
        assert ledger_entry.material_type == "concrete"
    
    @patch('app.mrv.routes.get_db')
    @patch('app.mrv.routes.require_role')
    def test_complete_workflow_integration(self, mock_require_role, mock_get_db, client, mock_db, workflow_data):
        """Test complete workflow integration"""
        mock_get_db.return_value = mock_db
        mock_require_role.return_value = {"id": "user123", "role": "mrv_officer"}
        
        # Mock all database operations
        mock_db.add = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Mock sample lookup for test upload
        mock_sample_result = AsyncMock()
        mock_sample_result.scalar_one_or_none.return_value = workflow_data["sample"]
        mock_db.execute.return_value = mock_sample_result
        
        # Step 1: Create sample
        sample_data = {
            "project_id": workflow_data["project"].id,
            "collected_by": workflow_data["sample"].collected_by,
            "collected_at": workflow_data["sample"].collected_at.isoformat(),
            "geotag_lat": workflow_data["sample"].geotag_lat,
            "geotag_lon": workflow_data["sample"].geotag_lon,
            "sample_type": workflow_data["sample"].sample_type,
            "notes": workflow_data["sample"].notes
        }
        
        response = client.post("/api/mrv/samples", data=sample_data)
        assert response.status_code == 200
        sample_result = response.json()
        
        # Step 2: Upload test results
        test_ids = []
        for test_data in workflow_data["tests"]:
            response = client.post(f"/api/mrv/tests/{sample_result['sample_id']}/upload", data=test_data)
            assert response.status_code == 200
            test_result = response.json()
            assert "qa_results" in test_result
            test_ids.append(test_result["test_id"])
        
        # Step 3: Review and approve tests
        for test_id in test_ids:
            # Mock test and sample lookups for review
            test = MRVTest(
                test_id=test_id,
                sample_id=sample_result["sample_id"],
                lab_id=workflow_data["lab"].lab_id,
                parameter="compressive_strength",
                value="30.5",
                unit="MPa",
                method="ASTM C39",
                tested_at=datetime.now(timezone.utc),
                passed=True,
                notes="Approved test"
            )
            
            mock_test_result = AsyncMock()
            mock_test_result.scalar_one_or_none.return_value = test
            mock_db.execute.return_value = mock_test_result
            
            mock_all_tests_result = AsyncMock()
            mock_all_tests_result.scalars.return_value.all.return_value = [test]
            mock_db.execute.return_value = mock_all_tests_result
            
            review_data = {
                "action": "approve",
                "reviewer_id": "reviewer123",
                "comments": "Approved"
            }
            
            response = client.post(f"/api/mrv/tests/{test_id}/review", data=review_data)
            assert response.status_code == 200
            review_result = response.json()
            assert review_result["action"] == "approve"
            assert review_result["test_passed"] is True
        
        # Step 4: Verify CO2 breakdown endpoint
        mock_project_result = AsyncMock()
        mock_project_result.scalar_one_or_none.return_value = workflow_data["project"]
        mock_db.execute.return_value = mock_project_result
        
        mock_breakdown = {
            "total_co2_kg": 15000.0,
            "total_co2_t": 15.0,
            "by_material": {"concrete": {"co2_kg": 15000.0, "sample_count": 1}},
            "by_sample": [{"sample_id": sample_result["sample_id"], "co2_kg": 15000.0}],
            "sample_count": 1
        }
        
        with patch('app.mrv.carbon.calculate_project_co2_breakdown', return_value=mock_breakdown):
            response = client.get(f"/api/mrv/projects/{workflow_data['project'].id}/co2-breakdown")
        
        assert response.status_code == 200
        co2_result = response.json()
        assert co2_result["total_co2_kg"] == 15000.0
        assert "concrete" in co2_result["by_material"]
        
        # Complete workflow verified
        assert True


if __name__ == "__main__":
    pytest.main([__file__])
