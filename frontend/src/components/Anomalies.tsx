import React, { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { apiClient } from "../services/api";

interface AnomalyPoint {
  date: string;
  count: number;
}

interface AnomaliesProps {
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

export const Anomalies: React.FC<AnomaliesProps> = ({ onError }) => {
  const [data, setData] = useState<AnomalyPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnomalies = async () => {
      try {
        const response = await apiClient.get("/api/v1/dashboard/charts");
        const charts = response.data;

        if (charts.anomaly_timeline && Array.isArray(charts.anomaly_timeline)) {
          setData(charts.anomaly_timeline);
        }
      } catch (error: unknown) {
        onError?.(getErrorMessage(error, "Failed to fetch anomalies"));
      } finally {
        setLoading(false);
      }
    };

    fetchAnomalies();
  }, [onError]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <p className="text-slate-400 text-sm">Loading anomalies…</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h3 className="text-sm font-semibold text-slate-100 mb-2">Anomalies Timeline</h3>
        <p className="text-slate-400 text-sm">No anomaly data available</p>
      </div>
    );
  }

  const totalAnomalies = data.reduce((sum, point) => sum + point.count, 0);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">Anomalies Timeline</h3>
        <span className="text-xs bg-slate-800 text-slate-200 px-2 py-1 rounded">
          Total: {totalAnomalies}
        </span>
      </div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
            <XAxis
              dataKey="date"
              stroke="#64748b"
              tick={{ fontSize: 11 }}
              tickFormatter={(value) => {
                try {
                  return new Date(value).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  });
                } catch {
                  return value;
                }
              }}
            />
            <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#020617",
                borderColor: "#1e293b",
                fontSize: 12,
              }}
              labelFormatter={(value) => {
                try {
                  return new Date(value).toLocaleDateString();
                } catch {
                  return value;
                }
              }}
            />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#ef4444"
              strokeWidth={2}
              dot={{ fill: "#ef4444", r: 4 }}
              activeDot={{ r: 6 }}
              name="Anomalies"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
