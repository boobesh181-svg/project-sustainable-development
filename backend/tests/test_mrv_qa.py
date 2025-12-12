"""
Unit tests for MRV QA functions
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.mrv.qa import (
    check_geotag, check_sample_age, check_expected_parameters,
    check_value_range, calculate_certificate_hash, run_quick_mrv_checks
)
from app.mrv.models import MRVSample, MRVTest, MRVSampleStatus


class TestCheckGeotag:
    """Test geotag validation function"""
    
    def test_geotag_within_threshold(self):
        """Test geotag within acceptable distance"""
        # Create mock sample
        sample = MagicMock()
        sample.geotag_lat = 40.7128
        sample.geotag_lon = -74.0060
        
        # Project location (same coordinates)
        project_geotag = (40.7128, -74.0060)
        
        passed, distance = check_geotag(sample, project_geotag, threshold_m=500)
        
        assert passed is True
        assert distance == 0.0
    
    def test_geotag_outside_threshold(self):
        """Test geotag outside acceptable distance"""
        # Create mock sample (far from project - different city)
        sample = MagicMock()
        sample.geotag_lat = 51.5074  # London
        sample.geotag_lon = -0.1278
        
        # Project location (New York)
        project_geotag = (40.7128, -74.0060)
        
        passed, distance = check_geotag(sample, project_geotag, threshold_m=500)
        
        assert passed is False
        assert distance > 500  # Should be much more than 500m (London to NYC is ~5570km)
    
    def test_geotag_no_project_location(self):
        """Test geotag check when no project location provided"""
        sample = MagicMock()
        sample.geotag_lat = 40.7128
        sample.geotag_lon = -74.0060
        
        passed, distance = check_geotag(sample, project_geotag=None, threshold_m=500)
        
        assert passed is True
        assert distance == 0.0
    
    def test_geotag_calculation_error(self):
        """Test geotag check with invalid coordinates"""
        sample = MagicMock()
        sample.geotag_lat = "invalid"
        sample.geotag_lon = -74.0060
        
        project_geotag = (40.7128, -74.0060)
        
        passed, distance = check_geotag(sample, project_geotag, threshold_m=500)
        
        assert passed is False
        assert distance == 0.0


class TestCheckSampleAge:
    """Test sample age validation function"""
    
    def test_sample_age_within_limit(self):
        """Test sample age within acceptable limit"""
        collected_at = datetime.now() - timedelta(days=30)
        tested_at = datetime.now()
        
        passed = check_sample_age(collected_at, tested_at, max_days=90)
        
        assert passed is True
    
    def test_sample_age_exceeds_limit(self):
        """Test sample age exceeds acceptable limit"""
        collected_at = datetime.now() - timedelta(days=100)
        tested_at = datetime.now()
        
        passed = check_sample_age(collected_at, tested_at, max_days=90)
        
        assert passed is False
    
    def test_sample_age_future_test(self):
        """Test sample tested before collection (invalid)"""
        collected_at = datetime.now()
        tested_at = datetime.now() - timedelta(days=10)
        
        passed = check_sample_age(collected_at, tested_at, max_days=90)
        
        assert passed is False
    
    def test_sample_age_edge_case(self):
        """Test sample age exactly at limit"""
        collected_at = datetime.now() - timedelta(days=90)
        tested_at = datetime.now()
        
        passed = check_sample_age(collected_at, tested_at, max_days=90)
        
        assert passed is True


class TestCheckExpectedParameters:
    """Test expected parameters validation function"""
    
    def test_all_required_parameters_present(self):
        """Test when all required parameters are present"""
        sample = MagicMock()
        sample.sample_type = "concrete"
        
        test_params = ["compressive_strength", "density", "ph"]  # All required + extra
        
        passed = check_expected_parameters(sample, test_params)
        
        assert passed is True
    
    def test_missing_required_parameters(self):
        """Test when required parameters are missing"""
        sample = MagicMock()
        sample.sample_type = "concrete"
        
        test_params = ["compressive_strength"]  # Missing density
        
        passed = check_expected_parameters(sample, test_params)
        
        assert passed is False
    
    def test_unknown_sample_type(self):
        """Test with unknown sample type"""
        sample = MagicMock()
        sample.sample_type = "unknown_material"
        
        test_params = ["some_parameter"]
        
        passed = check_expected_parameters(sample, test_params)
        
        assert passed is True  # No requirements for unknown type
    
    def test_case_insensitive_sample_type(self):
        """Test case insensitive sample type matching"""
        sample = MagicMock()
        sample.sample_type = "CONCRETE"
        
        test_params = ["compressive_strength", "density"]
        
        passed = check_expected_parameters(sample, test_params)
        
        assert passed is True


class TestCheckValueRange:
    """Test value range validation function"""
    
    def test_value_within_range(self):
        """Test value within acceptable range"""
        passed, range_info = check_value_range("concrete", "compressive_strength", 30.0, "MPa")
        
        assert passed is True
        assert range_info is not None
        assert range_info["min"] == 15.0
        assert range_info["max"] == 80.0
    
    def test_value_below_range(self):
        """Test value below acceptable range"""
        passed, range_info = check_value_range("concrete", "compressive_strength", 10.0, "MPa")
        
        assert passed is False
        assert range_info is not None
        assert range_info["min"] == 15.0
        assert range_info["max"] == 80.0
    
    def test_value_above_range(self):
        """Test value above acceptable range"""
        passed, range_info = check_value_range("concrete", "compressive_strength", 100.0, "MPa")
        
        assert passed is False
        assert range_info is not None
        assert range_info["min"] == 15.0
        assert range_info["max"] == 80.0
    
    def test_unknown_parameter(self):
        """Test with unknown parameter"""
        passed, range_info = check_value_range("concrete", "unknown_parameter", 50.0, "unit")
        
        assert passed is True  # No range defined, assume pass
        assert range_info is None
    
    def test_unknown_material_type(self):
        """Test with unknown material type"""
        passed, range_info = check_value_range("unknown_material", "some_parameter", 50.0, "unit")
        
        assert passed is True  # No ranges defined, assume pass
        assert range_info is None
    
    def test_parameter_name_matching(self):
        """Test flexible parameter name matching"""
        # Test partial match (heavy_metals should match heavy_metals_lead)
        passed, range_info = check_value_range("soil", "heavy_metals_lead", 50.0, "mg/kg")
        
        assert passed is True
        assert range_info is not None
        assert range_info["min"] == 0
        assert range_info["max"] == 400
    
    def test_invalid_value_format(self):
        """Test with non-numeric value"""
        passed, range_info = check_value_range("concrete", "compressive_strength", "invalid", "MPa")
        
        # Should return False for invalid values
        assert passed is False
        assert range_info is None


class TestCalculateCertificateHash:
    """Test certificate hash calculation function"""
    
    def test_calculate_hash_existing_file(self, tmp_path):
        """Test hash calculation for existing file"""
        # Create a test file
        test_file = tmp_path / "test_cert.pdf"
        test_file.write_text("test certificate content")
        
        hash_value = calculate_certificate_hash(str(test_file))
        
        assert hash_value is not None
        assert len(hash_value) == 64  # SHA256 hash length
        assert hash_value != ""
    
    def test_calculate_hash_nonexistent_file(self):
        """Test hash calculation for nonexistent file"""
        hash_value = calculate_certificate_hash("nonexistent_file.pdf")
        
        assert hash_value == ""
    
    def test_calculate_hash_empty_file(self, tmp_path):
        """Test hash calculation for empty file"""
        empty_file = tmp_path / "empty_cert.pdf"
        empty_file.write_text("")
        
        hash_value = calculate_certificate_hash(str(empty_file))
        
        assert hash_value is not None
        assert len(hash_value) == 64
        # Known SHA256 hash of empty string
        assert hash_value == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class TestRunQuickMrvChecks:
    """Test comprehensive MRV QA checks function"""
    
    @pytest.mark.asyncio
    async def test_comprehensive_qa_checks_all_pass(self):
        """Test QA checks with all passing results"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Create mock sample
        sample = MagicMock()
        sample.sample_id = "SAMPLE123"
        sample.sample_type = "concrete"
        sample.collected_at = datetime.now() - timedelta(days=30)
        sample.geotag_lat = 40.7128
        sample.geotag_lon = -74.0060
        
        # Create mock test
        test = MagicMock()
        test.id = "TEST123"
        test.parameter = "compressive_strength"
        test.value = "30.0"
        test.unit = "MPa"
        test.tested_at = datetime.now()
        test.certificate_file = "cert.pdf"
        
        # Mock project geotag (same location as sample)
        project_geotag = (40.7128, -74.0060)
        
        # Mock existing tests
        existing_tests = ["density"]
        
        # Mock duplicate certificate check
        with patch('app.mrv.qa.detect_duplicate_certificates', return_value=[]):
            with patch('app.mrv.qa.calculate_certificate_hash', return_value="hash123"):
                results = await run_quick_mrv_checks(
                    db=db,
                    sample=sample,
                    test=test,
                    project_geotag=project_geotag,
                    existing_tests=existing_tests
                )
        
        assert results["overall_pass"] is True
        assert results["geotag_flag"]["passed"] is True
        assert results["age_flag"]["passed"] is True
        assert results["parameter_flag"]["passed"] is True
        assert results["value_range_flag"]["passed"] is True
        assert results["duplicate_cert_flag"]["passed"] is True
        assert len(results["warnings"]) == 0
    
    @pytest.mark.asyncio
    async def test_comprehensive_qa_checks_with_failures(self):
        """Test QA checks with some failing results"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Create mock sample (far from project)
        sample = MagicMock()
        sample.sample_id = "SAMPLE123"
        sample.sample_type = "concrete"
        sample.collected_at = datetime.now() - timedelta(days=100)  # Too old
        sample.geotag_lat = 50.0  # Far from project
        sample.geotag_lon = -80.0
        
        # Create mock test (value out of range)
        test = MagicMock()
        test.id = "TEST123"
        test.parameter = "compressive_strength"
        test.value = "10.0"  # Below minimum
        test.unit = "MPa"
        test.tested_at = datetime.now()
        test.certificate_file = "cert.pdf"
        
        # Mock project geotag (different location)
        project_geotag = (40.7128, -74.0060)
        
        # Mock existing tests (missing required parameters)
        existing_tests = []  # Missing density
        
        # Mock duplicate certificate check
        with patch('app.mrv.qa.detect_duplicate_certificates', return_value=["SAMPLE456"]):
            with patch('app.mrv.qa.calculate_certificate_hash', return_value="hash123"):
                results = await run_quick_mrv_checks(
                    db=db,
                    sample=sample,
                    test=test,
                    project_geotag=project_geotag,
                    existing_tests=existing_tests
                )
        
        assert results["overall_pass"] is False
        assert results["geotag_flag"]["passed"] is False
        assert results["age_flag"]["passed"] is False
        assert results["parameter_flag"]["passed"] is False
        assert results["value_range_flag"]["passed"] is False
        assert results["duplicate_cert_flag"]["passed"] is False
        assert len(results["warnings"]) > 0
    
    @pytest.mark.asyncio
    async def test_qa_checks_no_project_geotag(self):
        """Test QA checks without project geotag"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Create mock sample
        sample = MagicMock()
        sample.sample_id = "SAMPLE123"
        sample.sample_type = "concrete"
        sample.collected_at = datetime.now() - timedelta(days=30)
        sample.geotag_lat = 40.7128
        sample.geotag_lon = -74.0060
        
        # Create mock test
        test = MagicMock()
        test.id = "TEST123"
        test.parameter = "compressive_strength"
        test.value = "30.0"
        test.unit = "MPa"
        test.tested_at = datetime.now()
        test.certificate_file = None  # No certificate
        
        # No project geotag
        project_geotag = None
        
        # Mock existing tests
        existing_tests = ["density"]
        
        # Mock duplicate certificate check
        with patch('app.mrv.qa.detect_duplicate_certificates', return_value=[]):
            results = await run_quick_mrv_checks(
                db=db,
                sample=sample,
                test=test,
                project_geotag=project_geotag,
                existing_tests=existing_tests
            )
        
        assert results["overall_pass"] is True
        assert results["geotag_flag"]["passed"] is True  # Should pass without project geotag
        assert results["duplicate_cert_flag"]["passed"] is True  # Should pass without certificate
    
    @pytest.mark.asyncio
    async def test_qa_checks_summary_generation(self):
        """Test QA checks summary generation"""
        # Mock database session
        db = AsyncMock(spec=AsyncSession)
        
        # Create mock sample
        sample = MagicMock()
        sample.sample_id = "SAMPLE123"
        sample.sample_type = "concrete"
        sample.collected_at = datetime.now() - timedelta(days=30)
        sample.geotag_lat = 40.7128
        sample.geotag_lon = -74.0060
        
        # Create mock test
        test = MagicMock()
        test.id = "TEST123"
        test.parameter = "compressive_strength"
        test.value = "30.0"
        test.unit = "MPa"
        test.tested_at = datetime.now()
        test.certificate_file = "cert.pdf"
        
        # Mock project geotag
        project_geotag = (40.7128, -74.0060)
        
        # Mock existing tests
        existing_tests = ["density"]
        
        # Mock duplicate certificate check
        with patch('app.mrv.qa.detect_duplicate_certificates', return_value=[]):
            with patch('app.mrv.qa.calculate_certificate_hash', return_value="hash123"):
                results = await run_quick_mrv_checks(
                    db=db,
                    sample=sample,
                    test=test,
                    project_geotag=project_geotag,
                    existing_tests=existing_tests
                )
        
        # Check summary
        assert "summary" in results
        assert results["summary"]["total_checks"] == 5  # 5 flag checks
        assert results["summary"]["passed_checks"] == 5
        assert results["summary"]["warning_count"] == 0
        
        # Check timestamp
        assert "check_timestamp" in results
        assert datetime.fromisoformat(results["check_timestamp"]) is not None


if __name__ == "__main__":
    pytest.main([__file__])
