const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface DashboardSummary {
  // 1. Active Projects
  active_projects: number;
  // 2. Total CO₂ Saved (tCO₂e)
  total_co2_saved_t: number;
  // 3. Estimated Embodied CO₂
  estimated_embodied_co2_t: number;
  // 4. Operational CO₂ (yearly)
  operational_co2_yearly_t: number;
  // 5. Material Tokens Issued (month)
  material_tokens_issued_month: number;
  // 6. Tokens Redeemed (%)
  tokens_redeemed_pct: number;
  // 7. Open Anomalies
  open_anomalies: number;
  // 8. Open Whistleblower Cases
  open_whistleblower_cases: number;
  // 9. Avg Delivery Geotag Distance (meters)
  avg_delivery_distance_m: number;
  // 10. Low-carbon Material Fraction (%)
  low_carbon_material_fraction_pct: number;
  // 11. Supplier Money Saved
  supplier_money_saved_usd: number;
  // 12. Project Budget Utilization (%)
  project_budget_utilization_pct: number;
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/summary`);
  if (!res.ok) {
    throw new Error(`Failed to fetch dashboard summary: ${res.status}`);
  }
  return res.json();
}

// Charts types mirror backend DashboardCharts schema (simplified for frontend use)
export interface Co2TrendPoint {
  month: string;
  embodied: number;
  operational: number;
  saved: number;
}

export interface MaterialMixSlice {
  material_type: string;
  qty: number;
}

export interface AnomalyTimelinePoint {
  date: string;
  count: number;
}

export interface DistanceBucket {
  bucket_label: string;
  count: number;
}

export interface SupplierScatterPoint {
  supplier: string;
  total_value: number;
  project_count: number;
}

export interface Co2CostPoint {
  project_name: string;
  co2_t: number;
  cost_usd: number;
}

export interface DashboardCharts {
  co2_trend: Co2TrendPoint[];
  material_mix: MaterialMixSlice[];
  anomaly_timeline: AnomalyTimelinePoint[];
  distance_histogram: DistanceBucket[];
  supplier_scatter: SupplierScatterPoint[];
  co2_cost_scatter: Co2CostPoint[];
}

export async function fetchDashboardCharts(): Promise<DashboardCharts> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/charts`);
  if (!res.ok) {
    throw new Error(`Failed to fetch dashboard charts: ${res.status}`);
  }
  return res.json();
}
