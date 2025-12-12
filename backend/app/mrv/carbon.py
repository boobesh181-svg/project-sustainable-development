"""
Carbon accounting for MRV samples and tests
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.mrv.models import MRVSample, MRVTest
from app.models.project import Project


# Carbon factors database (kgCO2 per tonne of material)
# These can be loaded from config or database in production
CARBON_FACTORS = {
    # Cement and concrete
    "cement": {
        "base_factor": 800,  # kgCO2 per tonne
        "unit": "kgCO2/t",
        "source": "EPD Database",
        "recycled_adjustment": 0.7  # 30% reduction for recycled content
    },
    "concrete": {
        "base_factor": 150,  # kgCO2 per tonne
        "unit": "kgCO2/t", 
        "source": "Industry Average",
        "recycled_adjustment": 0.8
    },
    
    # Steel
    "steel": {
        "base_factor": 1900,  # kgCO2 per tonne
        "unit": "kgCO2/t",
        "source": "World Steel Association",
        "recycled_adjustment": 0.4  # 60% reduction for recycled steel
    },
    "rebar": {
        "base_factor": 1900,
        "unit": "kgCO2/t",
        "source": "World Steel Association", 
        "recycled_adjustment": 0.4
    },
    
    # Asphalt
    "asphalt": {
        "base_factor": 400,  # kgCO2 per tonne
        "unit": "kgCO2/t",
        "source": "EPA",
        "recycled_adjustment": 0.85
    },
    
    # Aggregates
    "aggregate": {
        "base_factor": 30,  # kgCO2 per tonne
        "unit": "kgCO2/t",
        "source": "Industry Average",
        "recycled_adjustment": 0.9
    },
    "sand": {
        "base_factor": 25,
        "unit": "kgCO2/t", 
        "source": "Industry Average",
        "recycled_adjustment": 0.95
    },
    
    # Other materials
    "water": {
        "base_factor": 0.3,  # kgCO2 per cubic meter
        "unit": "kgCO2/m3",
        "source": "Treatment Plant Data",
        "recycled_adjustment": 1.0
    },
    "fly_ash": {
        "base_factor": 100,  # kgCO2 per tonne
        "unit": "kgCO2/t",
        "source": "Coal Combustion Byproducts",
        "recycled_adjustment": 1.0  # Already a recycled material
    }
}


def get_carbon_factor(material_type: str) -> Optional[Dict[str, Any]]:
    """
    Get carbon factor for material type
    
    Args:
        material_type: Type of material (e.g., 'cement', 'steel')
    
    Returns:
        Carbon factor dictionary or None if not found
    """
    material_key = material_type.lower().replace(" ", "_")
    return CARBON_FACTORS.get(material_key)


def compute_embodied_co2(sample: MRVSample, tests: List[MRVTest]) -> Dict[str, Any]:
    """
    Compute embodied CO2 for a sample based on test results
    
    Args:
        sample: MRVSample object
        tests: List of MRVTest objects for the sample
    
    Returns:
        Dictionary with CO2 calculation results
    """
    # Get carbon factor for sample type
    factor_info = get_carbon_factor(sample.sample_type)
    if not factor_info:
        return {
            "co2_kg": 0,
            "co2_notes": f"No carbon factor available for material type: {sample.sample_type}",
            "factor_used": None,
            "adjustments": []
        }
    
    base_factor = factor_info["base_factor"]
    
    # Find quantity test result (typically density or mass measurement)
    quantity_tonnes = None
    recycled_fraction = 0.0
    
    for test in tests:
        param_lower = test.parameter.lower()
        
        # Look for quantity/mass measurements
        if param_lower in ["density", "mass", "weight", "quantity"]:
            try:
                # Convert test value to tonnes based on unit
                value = float(test.value)
                unit = test.unit.lower()
                
                if unit in ["kg", "kilogram", "kilograms"]:
                    quantity_tonnes = value / 1000
                elif unit in ["t", "ton", "tonne", "tonnes"]:
                    quantity_tonnes = value
                elif unit in ["g", "gram", "grams"]:
                    quantity_tonnes = value / 1000000
                elif unit in ["lb", "pound", "pounds"]:
                    quantity_tonnes = value / 2204.62
                else:
                    # Default to tonnes if unit is unclear
                    quantity_tonnes = value
                    
            except (ValueError, TypeError):
                continue
        
        # Look for recycled content
        if param_lower in ["recycled", "recycled_content", "recycled_fraction"]:
            try:
                recycled_fraction = float(test.value) / 100.0  # Convert percentage to fraction
                if recycled_fraction > 1.0:  # If already a fraction
                    recycled_fraction = float(test.value)
            except (ValueError, TypeError):
                continue
    
    # If no quantity found, estimate based on sample type defaults
    if quantity_tonnes is None:
        # Use typical sample sizes for estimation
        default_quantities = {
            "cement": 0.05,    # 50kg sample
            "concrete": 0.1,   # 100kg sample  
            "steel": 0.02,     # 20kg sample
            "asphalt": 0.05,   # 50kg sample
            "aggregate": 0.1,  # 100kg sample
        }
        quantity_tonnes = default_quantities.get(sample.sample_type.lower(), 0.1)
    
    # Calculate base CO2
    base_co2_kg = quantity_tonnes * base_factor
    
    # Apply recycled content adjustment
    adjustment_factor = 1.0
    adjustments = []
    
    if recycled_fraction > 0 and "recycled_adjustment" in factor_info:
        adjustment_factor = factor_info["recycled_adjustment"] * (1 - recycled_fraction) + recycled_fraction
        co2_reduction = base_co2_kg * (1 - adjustment_factor)
        
        adjustments.append({
            "type": "recycled_content",
            "fraction": recycled_fraction,
            "adjustment_factor": adjustment_factor,
            "co2_reduction_kg": co2_reduction
        })
    
    # Calculate final CO2
    final_co2_kg = base_co2_kg * adjustment_factor
    
    return {
        "co2_kg": round(final_co2_kg, 2),
        "co2_notes": f"Calculated for {quantity_tonnes:.3f} tonnes of {sample.sample_type}",
        "factor_used": factor_info,
        "quantity_tonnes": quantity_tonnes,
        "base_co2_kg": round(base_co2_kg, 2),
        "adjustments": adjustments,
        "recycled_fraction": recycled_fraction,
        "lca_method": "hybrid_epd"  # Default LCA method
    }


async def calculate_project_co2_breakdown(db: AsyncSession, project_id: str) -> Dict[str, Any]:
    """
    Calculate CO2 breakdown for a project
    
    Args:
        db: Database session
        project_id: Project ID
    
    Returns:
        Dictionary with project CO2 breakdown
    """
    # Get all samples for the project
    samples_result = await db.execute(
        select(MRVSample).where(MRVSample.project_id == project_id)
    )
    samples = samples_result.scalars().all()
    
    # Get all tests for these samples
    sample_ids = [s.sample_id for s in samples]
    if not sample_ids:
        return {
            "total_co2_kg": 0,
            "total_co2_t": 0,
            "by_material": {},
            "by_sample": [],
            "sample_count": 0
        }
    
    tests_result = await db.execute(
        select(MRVTest).where(MRVTest.sample_id.in_(sample_ids))
    )
    tests = tests_result.scalars().all()
    
    # Group tests by sample
    tests_by_sample = {}
    for test in tests:
        if test.sample_id not in tests_by_sample:
            tests_by_sample[test.sample_id] = []
        tests_by_sample[test.sample_id].append(test)
    
    # Calculate CO2 for each sample
    total_co2_kg = 0
    by_material = {}
    by_sample = []
    
    for sample in samples:
        sample_tests = tests_by_sample.get(sample.sample_id, [])
        co2_result = compute_embodied_co2(sample, sample_tests)
        
        sample_co2_kg = co2_result["co2_kg"]
        total_co2_kg += sample_co2_kg
        
        # Add to material breakdown
        material_type = sample.sample_type
        if material_type not in by_material:
            by_material[material_type] = {
                "co2_kg": 0,
                "sample_count": 0,
                "quantity_tonnes": 0
            }
        
        by_material[material_type]["co2_kg"] += sample_co2_kg
        by_material[material_type]["sample_count"] += 1
        by_material[material_type]["quantity_tonnes"] += co2_result.get("quantity_tonnes", 0)
        
        # Add to sample breakdown
        by_sample.append({
            "sample_id": sample.sample_id,
            "sample_type": sample.sample_type,
            "co2_kg": sample_co2_kg,
            "quantity_tonnes": co2_result.get("quantity_tonnes", 0),
            "recycled_fraction": co2_result.get("recycled_fraction", 0),
            "test_count": len(sample_tests)
        })
    
    return {
        "total_co2_kg": round(total_co2_kg, 2),
        "total_co2_t": round(total_co2_kg / 1000, 2),
        "by_material": {
            mat_type: {
                **data,
                "co2_kg": round(data["co2_kg"], 2),
                "quantity_tonnes": round(data["quantity_tonnes"], 3)
            }
            for mat_type, data in by_material.items()
        },
        "by_sample": by_sample,
        "sample_count": len(samples)
    }


def calculate_carbon_credits(co2_reduction_tonnes: float, credit_rate_usd_per_ton: float = 50.0) -> Dict[str, Any]:
    """
    Calculate carbon credits and revenue
    
    Args:
        co2_reduction_tonnes: CO2 reduction in tonnes
        credit_rate_usd_per_ton: Credit rate in USD per tonne
    
    Returns:
        Dictionary with credit calculation results
    """
    credits_value_usd = co2_reduction_tonnes * credit_rate_usd_per_ton
    
    return {
        "co2_reduction_tonnes": co2_reduction_tonnes,
        "credits_t": co2_reduction_tonnes,
        "credit_rate_usd_per_ton": credit_rate_usd_per_ton,
        "credits_value_usd": round(credits_value_usd, 2),
        "calculation_timestamp": datetime.now(timezone.utc).isoformat()
    }


# Example calculation function for documentation
def example_calculation():
    """
    Example: 100 tonnes cement with factor 800 kgCO2/t => 80,000 kg CO2 = 80 tCO2
    """
    cement_factor = CARBON_FACTORS["cement"]
    quantity_tonnes = 100
    base_factor = cement_factor["base_factor"]
    
    base_co2_kg = quantity_tonnes * base_factor  # 100 * 800 = 80,000 kg CO2
    co2_tonnes = base_co2_kg / 1000  # 80 tonnes CO2
    
    return {
        "material": "cement",
        "quantity_tonnes": quantity_tonnes,
        "factor_kgco2_per_ton": base_factor,
        "co2_kg": base_co2_kg,
        "co2_tonnes": co2_tonnes,
        "credits_at_50_usd_per_ton": co2_tonnes * 50  # $4,000
    }
