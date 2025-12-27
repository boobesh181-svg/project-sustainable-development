from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class ProjectImpact(BaseModel):
    project_id: UUID
    project_name: str

    lifetime_years: int

    budget_usd: float

    # Embodied CO2 based on material-token factor mapping (baseline vs green)
    baseline_embodied_co2_t: float
    green_embodied_co2_t: float
    embodied_co2_savings_t: float

    # Authoritative reported embodied CO2 from MRV (approved/locked)
    reported_embodied_co2_t: float

    # Operational CO2 proxy (last 12 months)
    operational_co2_yearly_t: float

    # Carbon credits are potential credits based on embodied savings (1 tCO2e => 1 credit)
    potential_carbon_credits_t: float
    assumed_credit_price_usd_per_t: float
    potential_credit_value_usd: float

    # ROI as credit value / budget (if budget > 0)
    roi_pct: float

    methodology_version: str
    emission_factor_version: str
    notes: str
