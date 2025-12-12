"""Unit tests for MRV ingestion APIs."""

import pytest
import tempfile
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.mrv.models import MRVSample, MRVSampleStatus, Lab, ChainStep, MRVTest
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_user_contractor():
    """Mock contractor user."""
    return User(
        id="user123",
        email="contractor@test.com",
        role="contractor",
        is_active=True
    )


@pytest.fixture
def mock_user_lab():
    """Mock lab user."""
    return User(
        id="lab123",
        email="lab@test.com",
        role="lab",
        is_active=True
    )


@pytest.fixture
def mock_project():
    """Mock project."""
    return Project(
        id="proj123",
        name="Test Project",
        status="active",
        created_by="user123"
    )


@pytest.fixture
def mock_lab():
    """Mock laboratory."""
    return Lab(
        lab_id="lab123",
        name="Test Lab",
        address="123 Test St",
        accreditation="ISO-17025",
        contact="lab@test.com"
    )


@pytest.fixture
def sample_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"test image content")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def pdf_file():
    """Create a temporary PDF file."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 test pdf content")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestMRVIngestionAPIs:
    """Test MRV ingestion API endpoints."""

    @patch('app.mrv.routes.get_current_user')
    @patch('app.mrv.routes.select')
    @patch('app.mrv.routes.save_upload')
    @patch('app.mrv.routes.MRVService._log_event')
    async def test_create_sample_success(self, mock_log, mock_save, mock_select, mock_auth, client, mock_user_contractor, mock_project, sample_file):
        """Test successful sample creation."""
        # Setup mocks
        mock_auth.return_value = mock_user_contractor
        mock_select.return_value.scalar_one_or_none.return_value = mock_project
        mock_save.return_value = "uploads/mrv/sample_evidence_abc123.jpg"
        
        # Mock database operations
        mock_db = Mock(spec=AsyncSession)
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Test data
        with open(sample_file, 'rb') as f:
            response = client.post(
                "/api/mrv/samples/",
                data={
                    "project_id": "proj123",
                    "collected_by": "John Doe",
                    "sample_type": "soil",
                    "geotag_lat": "40.7128",
                    "geotag_lon": "-74.0060",
                    "notes": "Sample from construction site"
                },
                files={"evidence_file": ("sample.jpg", f, "image/jpeg")},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj123"
        assert data["collected_by"] == "John Doe"
        assert data["sample_type"] == "soil"
        assert data["status"] == "collected"

    @patch('app.mrv.routes.get_current_user')
    @patch('app.mrv.routes.select')
    async def test_create_sample_invalid_project(self, mock_select, mock_auth, client, mock_user_contractor):
        """Test sample creation with invalid project ID."""
        mock_auth.return_value = mock_user_contractor
        mock_select.return_value.scalar_one_or_none.return_value = None
        
        response = client.post(
            "/api/mrv/samples/",
            data={
                "project_id": "invalid_proj",
                "collected_by": "John Doe",
                "sample_type": "soil"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    @patch('app.mrv.routes.get_current_user')
    @patch('app.mrv.routes.select')
    @patch('app.mrv.routes.MRVService._log_event')
    async def test_add_chain_step_success(self, mock_log, mock_select, mock_auth, client, mock_user_contractor, mock_project, sample_file):
        """Test successful chain step addition."""
        # Setup mocks
        mock_auth.return_value = mock_user_contractor
        mock_sample = MRVSample(
            sample_id="sample123",
            project_id="proj123",
            collected_by="John Doe",
            sample_type="soil",
            status=MRVSampleStatus.COLLECTED
        )
        mock_select.return_value.scalar_one_or_none.side_effect = [mock_sample, None]  # For sample and lab checks
        
        mock_db = Mock(spec=AsyncSession)
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with open(sample_file, 'rb') as f:
            response = client.post(
                "/api/mrv/samples/sample123/chain",
                data={
                    "actor": "John Doe",
                    "action": "received_at_lab",
                    "notes": "Sample received in good condition"
                },
                files={"evidence_file": ("evidence.jpg", f, "image/jpeg")},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["sample_id"] == "sample123"
        assert data["actor"] == "John Doe"
        assert data["action"] == "received_at_lab"

    @patch('app.mrv.routes.get_current_user')
    @patch('app.mrv.routes.select')
    @patch('app.mrv.routes.MRVService._log_event')
    async def test_submit_to_lab_success(self, mock_log, mock_select, mock_auth, client, mock_user_contractor, mock_project, mock_lab):
        """Test successful lab submission."""
        mock_auth.return_value = mock_user_contractor
        mock_sample = MRVSample(
            sample_id="sample123",
            project_id="proj123",
            collected_by="John Doe",
            sample_type="soil",
            status=MRVSampleStatus.COLLECTED
        )
        mock_select.return_value.scalar_one_or_none.side_effect = [mock_sample, mock_lab]
        
        mock_db = Mock(spec=AsyncSession)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        response = client.post(
            "/api/mrv/samples/sample123/submit_lab",
            data={
                "lab_id": "lab123",
                "expected_tests": '["ph", "heavy_metals", "organic_content"]',
                "sample_condition": "good",
                "submitted_at": "2024-01-15T10:00:00Z"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["sample_id"] == "sample123"
        assert data["status"] == "in_lab"
        assert data["lab_id"] == "lab123"

    @patch('app.mrv.routes.get_current_user')
    @patch('app.mrv.routes.select')
    @patch('app.mrv.routes.save_upload')
    @patch('app.mrv.routes.MRVService._log_event')
    async def test_upload_test_result_success(self, mock_log, mock_save, mock_select, mock_auth, client, mock_user_lab, mock_project, pdf_file):
        """Test successful test result upload."""
        mock_auth.return_value = mock_user_lab
        mock_sample = MRVSample(
            sample_id="sample123",
            project_id="proj123",
            collected_by="John Doe",
            sample_type="soil",
            status=MRVSampleStatus.IN_LAB,
            expected_tests=["ph", "heavy_metals"]
        )
        mock_select.return_value.scalar_one_or_none.return_value = mock_sample
        mock_save.return_value = "uploads/mrv/test_certificate_xyz123.pdf"
        
        mock_db = Mock(spec=AsyncSession)
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        with open(pdf_file, 'rb') as f:
            response = client.post(
                "/api/mrv/tests/sample123/upload",
                data={
                    "parameter": "ph",
                    "value": "7.2",
                    "unit": "pH",
                    "method": "ISO 10304",
                    "tested_at": "2024-01-16T14:30:00Z"
                },
                files={"certificate_file": ("certificate.pdf", f, "application/pdf")},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["parameter"] == "ph"
        assert data["value"] == "7.2"
        assert data["unit"] == "pH"
        assert data["passed"] == True
        assert "certificate_file" in data

    @patch('app.mrv.routes.get_current_user')
    @patch('app.mrv.routes.select')
    async def test_upload_test_result_invalid_file_type(self, mock_select, mock_auth, client, mock_user_lab, mock_project):
        """Test test result upload with invalid file type."""
        mock_auth.return_value = mock_user_lab
        mock_sample = MRVSample(
            sample_id="sample123",
            project_id="proj123",
            collected_by="John Doe",
            sample_type="soil",
            status=MRVSampleStatus.IN_LAB
        )
        mock_select.return_value.scalar_one_or_none.return_value = mock_sample
        
        # Create invalid file (txt instead of pdf/jpg)
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"invalid file content")
            temp_path = f.name
        
        try:
            with open(temp_path, 'rb') as f:
                response = client.post(
                    "/api/mrv/tests/sample123/upload",
                    data={
                        "parameter": "ph",
                        "value": "7.2",
                        "unit": "pH",
                        "method": "ISO 10304"
                    },
                    files={"certificate_file": ("certificate.txt", f, "text/plain")},
                    headers={"Authorization": "Bearer test_token"}
                )
            
            assert response.status_code == 400
            assert "Invalid certificate file type" in response.json()["detail"]
        finally:
            os.unlink(temp_path)

    @patch('app.mrv.routes.get_current_user')
    @patch('app.mrv.routes.select')
    async def test_get_sample_detail_success(self, mock_select, mock_auth, client, mock_user_contractor, mock_project):
        """Test successful sample detail retrieval."""
        mock_auth.return_value = mock_user_contractor
        mock_sample = MRVSample(
            sample_id="sample123",
            project_id="proj123",
            collected_by="John Doe",
            sample_type="soil",
            status=MRVSampleStatus.COLLECTED
        )
        
        mock_test = MRVTest(
            test_id="test123",
            sample_id="sample123",
            parameter="ph",
            value="7.2",
            unit="pH",
            method="ISO 10304",
            passed=True
        )
        
        mock_chain_step = ChainStep(
            step_id="step123",
            sample_id="sample123",
            actor="John Doe",
            action="collected"
        )
        
        # Mock the different select calls
        mock_select.return_value.scalars.return_value.all.side_effect = [
            [mock_sample],  # Sample query
            [mock_test],    # Tests query
            [mock_chain_step]  # Chain steps query
        ]
        
        response = client.get(
            "/api/mrv/samples/sample123",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["sample"]["sample_id"] == "sample123"
        assert len(data["tests"]) == 1
        assert data["tests"][0]["parameter"] == "ph"
        assert len(data["chain_steps"]) == 1
        assert data["chain_steps"][0]["action"] == "collected"

    @patch('app.mrv.routes.get_current_user')
    @patch('app.mrv.routes.select')
    async def test_get_project_samples_success(self, mock_select, mock_auth, client, mock_user_contractor, mock_project):
        """Test successful project samples retrieval."""
        mock_auth.return_value = mock_user_contractor
        mock_select.return_value.scalar_one_or_none.return_value = mock_project
        
        mock_samples = [
            MRVSample(
                sample_id="sample123",
                project_id="proj123",
                collected_by="John Doe",
                sample_type="soil",
                status=MRVSampleStatus.COLLECTED
            ),
            MRVSample(
                sample_id="sample456",
                project_id="proj123",
                collected_by="Jane Doe",
                sample_type="water",
                status=MRVSampleStatus.IN_LAB
            )
        ]
        
        mock_select.return_value.scalars.return_value.all.side_effect = [
            mock_samples,  # Count query
            mock_samples   # Paginated query
        ]
        
        response = client.get(
            "/api/mrv/projects/proj123/samples?page=1&size=10",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["samples"]) == 2
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["size"] == 10
        assert data["pages"] == 1

    def test_require_role_success(self, client, mock_user_contractor):
        """Test role requirement decorator success."""
        from app.mrv.routes import require_role
        
        # This would need to be tested in integration context
        # For now, just verify the function exists
        assert callable(require_role)

    def test_validate_file_type(self):
        """Test file type validation utility."""
        from app.mrv.utils_file import validate_file_type
        from fastapi import UploadFile
        
        # Mock valid file
        valid_file = Mock(spec=UploadFile)
        valid_file.filename = "test.jpg"
        assert validate_file_type(valid_file, ['.jpg', '.png']) == True
        
        # Mock invalid file
        invalid_file = Mock(spec=UploadFile)
        invalid_file.filename = "test.txt"
        assert validate_file_type(invalid_file, ['.jpg', '.png']) == False

    def test_compute_geotag_distance(self):
        """Test geotag distance calculation."""
        from app.mrv.utils_file import compute_geotag_distance
        
        # Test distance between NYC coordinates (should be small)
        distance = compute_geotag_distance(40.7128, -74.0060, 40.7589, -73.9851)
        assert 0 < distance < 10  # Should be less than 10km
        
        # Test distance between NYC and LA (should be large)
        distance = compute_geotag_distance(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3000 < distance < 5000  # Should be around 4000km
