import React, { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { apiClient } from "../services/api";

interface Co2TrendPoint {
  month: string;
  embodied: number;
  operational: number;
  saved: number;
}

interface Co2TrendProps {
  onError?: (error: string) => void;
}

export const Co2Trend: React.FC<Co2TrendProps> = ({ onError }) => {
  const [data, setData] = useState<Co2TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrend = async () => {
      try {
        const response = await apiClient.get("/api/v1/dashboard/charts");
        const charts = response.data;

        if (charts.co2_trend && Array.isArray(charts.co2_trend)) {
          setData(charts.co2_trend);
        }
      } catch (error: any) {
        const msg = error?.response?.data?.detail || error?.message || "Failed to fetch CO₂ trend";
        onError?.(msg);
      } finally {
        setLoading(false);
      }
    };

    fetchTrend();
  }, [onError]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <p className="text-slate-400 text-sm">Loading trend…</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <p className="text-slate-400 text-sm">No CO₂ trend data available</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="mb-4 text-sm font-semibold text-slate-100">12-Month CO₂ Trend</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} stackOffset="none">
            <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
            <XAxis dataKey="month" stroke="#64748b" tick={{ fontSize: 11 }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#020617",
                borderColor: "#1e293b",
                fontSize: 12,
              }}
              formatter={(value: number) => value.toFixed(2)}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Area
              type="monotone"
              dataKey="embodied"
              stackId="1"
              stroke="#22c55e"
              fill="#22c55e33"
              name="Embodied"
            />
            <Area
              type="monotone"
              dataKey="operational"
              stackId="1"
              stroke="#38bdf8"
              fill="#38bdf833"
              name="Operational"
            />
            <Area
              type="monotone"
              dataKey="saved"
              stackId="1"
              stroke="#f97316"
              fill="#f9731633"
              name="Saved"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
