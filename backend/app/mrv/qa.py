"""
MRV Quality Assurance (QA) Rules and Auto-Flags

This module implements automated quality checks for MRV samples and tests,
including geotag validation, sample age checks, parameter validation, and
duplicate certificate detection.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.mrv.models import MRVSample, MRVTest
from app.mrv.utils_file import compute_geotag_distance


# Material-specific value ranges based on carbon/strength norms
# Sources: 
# - ACI 318 for concrete strength
# - ASTM standards for steel
# - EPA guidelines for soil contaminants
# - ISO standards for material testing
MATERIAL_RANGES = {
    "concrete": {
        "compressive_strength": {"min": 15.0, "max": 80.0, "unit": "MPa"},  # ACI 318
        "carbon_content": {"min": 0.1, "max": 0.5, "unit": "%"},  # Typical cement content
        "water_cement_ratio": {"min": 0.35, "max": 0.65, "unit": "ratio"},  # ACI guidelines
        "density": {"min": 2200, "max": 2600, "unit": "kg/m3"}  # Normal weight concrete
    },
    "steel": {
        "yield_strength": {"min": 250, "max": 550, "unit": "MPa"},  # ASTM A36 to A572
        "tensile_strength": {"min": 400, "max": 830, "unit": "MPa"},  # Common structural steel
        "carbon_content": {"min": 0.05, "max": 0.25, "unit": "%"},  # Low to medium carbon steel
        "density": {"min": 7850, "max": 8050, "unit": "kg/m3"}  # Steel density
    },
    "soil": {
        "ph": {"min": 4.0, "max": 9.0, "unit": "pH"},  # EPA soil pH range
        "organic_matter": {"min": 0.5, "max": 15.0, "unit": "%"},  # Typical soil organic matter
        "heavy_metals_lead": {"min": 0, "max": 400, "unit": "mg/kg"},  # EPA screening level
        "heavy_metals_cadmium": {"min": 0, "max": 100, "unit": "mg/kg"},  # EPA screening level
        "moisture_content": {"min": 5, "max": 40, "unit": "%"}  # Typical soil moisture
    },
    "water": {
        "ph": {"min": 6.5, "max": 8.5, "unit": "pH"},  # EPA drinking water standard
        "turbidity": {"min": 0, "max": 5, "unit": "NTU"},  # EPA standard
        "dissolved_oxygen": {"min": 5, "max": 15, "unit": "mg/L"},  # EPA standard
        "conductivity": {"min": 50, "max": 1500, "unit": "μS/cm"}  # Typical range
    },
    "asphalt": {
        "penetration": {"min": 20, "max": 100, "unit": "0.1mm"},  # Asphalt binder grades
        "viscosity": {"min": 150, "max": 3000, "unit": "Pa·s"},  # Hot mix asphalt
        "density": {"min": 2200, "max": 2500, "unit": "kg/m3"}  # Asphalt concrete
    }
}


def check_geotag(sample: MRVSample, project_geotag: Optional[Tuple[float, float]] = None, threshold_m: int = 500) -> Tuple[bool, float]:
    """
    Check if sample geotag is within acceptable distance from project location.
    
    Args:
        sample: MRVSample object with geotag coordinates
        project_geotag: Tuple of (latitude, longitude) for project location
        threshold_m: Maximum allowed distance in meters (default: 500m)
    
    Returns:
        Tuple of (passed: bool, distance_m: float)
    """
    if not project_geotag:
        # If no project geotag provided, assume pass
        return True, 0.0
    
    try:
        distance_m = compute_geotag_distance(
            sample.geotag_lat, sample.geotag_lon,
            project_geotag[0], project_geotag[1]
        )
        passed = distance_m <= threshold_m
        return passed, distance_m
    except Exception:
        # If distance calculation fails, flag for manual review
        return False, 0.0


def check_sample_age(sample_collected_at: datetime, tested_at: datetime, max_days: int = 90) -> bool:
    """
    Check if sample was tested within acceptable time frame.
    
    Args:
        sample_collected_at: When sample was collected
        tested_at: When sample was tested
        max_days: Maximum allowed days between collection and testing (default: 90)
    
    Returns:
        bool: True if sample age is acceptable
    """
    try:
        age_days = (tested_at - sample_collected_at).days
        return 0 <= age_days <= max_days
    except Exception:
        # If date calculation fails, flag for manual review
        return False


def check_expected_parameters(sample: MRVSample, test_parameter_list: List[str]) -> bool:
    """
    Check if required parameters for sample type are included in tests.
    
    Args:
        sample: MRVSample object
        test_parameter_list: List of parameters tested
    
    Returns:
        bool: True if all required parameters are present
    """
    # Define required parameters by sample type
    REQUIRED_PARAMS = {
        "concrete": ["compressive_strength", "density"],
        "steel": ["yield_strength", "tensile_strength"],
        "soil": ["ph", "heavy_metals_lead", "organic_matter"],
        "water": ["ph", "turbidity", "dissolved_oxygen"],
        "asphalt": ["penetration", "density", "viscosity"]
    }
    
    sample_type_lower = sample.sample_type.lower()
    required = REQUIRED_PARAMS.get(sample_type_lower, [])
    
    # Check if all required parameters are in the test list
    missing_params = [param for param in required if param not in test_parameter_list]
    return len(missing_params) == 0


async def detect_duplicate_certificates(db: AsyncSession, certificate_hash: str) -> List[str]:
    """
    Detect duplicate certificates by hash.
    
    Args:
        db: Database session
        certificate_hash: SHA256 hash of certificate file
    
    Returns:
        List of sample_ids that have this certificate hash
    """
    try:
        # Query for existing tests with same certificate hash
        stmt = select(MRVTest).where(MRVTest.certificate_hash == certificate_hash)
        result = await db.execute(stmt)
        existing_tests = result.scalars().all()
        
        return [test.sample_id for test in existing_tests]
    except Exception:
        return []


def check_value_range(sample_type: str, parameter: str, value: float, unit: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if test value falls within acceptable range for material type.
    
    Args:
        sample_type: Type of material (concrete, steel, soil, etc.)
        parameter: Parameter being tested
        value: Test result value (numeric)
        unit: Unit of measurement
    
    Returns:
        Tuple of (passed: bool, range_info: Optional[dict])
    """
    # Ensure value is numeric
    try:
        numeric_value = float(value)
    except (ValueError, TypeError):
        return False, None
    
    sample_type_lower = sample_type.lower()
    ranges = MATERIAL_RANGES.get(sample_type_lower, {})
    
    # Normalize parameter name
    param_lower = parameter.lower()
    range_info = None
    
    # Find matching parameter in ranges
    for range_param, info in ranges.items():
        if param_lower in range_param.lower() or range_param.lower() in param_lower:
            range_info = info
            break
    
    if not range_info:
        # No range defined for this parameter, assume pass
        return True, None
    
    # Check if value is within range
    min_val = range_info["min"]
    max_val = range_info["max"]
    passed = min_val <= numeric_value <= max_val
    
    return passed, range_info


def calculate_certificate_hash(certificate_file_path: str) -> str:
    """
    Calculate SHA256 hash of certificate file.
    
    Args:
        certificate_file_path: Path to certificate file
    
    Returns:
        SHA256 hash as hex string
    """
    try:
        with open(certificate_file_path, 'rb') as f:
            content = f.read()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return ""


async def run_quick_mrv_checks(
    db: AsyncSession,
    sample: MRVSample,
    test: MRVTest,
    project_geotag: Optional[Tuple[float, float]] = None,
    existing_tests: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Run comprehensive QA checks on sample and test.
    
    Args:
        db: Database session
        sample: MRVSample object
        test: MRVTest object
        project_geotag: Project location coordinates
        existing_tests: List of existing test parameters for this sample
    
    Returns:
        Dictionary with QA flags and overall assessment
    """
    qa_flags = {
        "geotag_flag": {"passed": True, "details": ""},
        "age_flag": {"passed": True, "details": ""},
        "parameter_flag": {"passed": True, "details": ""},
        "value_range_flag": {"passed": True, "details": ""},
        "duplicate_cert_flag": {"passed": True, "details": ""},
        "overall_pass": True,
        "check_timestamp": datetime.now(timezone.utc).isoformat(),
        "warnings": []
    }
    
    # 1. Geotag check
    if project_geotag:
        geotag_passed, distance = check_geotag(sample, project_geotag)
        qa_flags["geotag_flag"] = {
            "passed": geotag_passed,
            "details": f"Distance: {distance:.1f}m from project location"
        }
        if not geotag_passed:
            qa_flags["warnings"].append(f"Sample collected {distance:.1f}m from project location")
    
    # 2. Sample age check
    age_passed = check_sample_age(sample.collected_at, test.tested_at)
    qa_flags["age_flag"] = {
        "passed": age_passed,
        "details": f"Sample age: {(test.tested_at - sample.collected_at).days} days"
    }
    if not age_passed:
        qa_flags["warnings"].append(f"Sample tested {(test.tested_at - sample.collected_at).days} days after collection")
    
    # 3. Expected parameters check
    all_params = existing_tests + [test.parameter] if existing_tests else [test.parameter]
    param_passed = check_expected_parameters(sample, all_params)
    qa_flags["parameter_flag"] = {
        "passed": param_passed,
        "details": f"Tested parameters: {', '.join(all_params)}"
    }
    if not param_passed:
        qa_flags["warnings"].append("Missing required parameters for sample type")
    
    # 4. Value range check
    try:
        test_value = float(test.value)
        value_passed, range_info = check_value_range(sample.sample_type, test.parameter, test_value, test.unit)
        qa_flags["value_range_flag"] = {
            "passed": value_passed,
            "details": f"Value {test.value} {test.unit}" + (f" (range: {range_info['min']}-{range_info['max']} {range_info['unit']})" if range_info else "")
        }
        if not value_passed and range_info:
            qa_flags["warnings"].append(f"Test value {test.value} {test.unit} outside acceptable range ({range_info['min']}-{range_info['max']} {range_info['unit']})")
    except (ValueError, TypeError):
        qa_flags["value_range_flag"] = {
            "passed": False,
            "details": f"Invalid test value: {test.value}"
        }
        qa_flags["warnings"].append(f"Invalid test value format: {test.value}")
    
    # 5. Duplicate certificate check
    if test.certificate_file:
        cert_hash = calculate_certificate_hash(test.certificate_file)
        if cert_hash:
            duplicate_samples = await detect_duplicate_certificates(db, cert_hash)
            qa_flags["duplicate_cert_flag"] = {
                "passed": len(duplicate_samples) == 0,
                "details": f"Certificate hash: {cert_hash[:16]}..." if cert_hash else "No hash calculated"
            }
            if duplicate_samples:
                qa_flags["warnings"].append(f"Certificate duplicate found in samples: {', '.join(duplicate_samples)}")
    
    # Determine overall pass status
    critical_flags = ["geotag_flag", "age_flag", "value_range_flag"]
    qa_flags["overall_pass"] = all(
        qa_flags[flag]["passed"] for flag in critical_flags
    )
    
    # Add summary
    qa_flags["summary"] = {
        "total_checks": len([f for f in qa_flags.keys() if f.endswith("_flag")]),
        "passed_checks": len([f for f in qa_flags.keys() if f.endswith("_flag") and qa_flags[f]["passed"]]),
        "warning_count": len(qa_flags["warnings"])
    }
    
    return qa_flags
