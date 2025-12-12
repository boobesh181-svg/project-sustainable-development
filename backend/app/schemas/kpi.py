from pydantic import BaseModel


class DashboardSummary(BaseModel):
    # 1. Active Projects
    active_projects: int
    # 2. Total CO₂ Saved (tCO₂e)
    total_co2_saved_t: float
    # 3. Estimated Embodied CO₂
    estimated_embodied_co2_t: float
    # 4. Operational CO₂ (yearly)
    operational_co2_yearly_t: float
    # 5. Material Tokens Issued (month)
    material_tokens_issued_month: int
    # 6. Tokens Redeemed (%)
    tokens_redeemed_pct: float
    # 7. Open Anomalies
    open_anomalies: int
    # 8. Open Whistleblower Cases
    open_whistleblower_cases: int
    # 9. Avg Delivery Geotag Distance (meters)
    avg_delivery_distance_m: float
    # 10. Low-carbon Material Fraction (%)
    low_carbon_material_fraction_pct: float
    # 11. Supplier Money Saved
    supplier_money_saved_usd: float
    # 12. Project Budget Utilization (%)
    project_budget_utilization_pct: float


class Co2TrendPoint(BaseModel):
    month: str  # e.g. "2025-01"
    embodied: float
    operational: float
    saved: float


class MaterialMixSlice(BaseModel):
    material_type: str
    qty: float


class AnomalyTimelinePoint(BaseModel):
    date: str  # ISO date
    count: int


class DistanceBucket(BaseModel):
    bucket_label: str
    count: int


class SupplierScatterPoint(BaseModel):
    supplier: str
    total_value: float
    project_count: int


class Co2CostPoint(BaseModel):
    project_name: str
    co2_t: float
    cost_usd: float


class DashboardCharts(BaseModel):
    co2_trend: list[Co2TrendPoint]
    material_mix: list[MaterialMixSlice]
    anomaly_timeline: list[AnomalyTimelinePoint]
    distance_histogram: list[DistanceBucket]
    supplier_scatter: list[SupplierScatterPoint]
    co2_cost_scatter: list[Co2CostPoint]
