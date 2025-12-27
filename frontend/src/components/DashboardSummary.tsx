import React, { useEffect, useState } from "react";
import { apiClient } from "../services/api";

interface SummaryMetric {
  label: string;
  value: string | number;
  unit?: string;
}

interface DashboardSummaryProps {
  onError?: (error: string) => void;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null) {
    const maybe = error as {
      response?: { data?: { detail?: unknown } };
      message?: unknown;
    };
    const detail = maybe.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (typeof maybe.message === "string" && maybe.message.trim()) return maybe.message;
  }
  return fallback;
}

export const DashboardSummary: React.FC<DashboardSummaryProps> = ({ onError }) => {
  const [metrics, setMetrics] = useState<SummaryMetric[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const response = await apiClient.get("/api/v1/dashboard/summary");
        const data = response.data;

        const displayMetrics: SummaryMetric[] = [
          { label: "Active Projects", value: data.active_projects },
          { label: "Total CO₂ Saved", value: data.total_co2_saved_t.toFixed(2), unit: "tCO₂e" },
          { label: "Estimated Embodied CO₂", value: data.estimated_embodied_co2_t.toFixed(2), unit: "t" },
          { label: "Operational CO₂ (Yearly)", value: data.operational_co2_yearly_t.toFixed(2), unit: "t" },
          { label: "Material Tokens (Month)", value: data.material_tokens_issued_month },
          { label: "Tokens Redeemed", value: `${data.tokens_redeemed_pct.toFixed(1)}%` },
          { label: "Open Anomalies", value: data.open_anomalies },
          { label: "Open Cases", value: data.open_whistleblower_cases },
          { label: "Avg Delivery Distance", value: data.avg_delivery_distance_m.toFixed(0), unit: "m" },
          { label: "Low-carbon Materials", value: `${data.low_carbon_material_fraction_pct.toFixed(1)}%` },
          { label: "Supplier Savings", value: `$${data.supplier_money_saved_usd.toFixed(0)}` },
          { label: "Budget Utilization", value: `${data.project_budget_utilization_pct.toFixed(1)}%` },
        ];

        setMetrics(displayMetrics);
      } catch (error: unknown) {
        onError?.(getErrorMessage(error, "Failed to fetch summary"));
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
  }, [onError]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <p className="text-slate-400 text-sm">Loading summary…</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-100">Dashboard Summary</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 flex flex-col gap-1"
          >
            <span className="text-xs uppercase tracking-wide text-slate-400">
              {metric.label}
            </span>
            <div className="flex items-baseline gap-1">
              <span className="text-xl font-semibold text-slate-100">{metric.value}</span>
              {metric.unit && <span className="text-xs text-slate-500">{metric.unit}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
