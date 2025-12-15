from datetime import datetime
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func

from app.models.scope3_materials import (
    MaterialCategory, MaterialSubtype, EmissionFactor, 
    ActivityData, EmissionFactorType, DataQualityTier
)
from app.models.scope3_boundaries import ProjectBoundary
from app.models.projects import Project
from app.db.session import get_db


class EmissionFactorService:
    """Service for emission factor selection and calculation with hierarchical precedence"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_applicable_emission_factor(
        self,
        material_category_id: str,
        material_subtype_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        calculation_date: datetime = datetime.utcnow()
    ) -> Optional[EmissionFactor]:
        """
        Get emission factor following precedence hierarchy:
        1) Verified primary
        2) Unverified primary  
        3) National default
        4) International fallback
        """
        
        # Build query with precedence logic
        query = select(EmissionFactor).where(
            and_(
                EmissionFactor.material_category_id == material_category_id,
                or_(
                    EmissionFactor.material_subtype_id == material_subtype_id,
                    EmissionFactor.material_subtype_id.is_(None)
                ),
                EmissionFactor.validity_start <= calculation_date,
                or_(
                    EmissionFactor.validity_end.is_(None),
                    EmissionFactor.validity_end >= calculation_date
                )
            )
        )
        
        # Apply supplier-specific filter if provided
        if supplier_id:
            query = query.where(
                or_(
                    EmissionFactor.supplier_id == supplier_id,
                    EmissionFactor.supplier_id.is_(None)
                )
            )
        
        result = await self.db.execute(query)
        factors = result.scalars().all()
        
        # Sort by precedence hierarchy
        sorted_factors = self._sort_by_precedence(factors, supplier_id)
        
        return sorted_factors[0] if sorted_factors else None
    
    def _sort_by_precedence(
        self, 
        factors: List[EmissionFactor], 
        supplier_id: Optional[str] = None
    ) -> List[EmissionFactor]:
        """Sort emission factors by precedence hierarchy"""
        
        precedence_order = {
            EmissionFactorType.PRIMARY_VERIFIED: 1,
            EmissionFactorType.PRIMARY_UNVERIFIED: 2,
            EmissionFactorType.NATIONAL_DEFAULT: 3,
            EmissionFactorType.INTERNATIONAL_FALLBACK: 4
        }
        
        # Sort by precedence, then by supplier specificity
        def sort_key(factor):
            precedence = precedence_order.get(factor.factor_type, 999)
            supplier_specific = 0 if factor.supplier_id == supplier_id else 1
            data_quality = {
                DataQualityTier.TIER_1: 1,
                DataQualityTier.TIER_2: 2,
                DataQualityTier.TIER_3: 3,
                DataQualityTier.TIER_4: 4
            }.get(factor.data_quality_tier, 999)
            
            return (precedence, supplier_specific, data_quality)
        
        return sorted(factors, key=sort_key)
    
    async def calculate_emissions(
        self,
        quantity: Decimal,
        unit: str,
        material_category_id: str,
        material_subtype_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        calculation_date: datetime = datetime.utcnow()
    ) -> Dict[str, Any]:
        """
        Calculate CO2 emissions with unit normalization and factor locking
        """
        
        # Get material category for standard unit
        category_query = select(MaterialCategory).where(
            MaterialCategory.id == material_category_id
        )
        category_result = await self.db.execute(category_query)
        category = category_result.scalar_one_or_none()
        
        if not category:
            raise ValueError(f"Material category {material_category_id} not found")
        
        # Normalize quantity to standard unit
        normalized_quantity = await self._normalize_quantity(
            quantity, unit, category.standardized_unit.value, material_subtype_id
        )
        
        # Get applicable emission factor
        emission_factor = await self.get_applicable_emission_factor(
            material_category_id, material_subtype_id, supplier_id, calculation_date
        )
        
        if not emission_factor:
            raise ValueError(f"No applicable emission factor found for material category {material_category_id}")
        
        # Calculate CO2 emissions
        co2_emissions = normalized_quantity * Decimal(str(emission_factor.co2_factor_kg))
        
        # Calculate uncertainty range if available
        uncertainty_lower = None
        uncertainty_upper = None
        if emission_factor.uncertainty_lower and emission_factor.uncertainty_upper:
            uncertainty_lower = normalized_quantity * Decimal(str(emission_factor.uncertainty_lower))
            uncertainty_upper = normalized_quantity * Decimal(str(emission_factor.uncertainty_upper))
        
        return {
            "normalized_quantity": normalized_quantity,
            "standard_unit": category.standardized_unit.value,
            "emission_factor_used": Decimal(str(emission_factor.co2_factor_kg)),
            "emission_factor_id": str(emission_factor.id),
            "emission_factor_type": emission_factor.factor_type.value,
            "data_quality_tier": emission_factor.data_quality_tier.value,
            "co2_calculated": co2_emissions,
            "uncertainty_lower": uncertainty_lower,
            "uncertainty_upper": uncertainty_upper,
            "calculation_date": calculation_date
        }
    
    async def _normalize_quantity(
        self,
        quantity: Decimal,
        from_unit: str,
        to_unit: str,
        material_subtype_id: Optional[str] = None
    ) -> Decimal:
        """Normalize quantity to standard unit using conversion factors"""
        
        # Unit conversion factors (basic set - extend as needed)
        conversion_factors = {
            ("kg", "tonne"): Decimal("0.001"),
            ("tonne", "kg"): Decimal("1000"),
            ("g", "kg"): Decimal("0.001"),
            ("kg", "g"): Decimal("1000"),
            ("m", "m2"): Decimal("1.0"),  # Need area/height info for proper conversion
            ("m", "m3"): Decimal("1.0"),  # Need cross-sectional area info
            ("L", "m3"): Decimal("0.001"),
            ("m3", "L"): Decimal("1000"),
        }
        
        # If units are the same, return as-is
        if from_unit == to_unit:
            return quantity
        
        # Get conversion factor
        conversion_key = (from_unit, to_unit)
        if conversion_key not in conversion_factors:
            # Try to get density-based conversion for mass/volume
            if material_subtype_id:
                density_factor = await self._get_density_conversion(
                    from_unit, to_unit, material_subtype_id
                )
                if density_factor:
                    return quantity * density_factor
            
            raise ValueError(f"No conversion factor available from {from_unit} to {to_unit}")
        
        return quantity * conversion_factors[conversion_key]
    
    async def _get_density_conversion(
        self, 
        from_unit: str, 
        to_unit: str, 
        material_subtype_id: str
    ) -> Optional[Decimal]:
        """Get density-based conversion factor for mass/volume conversions"""
        
        subtype_query = select(MaterialSubtype).where(
            MaterialSubtype.id == material_subtype_id
        )
        subtype_result = await self.db.execute(subtype_query)
        subtype = subtype_result.scalar_one_or_none()
        
        if not subtype or not subtype.standard_density:
            return None
        
        density = Decimal(str(subtype.standard_density))  # kg/m3
        
        # Mass to volume: volume = mass / density
        if from_unit in ["kg", "tonne", "g"] and to_unit in ["m3", "L"]:
            mass_in_kg = await self._normalize_quantity(
                Decimal("1"), from_unit, "kg", material_subtype_id
            )
            volume_in_m3 = mass_in_kg / density
            return volume_in_m3
        
        # Volume to mass: mass = volume * density  
        elif from_unit in ["m3", "L"] and to_unit in ["kg", "tonne", "g"]:
            volume_in_m3 = await self._normalize_quantity(
                Decimal("1"), from_unit, "m3", material_subtype_id
            )
            mass_in_kg = volume_in_m3 * density
            return mass_in_kg
        
        return None


class ActivityDataService:
    """Service for activity data management with audit trails"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.emission_service = EmissionFactorService(db)
    
    async def create_activity_data(
        self,
        project_id: str,
        material_category_id: str,
        material_subtype_id: Optional[str],
        batch_identifier: str,
        quantity_submitted: Decimal,
        unit_submitted: str,
        supplier_id: str,
        submitted_by: str,
        evidence_files: Optional[List[str]] = None
    ) -> ActivityData:
        """Create new activity data with automatic CO2 calculation"""
        
        # Check for duplicate batch identifier
        existing_query = select(ActivityData).where(
            and_(
                ActivityData.project_id == project_id,
                ActivityData.batch_identifier == batch_identifier
            )
        )
        existing_result = await self.db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise ValueError(f"Batch identifier {batch_identifier} already exists for this project")
        
        # Calculate emissions
        calculation_result = await self.emission_service.calculate_emissions(
            quantity_submitted,
            unit_submitted,
            material_category_id,
            material_subtype_id,
            supplier_id
        )
        
        # Create activity data record
        activity_data = ActivityData(
            project_id=project_id,
            material_category_id=material_category_id,
            material_subtype_id=material_subtype_id,
            emission_factor_id=calculation_result["emission_factor_id"],
            batch_identifier=batch_identifier,
            quantity_submitted=quantity_submitted,
            unit_submitted=unit_submitted,
            quantity_normalized=calculation_result["normalized_quantity"],
            unit_normalized=calculation_result["standard_unit"],
            emission_factor_used=calculation_result["emission_factor_used"],
            co2_calculated=calculation_result["co2_calculated"],
            uncertainty_lower=calculation_result["uncertainty_lower"],
            uncertainty_upper=calculation_result["uncertainty_upper"],
            supplier_id=supplier_id,
            submitted_by=submitted_by,
            submission_date=datetime.utcnow()
        )
        
        self.db.add(activity_data)
        await self.db.flush()
        
        # TODO: Link evidence files if provided
        
        return activity_data
    
    async def create_correction(
        self,
        original_activity_data_id: str,
        corrected_fields: Dict[str, Any],
        correction_reason: str,
        corrected_by: str
    ) -> ActivityData:
        """Create correction record (no overwrites)"""
        
        # Get original activity data
        original_query = select(ActivityData).where(
            ActivityData.id == original_activity_data_id
        )
        original_result = await self.db.execute(original_query)
        original_data = original_result.scalar_one_or_none()
        
        if not original_data:
            raise ValueError(f"Original activity data {original_activity_data_id} not found")
        
        # Create new activity data with corrections
        corrected_data = ActivityData(
            project_id=original_data.project_id,
            material_category_id=original_data.material_category_id,
            material_subtype_id=original_data.material_subtype_id,
            batch_identifier=original_data.batch_identifier + "_corrected",
            quantity_submitted=corrected_fields.get("quantity_submitted", original_data.quantity_submitted),
            unit_submitted=corrected_fields.get("unit_submitted", original_data.unit_submitted),
            supplier_id=original_data.supplier_id,
            submitted_by=corrected_by
        )
        
        # Recalculate emissions if quantity or unit changed
        if "quantity_submitted" in corrected_fields or "unit_submitted" in corrected_fields:
            calculation_result = await self.emission_service.calculate_emissions(
                corrected_data.quantity_submitted,
                corrected_data.unit_submitted,
                corrected_data.material_category_id,
                corrected_data.material_subtype_id,
                corrected_data.supplier_id
            )
            corrected_data.quantity_normalized = calculation_result["normalized_quantity"]
            corrected_data.unit_normalized = calculation_result["standard_unit"]
            corrected_data.emission_factor_used = calculation_result["emission_factor_used"]
            corrected_data.co2_calculated = calculation_result["co2_calculated"]
            corrected_data.uncertainty_lower = calculation_result["uncertainty_lower"]
            corrected_data.uncertainty_upper = calculation_result["uncertainty_upper"]
        else:
            # Copy original calculation results
            corrected_data.quantity_normalized = original_data.quantity_normalized
            corrected_data.unit_normalized = original_data.unit_normalized
            corrected_data.emission_factor_used = original_data.emission_factor_used
            corrected_data.co2_calculated = original_data.co2_calculated
            corrected_data.uncertainty_lower = original_data.uncertainty_lower
            corrected_data.uncertainty_upper = original_data.uncertainty_upper
        
        self.db.add(corrected_data)
        await self.db.flush()
        
        # Create correction record
        from app.models.scope3_materials import ActivityDataCorrection
        correction = ActivityDataCorrection(
            original_submission_id=original_activity_data_id,
            corrected_submission_id=str(corrected_data.id),
            correction_reason=correction_reason,
            corrected_by=corrected_by,
            field_changes=str(list(corrected_fields.keys())),
            old_values=str({k: getattr(original_data, k) for k in corrected_fields}),
            new_values=str(corrected_fields)
        )
        
        self.db.add(correction)
        
        return corrected_data
