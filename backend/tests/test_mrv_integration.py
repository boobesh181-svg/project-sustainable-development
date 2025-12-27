"""
Integration tests for MRV end-to-end workflow
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.main import app
from app.mrv.models import MRVSample, MRVTest, MRVSampleStatus, Lab, ChainStep
from app.mrv.carbon import compute_embodied_co2, calculate_project_co2_breakdown
from app.models.project import Project
from app.core.config import settings


# Legacy MRV ingestion workflow is feature-gated.
pytestmark = pytest.mark.skipif(
    not settings.ENABLE_MRV_INGESTION,
    reason="Legacy MRV ingestion workflow disabled by default",
)


class TestMRVIntegration:
    """Test MRV end-to-end workflow"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)
    
    @pytest.fixture
    def sample_project(self):
        return Project(
            id="550e8400-e29b-41d4-a716-446655440001",
            name="Test Project",
            status="active",
            lat=37.7749,
            lon=-122.4194,
            budget_usd=1000000
        )
    
    @pytest.fixture
    def sample_lab(self):
        return Lab(
            lab_id="lab-test-001",
            name="Test Lab",
            address="123 Test St",
            accreditation="ISO 17025",
            contact="test@lab.com"
        )
    
    @pytest.fixture
    def sample_sample(self, sample_project):
        return MRVSample(
            sample_id="SAMP-TEST-001",
            project_id=sample_project.id,
            collected_by="Test User",
            collected_at=datetime(2025, 11, 15, 9, 0, 0, tzinfo=timezone.utc),
            geotag_lat=37.7749,
            geotag_lon=-122.4194,
            sample_type="concrete",
            notes="Test sample",
            status=MRVSampleStatus.COLLECTED
        )
    
    @pytest.fixture
    def sample_tests(self, sample_sample, sample_lab):
        return [
            MRVTest(
                id="TEST-001",
                sample_id=sample_sample.sample_id,
                lab_id=sample_lab.lab_id,
                parameter="compressive_strength",
                value="30.5",
                unit="MPa",
                method="ASTM C39",
                tested_at=datetime(2025, 11, 20, 10, 0, 0, tzinfo=timezone.utc),
                passed=True,
                notes="Normal strength"
            ),
            MRVTest(
                id="TEST-002",
                sample_id=sample_sample.sample_id,
                lab_id=sample_lab.lab_id,
                parameter="density",
                value="2400",
                unit="kg/m3",
                method="ASTM C138",
                tested_at=datetime(2025, 11, 20, 10, 30, 0, tzinfo=timezone.utc),
                passed=True,
                notes="Expected density"
            ),
            MRVTest(
                id="TEST-003",
                sample_id=sample_sample.sample_id,
                lab_id=sample_lab.lab_id,
                parameter="recycled_content",
                value="25",
                unit="%",
                method="Lab Analysis",
                tested_at=datetime(2025, 11, 20, 11, 0, 0, tzinfo=timezone.utc),
                passed=True,
                notes="25% recycled content"
            )
        ]
    
    def test_carbon_calculation_concrete_sample(self, sample_sample, sample_tests):
        """Test carbon calculation for concrete sample"""
        co2_result = compute_embodied_co2(sample_sample, sample_tests)
        
        # Verify CO2 calculation
        assert co2_result["co2_kg"] > 0
        assert "factor_used" in co2_result
        assert co2_result["factor_used"]["base_factor"] == 150  # Concrete factor
        assert co2_result["recycled_fraction"] == 0.25  # 25% recycled content
        assert co2_result["lca_method"] == "hybrid_epd"
        
        # Check recycled content adjustment
        assert len(co2_result["adjustments"]) > 0
        adjustment = co2_result["adjustments"][0]
        assert adjustment["type"] == "recycled_content"
        assert adjustment["fraction"] == 0.25
    
    def test_carbon_calculation_steel_sample(self):
        """Test carbon calculation for steel sample"""
        steel_sample = MRVSample(
            sample_id="SAMP-STEEL-001",
            project_id="proj-test-001",
            collected_by="Test User",
            collected_at=datetime(2025, 11, 15, 9, 0, 0, tzinfo=timezone.utc),
            geotag_lat=37.7749,
            geotag_lon=-122.4194,
            sample_type="steel",
            notes="Steel sample",
            status=MRVSampleStatus.COLLECTED
        )
        
        steel_tests = [
            MRVTest(
                id="TEST-STEEL-001",
                sample_id=steel_sample.sample_id,
                lab_id="lab-test-001",
                parameter="yield_strength",
                value="280",
                unit="MPa",
                method="ASTM A370",
                tested_at=datetime(2025, 11, 20, 10, 0, 0, tzinfo=timezone.utc),
                passed=True,
                notes="Normal steel strength"
            )
        ]
        
        co2_result = compute_embodied_co2(steel_sample, steel_tests)
        
        # Verify steel CO2 calculation
        assert co2_result["co2_kg"] > 0
        assert co2_result["factor_used"]["base_factor"] == 1900  # Steel factor
        assert co2_result["recycled_fraction"] == 0.0  # No recycled content in test data
    
    def test_carbon_calculation_unknown_material(self):
        """Test carbon calculation for unknown material type"""
        unknown_sample = MRVSample(
            sample_id="SAMP-UNKNOWN-001",
            project_id="proj-test-001",
            collected_by="Test User",
            collected_at=datetime(2025, 11, 15, 9, 0, 0, tzinfo=timezone.utc),
            geotag_lat=37.7749,
            geotag_lon=-122.4194,
            sample_type="unknown_material",
            notes="Unknown material",
            status=MRVSampleStatus.COLLECTED
        )
        
        co2_result = compute_embodied_co2(unknown_sample, [])
        
        # Unknown material should return 0 CO2
        assert co2_result["co2_kg"] == 0
        assert "No carbon factor available" in co2_result["co2_notes"]
        assert co2_result["factor_used"] is None
    
    @patch('app.mrv.routes.get_db')
    @patch('app.mrv.routes.require_role')
    def test_sample_creation_endpoint(self, mock_require_role, mock_get_db, client, mock_db, sample_project):
        """Test sample creation endpoint"""
        mock_get_db.return_value = mock_db
        mock_require_role.return_value = {"id": "user123", "role": "field_technician"}
        
        # Mock database operations
        mock_db.add = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Create sample data
        sample_data = {
            "project_id": sample_project.id,
            "collected_by": "Test User",
            "collected_at": "2025-11-15T09:00:00Z",
            "geotag_lat": 37.7749,
            "geotag_lon": -122.4194,
            "sample_type": "concrete",
            "notes": "Test sample"
        }
        
        response = client.post("/api/mrv/samples", data=sample_data)
        
        assert response.status_code == 200
        result = response.json()
        assert "sample_id" in result
        assert result["project_id"] == sample_project.id
        assert result["sample_type"] == "concrete"
    
    @patch('app.mrv.routes.get_db')
    @patch('app.mrv.routes.require_role')
    def test_test_upload_with_qa_flags(self, mock_require_role, mock_get_db, client, mock_db, sample_sample, sample_lab):
        """Test test upload with automatic QA flagging"""
        mock_get_db.return_value = mock_db
        mock_require_role.return_value = {"id": "user123", "role": "lab_technician"}
        
        # Mock sample lookup
        mock_sample_result = AsyncMock()
        mock_sample_result.scalar_one_or_none.return_value = sample_sample
        mock_db.execute.return_value = mock_sample_result
        
        # Mock test creation
        mock_db.add = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        test_data = {
            "parameter": "compressive_strength",
            "value": "30.5",
            "unit": "MPa",
            "method": "ASTM C39",
            "tested_at": "2025-11-20T10:00:00Z",
            "notes": "Test result"
        }
        
        response = client.post(f"/api/mrv/tests/{sample_sample.sample_id}/upload", data=test_data)
        
        assert response.status_code == 200
        result = response.json()
        assert "test_id" in result
        assert "qa_results" in result
        assert "passed" in result
    
    @patch('app.mrv.routes.get_db')
    @patch('app.mrv.routes.require_role')
    def test_review_approve_flow(self, mock_require_role, mock_get_db, client, mock_db, sample_sample, sample_tests):
        """Test review approval flow with CO2 calculation"""
        mock_get_db.return_value = mock_db
        mock_require_role.return_value = {"id": "user123", "role": "mrv_officer"}
        
        # Mock test lookup
        test = sample_tests[0]
        mock_test_result = AsyncMock()
        mock_test_result.scalar_one_or_none.return_value = test
        mock_db.execute.return_value = mock_test_result
        
        # Mock sample lookup
        mock_sample_result = AsyncMock()
        mock_sample_result.scalar_one_or_none.return_value = sample_sample
        mock_db.execute.return_value = mock_sample_result
        
        # Mock all tests lookup
        mock_all_tests_result = AsyncMock()
        mock_all_tests_result.scalars.return_value.all.return_value = sample_tests
        mock_db.execute.return_value = mock_all_tests_result
        
        # Mock database operations
        mock_db.add = AsyncMock()
        mock_db.commit = AsyncMock()
        
        review_data = {
            "action": "approve",
            "reviewer_id": "reviewer123",
            "comments": "Test looks good"
        }
        
        response = client.post(f"/api/mrv/tests/{test.test_id}/review", data=review_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["action"] == "approve"
        assert result["test_passed"] is True
        assert result["sample_status"] == "approved"  # All tests should be approved
    
    @patch('app.mrv.routes.get_db')
    @patch('app.mrv.routes.require_role')
    def test_co2_breakdown_endpoint(self, mock_require_role, mock_get_db, client, mock_db, sample_project, sample_sample, sample_tests):
        """Test CO2 breakdown endpoint"""
        mock_get_db.return_value = mock_db
        mock_require_role.return_value = {"id": "user123", "role": "mrv_officer"}
        
        # Mock project lookup
        mock_project_result = AsyncMock()
        mock_project_result.scalar_one_or_none.return_value = sample_project
        mock_db.execute.return_value = mock_project_result
        
        # Mock CO2 breakdown calculation
        mock_breakdown = {
            "total_co2_kg": 15000.0,
            "total_co2_t": 15.0,
            "by_material": {
                "concrete": {
                    "co2_kg": 15000.0,
                    "sample_count": 1,
                    "quantity_tonnes": 100.0
                }
            },
            "by_sample": [
                {
                    "sample_id": sample_sample.sample_id,
                    "sample_type": "concrete",
                    "co2_kg": 15000.0,
                    "quantity_tonnes": 100.0,
                    "recycled_fraction": 0.25,
                    "test_count": 3
                }
            ],
            "sample_count": 1
        }
        
        with patch('app.mrv.carbon.calculate_project_co2_breakdown', return_value=mock_breakdown):
            response = client.get(f"/api/mrv/projects/{sample_project.id}/co2-breakdown")
        
        assert response.status_code == 200
        result = response.json()
        assert result["total_co2_kg"] == 15000.0
        assert result["total_co2_t"] == 15.0
        assert "concrete" in result["by_material"]
        assert len(result["by_sample"]) == 1
    
    def test_chain_of_custody_creation(self, sample_sample):
        """Test chain of custody step creation"""
        chain_step = ChainStep(
            id="CHAIN-TEST-001",
            sample_id=sample_sample.sample_id,
            actor="Test User",
            action="sample_collected",
            timestamp=datetime(2025, 11, 15, 9, 0, 0, tzinfo=timezone.utc),
            evidence_file="evidence/test.jpg"
        )
        
        assert chain_step.sample_id == sample_sample.sample_id
        assert chain_step.actor == "Test User"
        assert chain_step.action == "sample_collected"
        assert chain_step.evidence_file == "evidence/test.jpg"
    
    def test_qa_flag_anomaly_detection(self):
        """Test QA flag detection for anomalies"""
        # Sample with anomalous geotag (far from project)
        anomalous_sample = MRVSample(
            sample_id="SAMP-ANOMALY-001",
            project_id="proj-test-001",
            collected_by="Test User",
            collected_at=datetime.now(timezone.utc),
            geotag_lat=40.7128,  # New York coordinates
            geotag_lon=-74.006,
            sample_type="concrete",
            notes="Anomalous sample",
            status=MRVSampleStatus.COLLECTED
        )
        
        # Test with normal value
        normal_test = MRVTest(
            id="TEST-NORMAL-001",
            sample_id=anomalous_sample.sample_id,
            lab_id="lab-test-001",
            parameter="compressive_strength",
            value="30.5",
            unit="MPa",
            method="ASTM C39",
            tested_at=datetime.now(timezone.utc),
            passed=True,
            notes="Normal strength"
        )
        
        co2_result = compute_embodied_co2(anomalous_sample, [normal_test])
        
        # Should still calculate CO2 even with geotag anomaly
        assert co2_result["co2_kg"] > 0
        
        # Test with anomalous value (too low for steel)
        steel_sample = MRVSample(
            sample_id="SAMP-STEEL-ANOMALY-001",
            project_id="proj-test-001",
            collected_by="Test User",
            collected_at=datetime.now(timezone.utc),
            geotag_lat=37.7749,
            geotag_lon=-122.4194,
            sample_type="steel",
            notes="Steel sample",
            status=MRVSampleStatus.COLLECTED
        )
        
        anomalous_steel_test = MRVTest(
            id="TEST-STEEL-ANOMALY-001",
            sample_id=steel_sample.sample_id,
            lab_id="lab-test-001",
            parameter="yield_strength",
            value="150",  # Too low for steel
            unit="MPa",
            method="ASTM A370",
            tested_at=datetime.now(timezone.utc),
            passed=False,
            notes="Anomalous low strength"
        )
        
        co2_result = compute_embodied_co2(steel_sample, [anomalous_steel_test])
        
        # Should still calculate CO2 even with value anomaly
        assert co2_result["co2_kg"] > 0
        assert co2_result["factor_used"]["base_factor"] == 1900  # Steel factor


if __name__ == "__main__":
    pytest.main([__file__])
