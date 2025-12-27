import React from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Co2CostPoint } from "../services/api";

interface Co2CostScatterProps {
  data: Co2CostPoint[];
}

export const Co2CostScatter: React.FC<Co2CostScatterProps> = ({ data }) => {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-medium text-slate-300 mb-4">CO₂ vs Cost Analysis</h3>
      <ResponsiveContainer width="100%" height={200}>
        <ScatterChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
          <XAxis 
            dataKey="cost_usd" 
            name="Cost (USD)"
            stroke="#94a3b8"
            fontSize={12}
            tickFormatter={(value) => `$${(value as number).toLocaleString()}`}
          />
          <YAxis 
            dataKey="co2_t" 
            name="CO₂ (t)"
            stroke="#94a3b8"
            fontSize={12}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #475569",
              borderRadius: "8px",
            }}
            formatter={(value: number | string, name: string) => [
              name === "Cost (USD)" ? `$${Number(value).toLocaleString()}` : `${Number(value).toFixed(2)} t`,
              name,
            ]}
            labelFormatter={(value) => `Project: ${value}`}
          />
          <Scatter
            dataKey="co2_t"
            fill="#10b981"
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
};
