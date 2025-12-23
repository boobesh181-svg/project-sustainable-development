import React, { useEffect, useState } from "react";
import {
  fetchDashboardSummary,
  fetchDashboardCharts,
  DashboardSummary,
  DashboardCharts,
} from "./services/api";
import { Co2TrendChart } from "./charts/Co2TrendChart";
import { MaterialMixChart } from "./charts/MaterialMixChart";
import { AnomalyTimelineChart } from "./charts/AnomalyTimelineChart";
import { DistanceHistogram } from "./charts/DistanceHistogram";
import { SupplierRiskScatter } from "./charts/SupplierRiskScatter";
import { Co2CostScatter } from "./charts/Co2CostScatter";

export const App: React.FC = () => {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [charts, setCharts] = useState<DashboardCharts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    (async () => {
      try {
        const [summary, charts] = await Promise.all([
          fetchDashboardSummary(),
          fetchDashboardCharts(),
        ]);
        setData(summary);
        setCharts(charts);
      } catch (e: any) {
        setError(e?.message ?? "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">
          Windsurf Sustainable City Dashboard
        </h1>
        <span className="text-xs text-slate-400">Backend: /api (Vite proxy)</span>
      </header>

      <main className="flex-1 p-6">
        {loading && <p className="text-slate-300">Loading dashboard…</p>}
        {error && !loading && (
          <p className="text-red-400 text-sm">Error: {error}</p>
        )}
        {data && !loading && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
              <KpiCard label="Active Projects" value={data.active_projects} />
              <KpiCard
                label="Total CO₂ Saved (tCO₂e)"
                value={data.total_co2_saved_t.toFixed(2)}
              />
              <KpiCard
                label="Estimated Embodied CO₂ (t)"
                value={data.estimated_embodied_co2_t.toFixed(2)}
              />
              <KpiCard
                label="Operational CO₂ (yearly, t)"
                value={data.operational_co2_yearly_t.toFixed(2)}
              />
              <KpiCard
                label="Material Tokens Issued (month)"
                value={data.material_tokens_issued_month}
              />
              <KpiCard
                label="Tokens Redeemed (%)"
                value={`${data.tokens_redeemed_pct.toFixed(1)}%`}
              />
              <KpiCard
                label="Open Anomalies"
                value={data.open_anomalies}
              />
              <KpiCard
                label="Open Whistleblower Cases"
                value={data.open_whistleblower_cases}
              />
              <KpiCard
                label="Avg Delivery Distance (m)"
                value={data.avg_delivery_distance_m.toFixed(0)}
              />
              <KpiCard
                label="Low-carbon Material Fraction (%)"
                value={`${data.low_carbon_material_fraction_pct.toFixed(1)}%`}
              />
              <KpiCard
                label="Supplier Money Saved ($)"
                value={`$${data.supplier_money_saved_usd.toFixed(0)}`}
              />
              <KpiCard
                label="Project Budget Utilization (%)"
                value={`${data.project_budget_utilization_pct.toFixed(1)}%`}
              />
            </div>

            {charts && (
              <div className="space-y-6">
                {/* CO2 Trend Chart */}
                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="lg:col-span-2">
                    <Co2TrendChart data={charts.co2_trend} />
                  </div>
                  <div>
                    <MaterialMixChart data={charts.material_mix} />
                  </div>
                </div>

                {/* Anomalies Timeline and Distance Histogram */}
                <div className="grid gap-4 lg:grid-cols-2">
                  <AnomalyTimelineChart data={charts.anomaly_timeline} />
                  <DistanceHistogram data={charts.distance_histogram} />
                </div>

                {/* Supplier Risk and CO2 vs Cost Scatter */}
                <div className="grid gap-4 lg:grid-cols-2">
                  <SupplierRiskScatter data={charts.supplier_scatter} />
                  <Co2CostScatter data={charts.co2_cost_scatter} />
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};

interface KpiCardProps {
  label: string;
  value: string | number;
}

const KpiCard: React.FC<KpiCardProps> = ({ label, value }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 flex flex-col gap-2">
    <span className="text-xs uppercase tracking-wide text-slate-400">
      {label}
    </span>
    <span className="text-2xl font-semibold">{value}</span>
  </div>
);
